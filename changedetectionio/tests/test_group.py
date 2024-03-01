#!/usr/bin/env python3

import time
from flask import url_for
from .util import live_server_setup, wait_for_all_checks, extract_rss_token_from_UI, get_UUID_for_tag_name, extract_UUID_from_client, delete_all_watches
import os

from ..store import ChangeDetectionStore


# def test_setup(client, live_server, measure_memory_usage, datastore_path):
   #  live_server_setup(live_server) # Setup on conftest per function

def set_original_response(datastore_path):
    test_return_data = """<html>
       <body>
     Some initial text<br>
     <p id="only-this">Should be only this</p>
     <br>
     <p id="not-this">And never this</p>
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
     <p id="only-this">Should be REALLY only this</p>
     <br>
     <p id="not-this">And never this</p>
     </body>
     </html>
    """

    with open(os.path.join(datastore_path, "endpoint-content.txt"), "w") as f:
        f.write(test_return_data)
    return None

#
    res = client.post(
        url_for("tags.form_tag_add"),
        data={"name": "new-test-tag"},
        follow_redirects=True
    )
    assert b"Tag added" in res.data
    assert b"new-test-tag" in res.data

    res = client.post(url_for("tags.delete_all"), follow_redirects=True)
    assert b'All tags deleted' in res.data

    delete_all_watches(client)

def test_group_tag_notification(client, live_server, measure_memory_usage, datastore_path):
    delete_all_watches(client)

    set_original_response(datastore_path=datastore_path)

    test_url = url_for('test_endpoint', _external=True)
    res = client.post(
        url_for("ui.ui_views.form_quick_watch_add"),
        data={"url": test_url, "tags": 'test-tag, other-tag'},
        follow_redirects=True
    )

    assert b"Watch added" in res.data

    notification_url = url_for('test_notification_endpoint', _external=True).replace('http', 'json')
    notification_form_data = {"notification_urls": notification_url,
                              "notification_title": "New GROUP TAG ChangeDetection.io Notification - {{watch_url}}",
                              "notification_body": "BASE URL: {{base_url}}\n"
                                                   "Watch URL: {{watch_url}}\n"
                                                   "Watch UUID: {{watch_uuid}}\n"
                                                   "Watch title: {{watch_title}}\n"
                                                   "Watch tag: {{watch_tag}}\n"
                                                   "Preview: {{preview_url}}\n"
                                                   "Diff URL: {{diff_url}}\n"
                                                   "Snapshot: {{current_snapshot}}\n"
                                                   "Diff: {{diff}}\n"
                                                   "Diff Added: {{diff_added}}\n"
                                                   "Diff Removed: {{diff_removed}}\n"
                                                   "Diff Full: {{diff_full}}\n"
                                                   "Diff as Patch: {{diff_patch}}\n"
                                                   ":-)",
                              "notification_screenshot": True,
                              "notification_format": 'text',
                              "title": "test-tag"}

    res = client.post(
        url_for("tags.form_tag_edit_submit", uuid=get_UUID_for_tag_name(client, name="test-tag")),
        data=notification_form_data,
        follow_redirects=True
    )
    assert b"Updated" in res.data

    wait_for_all_checks(client)

    set_modified_response(datastore_path=datastore_path)
    client.post(url_for("ui.form_watch_checknow"), follow_redirects=True)
    wait_for_all_checks(client)

    time.sleep(3)

    assert os.path.isfile(os.path.join(datastore_path, "notification.txt"))

    # Verify what was sent as a notification, this file should exist
    with open(os.path.join(datastore_path, "notification.txt"), "r") as f:
        notification_submission = f.read()
    os.unlink(os.path.join(datastore_path, "notification.txt"))

    # Did we see the URL that had a change, in the notification?
    # Diff was correctly executed
    assert test_url in notification_submission
    assert ':-)' in notification_submission
    assert "Diff Full: Some initial text" in notification_submission
    assert "New GROUP TAG ChangeDetection.io" in notification_submission
    assert "test-tag" in notification_submission
    assert "other-tag" in notification_submission

    #@todo Test that multiple notifications fired
    #@todo Test that each of multiple notifications with different settings
    delete_all_watches(client)

