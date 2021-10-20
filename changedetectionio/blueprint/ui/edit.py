from copy import deepcopy
import os
import importlib.resources
from flask import Blueprint, request, redirect, url_for, flash, render_template, abort
from flask_babel import gettext
from loguru import logger
from jinja2 import Environment, FileSystemLoader

from changedetectionio.store import ChangeDetectionStore
from changedetectionio.auth_decorator import login_optionally_required
from changedetectionio.time_handler import default_timezone_name, is_within_schedule
from changedetectionio import worker_pool
from changedetectionio.llm.evaluator import get_llm_config as _get_llm_config

def construct_blueprint(datastore: ChangeDetectionStore, update_q, queuedWatchMetaData):
    edit_blueprint = Blueprint('ui_edit', __name__, template_folder="../ui/templates")

    def _watch_tags(watch):
        """(uuid, tag) for this watch's tags, in its own tag order, skipping UUIDs we don't know."""
        tags = datastore.data['settings']['application'].get('tags', {})
        return [(tag_uuid, tags[tag_uuid]) for tag_uuid in watch.get('tags', []) if tag_uuid in tags]

    def _resolve_llm_group_overrides(watch, datastore) -> dict:
        """
        For each LLM field (llm_intent, llm_change_summary): if the watch has no own
        value but a linked group does, return {'value': ..., 'group_name': ..., 'group_uuid': ...}
        so the edit template can show the inherited value as the textarea placeholder and link
        back to the group that supplied it.
        Returns None for each field when the watch has its own value (nothing inherited).

        Only groups whose AI setting is "On" lend their prompts — the same gate the evaluator
        applies via resolve_llm_field(), so the placeholder always reflects what will actually
        run. See llm/evaluator.py:tag_llm_decision().
        """
        from changedetectionio.llm.evaluator import tag_llm_applies_to_watches, tag_llm_decision

        result = {'llm_intent': None, 'llm_change_summary': None, 'llm_backend_profile': None}

        # AI on/off is not a "fill in the blank" field: a group that has taken the decision
        # (On or Off, i.e. not "leave it to each watch") decides for every watch in it (#4204),
        # so report it and let the template show the watch's own checkbox as overridden.
        for tag_uuid, tag in _watch_tags(watch):
            if tag_llm_decision(tag) is not None:
                result['llm_backend_profile'] = {
                    'value': tag_llm_decision(tag),
                    'group_name': tag.get('title', 'tag'),
                    'group_uuid': tag_uuid,
                }
                break

        for field in ('llm_intent', 'llm_change_summary'):
            if (watch.get(field) or '').strip():
                continue  # watch has its own value — editable, no group override
            for tag_uuid, tag in _watch_tags(watch):
                if not tag_llm_applies_to_watches(tag):
                    continue
                if (tag.get(field) or '').strip():
                    result[field] = {
                        'value': tag.get(field).strip(),
                        'group_name': tag.get('title', 'tag'),
                        'group_uuid': tag_uuid,
                    }
                    break
        return result

    def _watch_has_tag_options_set(watch):
        """This should be fixed better so that Tag is some proper Model, a tag is just a Watch also"""
        for tag_uuid, tag in datastore.data['settings']['application'].get('tags', {}).items():
            if tag_uuid in watch.get('tags', []) and (tag.get('include_filters') or tag.get('subtractive_selectors')):
                return True

    @edit_blueprint.route("/edit/<uuid_str:uuid>", methods=['GET', 'POST'])
    @login_optionally_required
    # https://stackoverflow.com/questions/42984453/wtforms-populate-form-with-data-if-data-exists
    # https://wtforms.readthedocs.io/en/3.0.x/forms/#wtforms.form.Form.populate_obj ?
    def edit_page(uuid):
        from changedetectionio import forms
        from changedetectionio.browser_steps.browser_steps import browser_step_ui_config
        from changedetectionio import processors
        import importlib

        if uuid == 'first':
            uuid = list(datastore.data['watching'].keys()).pop()
        # More for testing, possible to return the first/only
        if not datastore.data['watching'].keys():
            flash(gettext("No watches to edit"), "error")
            return redirect(url_for('watchlist.index'))

        if not uuid in datastore.data['watching']:
            flash(gettext("No watch with the UUID {} found.").format(uuid), "error")
            return redirect(url_for('watchlist.index'))

        switch_processor = request.args.get('switch_processor')
        if switch_processor:
            for p in processors.available_processors():
                if p[0] == switch_processor:
                    datastore.data['watching'][uuid]['processor'] = switch_processor
                    flash(gettext("Switched to mode - {}.").format(p[1]))
                    datastore.clear_watch_history(uuid)
                    redirect(url_for('ui_edit.edit_page', uuid=uuid))

        # be sure we update with a copy instead of accidently editing the live object by reference
        default = None
        while not default:
            try:
                default = deepcopy(datastore.data['watching'][uuid])
            except RuntimeError as e:
                # Dictionary changed
                continue

        # Defaults for proxy choice
        if datastore.proxy_list is not None:  # When enabled
            # @todo
            # Radio needs '' not None, or incase that the chosen one no longer exists
            if default['proxy'] is None or not any(default['proxy'] in tup for tup in datastore.proxy_list):
                default['proxy'] = ''
        # proxy_override set to the json/text list of the items

        # Does it use some custom form? does one exist?
        processor_name = datastore.data['watching'][uuid].get('processor', '')
        processor_classes = next((tpl for tpl in processors.find_processors() if tpl[1] == processor_name), None)
        if not processor_classes:
            flash(gettext("Could not load '{}' processor, processor plugin might be missing. Please select a different processor.").format(processor_name), 'error')
            # Fall back to default processor so user can still edit and change processor
            processor_classes = next((tpl for tpl in processors.find_processors() if tpl[1] == 'text_json_diff'), None)
            if not processor_classes:
                # If even text_json_diff is missing, something is very wrong
                flash(gettext("Could not load '{}' processor, processor plugin might be missing.").format(processor_name), 'error')
                return redirect(url_for('watchlist.index'))

        parent_module = processors.get_parent_module(processor_classes[0])

        try:
            # Get the parent of the "processor.py" go up one, get the form (kinda spaghetti but its reusing existing code)
            forms_module = importlib.import_module(f"{parent_module.__name__}.forms")
            # Access the 'processor_settings_form' class from the 'forms' module
            form_class = getattr(forms_module, 'processor_settings_form')
        except ModuleNotFoundError as e:
            # .forms didnt exist
            form_class = forms.processor_text_json_diff_form
        except AttributeError as e:
            # .forms exists but no useful form
            form_class = forms.processor_text_json_diff_form

        form = form_class(formdata=request.form if request.method == 'POST' else None,
                          data=default,
                          extra_notification_tokens=default.extra_notification_token_values(),
                          default_system_settings=datastore.data['settings']
                          )

        # For the form widget tag UUID back to "string name" for the field
        form.tags.datastore = datastore

