#!/usr/bin/env python3
"""
Tests for the /diff/<uuid>/download-patch endpoint.

The route should accept from_version and to_version query parameters,
read those two snapshots from the watch history, generate a unified diff
patch, and return it as a downloadable text/plain file.
"""

from flask import url_for

from changedetectionio.tests.util import live_server_setup, delete_all_watches, wait_for_all_checks


def _add_watch_with_history(app, url, v1_text, v2_text):
    """
    Add a watch and inject two synthetic snapshots into its history so we
    can test the download-patch route without hitting a live fetch cycle.
    """
    datastore = app.config['DATASTORE']
    uuid = datastore.add_watch(url=url, extras={})
    watch = datastore.data['watching'][uuid]

    # Write the two snapshots directly via save_history_blob
    # Args: contents (str), timestamp (str), snapshot_id (str)
    watch.save_history_blob(v1_text, '1000000000', 'snap-v1')
    watch.save_history_blob(v2_text, '1000000001', 'snap-v2')

    return uuid


