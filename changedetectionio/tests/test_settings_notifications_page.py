#!/usr/bin/env python3
"""
Tests for the /settings/notifications page (separated from the main /settings
form in 2026). The notification config lives at
    datastore.data['settings']['application']['notification_*']
and is now edited via its own form + route. The main settings page must NOT
clobber those values when an unrelated section (workers, RSS, etc.) is saved,
because both pages mutate the same `application` dict.
"""

from flask import url_for

from changedetectionio.tests.util import live_server_setup, delete_all_watches


def _seed_notification_config(datastore):
    """Pre-load the notification config into the application settings dict."""
    app = datastore.data['settings']['application']
    app['notification_urls'] = ['json://example.invalid/preserved']
    app['notification_title'] = 'Preserved title - {{ watch_url }}'
    app['notification_body'] = 'Preserved body - {{ diff }}'
    app['notification_format'] = 'html'
    app['base_url'] = 'https://preserved.example/'


def test_notifications_page_renders_form_inputs(
        client, live_server, measure_memory_usage, datastore_path):
    """Smoke test that the standalone /settings/notifications template actually
    renders the form. Catches template-level regressions — bad macro import,
    missing field, broken Jinja, etc. — that would still return HTTP 200 but
    silently drop the input boxes.

    Scans for each field's `name="..."` attribute (widget-agnostic — works for
    StringField/TextAreaField/SelectField/StringListField alike) plus the
    submit button and the notifications.js wiring."""
    res = client.get(url_for('settings.notifications.apprise'))
    assert res.status_code == 200
    body = res.data.decode('utf-8', errors='replace')

    for field in ('notification_urls', 'notification_title', 'notification_body',
                  'notification_format', 'base_url'):
        assert f'name="{field}"' in body, \
            f"Form input for {field!r} missing from /settings/notifications HTML"

    # Submit form actually wired to the right route
    assert f'action="{url_for("settings.notifications.apprise")}"' in body, \
        "Form should POST back to /settings/notifications/apprise"

    # notifications.js needs the JS-side ajax endpoint to test sends from this page
    assert 'notification_base_url' in body, \
        "notifications.js depends on notification_base_url being defined"
    assert 'send-test-notification' in body, \
        "'Send test notification' button missing — notifications.js binds to it"

    # The page uses the same tab UI scaffolding as /settings so the page styles
    # the same way (collapsable tabs wrapper, single 'All Notifications' tab,
    # tabs.js loaded). Catches regressions where the tab markup gets stripped
    # back out, which would visually break the layout.
    assert 'class="tabs collapsable"' in body, \
        "Tabs wrapper missing — page won't get the standard settings styling"
    assert 'href="#all-notifications"' in body, \
        "'All Notifications' tab anchor missing"
    assert 'id="all-notifications"' in body, \
        "tab-pane-inner target #all-notifications missing — tab would be inert"
    assert 'tabs.js' in body, \
        "tabs.js not loaded — the tab UI won't activate"


