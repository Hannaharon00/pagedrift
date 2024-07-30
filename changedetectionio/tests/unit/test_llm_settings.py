#!/usr/bin/env python3

# run from dir above changedetectionio/ dir
# python3 -m unittest changedetectionio.tests.unit.test_llm_settings

import unittest

from pydantic import ValidationError

from changedetectionio.model.LLMSettings import (
    LLMSettings,
    LLM_DEFAULT_BUDGET_ACTION,
    LLM_DEFAULT_LOCAL_TOKEN_MULTIPLIER,
    LLM_DEFAULT_MAX_INPUT_CHARS,
    LLM_DEFAULT_MAX_SUMMARY_TOKENS,
    LLM_DEFAULT_THINKING_BUDGET,
)


class TestLLMSettingsDefaults(unittest.TestCase):
    def test_empty_dict_yields_default_model(self):
        s = LLMSettings.model_validate({})
        self.assertTrue(s.enabled)
        self.assertFalse(s.debug)
        self.assertEqual(s.model, '')
        self.assertEqual(s.api_key, '')
        self.assertEqual(s.thinking_budget, LLM_DEFAULT_THINKING_BUDGET)
        self.assertEqual(s.max_summary_tokens, LLM_DEFAULT_MAX_SUMMARY_TOKENS)
        self.assertEqual(s.local_token_multiplier, LLM_DEFAULT_LOCAL_TOKEN_MULTIPLIER)
        self.assertEqual(s.max_input_chars, LLM_DEFAULT_MAX_INPUT_CHARS)
        self.assertEqual(s.budget_action, LLM_DEFAULT_BUDGET_ACTION)
        self.assertEqual(s.tokens_total_cumulative, 0)
        self.assertEqual(s.cost_usd_this_month, 0.0)

    def test_default_construct_matches_validate_empty(self):
        self.assertEqual(LLMSettings().model_dump(), LLMSettings.model_validate({}).model_dump())


class TestLLMSettingsValidation(unittest.TestCase):
    def test_stripped_keys_validate(self):
        s = LLMSettings.model_validate({'model': 'gpt-4o-mini', 'enabled': False})
        self.assertEqual(s.model, 'gpt-4o-mini')
        self.assertFalse(s.enabled)


class TestLLMSettingsTypeCoercion(unittest.TestCase):
    def test_select_field_string_int_coerces_to_int(self):
        # WTForms SelectField returns the choice key as a string ('500');
        # Pydantic coerces to int so storage stays typed.
        s = LLMSettings.model_validate({'thinking_budget': '500', 'max_summary_tokens': '5000'})
        self.assertEqual(s.thinking_budget, 500)
        self.assertEqual(s.max_summary_tokens, 5000)

    def test_invalid_int_raises(self):
        with self.assertRaises(ValidationError):
            LLMSettings.model_validate({'thinking_budget': 'not_a_number'})


class TestLLMSettingsExtraForbid(unittest.TestCase):
    def test_unknown_key_raises(self):
        # extra='forbid' is the security gate against CWE-915 mass-assignment.
        with self.assertRaises(ValidationError) as ctx:
            LLMSettings.model_validate({'model': 'gpt-4o-mini', 'evil_field': 'pwn'})
        self.assertIn('evil_field', str(ctx.exception))

    def test_dunder_key_raises(self):
        with self.assertRaises(ValidationError):
            LLMSettings.model_validate({'model': 'gpt-4o-mini', '__class__': 'attack'})

    def test_legitimate_unknown_key_also_raises(self):
        # No "future-tolerant" silent acceptance — new fields must be declared.
        with self.assertRaises(ValidationError):
            LLMSettings.model_validate({'maybe_future_counter': 42})

    def test_legacy_prefixed_key_raises(self):
        # Pre-update_31 storage used flat application.llm_* keys (handled by the
        # migration). After migration the prefix is gone — and any code path that
        # still tries to write a prefixed key into the LLM dict must be rejected
        # so the prefix can never reappear through any side channel.
        with self.assertRaises(ValidationError):
            LLMSettings.model_validate({'llm_model': 'gpt-4o-mini'})


class TestLLMSettingsDumpShapes(unittest.TestCase):
    def test_dump_uses_field_names(self):
        s = LLMSettings.model_validate({'model': 'gpt-4o-mini'})
        out = s.model_dump()
        self.assertEqual(out['model'], 'gpt-4o-mini')
        self.assertNotIn('llm_model', out)

    def test_dump_exclude_connection_drops_provider_fields(self):
        s = LLMSettings.model_validate({
            'model': 'gpt-4o-mini', 'api_key': 'sk-test', 'api_base': 'https://example',
            'provider_kind': 'ollama', 'local_token_multiplier': 5,
            'enabled': False, 'tokens_this_month': 42,
        })
        out = s.model_dump(exclude=set(LLMSettings.CONNECTION_FIELDS))
        for k in LLMSettings.CONNECTION_FIELDS:
            self.assertNotIn(k, out, f"connection field {k} should be excluded")
        # Non-connection fields survive
        self.assertFalse(out['enabled'])
        self.assertEqual(out['tokens_this_month'], 42)


