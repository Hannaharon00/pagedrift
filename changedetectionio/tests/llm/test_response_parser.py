"""
Unit tests for changedetectionio/llm/response_parser.py

All functions are pure — no external dependencies needed.
"""

import pytest

from changedetectionio.llm.response_parser import (
    _extract_json,
    parse_eval_response,
    parse_preview_response,
    parse_setup_response,
)


class TestExtractJson:
    def test_plain_json_passes_through(self):
        raw = '{"important": true, "summary": "price dropped"}'
        assert _extract_json(raw) == raw

    def test_strips_json_code_fence(self):
        raw = '```json\n{"important": false, "summary": "no match"}\n```'
        result = _extract_json(raw)
        assert result.startswith('{')
        assert '"important"' in result

    def test_strips_plain_code_fence(self):
        raw = '```\n{"important": true, "summary": "ok"}\n```'
        result = _extract_json(raw)
        assert result.startswith('{')

    def test_extracts_json_from_surrounding_text(self):
        raw = 'Here is my response: {"important": true, "summary": "match"} — done.'
        result = _extract_json(raw)
        assert result == '{"important": true, "summary": "match"}'

    def test_multiline_json(self):
        raw = '{\n  "important": false,\n  "summary": "nothing relevant"\n}'
        result = _extract_json(raw)
        assert '"important"' in result

    def test_strips_reasoning_think_tags(self):
        raw = (
            '<think>\n'
            'Let us consider if {"important": false} is right. Actually, yes.\n'
            '</think>\n'
            '{"important": true, "summary": "Price fell to $300"}'
        )
        result = _extract_json(raw)
        assert result == '{"important": true, "summary": "Price fell to $300"}'

    def test_strips_reasoning_think_tags_with_code_fence(self):
        raw = (
            '<think>\nThinking about the price change.\n</think>\n'
            '```json\n{"important": false, "summary": "Cosmetic change only"}\n```'
        )
        result = _extract_json(raw)
        assert '"important"' in result
        assert '<think>' not in result


class TestReasoningBlockEdgeCases:
    """A reasoning scratchpad usually contains JSON of its own, so any leftover scratchpad
    lets _extract_json return a discarded intermediate answer. Every shape below carries a
    misleading `"important": false` in the scratchpad and the real verdict outside it."""

    def test_closing_tag_only_is_still_stripped(self):
        # Several providers/chat templates inject the opening tag themselves, so only the
        # closer comes back over the wire.
        raw = (
            'My first read was {"important": false, "summary": "nothing"}\n'
            '</think>\n'
            '{"important": true, "summary": "Price dropped"}'
        )
        assert _extract_json(raw) == '{"important": true, "summary": "Price dropped"}'
        assert parse_eval_response(raw) == {
            'important': True,
            'summary': 'Price dropped',
        }

    def test_thinking_tag_variant_is_stripped(self):
        raw = (
            '<thinking>weighing {"important": false, "summary": "no"}</thinking>\n'
            '{"important": true, "summary": "Price dropped"}'
        )
        assert parse_eval_response(raw)['important'] is True

    def test_multiple_reasoning_blocks_are_stripped(self):
        raw = (
            '<think>step one</think>'
            '<think>{"important": false, "summary": "no"}</think>'
            '{"important": true, "summary": "Price dropped"}'
        )
        assert parse_eval_response(raw)['important'] is True

    def test_unterminated_reasoning_block_raises(self):
        # Truncated by max_tokens mid-thought: the only JSON present is the abandoned guess,
        # so returning it would silently invert the verdict. Raise instead and let
        # evaluator.py's handler fall back to "important" rather than dropping the change.
        raw = (
            '<think>\n'
            'First guess: {"important": false, "summary": "nothing"}\n'
            'But actually the price dropped, so'
        )
        with pytest.raises(ValueError, match='unterminated reasoning block'):
            _extract_json(raw)

    def test_unterminated_block_propagates_out_of_parse_eval_response(self):
        """Deliberately NOT swallowed. parse_eval_response's own fallback is
        important=False, which suppresses the notification - the opposite of what
        evaluator.py wants on failure ("don't suppress the notification"). Letting
        ValueError escape routes it to that handler instead. Do not add ValueError to
        the except tuple in parse_eval_response."""
        raw = '<think>truncated mid-thought {"important": false}'
        with pytest.raises(ValueError):
            parse_eval_response(raw)

    def test_response_with_no_reasoning_block_is_untouched(self):
        raw = '{"important": true, "summary": "plain"}'
        assert _extract_json(raw) == raw


