#!/usr/bin/env python3
"""
Integration tests: /edit/<uuid>/preview-rendered returns llm_evaluation when
llm_intent is submitted alongside the filter form data.

These tests verify the full backend path:
  JS POSTs llm_intent → prepare_filter_prevew() applies it to tmp_watch
  → preview_extract() is called → llm_evaluation appears in JSON response

The response uses {'found': bool, 'answer': str} — NOT the diff-evaluation
{'important', 'summary'} shape, because preview asks the LLM to extract from
the current content directly (e.g. "30 articles listed") rather than compare
a diff.
"""

import json
import time
from unittest.mock import patch

from flask import url_for

from changedetectionio.tests.util import wait_for_all_checks, delete_all_watches


HTML_WITH_ARTICLES = """<html><body>
<ul id="articles">
  <li>Article One</li>
  <li>Article Two</li>
  <li>Article Three</li>
</ul>
</body></html>"""

HTML_WITH_PRICE = """<html><body>
<p class="price">Original price: $199.00</p>
<p class="discount">Now: $149.00 — 25% off!</p>
</body></html>"""


def _set_response(datastore_path, content):
    import os
    with open(os.path.join(datastore_path, "endpoint-content.txt"), "w") as f:
        f.write(content)


def _add_and_fetch(client, live_server, datastore_path, html):
    """Add a watch, fetch it once so a snapshot exists, return uuid."""
    _set_response(datastore_path, html)
    test_url = url_for('test_endpoint', _external=True)
    uuid = client.application.config.get('DATASTORE').add_watch(url=test_url)
    client.post(url_for("ui.form_watch_checknow"), follow_redirects=True)
    time.sleep(0.5)
    wait_for_all_checks(client)
    return uuid


