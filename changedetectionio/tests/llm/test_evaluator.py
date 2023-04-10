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

class TestGroupAiSettingGatesTheCascade:
    def test_only_the_on_state_hands_settings_down(self):
        from changedetectionio.llm.evaluator import tag_llm_applies_to_watches
        assert tag_llm_applies_to_watches(_make_tag(ai=True)) is True
        # "Off" suppresses AI rather than lending prompts; "leave it to each watch" and tags
        # predating the setting (and missing tags) hand nothing down either
        assert tag_llm_applies_to_watches(_make_tag(ai=False)) is False
        assert tag_llm_applies_to_watches(_make_tag(ai=None)) is False
        assert tag_llm_applies_to_watches({'title': 'legacy'}) is False
        assert tag_llm_applies_to_watches(None) is False

    def test_intent_not_inherited_when_group_is_off(self):
        from changedetectionio.llm.evaluator import resolve_intent
        tag = _make_tag(ai=False, title='pricing-group', llm_intent='flag price drops')
        ds = _make_datastore(tags={'tag-1': tag})
        watch = _make_watch(llm_intent='', tags=['tag-1'])
        assert resolve_intent(watch, ds) == ('', '')

    def test_field_not_inherited_when_group_is_off(self):
        from changedetectionio.llm.evaluator import resolve_llm_field
        tag = _make_tag(ai=False, llm_change_summary='list new events')
        ds = _make_datastore(tags={'t1': tag})
        watch = _make_watch(llm_change_summary='', tags=['t1'])
        assert resolve_llm_field(watch, ds, 'llm_change_summary') == ('', '')

    def test_summary_prompt_not_inherited_when_group_is_off(self):
        from changedetectionio.llm.evaluator import get_effective_summary_prompt
        tag = _make_tag(ai=False, llm_change_summary='TAG')
        ds = _make_datastore(llm_cfg={'change_summary_default': 'GLOBAL'}, tags={'t1': tag})
        watch = _make_watch(llm_change_summary='', tags=['t1'])
        assert get_effective_summary_prompt(watch, ds) == 'GLOBAL'

    def test_first_group_set_to_on_wins_over_an_earlier_one_that_is_off(self):
        """A group that isn't "On" is skipped entirely, not treated as "found, but empty"."""
        from changedetectionio.llm.evaluator import resolve_intent
        ds = _make_datastore(tags={
            'ignored': _make_tag(ai=False, title='ignored-group', llm_intent='IGNORED'),
            'used': _make_tag(ai=True, title='used-group', llm_intent='USED'),
        })
        watch = _make_watch(llm_intent='', tags=['ignored', 'used'])
        assert resolve_intent(watch, ds) == ('USED', 'used-group')


# ---------------------------------------------------------------------------
# llm_enabled_for_watch — per-watch / per-group AI on-off switch (#4204)
# ---------------------------------------------------------------------------

