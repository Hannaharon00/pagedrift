#!/usr/bin/env python3
"""PAGE_WATCH_LIMIT - the optional cap on how many watches one instance will hold.

The limit is enforced in datastore.add_watch(), which every add path funnels through, but each
surface has to report it in its own terms: a flash for the UI, a 429 for the API, one flash for
a whole file in the importers, and nothing at all (just a None) where there's no request context.
"""

import json
from flask import url_for
from .util import delete_all_watches


def test_watch_limit_absent_or_junk_means_unlimited(client, live_server, measure_memory_usage, datastore_path, monkeypatch):
    """No env var, an empty one, or an unparseable one all leave the limit switched off."""
    datastore = live_server.app.config['DATASTORE']

    monkeypatch.delenv('PAGE_WATCH_LIMIT', raising=False)
    assert datastore.watch_limit is None
    assert datastore.watch_limit_reached() is False

    # Junk must not block every add, and must not raise
    monkeypatch.setenv('PAGE_WATCH_LIMIT', 'not-a-number')
    assert datastore.watch_limit is None
    assert datastore.watch_limit_reached() is False

    # Set-but-empty is the same as unset
    monkeypatch.setenv('PAGE_WATCH_LIMIT', '')
    assert datastore.watch_limit is None
    assert datastore.watch_limit_reached() is False


def test_api_create_watch_refused_at_limit(client, live_server, measure_memory_usage, datastore_path, monkeypatch):
    api_key = live_server.app.config['DATASTORE'].data['settings']['application'].get('api_access_token')
    datastore = live_server.app.config['DATASTORE']
    test_url = url_for('test_endpoint', _external=True)

    monkeypatch.setenv('PAGE_WATCH_LIMIT', '1')

    res = client.post(
        url_for("createwatch"),
        data=json.dumps({"url": test_url}),
        headers={'content-type': 'application/json', 'x-api-key': api_key},
    )
    assert res.status_code == 201

    res = client.post(
        url_for("createwatch"),
        data=json.dumps({"url": f"{test_url}?second=1"}),
        headers={'content-type': 'application/json', 'x-api-key': api_key},
    )
    assert res.status_code == 429
    assert b'Watch limit reached (1/1 watches)' in res.data
    assert len(datastore.data['watching']) == 1

    delete_all_watches(client)


def test_api_import_refuses_the_whole_batch(client, live_server, measure_memory_usage, datastore_path, monkeypatch):
    """A 429 from import always means nothing was created, so the same request can be retried."""
    api_key = live_server.app.config['DATASTORE'].data['settings']['application'].get('api_access_token')
    datastore = live_server.app.config['DATASTORE']
    test_url = url_for('test_endpoint', _external=True)
    headers = {'x-api-key': api_key, 'content-type': 'text/plain'}

    monkeypatch.setenv('PAGE_WATCH_LIMIT', '3')

    res = client.post(url_for("import"), data=f"{test_url}?a=1\n{test_url}?a=2", headers=headers)
    assert res.status_code == 200
    assert len(res.json) == 2

    # Two more would make four - refused whole rather than importing the one that fits
    res = client.post(url_for("import"), data=f"{test_url}?a=3\n{test_url}?a=4", headers=headers)
    assert res.status_code == 429
    assert b'would exceed it' in res.data
    assert len(datastore.data['watching']) == 2

    # The one that does fit still goes in
    res = client.post(url_for("import"), data=f"{test_url}?a=3", headers=headers)
    assert res.status_code == 200
    assert len(datastore.data['watching']) == 3

    delete_all_watches(client)


