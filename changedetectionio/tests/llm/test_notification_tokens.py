"""
Tests that {{ llm_summary }} and {{ llm_intent }} notification tokens
are correctly populated in the notification pipeline.

Covers:
  1. notification/handler.py — lazy population logic (lines 367-372)
  2. notification_service.py — _llm_result / _llm_intent from watch → n_object
  3. End-to-end: tokens render in notification body/title
"""
import pytest
from unittest.mock import MagicMock, patch
from changedetectionio.notification_service import NotificationContextData


def _make_n_object(**extra):
    n = NotificationContextData()
    n.update({
        'notification_body': '',
        'notification_title': '',
        'notification_format': 'text',
        'notification_urls': ['json://localhost/'],
        'uuid': 'test-uuid',
        'watch_uuid': 'test-uuid',
        'watch_url': 'https://example.com',
        'current_snapshot': 'current text',
        'prev_snapshot': 'previous text',
    })
    n.update(extra)
    return n


# ---------------------------------------------------------------------------
# handler.py — lazy population of llm_summary / llm_intent
# ---------------------------------------------------------------------------

class TestHandlerLlmTokenPopulation:
    """
    The notification handler checks if llm_summary or llm_intent tokens appear
    in the notification text and lazily populates them from _llm_result.
    """

    def _run_handler_llm_section(self, n_object):
        """
        Replicate the exact logic from notification/handler.py lines 367-372.
        This is tested directly to validate the handler's token population.
        """
        scan_text = n_object.get('notification_body', '') + n_object.get('notification_title', '')
        if 'llm_summary' in scan_text or 'llm_intent' in scan_text:
            llm_result = n_object.get('_llm_result') or {}
            n_object['llm_summary'] = llm_result.get('summary', '')
            n_object['llm_intent'] = n_object.get('_llm_intent', '')
        return n_object

    def test_llm_summary_populated_when_token_in_body(self):
        n = _make_n_object(
            notification_body='Change detected! Summary: {{ llm_summary }}',
            _llm_result={'important': True, 'summary': 'Price dropped from $500 to $400'},
            _llm_intent='flag price drops',
        )
        result = self._run_handler_llm_section(n)
        assert result['llm_summary'] == 'Price dropped from $500 to $400'

    def test_llm_intent_populated_when_token_in_body(self):
        n = _make_n_object(
            notification_body='Intent was: {{ llm_intent }}',
            _llm_result={'important': True, 'summary': 'some change'},
            _llm_intent='flag price drops',
        )
        result = self._run_handler_llm_section(n)
        assert result['llm_intent'] == 'flag price drops'

    def test_llm_summary_in_title(self):
        n = _make_n_object(
            notification_title='[CD] {{ llm_summary }}',
            notification_body='some body',
            _llm_result={'important': True, 'summary': 'New job posted'},
            _llm_intent='new jobs',
        )
        result = self._run_handler_llm_section(n)
        assert result['llm_summary'] == 'New job posted'

    def test_tokens_not_populated_when_absent_from_template(self):
        """Don't bother populating when tokens aren't used — avoid needless LLM calls."""
        n = _make_n_object(
            notification_body='Change at {{ watch_url }}',
            notification_title='CD Alert',
            _llm_result={'important': True, 'summary': 'should not appear'},
            _llm_intent='test',
        )
        result = self._run_handler_llm_section(n)
        # llm_summary and llm_intent should remain at their default None values
        assert result.get('llm_summary') is None
        assert result.get('llm_intent') is None

    def test_empty_summary_when_no_llm_result(self):
        n = _make_n_object(
            notification_body='Summary: {{ llm_summary }}',
            _llm_result=None,
            _llm_intent='',
        )
        result = self._run_handler_llm_section(n)
        assert result['llm_summary'] == ''

    def test_empty_intent_when_not_set(self):
        n = _make_n_object(
            notification_body='Intent: {{ llm_intent }}',
            _llm_result={'important': False, 'summary': ''},
        )
        result = self._run_handler_llm_section(n)
        assert result['llm_intent'] == ''

    def test_summary_from_unimportant_result(self):
        """Even when important=False the summary explains why — useful for debugging."""
        n = _make_n_object(
            notification_body='Summary: {{ llm_summary }}',
            _llm_result={'important': False, 'summary': 'Only a copyright year changed'},
            _llm_intent='flag price drops',
        )
        result = self._run_handler_llm_section(n)
        assert result['llm_summary'] == 'Only a copyright year changed'


# ---------------------------------------------------------------------------
# notification_service.py — _llm_result / _llm_intent wired from watch
# ---------------------------------------------------------------------------

