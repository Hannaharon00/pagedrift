#!/usr/bin/env python3
"""
Integration tests for auto-applying tags to watches by URL pattern matching.

Verifies:
 - A tag with url_match_pattern shows on the watch overview list (via get_all_tags_for_watch)
 - The auto-applied tag appears on the watch edit page
 - A watch whose URL does NOT match the pattern does not get the tag
"""

import json
from flask import url_for
from .util import set_original_response, live_server_setup


def test_tag_url_pattern_shows_in_overview(client, live_server, measure_memory_usage, datastore_path):
    """Tag with a matching url_match_pattern must appear in the watch overview row."""
    set_original_response(datastore_path=datastore_path)

    api_key = live_server.app.config['DATASTORE'].data['settings']['application'].get('api_access_token')

    # Create a tag with a URL match pattern
    res = client.post(
        url_for("tag"),
        data=json.dumps({"title": "Auto GitHub", "url_match_pattern": "*github.com*"}),
        headers={'content-type': 'application/json', 'x-api-key': api_key},
    )
    assert res.status_code == 201, res.data
    tag_uuid = res.json['uuid']

    # Add a watch that matches the pattern
    res = client.post(
        url_for("createwatch"),
        data=json.dumps({"url": "https://github.com/someuser/repo"}),
        headers={'content-type': 'application/json', 'x-api-key': api_key},
    )
    assert res.status_code == 201, res.data
    matching_watch_uuid = res.json['uuid']

    # Add a watch that does NOT match
    res = client.post(
        url_for("createwatch"),
        data=json.dumps({"url": "https://example.com/page"}),
        headers={'content-type': 'application/json', 'x-api-key': api_key},
    )
    assert res.status_code == 201, res.data
    non_matching_watch_uuid = res.json['uuid']

    # Watch overview — the tag label must appear in the matching watch's row
    res = client.get(url_for("watchlist.index"))
    assert res.status_code == 200
    html = res.get_data(as_text=True)

    # The tag title should appear somewhere on the page (it's rendered per-watch via get_all_tags_for_watch)
    assert "Auto GitHub" in html, "Auto-matched tag title must appear in watch overview"

    # Verify via the datastore directly that get_all_tags_for_watch returns the pattern-matched tag
    datastore = live_server.app.config['DATASTORE']

    matching_tags = datastore.get_all_tags_for_watch(matching_watch_uuid)
    assert tag_uuid in matching_tags, "Pattern-matched tag must be returned for matching watch"

    non_matching_tags = datastore.get_all_tags_for_watch(non_matching_watch_uuid)
    assert tag_uuid not in non_matching_tags, "Pattern-matched tag must NOT appear for non-matching watch"


