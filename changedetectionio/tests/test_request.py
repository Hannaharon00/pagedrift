import json
import os
import time
from flask import url_for
from . util import set_original_response, set_modified_response, live_server_setup, wait_for_all_checks, extract_UUID_from_client, delete_all_watches



# Hard to just add more live server URLs when one test is already running (I think)
# So we add our test here (was in a different file)
def test_headers_in_request(client, live_server, measure_memory_usage, datastore_path):
    #ve_server_setup(live_server)
    # Add our URL to the import page
    test_url = url_for('test_headers', _external=True)
    if os.getenv('PLAYWRIGHT_DRIVER_URL'):
        # Because its no longer calling back to localhost but from the browser container, set in test-only.yml
        test_url = test_url.replace('localhost', 'changedet')

    # Add the test URL twice, we will check
    uuidA = client.application.config.get('DATASTORE').add_watch(url=test_url)
    client.post(url_for("ui.form_watch_checknow"), follow_redirects=True)

    wait_for_all_checks(client)

    uuidB = client.application.config.get('DATASTORE').add_watch(url=test_url)
    client.post(url_for("ui.form_watch_checknow"), follow_redirects=True)

    wait_for_all_checks(client)
    cookie_header = '_ga=GA1.2.1022228332; cookie-preferences=analytics:accepted;'


    # Add some headers to a request
    res = client.post(
        url_for("ui.ui_edit.edit_page", uuid=uuidA),
        data={
              "url": test_url,
              "tags": "",
              "fetch_backend": 'html_webdriver' if os.getenv('PLAYWRIGHT_DRIVER_URL') else 'html_requests',
              "headers": "jinja2:{{ 1+1 }}\nxxx:ooo\ncool:yeah\r\ncookie:"+cookie_header,
              "time_between_check_use_default": "y"},
        follow_redirects=True
    )
    assert b"Updated watch." in res.data

    client.post(url_for("ui.form_watch_checknow"), follow_redirects=True)

    # Give the thread time to pick up the first version
    wait_for_all_checks(client)

    # The service should echo back the request headers
    res = client.get(
        url_for("ui.ui_preview.preview_page", uuid=uuidA),
        follow_redirects=True
    )

    # Flask will convert the header key to uppercase
    assert b"Jinja2:2" in res.data
    assert b"Xxx:ooo" in res.data
    assert b"Cool:yeah" in res.data

    # The test call service will return the headers as the body
    from html import escape
    assert escape(cookie_header).encode('utf-8') in res.data

    wait_for_all_checks(client)

    # Re #137 -  It should have only one set of headers entered
    watches_with_headers = 0
    for k, watch in client.application.config.get('DATASTORE').data.get('watching').items():
            if (len(watch['headers'])):
                watches_with_headers += 1
    assert watches_with_headers == 1

    # 'server' http header was automatically recorded
    for k, watch in client.application.config.get('DATASTORE').data.get('watching').items():
        assert 'custom' in watch.get('remote_server_reply') # added in util.py

    delete_all_watches(client)

def test_body_in_request(client, live_server, measure_memory_usage, datastore_path):
    import os

    # Add our URL to the import page
    test_url = url_for('test_body', _external=True)
    if os.getenv('PLAYWRIGHT_DRIVER_URL'):
        # Because its no longer calling back to localhost but from the browser container, set in test-only.yml
        test_url = test_url.replace('localhost', 'cdio')

    uuid = client.application.config.get('DATASTORE').add_watch(url=test_url)
    client.post(url_for("ui.form_watch_checknow"), follow_redirects=True)

    wait_for_all_checks(client)

    # add the first 'version'
    res = client.post(
        url_for("ui.ui_edit.edit_page", uuid=uuid),
        data={
              "url": test_url,
              "tags": "",
              "method": "POST",
              "fetch_backend": "html_requests",
              "body": "something something",
              "time_between_check_use_default": "y"},
        follow_redirects=True
    )
    assert b"Updated watch." in res.data

    wait_for_all_checks(client)

    # Now the change which should trigger a change
    body_value = 'Test Body Value {{ 1+1 }}'
    body_value_formatted = 'Test Body Value 2'
    res = client.post(
        url_for("ui.ui_edit.edit_page", uuid=uuid),
        data={
              "url": test_url,
              "tags": "",
              "method": "POST",
              "fetch_backend": "html_requests",
              "body": body_value,
              "time_between_check_use_default": "y"},
        follow_redirects=True
    )
    assert b"Updated watch." in res.data

    wait_for_all_checks(client)

    # The service should echo back the body
    res = client.get(
        url_for("ui.ui_preview.preview_page", uuid=uuid),
        follow_redirects=True
    )

    # If this gets stuck something is wrong, something should always be there
    assert b"No history found" not in res.data
    # We should see the formatted value of what we sent in the reply
    assert str.encode(body_value) not in res.data
    assert str.encode(body_value_formatted) in res.data

    ####### data sanity checks
    # Add the test URL twice, we will check
    uuid = client.application.config.get('DATASTORE').add_watch(url=test_url)
    client.post(url_for("ui.form_watch_checknow"), follow_redirects=True)
    wait_for_all_checks(client)
    watches_with_body = 0

    # Read individual watch.json files
    for uuid in client.application.config.get('DATASTORE').data['watching'].keys():
        watch_json_file = os.path.join(datastore_path, uuid, 'watch.json')
        assert os.path.exists(watch_json_file), f"watch.json should exist at {watch_json_file}"
        with open(watch_json_file, 'r', encoding='utf-8') as f:
            watch_data = json.load(f)
            if watch_data.get('body') == body_value:
                watches_with_body += 1

    # Should be only one with body set
    assert watches_with_body==1

    # Attempt to add a body with a GET method
    res = client.post(
        url_for("ui.ui_edit.edit_page", uuid=uuid),
        data={
              "url": test_url,
              "tags": "",
              "method": "GET",
              "fetch_backend": "html_requests",
              "body": "invalid",
              "time_between_check_use_default": "y"},
        follow_redirects=True
    )
    assert b"Body must be empty when Request Method is set to GET" in res.data
    delete_all_watches(client)

def test_method_in_request(client, live_server, measure_memory_usage, datastore_path):
    import os
    # Add our URL to the import page
    test_url = url_for('test_method', _external=True)
    if os.getenv('PLAYWRIGHT_DRIVER_URL'):
        # Because its no longer calling back to localhost but from the browser container, set in test-only.yml
        test_url = test_url.replace('localhost', 'cdio')

    # Add the test URL twice, we will check
    uuid = client.application.config.get('DATASTORE').add_watch(url=test_url)
    client.post(url_for("ui.form_watch_checknow"), follow_redirects=True)

    wait_for_all_checks(client)
    uuid = client.application.config.get('DATASTORE').add_watch(url=test_url)
    client.post(url_for("ui.form_watch_checknow"), follow_redirects=True)

    wait_for_all_checks(client)

    # Attempt to add a method which is not valid
    res = client.post(
        url_for("ui.ui_edit.edit_page", uuid="first"),
        data={
            "url": test_url,
            "tags": "",
            "fetch_backend": "html_requests",
            "method": "invalid",
            "time_between_check_use_default": "y"},
        follow_redirects=True
    )
    assert b"Not a valid choice" in res.data

    # Add a properly formatted body
    res = client.post(
        url_for("ui.ui_edit.edit_page", uuid="first"),
        data={
            "url": test_url,
            "tags": "",
            "fetch_backend": "html_requests",
            "method": "PATCH",
            "time_between_check_use_default": "y"},
        follow_redirects=True
    )
    assert b"Updated watch." in res.data

    # Give the thread time to pick up the first version
    wait_for_all_checks(client)

    # The service should echo back the request verb
    res = client.get(
        url_for("ui.ui_preview.preview_page", uuid="first"),
        follow_redirects=True
    )

    # The test call service will return the verb as the body
    assert b"PATCH" in res.data

    wait_for_all_checks(client)

    watches_with_method = 0

    # Read individual watch.json files
    for uuid in client.application.config.get('DATASTORE').data['watching'].keys():
        watch_json_file = os.path.join(datastore_path, uuid, 'watch.json')
        assert os.path.exists(watch_json_file), f"watch.json should exist at {watch_json_file}"
        with open(watch_json_file, 'r', encoding='utf-8') as f:
            watch_data = json.load(f)
            if watch_data.get('method') == 'PATCH':
                watches_with_method += 1

    # Should be only one with method set to PATCH
    assert watches_with_method == 1

    delete_all_watches(client)

# Re #2408 - user-agent override test, also should handle case-insensitive header deduplication
def test_ua_global_override(client, live_server, measure_memory_usage, datastore_path):
    ##  live_server_setup(live_server) # Setup on conftest per function
    test_url = url_for('test_headers', _external=True)

    res = client.post(
        url_for("settings.settings_page"),
        data={
            "application-fetch_backend": "html_requests",
            "application-minutes_between_check": 180,
            "requests-default_ua-html_requests": "html-requests-user-agent"
        },
        follow_redirects=True
    )
    assert b'Settings updated' in res.data

    uuid = client.application.config.get('DATASTORE').add_watch(url=test_url)
    client.post(url_for("ui.form_watch_checknow"), follow_redirects=True)

    wait_for_all_checks(client)
    res = client.get(
        url_for("ui.ui_preview.preview_page", uuid="first"),
        follow_redirects=True
    )

    assert b"html-requests-user-agent" in res.data
    # default user-agent should have shown by now
    # now add a custom one in the headers


    # Add some headers to a request
    res = client.post(
        url_for("ui.ui_edit.edit_page", uuid="first"),
        data={
            "url": test_url,
            "tags": "testtag",
            "fetch_backend": 'html_requests',
            # Important - also test case-insensitive
            "headers": "User-AGent: agent-from-watch",
            "time_between_check_use_default": "y"},
        follow_redirects=True
    )
    assert b"Updated watch." in res.data
    wait_for_all_checks(client)
    res = client.get(
        url_for("ui.ui_preview.preview_page", uuid="first"),
        follow_redirects=True
    )
    assert b"agent-from-watch" in res.data
    assert b"html-requests-user-agent" not in res.data
    delete_all_watches(client)

