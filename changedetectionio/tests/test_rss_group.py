#!/usr/bin/env python3

import time
from flask import url_for
from .util import live_server_setup, wait_for_all_checks, wait_for_watch_history, extract_rss_token_from_UI, get_UUID_for_tag_name, delete_all_watches
import os


def set_original_response(datastore_path):
    test_return_data = """<html>
       <body>
     Some initial text<br>
     <p>Watch 1 content</p>
     <p>Watch 2 content</p>
     </body>
     </html>
    """

    with open(os.path.join(datastore_path, "endpoint-content.txt"), "w") as f:
        f.write(test_return_data)
    return None


def set_modified_response(datastore_path):
    test_return_data = """<html>
       <body>
     Some initial text<br>
     <p>Watch 1 content MODIFIED</p>
     <p>Watch 2 content CHANGED</p>
     </body>
     </html>
    """

    with open(os.path.join(datastore_path, "endpoint-content.txt"), "w") as f:
        f.write(test_return_data)
    return None


def test_rss_group_only_unviewed(client, live_server, measure_memory_usage, datastore_path):
    """
    Test that RSS feed for a tag only shows unviewed watches.
    """

    set_original_response(datastore_path=datastore_path)

    # Create a tag
    res = client.post(
        url_for("tags.form_tag_add"),
        data={"name": "unviewed-test"},
        follow_redirects=True
    )
    assert b"Tag added" in res.data

    tag_uuid = get_UUID_for_tag_name(client, name="unviewed-test")

    # Add two watches with the tag
    test_url_1 = url_for('test_endpoint', _external=True) + "?unviewed=1"
    res = client.post(
        url_for("ui.ui_views.form_quick_watch_add"),
        data={"url": test_url_1, "tags": 'unviewed-test'},
        follow_redirects=True
    )
    assert b"Watch added" in res.data

    test_url_2 = url_for('test_endpoint', _external=True) + "?unviewed=2"
    res = client.post(
        url_for("ui.ui_views.form_quick_watch_add"),
        data={"url": test_url_2, "tags": 'unviewed-test'},
        follow_redirects=True
    )
    assert b"Watch added" in res.data

    wait_for_all_checks(client)
    assert wait_for_watch_history(client, min_history_count=1, timeout=10), "Initial snapshots not saved"

    # Trigger changes
    set_modified_response(datastore_path=datastore_path)
    res = client.post(url_for("ui.form_watch_checknow"), follow_redirects=True)
    wait_for_all_checks(client)
    assert wait_for_watch_history(client, min_history_count=2, timeout=10), "History not accumulated"

    # Get RSS token
    rss_token = extract_rss_token_from_UI(client)

    # Request RSS feed - should show both watches (both unviewed)
    res = client.get(
        url_for("rss.rss_tag_feed", tag_uuid=tag_uuid, token=rss_token, _external=True),
        follow_redirects=True
    )
    assert res.status_code == 200
    assert b"unviewed=1" in res.data
    assert b"unviewed=2" in res.data

    # Mark all as viewed
    res = client.post(url_for('ui.mark_all_viewed'), follow_redirects=True)
    wait_for_all_checks(client)

    # Request RSS feed again - should be empty now (no unviewed watches)
    res = client.get(
        url_for("rss.rss_tag_feed", tag_uuid=tag_uuid, token=rss_token, _external=True),
        follow_redirects=True
    )
    assert res.status_code == 200
    # Should not contain the watch URLs anymore since they're viewed
    assert b"unviewed=1" not in res.data
    assert b"unviewed=2" not in res.data

    # Clean up
    delete_all_watches(client)
    res = client.post(url_for("tags.delete_all"), follow_redirects=True)
    assert b'All tags deleted' in res.data
