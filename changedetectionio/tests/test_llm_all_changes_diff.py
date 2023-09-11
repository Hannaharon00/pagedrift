#!/usr/bin/env python3
"""
Tests for the 'AI: every change between versions' (all_changes=1) feature.

Covers:
  - all_changes=1 builds a multi-segment diff (pairwise across intermediate snapshots)
  - all_changes=0 (default) uses a single from→to diff
  - the two modes are cached under separate keys (no cross-contamination)
  - a repeated all_changes=1 call returns the cached result without re-calling the LLM
"""

from unittest.mock import patch, call

from flask import url_for

from changedetectionio.tests.util import delete_all_watches


SNAP1 = "apple\nbanana\n"
SNAP2 = "apple\nbanana\ncherry\n"
SNAP3 = "apple\nbanana\ncherry\ndate\n"

TS1 = "2000000001"
TS2 = "2000000002"
TS3 = "2000000003"


def _configure_llm(client):
    ds = client.application.config.get('DATASTORE')
    ds.data['settings']['application']['llm'] = {'model': 'gpt-4o-mini', 'api_key': 'sk-test'}


def _make_watch_with_three_snapshots(client):
    ds = client.application.config.get('DATASTORE')
    uuid = ds.add_watch(url='https://example.com/allchanges')
    watch = ds.data['watching'][uuid]
    watch.save_history_blob(SNAP1, TS1, 'snap1')
    watch.save_history_blob(SNAP2, TS2, 'snap2')
    watch.save_history_blob(SNAP3, TS3, 'snap3')
    return uuid, watch


