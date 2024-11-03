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

def test_rss_single_watch_order(client, live_server, measure_memory_usage, datastore_path):
    """
    Test that single watch RSS feed shows changes in correct order (newest first).
    """

    # Create initial content
    def set_response(datastore_path, version):
        test_return_data = f"""<html>
           <body>
         <p>Version {version} content</p>
         </body>
         </html>
        """
        with open(os.path.join(datastore_path, "endpoint-content.txt"), "w") as f:
            f.write(test_return_data)

    # Start with version 1
    set_response(datastore_path, 1)

    # Add a watch
    test_url = url_for('test_endpoint', _external=True) + "?order_test=1"
    res = client.post(
        url_for("ui.ui_views.form_quick_watch_add"),
        data={"url": test_url, "tags": 'test-tag'},
        follow_redirects=True
    )
    assert b"Watch added" in res.data

    # Get the watch UUID
    watch_uuid = extract_UUID_from_client(client)

    # Wait for initial check
    wait_for_all_checks(client)

    # Create multiple versions by triggering changes
    for version in range(2, 6):  # Create versions 2, 3, 4, 5
        set_response(datastore_path, version)
        res = client.post(url_for("ui.form_watch_checknow"), follow_redirects=True)
        wait_for_all_checks(client)
        time.sleep(0.5)  # Small delay to ensure different timestamps

    # Get RSS token
    rss_token = extract_rss_token_from_UI(client)

    # Request RSS feed for the single watch
    res = client.get(
        url_for("rss.rss_single_watch", uuid=watch_uuid, token=rss_token, _external=True),
        follow_redirects=True
    )

    # Should return valid RSS
    assert res.status_code == 200
    assert b"<?xml" in res.data or b"<rss" in res.data

    # Parse the RSS/XML
    root = ET.fromstring(res.data)

    # Find all items (RSS 2.0) or entries (Atom)
    items = root.findall('.//item')
    if not items:
        items = root.findall('.//{http://www.w3.org/2005/Atom}entry')

    # Should have multiple items
    assert len(items) >= 3, f"Expected at least 3 items, got {len(items)}"

    # Get the descriptions/content from first 3 items
    descriptions = []
    for item in items[:3]:
        # Try RSS format first
        desc = item.findtext('description')
        if not desc:
            # Try Atom format
            content_elem = item.find('{http://www.w3.org/2005/Atom}content')
            if content_elem is not None:
                desc = content_elem.text
        descriptions.append(desc if desc else "")

    print(f"First item content (first 200 chars): {descriptions[0][:200] if descriptions[0] else 'None'}")
    print(f"Second item content (first 200 chars): {descriptions[1][:200] if descriptions[1] else 'None'}")
    print(f"Third item content (first 200 chars): {descriptions[2][:200] if descriptions[2] else 'None'}")

    # The FIRST item should contain the NEWEST change (Version 5)
    # The SECOND item should contain Version 4
    # The THIRD item should contain Version 3
    # Note: Content may include [edit watch] links and diff markup like "(added) 5"
    # So we check for "5 content" which appears in "Version 5 content"
    assert "5 content" in descriptions[0], \
        f"First item should show newest change (with '5 content'), but got: {descriptions[0][:500]}"

    # Verify the order is correct
    assert "4 content" in descriptions[1], \
        f"Second item should show Version 4 (with '4 content'), but got: {descriptions[1][:500]}"

    assert "3 content" in descriptions[2], \
        f"Third item should show Version 3 (with '3 content'), but got: {descriptions[2][:500]}"

    # Clean up
    delete_all_watches(client)


