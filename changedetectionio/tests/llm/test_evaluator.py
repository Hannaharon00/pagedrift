"""
Unit tests for changedetectionio/llm/evaluator.py

Uses mocked LLM calls — no real API key needed.
"""
import pytest
from unittest.mock import patch, MagicMock


def _make_datastore(llm_cfg=None, tags=None):
    """Build a minimal datastore-like dict for testing."""
    ds = MagicMock()
    app_settings = {
        'llm': llm_cfg or {},
        'tags': tags or {},
    }
    ds.data = {
        'settings': {
            'application': app_settings,
        }
    }
    return ds


def _make_tag(ai=True, **fields):
    """Build a tag dict.

    `ai` is the group's single AI control (llm_backend_profile): True = on, and its AI
    settings apply to its watches; False = off for every watch in the group; None = the
    group has no say. Defaults to True because most cases here are about what a group set
    to "On" does.
    """
    tag = {'title': 'grp', 'llm_backend_profile': ai}
    tag.update(fields)
    return tag


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

class TestResolveIntent:
    def test_watch_intent_takes_priority(self):
        from changedetectionio.llm.evaluator import resolve_intent

        tag = _make_tag(title='mygroup', llm_intent='group intent')
        ds = _make_datastore(tags={'tag-1': tag})
        watch = _make_watch(llm_intent='watch intent', tags=['tag-1'])

        intent, source = resolve_intent(watch, ds)
        assert intent == 'watch intent'
        assert source == 'watch'

    def test_tag_intent_used_when_watch_has_none(self):
        from changedetectionio.llm.evaluator import resolve_intent

        tag = _make_tag(title='pricing-group', llm_intent='flag price drops')
        ds = _make_datastore(tags={'tag-1': tag})
        watch = _make_watch(llm_intent='', tags=['tag-1'])

        intent, source = resolve_intent(watch, ds)
        assert intent == 'flag price drops'
        assert source == 'pricing-group'

    def test_no_intent_anywhere_returns_empty(self):
        from changedetectionio.llm.evaluator import resolve_intent

        ds = _make_datastore()
        watch = _make_watch(llm_intent='')

        intent, source = resolve_intent(watch, ds)
        assert intent == ''
        assert source == ''

    def test_tag_applied_to_all_watches_in_group(self):
        """An opted-in tag's intent propagates to every watch in the tag."""
        from changedetectionio.llm.evaluator import resolve_intent

        tag = _make_tag(title='job-board', llm_intent='new engineering jobs')
        ds = _make_datastore(tags={'tag-1': tag})

        # Three different watches, all in the tag, none have their own intent
        for watch_uuid in ['uuid-A', 'uuid-B', 'uuid-C']:
            watch = _make_watch(llm_intent='', tags=['tag-1'], uuid=watch_uuid)
            intent, source = resolve_intent(watch, ds)
            assert intent == 'new engineering jobs', f"Watch {watch_uuid} should inherit tag intent"
            assert source == 'job-board'

    def test_whitespace_only_intent_treated_as_empty(self):
        from changedetectionio.llm.evaluator import resolve_intent

        ds = _make_datastore()
        watch = _make_watch(llm_intent='   ')
        intent, source = resolve_intent(watch, ds)
        assert intent == ''

    def test_missing_tag_in_datastore_skipped(self):
        from changedetectionio.llm.evaluator import resolve_intent

        ds = _make_datastore(tags={})  # no tags registered
        watch = _make_watch(llm_intent='', tags=['nonexistent-tag'])
        intent, source = resolve_intent(watch, ds)
        assert intent == ''


# ---------------------------------------------------------------------------
# The group's AI setting gates the whole cascade
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

class TestLlmEnabledForWatch:
    def test_enabled_by_default(self):
        """Watches predating the switch (no key at all) keep AI on."""
        from changedetectionio.llm.evaluator import llm_enabled_for_watch
        ds = _make_datastore()
        assert llm_enabled_for_watch(_make_watch(), ds) == (True, 'watch')

    def test_watch_switch_off(self):
        from changedetectionio.llm.evaluator import llm_enabled_for_watch
        ds = _make_datastore()
        watch = _make_watch()
        watch['llm_backend_profile'] = False
        assert llm_enabled_for_watch(watch, ds) == (False, 'watch')

    def test_group_switch_overrides_watch_off(self):
        """"The group setting overrides any watch on/off" — group ON beats watch OFF."""
        from changedetectionio.llm.evaluator import llm_enabled_for_watch
        tag = _make_tag(ai=True, title='ai-group')
        ds = _make_datastore(tags={'t1': tag})
        watch = _make_watch(tags=['t1'])
        watch['llm_backend_profile'] = False
        assert llm_enabled_for_watch(watch, ds) == (True, 'ai-group')

    def test_group_switch_overrides_watch_on(self):
        from changedetectionio.llm.evaluator import llm_enabled_for_watch
        tag = _make_tag(ai=False, title='no-ai-group')
        ds = _make_datastore(tags={'t1': tag})
        watch = _make_watch(tags=['t1'])
        watch['llm_backend_profile'] = True
        assert llm_enabled_for_watch(watch, ds) == (False, 'no-ai-group')

    def test_group_leaving_it_to_each_watch_does_not_decide(self):
        from changedetectionio.llm.evaluator import llm_enabled_for_watch
        ds = _make_datastore(tags={'t1': _make_tag(ai=None, title='undecided-group')})
        watch = _make_watch(tags=['t1'])
        watch['llm_backend_profile'] = False
        assert llm_enabled_for_watch(watch, ds) == (False, 'watch')

    def test_group_without_the_key_leaves_it_to_the_watch(self):
        """Tags predating the setting behave like "leave it to each watch"."""
        from changedetectionio.llm.evaluator import llm_enabled_for_watch
        ds = _make_datastore(tags={'t1': {'title': 'legacy'}})
        watch = _make_watch(tags=['t1'])
        watch['llm_backend_profile'] = False
        assert llm_enabled_for_watch(watch, ds) == (False, 'watch')

    def test_first_deciding_group_wins(self):
        """An undecided group is skipped; the next group with an opinion decides."""
        from changedetectionio.llm.evaluator import llm_enabled_for_watch
        ds = _make_datastore(tags={
            'a': _make_tag(ai=None, title='undecided-group'),
            'b': _make_tag(ai=False, title='no-ai-group'),
        })
        watch = _make_watch(tags=['a', 'b'])
        assert llm_enabled_for_watch(watch, ds) == (False, 'no-ai-group')


# ---------------------------------------------------------------------------
# get_llm_config
# ---------------------------------------------------------------------------

class TestGetLlmConfig:
    def test_returns_none_when_no_model(self):
        from changedetectionio.llm.evaluator import get_llm_config
        ds = _make_datastore(llm_cfg={})
        assert get_llm_config(ds) is None

    def test_returns_config_when_model_set(self):
        from changedetectionio.llm.evaluator import get_llm_config
        cfg = {'model': 'gpt-4o-mini', 'api_key': 'sk-test'}
        ds = _make_datastore(llm_cfg=cfg)
        result = get_llm_config(ds)
        assert result['model'] == 'gpt-4o-mini'

    def test_env_var_overrides_datastore(self):
        """LLM_MODEL env var takes priority over datastore settings."""
        from changedetectionio.llm.evaluator import get_llm_config
        ds = _make_datastore(llm_cfg={'model': 'datastore-model'})
        with patch.dict('os.environ', {'LLM_MODEL': 'ollama/llama3.2', 'LLM_API_KEY': '', 'LLM_API_BASE': ''}):
            result = get_llm_config(ds)
        assert result['model'] == 'ollama/llama3.2'

    def test_env_var_api_key_and_base_included(self):
        """LLM_API_KEY and LLM_API_BASE are picked up alongside LLM_MODEL."""
        from changedetectionio.llm.evaluator import get_llm_config
        ds = _make_datastore()
        env = {'LLM_MODEL': 'gpt-4o', 'LLM_API_KEY': 'env-key', 'LLM_API_BASE': 'http://localhost:11434'}
        with patch.dict('os.environ', env):
            result = get_llm_config(ds)
        assert result['api_key'] == 'env-key'
        assert result['api_base'] == 'http://localhost:11434'

    def test_llm_configured_via_env_true_when_model_set(self):
        """llm_configured_via_env() returns True when LLM_MODEL is set."""
        from changedetectionio.llm.evaluator import llm_configured_via_env
        with patch.dict('os.environ', {'LLM_MODEL': 'gpt-4o-mini'}):
            assert llm_configured_via_env() is True

    def test_llm_configured_via_env_false_when_not_set(self):
        """llm_configured_via_env() returns False when LLM_MODEL is absent."""
        from changedetectionio.llm.evaluator import llm_configured_via_env
        env = {k: '' for k in ['LLM_MODEL', 'LLM_API_KEY', 'LLM_API_BASE']}
        with patch.dict('os.environ', env, clear=False):
            # Ensure LLM_MODEL is truly absent
            import os
            os.environ.pop('LLM_MODEL', None)
            assert llm_configured_via_env() is False


# ---------------------------------------------------------------------------
# evaluate_change
# ---------------------------------------------------------------------------

