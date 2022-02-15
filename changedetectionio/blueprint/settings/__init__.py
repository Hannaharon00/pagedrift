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

