#!/usr/bin/env python3
"""
Test the watch edited flag functionality.

This tests the private __watch_was_edited flag that tracks when writable
watch fields are modified, which prevents skipping reprocessing when the
watch configuration has changed.
"""

import os
import time
from flask import url_for
from .util import live_server_setup, wait_for_all_checks


def set_test_content(datastore_path):
    """Write test HTML content to endpoint-content.txt for test server."""
    test_html = """<html>
     <body>
     <p>Test content for watch edited flag tests</p>
     <p>This content stays the same across checks</p>
     </body>
     </html>
    """
    with open(os.path.join(datastore_path, "endpoint-content.txt"), "w") as f:
        f.write(test_html)


def test_watch_edited_flag_lifecycle(client, live_server, measure_memory_usage, datastore_path):
    """
    Test the full lifecycle of the was_edited flag:
    1. Flag starts False when watch is created
    2. Flag becomes True when writable fields are modified
    3. Flag is reset False after worker processing
    4. Flag stays False when readonly fields are modified
    """

    # Setup - Add a watch
    test_url = url_for('test_endpoint', _external=True)
    res = client.post(
        url_for("ui.ui_views.form_quick_watch_add"),
        data={"url": test_url, "tags": "", "edit_and_watch_submit_button": "Edit > Watch"},
        follow_redirects=True
    )
    assert b"Watch added" in res.data or b"Updated watch" in res.data

    # Get the watch UUID
    datastore = client.application.config.get('DATASTORE')
    uuid = list(datastore.data['watching'].keys())[0]
    watch = datastore.data['watching'][uuid]

    # Reset flag after initial form submission (form sets fields which trigger the flag)
    watch.reset_watch_edited_flag()

    # Test 1: Flag should be False after reset
    assert not watch.was_edited, "Flag should be False after reset"

    # Test 2: Modify a writable field (title) - flag should become True
    watch['title'] = 'New Title'
    assert watch.was_edited, "Flag should be True after modifying writable field 'title'"

    # Test 3: Reset flag manually (simulating what worker does)
    watch.reset_watch_edited_flag()
    assert not watch.was_edited, "Flag should be False after reset"

    # Test 4: Modify another writable field (url) - flag should become True again
    watch['url'] = 'https://example.com'
    assert watch.was_edited, "Flag should be True after modifying writable field 'url'"

    # Test 5: Reset and modify a readonly field - flag should stay False
    watch.reset_watch_edited_flag()
    assert not watch.was_edited, "Flag should be False after reset"

    # Modify readonly field (uuid) - should not set flag
    old_uuid = watch['uuid']
    watch['uuid'] = 'readonly-test-uuid'
    assert not watch.was_edited, "Flag should stay False when modifying readonly field 'uuid'"
    watch['uuid'] = old_uuid  # Restore original

    # Note: Worker reset behavior is tested in test_check_removed_line_contains_trigger
    # and test_watch_edited_flag_prevents_skip

    print("✓ All watch edited flag lifecycle tests passed")


