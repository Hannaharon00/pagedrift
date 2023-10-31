#!/usr/bin/env python3
"""
Integration tests for AI Change Summary:
  - llm_change_summary field saved via watch edit form
  - llm_change_summary cascades from tag to watches
  - {{ diff }} replaced by AI summary in notifications
  - {{ raw_diff }} always contains original diff
  - summarise_change only runs when change is detected
"""

import json
import time
from unittest.mock import patch

def test_llm_change_summary_saved_via_edit_form(
        client, live_server, measure_memory_usage, datastore_path):
    """llm_change_summary submitted via watch edit form is persisted."""
    _set_response(datastore_path, HTML_V1)
    _configure_llm(client)
    test_url = url_for('test_endpoint', _external=True)
    uuid = client.application.config.get('DATASTORE').add_watch(url=test_url)

    res = client.post(
        url_for("ui.ui_edit.edit_page", uuid=uuid),
        data={
            "url": test_url,
            "fetch_backend": "html_requests",
            "time_between_check_use_default": "y",
            "llm_change_summary": "List new items added as bullet points. Translate to English.",
        },
        follow_redirects=True,
    )
    assert b"Updated watch." in res.data

    watch = client.application.config.get('DATASTORE').data['watching'][uuid]
    assert watch.get('llm_change_summary') == "List new items added as bullet points. Translate to English."

    delete_all_watches(client)


def test_llm_change_summary_cascades_from_tag(
        client, live_server, measure_memory_usage, datastore_path):
    """llm_change_summary set on a tag is resolved for watches in that tag."""
    from changedetectionio.llm.evaluator import resolve_llm_field

    ds = client.application.config.get('DATASTORE')
    _configure_llm(client)
    _set_response(datastore_path, HTML_V1)
    test_url = url_for('test_endpoint', _external=True)

    # Create a tag with llm_change_summary, AI set to On so its watches inherit it
    tag_uuid = ds.add_tag('events-group')
    ds.data['settings']['application']['tags'][tag_uuid]['llm_change_summary'] = 'Summarise new events'
    ds.data['settings']['application']['tags'][tag_uuid]['llm_backend_profile'] = True

    # Watch in that tag, no own summary prompt
    uuid = ds.add_watch(url=test_url)
    ds.data['watching'][uuid]['tags'] = [tag_uuid]
    ds.data['watching'][uuid]['llm_change_summary'] = ''

    watch = ds.data['watching'][uuid]
    value, source = resolve_llm_field(watch, ds, 'llm_change_summary')
    assert value == 'Summarise new events'
    assert source == 'events-group'

    delete_all_watches(client)


# ---------------------------------------------------------------------------
# Notification token behaviour
# ---------------------------------------------------------------------------

