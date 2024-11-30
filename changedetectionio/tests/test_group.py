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

def test_setup_group_tag(client, live_server, measure_memory_usage, datastore_path):
    
    set_original_response(datastore_path=datastore_path)

    # Add a tag with some config, import a tag and it should roughly work
    res = client.post(
        url_for("tags.form_tag_add"),
        data={"name": "test-tag"},
        follow_redirects=True
    )
    assert b"Tag added" in res.data
    assert b"test-tag" in res.data

    res = client.post(
        url_for("tags.form_tag_edit_submit", uuid="first"),
        data={"name": "test-tag",
              "include_filters": '#only-this',
              "subtractive_selectors": '#not-this'},
        follow_redirects=True
    )
    assert b"Updated" in res.data
    tag_uuid = get_UUID_for_tag_name(client, name="test-tag")
    res = client.get(
        url_for("tags.form_tag_edit", uuid="first")
    )
    assert b"#only-this" in res.data
    assert b"#not-this" in res.data

    # Tag should be setup and ready, now add a watch

    test_url = url_for('test_endpoint', _external=True)
    res = client.post(
        url_for("imports.import_page"),
        data={"urls": test_url + "?first-imported=1 test-tag, extra-import-tag"},
        follow_redirects=True
    )
    assert b"1 Imported" in res.data

    res = client.get(url_for("watchlist.index"))
    assert b'import-tag' in res.data
    assert b'extra-import-tag' in res.data

    res = client.get(
        url_for("tags.tags_overview_page"),
        follow_redirects=True
    )
    assert b'import-tag' in res.data
    assert b'extra-import-tag' in res.data

    wait_for_all_checks(client)

    res = client.get(url_for("watchlist.index"))
    assert b'Warning, no filters were found' not in res.data

    res = client.get(
        url_for("ui.ui_preview.preview_page", uuid="first"),
        follow_redirects=True
    )
    assert b'Should be only this' in res.data
    assert b'And never this' not in res.data

    res = client.get(
        url_for("ui.ui_edit.edit_page", uuid="first"),
        follow_redirects=True
    )
    # 2307 the UI notice should appear in the placeholder
    assert b'WARNING: Watch has tag/groups set with special filters' in res.data

    # RSS Group tag filter
    # An extra one that should be excluded
    res = client.post(
        url_for("imports.import_page"),
        data={"urls": test_url + "?should-be-excluded=1 some-tag"},
        follow_redirects=True
    )
    assert b"1 Imported" in res.data
    wait_for_all_checks(client)
    set_modified_response(datastore_path=datastore_path)
    res = client.post(url_for("ui.form_watch_checknow"), follow_redirects=True)
    wait_for_all_checks(client)
    rss_token = extract_rss_token_from_UI(client)
    res = client.get(
        url_for("rss.feed", token=rss_token, tag="extra-import-tag", _external=True),
        follow_redirects=True
    )
    assert b"should-be-excluded" not in res.data
    assert res.status_code == 200
    assert b"first-imported=1" in res.data
    delete_all_watches(client)

def test_tag_import_singular(client, live_server, measure_memory_usage, datastore_path):
    

    test_url = url_for('test_endpoint', _external=True)
    res = client.post(
        url_for("imports.import_page"),
        data={"urls": test_url + " test-tag, test-tag\r\n"+ test_url + "?x=1 test-tag, test-tag\r\n"},
        follow_redirects=True
    )
    assert b"2 Imported" in res.data

    res = client.get(
        url_for("tags.tags_overview_page"),
        follow_redirects=True
    )
    # Should be only 1 tag because they both had the same
    assert len(live_server.app.config['DATASTORE'].data['settings']['application'].get('tags')) ==1

    delete_all_watches(client)

def test_tag_add_in_ui(client, live_server, measure_memory_usage, datastore_path):
    
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

def test_limit_tag_ui(client, live_server, measure_memory_usage, datastore_path):

    test_url = url_for('test_random_content_endpoint', _external=True)

    # A space can label the tag, only the first one will have a tag
    client.post(
        url_for("imports.import_page"),
        data={"urls": f"{test_url} test-tag\r\n{test_url}"},
        follow_redirects=True
    )
    tag_uuid = get_UUID_for_tag_name(client, name="test-tag")
    assert tag_uuid

    res = client.get(url_for("watchlist.index"))
    assert b'test-tag' in res.data
    client.post(url_for("ui.form_watch_checknow"), follow_redirects=True)
    wait_for_all_checks(client)
    client.post(url_for("ui.form_watch_checknow"), follow_redirects=True)
    wait_for_all_checks(client)

    # Should be both unviewed
    res = client.get(url_for("watchlist.index"))
    assert res.data.count(b' unviewed ') == 2


    # Now we recheck only the tag
    client.post(url_for('ui.mark_all_viewed', tag=tag_uuid), follow_redirects=True)
    wait_for_all_checks(client)

    # Should be only 1 unviewed
    res = client.get(url_for("watchlist.index"))
    assert res.data.count(b' unviewed ') == 1


    delete_all_watches(client)
    res = client.post(url_for("tags.delete_all"), follow_redirects=True)
    assert b'All tags deleted' in res.data

def test_clone_tag_on_import(client, live_server, measure_memory_usage, datastore_path):
    
    test_url = url_for('test_endpoint', _external=True)
    res = client.post(
        url_for("imports.import_page"),
        data={"urls": test_url + " test-tag, another-tag\r\n"},
        follow_redirects=True
    )

    assert b"1 Imported" in res.data

    res = client.get(url_for("watchlist.index"))
    assert b'test-tag' in res.data
    assert b'another-tag' in res.data

    watch_uuid = next(iter(live_server.app.config['DATASTORE'].data['watching']))
    res = client.post(url_for("ui.form_clone", uuid=watch_uuid), follow_redirects=True)

    assert b'Cloned' in res.data
    res = client.get(url_for("watchlist.index"))
    # 2 times plus the top link to tag
    assert res.data.count(b'test-tag') == 3
    assert res.data.count(b'another-tag') == 3
    delete_all_watches(client)

