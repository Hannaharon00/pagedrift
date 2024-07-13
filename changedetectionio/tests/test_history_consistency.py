#!/usr/bin/env python3

import time
import os
import json
from flask import url_for
from loguru import logger
from .. import strtobool
from .util import wait_for_all_checks, delete_all_watches
import brotli


def test_history_trim_global_only(client, live_server, measure_memory_usage, datastore_path):
    # Add our URL to the import page
    test_url = url_for('test_endpoint', _external=True)
    uuid = None
    limit = 3

    for i in range(0, 10):
        with open(os.path.join(datastore_path, "endpoint-content.txt"), "w") as f:
            f.write(f"<html>test {i}</html>")
        if not uuid:
            uuid = client.application.config.get('DATASTORE').add_watch(url=test_url)
        client.post(url_for("ui.form_watch_checknow"), follow_redirects=True)
        wait_for_all_checks(client)

        if i ==8:
            watch = live_server.app.config['DATASTORE'].data['watching'][uuid]
            history_n = len(list(watch.history.keys()))
            logger.debug(f"History length should be at limit {limit} and it is {history_n}")
            assert history_n == limit

        if i == 6:
            res = client.post(
                url_for("settings.settings_page"),
                data={"application-history_snapshot_max_length": limit},
                follow_redirects=True
            )
            # It will need to detect one more change to start trimming it, which is really at 'start of 7'
            assert b'Settings updated' in res.data

    delete_all_watches(client)


