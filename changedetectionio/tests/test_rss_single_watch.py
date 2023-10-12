#!/usr/bin/env python3

import time
import os
import xml.etree.ElementTree as ET
from flask import url_for

from .restock.test_restock import set_original_response
from .util import live_server_setup, wait_for_all_checks, extract_rss_token_from_UI, extract_UUID_from_client, delete_all_watches, set_modified_response
from ..notification import default_notification_format


# Watch with no change should not break the output
def test_rss_feed_empty(client, live_server, measure_memory_usage, datastore_path):
    set_original_response(datastore_path=datastore_path)
    rss_token = extract_rss_token_from_UI(client)
    test_url = url_for('test_endpoint', _external=True)
    uuid = client.application.config.get('DATASTORE').add_watch(url=test_url)
    # Request RSS feed for the single watch
    res = client.get(
        url_for("rss.rss_single_watch", uuid=uuid, token=rss_token, _external=True),
        follow_redirects=True
    )
    assert res.status_code == 400
    assert b'does not have enough history snapshots to show' in res.data
    delete_all_watches(client)

