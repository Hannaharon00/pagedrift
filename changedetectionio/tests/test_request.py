import json
import os
import time
from flask import url_for
from . util import set_original_response, set_modified_response, live_server_setup, wait_for_all_checks, extract_UUID_from_client, delete_all_watches



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

