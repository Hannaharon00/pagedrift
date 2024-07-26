#!/usr/bin/env python3

# Add a site in paused mode, add an invalid filter, we should still have visual selector data ready
def test_visual_selector_content_ready(client, live_server, measure_memory_usage, datastore_path):

    import os
    import json

    assert os.getenv('PLAYWRIGHT_DRIVER_URL'), "Needs PLAYWRIGHT_DRIVER_URL set for this test"

    # Add our URL to the import page, because the docker container (playwright/selenium) wont be able to connect to our usual test url
    test_url = url_for('test_interactive_html_endpoint', _external=True)
    test_url = test_url.replace('localhost.localdomain', 'cdio')
    test_url = test_url.replace('localhost', 'cdio')

    res = client.post(
        url_for("ui.ui_views.form_quick_watch_add"),
        data={"url": test_url, "tags": '', 'edit_and_watch_submit_button': 'Edit > Watch'},
        follow_redirects=True
    )
    assert b"Watch added in Paused state, saving will unpause" in res.data
    uuid = next(iter(live_server.app.config['DATASTORE'].data['watching']))
    res = client.post(
        url_for("ui.ui_edit.edit_page", uuid=uuid, unpause_on_save=1),
        data={
            "url": test_url,
            "tags": "",
            # For now, cookies doesnt work in headers because it must be a full cookiejar object
            'headers': "testheader: yes\buser-agent: MyCustomAgent",
            'fetch_backend': "html_webdriver",
            "time_between_check_use_default": "y",
        },
        follow_redirects=True
    )
    assert b"unpaused" in res.data
    wait_for_all_checks(client)


    assert live_server.app.config['DATASTORE'].data['watching'][uuid].history_n >= 1, "Watch history had atleast 1 (everything fetched OK)"

    res = client.get(
        url_for("ui.ui_preview.preview_page", uuid=uuid),
        follow_redirects=True
    )
    assert b"testheader: yes" in res.data
    assert b"user-agent: mycustomagent" in res.data


    assert os.path.isfile(os.path.join(datastore_path, uuid, 'last-screenshot.png')), "last-screenshot.png should exist"
    assert os.path.isfile(os.path.join(datastore_path, uuid, 'elements.deflate')), "xpath elements.deflate data should exist"

    # Open it and see if it roughly looks correct
    with open(os.path.join(datastore_path, uuid, 'elements.deflate'), 'rb') as f:
        import zlib
        compressed_data = f.read()
        decompressed_data = zlib.decompress(compressed_data)
        # See if any error was thrown
        json_data = json.loads(decompressed_data.decode('utf-8'))

    # Attempt to fetch it via the web hook that the browser would use
    res = client.get(url_for('static_content', group='visual_selector_data', filename=uuid))
    decompressed_data = zlib.decompress(res.data)
    json_data = json.loads(decompressed_data.decode('utf-8'))
    
    assert res.mimetype == 'application/json'
    assert res.status_code == 200


    # Some options should be enabled
    # @todo - in the future, the visibility should be toggled by JS from the request type setting
    res = client.get(
        url_for("ui.ui_edit.edit_page", uuid="first"),
        follow_redirects=True
    )
    assert b'notification_screenshot' in res.data
    client.post(
        url_for("ui.form_delete", uuid="all"),
        follow_redirects=True
    )

