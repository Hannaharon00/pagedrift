#!/usr/bin/env python3

import time
import os

from flask import url_for
from .util import live_server_setup, wait_for_all_checks, delete_all_watches




def _runner_test_http_errors(client, live_server, http_code, expected_text, datastore_path):

    with open(os.path.join(datastore_path, "endpoint-content.txt"), "w") as f:
        f.write("Now you going to get a {} error code\n".format(http_code))


    # Add our URL to the import page
    test_url = url_for('test_endpoint',
                       status_code=http_code,
                       _external=True)

    uuid = client.application.config.get('DATASTORE').add_watch(url=test_url)
    client.post(url_for("ui.form_watch_checknow"), follow_redirects=True)

    # Give the thread time to pick it up
    wait_for_all_checks(client)

    res = client.get(url_for("watchlist.index"))
    # no change
    assert b'has-unread-changes' not in res.data
    assert bytes(expected_text.encode('utf-8')) in res.data


    # Error viewing tabs should appear
    res = client.get(
        url_for("ui.ui_preview.preview_page", uuid="first"),
        follow_redirects=True
    )

    assert b'Error Text' in res.data

    # 'Error Screenshot' only when in playwright mode
    #assert b'Error Screenshot' in res.data


    delete_all_watches(client)


def test_http_error_handler(client, live_server, measure_memory_usage, datastore_path):
    _runner_test_http_errors(client, live_server, 403, 'Access denied', datastore_path=datastore_path)
    _runner_test_http_errors(client, live_server, 404, 'Page not found', datastore_path=datastore_path)
    _runner_test_http_errors(client, live_server, 500, '(Internal server error) received', datastore_path=datastore_path)
    _runner_test_http_errors(client, live_server, 400, 'Error - Request returned a HTTP error code 400', datastore_path=datastore_path)
    delete_all_watches(client)

