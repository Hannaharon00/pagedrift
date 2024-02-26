"""
Tests for the LLM restock fallback plugin.

All LLM calls are mocked — no real API key required.
"""
import json
import pytest
from unittest.mock import patch, MagicMock


@pytest.fixture(autouse=True)
def _clear_llm_result_cache():
    """The plugin keeps a module-level result cache (keyed by model+prompt) so it won't
    re-bill the LLM when the meaningful page content is unchanged. That cache persists
    across tests in the same process, which makes token-accounting assertions order
    dependent (a cache hit returns zeroed tokens). Clear it before every test so each
    one exercises a fresh extraction."""
    from changedetectionio.processors.restock_diff.plugins import llm_restock
    llm_restock._LLM_RESULT_CACHE.clear()
    yield
    llm_restock._LLM_RESULT_CACHE.clear()


def _make_datastore(llm_model='gpt-4o-mini', enabled=True):
    """Minimal datastore mock with the fields the plugin reads."""
    ds = MagicMock()
    ds.data = {
        'settings': {
            'application': {
                'llm': {
                    'enabled': True,
                    'restock_use_fallback_extract': enabled,
                    'model': llm_model,
                    'api_key': 'test-key',
                    'api_base': '',
                    'tokens_total_cumulative': 0,
                    'tokens_this_month': 0,
                    'tokens_month_key': '2099-01',
                    'cost_usd_total_cumulative': 0.0,
                    'cost_usd_this_month': 0.0,
                },
            }
        }
    }
    return ds


def _call_plugin(content, url='https://example.com/product',
                 llm_json=None, datastore=None, enabled=True, llm_intent=None):
    """Helper: import plugin, inject datastore, call the hook, return result."""
    from changedetectionio.processors.restock_diff.plugins import llm_restock

    if datastore is None:
        datastore = _make_datastore(enabled=enabled)
    llm_restock.datastore = datastore

    if llm_json is not None:
        with patch('changedetectionio.llm.client.completion',
                   return_value=(llm_json, 50, 40, 10)):
            return llm_restock.get_itemprop_availability_override(
                content=content,
                fetcher_name='html_requests',
                fetcher_instance=None,
                url=url,
                llm_intent=llm_intent,
            )
    else:
        return llm_restock.get_itemprop_availability_override(
            content=content,
            fetcher_name='html_requests',
            fetcher_instance=None,
            url=url,
            llm_intent=llm_intent,
        )


class TestLLMRestockPluginDisabled:
    def test_returns_none_when_no_datastore(self):
        from changedetectionio.processors.restock_diff.plugins import llm_restock
        llm_restock.datastore = None
        result = llm_restock.get_itemprop_availability_override(
            content='<html><body>Price: $49.99 In Stock</body></html>',
            fetcher_name='html_requests',
            fetcher_instance=None,
            url='https://example.com/product',
        )
        assert result is None

    def test_returns_none_when_setting_disabled(self):
        result = _call_plugin(
            '<html><body>Price: $49.99 In Stock</body></html>',
            enabled=False,
        )
        assert result is None

    def test_returns_none_when_no_llm_configured(self):
        ds = MagicMock()
        ds.data = {
            'settings': {
                'application': {
                    # No 'llm' key → get_llm_config returns None;
                    # restock_use_fallback_extract still defaults to True via LLMSettings
                }
            }
        }
        result = _call_plugin(
            '<html><body>Price: $49.99 In Stock</body></html>',
            datastore=ds,
        )
        assert result is None

    def test_returns_none_for_empty_content(self):
        result = _call_plugin('', llm_json='{"price": 9.99, "currency": "USD", "availability": "instock"}')
        assert result is None


