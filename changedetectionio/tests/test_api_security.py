#!/usr/bin/env python3
"""
Comprehensive security and edge case tests for the API.
Tests critical areas that were identified as gaps in the existing test suite.
"""

import time
import json
import threading
import uuid as uuid_module
from flask import url_for
from .util import live_server_setup, wait_for_all_checks, wait_for_watch_history, delete_all_watches
import os


def set_original_response(datastore_path):
    test_return_data = """<html>
       <body>
     Some initial text<br>
     <p>Which is across multiple lines</p>
     </body>
     </html>
    """
    with open(os.path.join(datastore_path, "endpoint-content.txt"), "w") as f:
        f.write(test_return_data)
    return None


def is_valid_uuid(val):
    try:
        uuid_module.UUID(str(val))
        return True
    except ValueError:
        return False


# ============================================================================
# TIER 1: CRITICAL SECURITY TESTS
# ============================================================================

def test_api_utf8_encoding_edge_cases(client, live_server, measure_memory_usage, datastore_path):
    """
    Test UTF-8 encoding edge cases that have caused bugs on Windows.
    Addresses 18+ encoding bugs from changelog.
    """
    api_key = live_server.app.config['DATASTORE'].data['settings']['application'].get('api_access_token')
    set_original_response(datastore_path=datastore_path)
    test_url = url_for('test_endpoint', _external=True)

    # Test 1: Unicode in title (should work)
    res = client.post(
        url_for("createwatch"),
        data=json.dumps({
            "url": test_url,
            "title": "Test 中文 Ελληνικά 日本語 🔥"
        }),
        headers={'content-type': 'application/json', 'x-api-key': api_key},
    )
    assert res.status_code == 201
    watch_uuid = res.json.get('uuid')

    # Verify it round-trips correctly
    res = client.get(url_for("watch", uuid=watch_uuid), headers={'x-api-key': api_key})
    assert res.status_code == 200
    assert "中文" in res.json.get('title')

    client.delete(url_for("watch", uuid=watch_uuid), headers={'x-api-key': api_key})

    # Test 2: Unicode in URL query parameters
    res = client.post(
        url_for("createwatch"),
        data=json.dumps({
            "url": test_url + "?search=日本語"
        }),
        headers={'content-type': 'application/json', 'x-api-key': api_key},
    )
    # Should handle URL encoding properly
    assert res.status_code in [201, 400]
    if res.status_code == 201:
        watch_uuid = res.json.get('uuid')
        client.delete(url_for("watch", uuid=watch_uuid), headers={'x-api-key': api_key})

    # Test 3: Null byte in title (should be rejected or sanitized)
    res = client.post(
        url_for("createwatch"),
        data=json.dumps({
            "url": test_url,
            "title": "Test\x00Title"
        }),
        headers={'content-type': 'application/json', 'x-api-key': api_key},
    )
    # Should handle gracefully
    assert res.status_code in [201, 400]
    if res.status_code == 201:
        watch_uuid = res.json.get('uuid')
        client.delete(url_for("watch", uuid=watch_uuid), headers={'x-api-key': api_key})

    # Test 4: BOM (Byte Order Mark) in title
    res = client.post(
        url_for("createwatch"),
        data=json.dumps({
            "url": test_url,
            "title": "\ufeffTest with BOM"
        }),
        headers={'content-type': 'application/json', 'x-api-key': api_key},
    )
    assert res.status_code in [201, 400]
    if res.status_code == 201:
        watch_uuid = res.json.get('uuid')
        client.delete(url_for("watch", uuid=watch_uuid), headers={'x-api-key': api_key})

    delete_all_watches(client)


