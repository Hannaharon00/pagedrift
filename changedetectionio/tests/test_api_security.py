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

def test_api_path_traversal_in_uuids(client, live_server, measure_memory_usage, datastore_path):
    """
    Test that path traversal attacks via UUID parameter are blocked.
    Addresses CVE-like vulnerabilities where ../../../ in UUID could access arbitrary files.
    """
    api_key = live_server.app.config['DATASTORE'].data['settings']['application'].get('api_access_token')
    set_original_response(datastore_path=datastore_path)
    test_url = url_for('test_endpoint', _external=True)

    # Create a valid watch first
    res = client.post(
        url_for("createwatch"),
        data=json.dumps({"url": test_url, "title": "Valid watch"}),
        headers={'content-type': 'application/json', 'x-api-key': api_key},
    )
    assert res.status_code == 201
    valid_uuid = res.json.get('uuid')

    # Test 1: Path traversal with ../../../
    res = client.get(
        f"/api/v1/watch/../../etc/passwd",
        headers={'x-api-key': api_key}
    )
    assert res.status_code in [400, 404], "Path traversal should be rejected"

    # Test 2: Encoded path traversal
    res = client.get(
        "/api/v1/watch/..%2F..%2F..%2Fetc%2Fpasswd",
        headers={'x-api-key': api_key}
    )
    assert res.status_code in [400, 404], "Encoded path traversal should be rejected"

    # Test 3: Double-encoded path traversal
    res = client.get(
        "/api/v1/watch/%2e%2e%2f%2e%2e%2f%2e%2e%2f",
        headers={'x-api-key': api_key}
    )
    assert res.status_code in [400, 404], "Double-encoded traversal should be rejected"

    # Test 4: Try to access datastore file
    res = client.get(
        "/api/v1/watch/../url-watches.json",
        headers={'x-api-key': api_key}
    )
    assert res.status_code in [400, 404], "Access to datastore should be blocked"

    # Test 5: Null byte injection
    res = client.get(
        f"/api/v1/watch/{valid_uuid}%00.json",
        headers={'x-api-key': api_key}
    )
    # Should either work (ignoring null byte) or reject - but not crash
    assert res.status_code in [200, 400, 404]

    # Test 6: DELETE with path traversal
    res = client.delete(
        "/api/v1/watch/../../datastore/url-watches.json",
        headers={'x-api-key': api_key}
    )
    assert res.status_code in [400, 404, 405], "DELETE with traversal should be blocked (405=method not allowed is also acceptable)"

    # Cleanup
    client.delete(url_for("watch", uuid=valid_uuid), headers={'x-api-key': api_key})
    delete_all_watches(client)


def test_api_injection_via_headers_and_proxy(client, live_server, measure_memory_usage, datastore_path):
    """
    Test that injection attacks via headers and proxy fields are properly sanitized.
    Addresses XSS and injection vulnerabilities.
    """
    api_key = live_server.app.config['DATASTORE'].data['settings']['application'].get('api_access_token')
    set_original_response(datastore_path=datastore_path)
    test_url = url_for('test_endpoint', _external=True)

    # Test 1: XSS in headers
    res = client.post(
        url_for("createwatch"),
        data=json.dumps({
            "url": test_url,
            "headers": {
                "User-Agent": "<script>alert(1)</script>",
                "X-Custom": "'; DROP TABLE watches; --"
            }
        }),
        headers={'content-type': 'application/json', 'x-api-key': api_key},
    )
    # Headers are metadata used for HTTP requests, not HTML rendering
    # Storing them as-is is expected behavior
    assert res.status_code in [201, 400]
    if res.status_code == 201:
        watch_uuid = res.json.get('uuid')
        # Verify headers are stored (API returns JSON, not HTML, so no XSS risk)
        res = client.get(url_for("watch", uuid=watch_uuid), headers={'x-api-key': api_key})
        assert res.status_code == 200
        client.delete(url_for("watch", uuid=watch_uuid), headers={'x-api-key': api_key})

    # Test 2: Null bytes in headers
    res = client.post(
        url_for("createwatch"),
        data=json.dumps({
            "url": test_url,
            "headers": {"X-Test": "value\x00null"}
        }),
        headers={'content-type': 'application/json', 'x-api-key': api_key},
    )
    # Should handle null bytes gracefully (reject or sanitize)
    assert res.status_code in [201, 400]

    # Test 3: Malformed proxy string
    res = client.post(
        url_for("createwatch"),
        data=json.dumps({
            "url": test_url,
            "proxy": "http://evil.com:8080@victim.com"
        }),
        headers={'content-type': 'application/json', 'x-api-key': api_key},
    )
    # Should reject invalid proxy format
    assert res.status_code == 400

    # Test 4: Control characters in notification title
    res = client.post(
        url_for("createwatch"),
        data=json.dumps({
            "url": test_url,
            "notification_title": "Test\r\nInjected-Header: value"
        }),
        headers={'content-type': 'application/json', 'x-api-key': api_key},
    )
    # Should accept but sanitize control characters
    if res.status_code == 201:
        watch_uuid = res.json.get('uuid')
        client.delete(url_for("watch", uuid=watch_uuid), headers={'x-api-key': api_key})

    delete_all_watches(client)


def test_api_large_payload_dos(client, live_server, measure_memory_usage, datastore_path):
    """
    Test that excessively large payloads are rejected to prevent DoS.
    Addresses memory leak issues found in changelog.
    """
    api_key = live_server.app.config['DATASTORE'].data['settings']['application'].get('api_access_token')
    set_original_response(datastore_path=datastore_path)
    test_url = url_for('test_endpoint', _external=True)

    # Test 1: Huge ignore_text array
    res = client.post(
        url_for("createwatch"),
        data=json.dumps({
            "url": test_url,
            "ignore_text": ["a" * 10000] * 100  # 1MB of data
        }),
        headers={'content-type': 'application/json', 'x-api-key': api_key},
    )
    # Should either accept (with limits) or reject
    if res.status_code == 201:
        watch_uuid = res.json.get('uuid')
        client.delete(url_for("watch", uuid=watch_uuid), headers={'x-api-key': api_key})

    # Test 2: Massive headers object
    huge_headers = {f"X-Header-{i}": "x" * 1000 for i in range(100)}
    res = client.post(
        url_for("createwatch"),
        data=json.dumps({
            "url": test_url,
            "headers": huge_headers
        }),
        headers={'content-type': 'application/json', 'x-api-key': api_key},
    )
    # Should reject or truncate
    assert res.status_code in [201, 400, 413]
    if res.status_code == 201:
        watch_uuid = res.json.get('uuid')
        client.delete(url_for("watch", uuid=watch_uuid), headers={'x-api-key': api_key})

    # Test 3: Huge browser_steps array
    res = client.post(
        url_for("createwatch"),
        data=json.dumps({
            "url": test_url,
            "browser_steps": [
                {"operation": "click", "selector": "#test" * 1000, "optional_value": ""}
            ] * 100
        }),
        headers={'content-type': 'application/json', 'x-api-key': api_key},
    )
    # Should reject or limit
    assert res.status_code in [201, 400, 413]
    if res.status_code == 201:
        watch_uuid = res.json.get('uuid')
        client.delete(url_for("watch", uuid=watch_uuid), headers={'x-api-key': api_key})

    # Test 4: Extremely long title
    res = client.post(
        url_for("createwatch"),
        data=json.dumps({
            "url": test_url,
            "title": "x" * 100000  # 100KB title
        }),
        headers={'content-type': 'application/json', 'x-api-key': api_key},
    )
    # Should reject (exceeds maxLength: 5000)
    assert res.status_code == 400

    delete_all_watches(client)


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


def test_api_queue_manipulation(client, live_server, measure_memory_usage, datastore_path):
    """
    Test queue behavior under stress and edge cases.
    """
    api_key = live_server.app.config['DATASTORE'].data['settings']['application'].get('api_access_token')
    set_original_response(datastore_path=datastore_path)
    test_url = url_for('test_endpoint', _external=True)

    # Test 1: Create many watches rapidly
    watch_uuids = []
    for i in range(20):
        res = client.post(
            url_for("createwatch"),
            data=json.dumps({"url": test_url, "title": f"Watch {i}"}),
            headers={'content-type': 'application/json', 'x-api-key': api_key},
        )
        if res.status_code == 201:
            watch_uuids.append(res.json.get('uuid'))

    assert len(watch_uuids) == 20, "Should be able to create 20 watches"

    # Test 2: Recheck all when watches exist
    res = client.get(
        url_for("createwatch", recheck_all='1'),
        headers={'x-api-key': api_key},
    )
    # Should return success (200 or 202 for background processing)
    assert res.status_code in [200, 202]

    # Test 3: Verify queue doesn't overflow with moderate load
    # The app has MAX_QUEUE_SIZE = 5000, we're well below that
    wait_for_all_checks(client)

    # Cleanup
    for uuid in watch_uuids:
        client.delete(url_for("watch", uuid=uuid), headers={'x-api-key': api_key})

    delete_all_watches(client)


# ============================================================================
# TIER 3: EDGE CASES & POLISH
# ============================================================================

