#!/usr/bin/env python3
"""The Add-Watch page's browser picker.

The live preview needs a browser that can render screenshots + xpath element data, and
whatever rendered the preview is what the saved watch must check with - otherwise you
visually pick an element with Chrome and the watch then re-checks it with the plain HTTP
client. These tests cover the offered list, the server-side gate, and that the browser
which rendered a parked snapshot wins over the posted form.
"""
import json
import os

from flask import url_for


def _datastore(client):
    return client.application.config.get('DATASTORE')


def test_hidden_without_a_live_preview_browser(client, live_server, measure_memory_usage, datastore_path, monkeypatch):
    """No capable browser -> the sidebar link is hidden and the route bounces.

    One seam is patched deliberately: has_visual_browser() (page + sidebar gate) and
    default_visual_browser() both resolve through list_visual_browser_choices(), so the
    gate can't disagree with what the picker would have offered.
    """
    from changedetectionio.blueprint.add_watch_ui import browser_config
    monkeypatch.setattr(browser_config, 'list_visual_browser_choices', lambda datastore: [])

    # Sidebar link is not rendered
    res = client.get(url_for('watchlist.index'))
    assert url_for('add_watch_ui.add_watch_ui_index').encode() not in res.data

    # Direct navigation is bounced back to the watch list
    res = client.get(url_for('add_watch_ui.add_watch_ui_index'), follow_redirects=True)
    assert b'name="fetch_backend"' not in res.data
    assert b'needs an interactive browser' in res.data


def test_shown_when_a_live_preview_browser_exists(client, live_server, measure_memory_usage, datastore_path, monkeypatch):
    """A capable browser -> the sidebar link is offered and the page serves its picker."""
    from changedetectionio.blueprint.add_watch_ui import browser_config
    monkeypatch.setattr(browser_config, 'list_visual_browser_choices',
                        lambda datastore: [('html_webdriver', 'WebDriver Chrome/Javascript')])

    res = client.get(url_for('watchlist.index'))
    assert url_for('add_watch_ui.add_watch_ui_index').encode() in res.data

    res = client.get(url_for('add_watch_ui.add_watch_ui_index'))
    assert res.status_code == 200
    assert b'name="fetch_backend"' in res.data
    assert b'value="html_webdriver"' in res.data
    # The system default resolves to html_requests (no preview), so a real browser is preselected
    assert b'checked' in res.data


def test_browser_picker_lists_only_live_preview_capable(client, live_server, measure_memory_usage, datastore_path, monkeypatch):
    """Capable browsers are offered; the plain HTTP client never is."""
    from changedetectionio.blueprint.add_watch_ui import browser_config

    # html_webdriver is only preview-capable when it resolves to playwright/puppeteer, so
    # pretend it does (a WEBDRIVER_URL-only deployment resolves it to selenium, which can't).
    monkeypatch.setattr(browser_config, 'is_visual_capable',
                        lambda name, datastore: name == 'html_webdriver')

    res = client.get(url_for('add_watch_ui.add_watch_ui_index'))
    assert res.status_code == 200
    assert b'name="fetch_backend"' in res.data
    assert b'value="html_webdriver"' in res.data
    # The plain HTTP client can't render a preview, so it is not an option
    assert b'value="html_requests"' not in res.data
    # The system default resolves to html_requests here, so it is listed but disabled
    assert b'value="system"' in res.data
    assert b'disabled' in res.data


