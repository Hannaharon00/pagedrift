import os
from copy import deepcopy
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo, available_timezones
import secrets
import time
import flask_login
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_babel import gettext

from changedetectionio.store import ChangeDetectionStore
from changedetectionio.auth_decorator import login_optionally_required
from changedetectionio.model.LLMSettings import LLMSettings


def construct_blueprint(datastore: ChangeDetectionStore):
    from changedetectionio.llm.evaluator import is_llm_features_disabled
    settings_blueprint = Blueprint('settings', __name__, template_folder="templates")
    if not is_llm_features_disabled():
        from changedetectionio.blueprint.settings.llm import construct_llm_blueprint
        settings_blueprint.register_blueprint(construct_llm_blueprint(datastore), url_prefix='/llm')

    # Notification settings live in their own child blueprint so future backends
    # (simple_email, webhooks, etc.) slot in as /settings/notifications/<backend>
    # without further URL-shaping churn.
    from changedetectionio.blueprint.settings.notifications import construct_notifications_blueprint
    settings_blueprint.register_blueprint(
        construct_notifications_blueprint(datastore), url_prefix='/notifications',
    )

    @settings_blueprint.route("", methods=['GET', "POST"])
    @login_optionally_required
    def settings_page():
        from changedetectionio import forms
        from changedetectionio.pluggy_interface import (
            get_plugin_settings_tabs,
            load_plugin_settings,
            save_plugin_settings
        )


        default = deepcopy(datastore.data['settings'])

        # api_key is intentionally blanked on GET — PasswordField never re-renders
        # its value, and a blank submission preserves the stored key.
        default['llm'] = LLMSettings.model_validate(
            datastore.data['settings']['application'].get('llm') or {}
        ).model_dump()
        default['llm']['api_key'] = ''

        if datastore.proxy_list is not None:
            available_proxies = list(datastore.proxy_list.keys())
            # When enabled
            system_proxy = datastore.data['settings']['requests']['proxy']
            # In the case it doesnt exist anymore
            if not system_proxy in available_proxies:
                system_proxy = None

            default['requests']['proxy'] = system_proxy if system_proxy is not None else available_proxies[0]
            # Used by the form handler to keep or remove the proxy settings
            default['proxy_list'] = available_proxies[0]

        # Don't use form.data on POST so that it doesnt overrid the checkbox status from the POST status
        form = forms.globalSettingsForm(formdata=request.form if request.method == 'POST' else None,
                                        data=default,
                                        extra_notification_tokens=datastore.get_unique_notification_tokens_available()
                                        )

        # Remove the last option 'System default'
        form.application.form.notification_format.choices.pop()

        if datastore.proxy_list is None:
            # @todo - Couldn't get setattr() etc dynamic addition working, so remove it instead
            del form.requests.form.proxy
        else:
            form.requests.form.proxy.choices = []
            for p in datastore.proxy_list:
                form.requests.form.proxy.choices.append(tuple((p, datastore.proxy_list[p]['label'])))

        if request.method == 'POST':
            # Password unset is a GET, but we can lock the session to a salted env password to always need the password
            if form.application.form.data.get('removepassword_button', False):
                # SALTED_PASS means the password is "locked" to what we set in the Env var
                if not os.getenv("SALTED_PASS", False):
                    datastore.remove_password()
                    flash(gettext("Password protection removed."), 'notice')
                    flask_login.logout_user()
                    return redirect(url_for('settings.settings_page'))

            if form.validate():
                # Don't set password to False when a password is set - should be only removed with the `removepassword` button
                app_update = dict(deepcopy(form.data['application']))

                # Never update password with '' or False (Added by wtforms when not in submission)
                if 'password' in app_update and not app_update['password']:
                    del (app_update['password'])

                # Notification fields live on the dedicated /settings/notifications page now.
                # The application sub-form still defines them (inherited from commonSettingsForm),
                # so an unrelated save here would clobber the stored values with empty WTForms
                # defaults. Drop them from the merge to leave the notifications config alone.
                for nf in ('notification_urls', 'notification_title', 'notification_body',
                           'notification_format', 'base_url'):
                    app_update.pop(nf, None)

                datastore.data['settings']['application'].update(app_update)

                # LLM config lives under settings.application.llm.* (post update_31).
                # Hydrate the stored dict into LLMSettings, then merge form input over it.
                # WTForms field names match LLMSettings field names exactly, so both sides
                # of the merge use the same key shape.
                existing_llm = LLMSettings.model_validate(
                    datastore.data['settings']['application'].get('llm') or {}
                )

                llm_form_input = dict(form.data.get('llm') or {})

                # Empty IntegerField submissions come back as None from WTForms;
                # the schema declares those fields as strict `int`, so passing
                # them through would fail validation. Treat None like the
                # absent-key case: keep the stored value, don't merge.
                llm_form_input = {k: v for k, v in llm_form_input.items() if v is not None}

                # PasswordField never re-renders, so a blank submitted value means
                # "keep stored key" — drop it from the merge.
                if not (llm_form_input.get('api_key') or '').strip():
                    llm_form_input.pop('api_key', None)

                # Env-var overrides make these fields read-only in the UI — ignore form input.
                if os.getenv('LLM_TOKEN_BUDGET_MONTH', '').strip():
                    llm_form_input.pop('token_budget_month', None)
                if os.getenv('LLM_MAX_INPUT_CHARS', '').strip():
                    llm_form_input.pop('max_input_chars', None)

                # System-managed counters must never come from the form.
                for protected in LLMSettings.PROTECTED_FIELDS:
                    llm_form_input.pop(protected, None)

                merged = LLMSettings.model_validate({**existing_llm.model_dump(), **llm_form_input})

                # Clearing the model field strips only the provider-connection fields.
                # User toggles, budgets, prompts and system counters survive (matches /llm/clear).
                exclude = set(LLMSettings.CONNECTION_FIELDS) if not merged.model.strip() else None
                datastore.data['settings']['application']['llm'] = merged.model_dump(exclude=exclude)

                # Handle dynamic worker count adjustment
                old_worker_count = datastore.data['settings']['requests'].get('workers', 1)
                new_worker_count = form.data['requests'].get('workers', 1)

                datastore.data['settings']['requests'].update(form.data['requests'])
                datastore.commit()

                # Clear all checksums to force reprocessing with new settings
                # Global settings can affect watch behavior (filters, rendering, etc.)
                datastore.clear_all_last_checksums()

                # Adjust worker count if it changed
                if new_worker_count != old_worker_count:
                    from changedetectionio import worker_pool
                    from changedetectionio.flask_app import update_q, notification_q, app, datastore as ds

