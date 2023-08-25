import json
import os
import time
import re
from flask import url_for
from loguru import logger

# Hard to just add more live server URLs when one test is already running (I think)
# So we add our test here (was in a different file)
def test_check_notification(client, live_server, measure_memory_usage, datastore_path):
    
    set_original_response(datastore_path=datastore_path)

    # Re 360 - new install should have defaults set
    # Notification UI lives on its own page since the global settings refactor.
    res = client.get(url_for("settings.notifications.apprise"))
    notification_url = url_for('test_notification_endpoint', _external=True).replace('http', 'json')+"?status_code=204"

    assert default_notification_body.encode() in res.data
    assert default_notification_title.encode() in res.data

    #####################
    # Set this up for when we remove the notification from the watch, it should fallback with these details
    res = client.post(
        url_for("settings.notifications.apprise"),
        data={"notification_urls": notification_url,
              "notification_title": "fallback-title "+default_notification_title,
              "notification_body": "fallback-body "+default_notification_body,
              "notification_format": default_notification_format},
        follow_redirects=True
    )

    assert b"Settings updated." in res.data

    res = client.get(url_for("settings.notifications.apprise"))
    for k,v in valid_notification_formats.items():
        if k == USE_SYSTEM_DEFAULT_NOTIFICATION_FORMAT_FOR_WATCH:
            continue
        assert f'value="{k}"'.encode() in res.data # Should be by key NOT value
        assert f'value="{v}"'.encode() not in res.data # Should be by key NOT value


    # When test mode is in BASE_URL env mode, we should see this already configured
    env_base_url = os.getenv('BASE_URL', '').strip()
    if len(env_base_url):
        logging.debug(">>> BASE_URL enabled, looking for %s", env_base_url)
        res = client.get(url_for("settings.notifications.apprise"))
        assert bytes(env_base_url.encode('utf-8')) in res.data
    else:
        logging.debug(">>> SKIPPING BASE_URL check")

    # re #242 - when you edited an existing new entry, it would not correctly show the notification settings
    # Add our URL to the import page
    test_url = url_for('test_endpoint', _external=True)
    res = client.post(
        url_for("ui.ui_views.form_quick_watch_add"),
        data={"url": test_url, "tags": ''},
        follow_redirects=True
    )
    assert b"Watch added" in res.data

    # Give the thread time to pick up the first version
    wait_for_all_checks(client)

    # We write the PNG to disk, but a JPEG should appear in the notification
    # Write the last screenshot png
    testimage_png = 'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII='


    uuid = next(iter(live_server.app.config['DATASTORE'].data['watching']))
    screenshot_dir = os.path.join(datastore_path, str(uuid))
    os.makedirs(screenshot_dir, exist_ok=True)
    with open(os.path.join(screenshot_dir, 'last-screenshot.png'), 'wb') as f:
        f.write(base64.b64decode(testimage_png))

    # Goto the edit page, add our ignore text
    # Add our URL to the import page

    print (">>>> Notification URL: "+notification_url)

    notification_form_data = {"notification_urls": notification_url,
                              "notification_title": "New ChangeDetection.io Notification - {{watch_url}}",
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
                                                   "Diff with args: {{diff(context=3)}}"
                                                   "Diff as Patch: {{diff_patch}}\n"
                                                   "Change datetime: {{change_datetime}}\n"
                                                   "Change datetime format: Weekday {{change_datetime(format='%A')}}\n"
                                                   "Change datetime format: {{change_datetime(format='%Y-%m-%dT%H:%M:%S%z')}}\n"
                                                   ":-)",
                              "notification_screenshot": True,
                              "notification_format": 'text'}

    notification_form_data.update({
        "url": test_url,
        "tags": "my tag, my second tag",
        "title": "my title",
        "headers": "",
        "fetch_backend": "html_requests",
        "time_between_check_use_default": "y"})

    res = client.post(
        url_for("ui.ui_edit.edit_page", uuid="first"),
        data=notification_form_data,
        follow_redirects=True
    )
    assert b"Updated watch." in res.data


    # Hit the edit page, be sure that we saved it
    # Re #242 - wasnt saving?
    res = client.get(
        url_for("ui.ui_edit.edit_page", uuid="first"))
    assert bytes(notification_url.encode('utf-8')) in res.data
    assert bytes("New ChangeDetection.io Notification".encode('utf-8')) in res.data

    ## Now recheck, and it should have sent the notification
    wait_for_all_checks(client)
    set_modified_response(datastore_path=datastore_path)

    # Trigger a check
    client.post(url_for("ui.form_watch_checknow"), follow_redirects=True)
    wait_for_all_checks(client)
    wait_for_notification_endpoint_output(datastore_path=datastore_path)

    # Check no errors were recorded
    res = client.get(url_for("watchlist.index"))
    assert b'notification-error' not in res.data


    # Verify what was sent as a notification, this file should exist
    with open(os.path.join(datastore_path, "notification.txt"), "r") as f:
        notification_submission = f.read()
    os.unlink(os.path.join(datastore_path, "notification.txt"))

    # Did we see the URL that had a change, in the notification?
    # Diff was correctly executed

    assert "Diff Full: Some initial text" in notification_submission
    assert "Diff: (changed) Which is across multiple lines" in notification_submission
    assert "(into) which has this one new line" in notification_submission
    # Re #342 - check for accidental python byte encoding of non-utf8/string
    assert "b'" not in notification_submission
    assert re.search('Watch UUID: [0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}', notification_submission, re.IGNORECASE)
    assert "Watch title: my title" in notification_submission
    assert "Watch tag: my tag, my second tag" in notification_submission
    assert "diff/" in notification_submission
    assert "preview/" in notification_submission
    assert ":-)" in notification_submission
    assert "New ChangeDetection.io Notification - {}".format(test_url) in notification_submission
    assert test_url in notification_submission

    assert ':-)' in notification_submission
    # Check the attachment was added, and that it is a JPEG from the original PNG
    notification_submission_object = json.loads(notification_submission)
    assert notification_submission_object

    import time
    # Could be from a few seconds ago (when the notification was fired vs in this test checking), so check for any
    times_possible = [str(FormattableTimestamp(int(time.time()) - i)) for i in range(15)]
    assert any(t in notification_submission for t in times_possible)

    txt = f"Weekday {FormattableTimestamp(int(time.time()))(format='%A')}"
    assert txt in notification_submission




    # We keep PNG screenshots for now
    # IF THIS FAILS YOU SHOULD BE TESTING WITH ENV VAR REMOVE_REQUESTS_OLD_SCREENSHOTS=False
    assert notification_submission_object['attachments'][0]['filename'] == 'last-screenshot.png'
    assert len(notification_submission_object['attachments'][0]['base64'])
    assert notification_submission_object['attachments'][0]['mimetype'] == 'image/png'
    jpeg_in_attachment = base64.b64decode(notification_submission_object['attachments'][0]['base64'])

    # Assert that the JPEG is readable (didn't get chewed up somewhere)
    from PIL import Image
    import io
    assert Image.open(io.BytesIO(jpeg_in_attachment))

    if env_base_url:
        # Re #65 - did we see our BASE_URl ?
        logging.debug (">>> BASE_URL checking in notification: %s", env_base_url)
        assert env_base_url in notification_submission
    else:
        logging.debug(">>> Skipping BASE_URL check")


    # This should insert the {current_snapshot}
    set_more_modified_response(datastore_path=datastore_path)
    client.post(url_for("ui.form_watch_checknow"), follow_redirects=True)
    wait_for_all_checks(client)
    wait_for_notification_endpoint_output(datastore_path=datastore_path)
    # Verify what was sent as a notification, this file should exist
    with open(os.path.join(datastore_path, "notification.txt"), "r") as f:
        notification_submission = f.read()
    assert "Ohh yeah awesome" in notification_submission


    # Prove that "content constantly being marked as Changed with no Updating causes notification" is not a thing
    # https://github.com/dgtlmoon/changedetection.io/discussions/192
    os.unlink(os.path.join(datastore_path, "notification.txt"))

    # Trigger a check
    client.post(url_for("ui.form_watch_checknow"), follow_redirects=True)
    wait_for_all_checks(client)
    client.post(url_for("ui.form_watch_checknow"), follow_redirects=True)
    wait_for_all_checks(client)
    client.post(url_for("ui.form_watch_checknow"), follow_redirects=True)
    wait_for_all_checks(client)
    assert os.path.exists(os.path.join(datastore_path, "notification.txt")) == False

    res = client.get(url_for("settings.notification_logs"))
    # be sure we see it in the output log
    assert b'New ChangeDetection.io Notification - ' + test_url.encode('utf-8') in res.data

    set_original_response(datastore_path=datastore_path)
    res = client.post(
        url_for("ui.ui_edit.edit_page", uuid="first"),
        data={
        "url": test_url,
        "tags": "my tag",
        "title": "my title",
        "notification_urls": '',
        "notification_title": '',
        "notification_body": '',
        "notification_format": default_notification_format,
        "fetch_backend": "html_requests",
        "time_between_check_use_default": "y"},
        follow_redirects=True
    )
    assert b"Updated watch." in res.data

    wait_for_all_checks(client)
    wait_for_notification_endpoint_output(datastore_path=datastore_path)

    # Verify what was sent as a notification, this file should exist
    with open(os.path.join(datastore_path, "notification.txt"), "r") as f:
        notification_submission = f.read()
    assert "fallback-title" in notification_submission
    assert "fallback-body" in notification_submission

    # cleanup for the next
    client.post(
        url_for("ui.form_delete", uuid="all"),
        follow_redirects=True
    )


