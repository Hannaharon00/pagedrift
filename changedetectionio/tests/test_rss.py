#!/usr/bin/env python3
import email.utils
import os
import time
import pytest
from flask import url_for
from .util import set_original_response, set_modified_response, live_server_setup, wait_for_all_checks, extract_rss_token_from_UI, \
    extract_UUID_from_client, delete_all_watches
from loguru import logger
from ..blueprint.rss import RSS_FORMAT_TYPES


def test_rss_feed_empty(client, live_server, measure_memory_usage, datastore_path):

    rss_token = extract_rss_token_from_UI(client)

    res = client.get(
        url_for("rss.feed", token=rss_token, _external=True),
        follow_redirects=True
    )
    assert res.status_code == 200
    assert b'xml' in res.data

def test_rss_and_token(client, live_server, measure_memory_usage, datastore_path):
    #   #  live_server_setup(live_server) # Setup on conftest per function

    set_original_response(datastore_path=datastore_path)
    rss_token = extract_rss_token_from_UI(client)

    uuid = client.application.config.get('DATASTORE').add_watch(url=url_for('test_random_content_endpoint', _external=True))
    client.post(url_for("ui.form_watch_checknow"), follow_redirects=True)
    wait_for_all_checks(client)
    set_modified_response(datastore_path=datastore_path)
    client.post(url_for("ui.form_watch_checknow"), follow_redirects=True)
    wait_for_all_checks(client)

    # Add our URL to the import page
    res = client.get(
        url_for("rss.feed", token="bad token", _external=True),
        follow_redirects=True
    )

    assert b"Access denied, bad token" in res.data

    res = client.get(
        url_for("rss.feed", token=rss_token, _external=True),
        follow_redirects=True
    )
    assert b"Access denied, bad token" not in res.data
    assert b"Random content" in res.data

    delete_all_watches(client)

def test_basic_cdata_rss_markup(client, live_server, measure_memory_usage, datastore_path):
    

    set_original_cdata_xml(datastore_path)
    # Rarely do endpoints give the right header, usually just text/xml, so we check also for <rss
    # This also triggers the automatic CDATA text parser so the RSS goes back a nice content list
    test_url = url_for('test_endpoint', content_type="text/xml; charset=UTF-8", _external=True)

    # Add our URL to the import page
    uuid = client.application.config.get('DATASTORE').add_watch(url=test_url)
    client.post(url_for("ui.form_watch_checknow"), follow_redirects=True)

    wait_for_all_checks(client)

    res = client.get(
        url_for("ui.ui_preview.preview_page", uuid="first"),
        follow_redirects=True
    )
    assert b'CDATA' not in res.data
    assert b'<![' not in res.data
    assert b'Hackers can access your computer' in res.data
    assert b'The days of Terminator' in res.data
    delete_all_watches(client)

