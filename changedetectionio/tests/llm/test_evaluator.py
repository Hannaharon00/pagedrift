"""
Unit tests for changedetectionio/llm/evaluator.py

Uses mocked LLM calls — no real API key needed.
"""
import pytest
from unittest.mock import patch, MagicMock


def _make_watch(llm_intent='', llm_change_summary='', tags=None, uuid='test-uuid-1234'):
    w = {}
    w['llm_intent'] = llm_intent
    w['llm_change_summary'] = llm_change_summary
    w['tags'] = tags or []
    w['uuid'] = uuid
    w['url'] = 'https://example.com'
    w['page_title'] = 'Test Page'
    w['llm_evaluation_cache'] = {}
    w['llm_prefilter'] = None
    return w


# ---------------------------------------------------------------------------
# resolve_intent
# ---------------------------------------------------------------------------

