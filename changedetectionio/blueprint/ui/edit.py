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

