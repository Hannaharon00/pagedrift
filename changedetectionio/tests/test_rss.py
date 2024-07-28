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

