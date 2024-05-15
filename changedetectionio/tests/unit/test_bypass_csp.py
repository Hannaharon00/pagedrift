import asyncio
import sys
from types import ModuleType, SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from changedetectionio.browser_steps.browser_steps import browsersteps_live_ui
from changedetectionio.content_fetchers.base import get_playwright_bypass_csp


def test_playwright_bypass_csp_defaults_to_enabled(monkeypatch):
    monkeypatch.delenv('PLAYWRIGHT_BYPASS_CSP', raising=False)

    assert get_playwright_bypass_csp() is True


@pytest.mark.parametrize(
    ('configured_value', 'expected'),
    [
        ('true', True),
        ('1', True),
        ('yes', True),
        ('false', False),
        ('0', False),
        ('no', False),
    ],
)
def test_playwright_bypass_csp_parses_boolean_environment_values(
    monkeypatch, configured_value, expected
):
    monkeypatch.setenv('PLAYWRIGHT_BYPASS_CSP', configured_value)

    assert get_playwright_bypass_csp() is expected


@pytest.mark.parametrize('configured_value', ('true', 'false'))
def test_playwright_fetcher_passes_bypass_csp_to_browser_context(monkeypatch, configured_value):
    monkeypatch.setenv('PLAYWRIGHT_BYPASS_CSP', configured_value)

    class ContextCreationStopped(Exception):
        pass

    browser = SimpleNamespace(
        new_context=AsyncMock(side_effect=ContextCreationStopped),
    )
    browser_type = SimpleNamespace(
        connect_over_cdp=AsyncMock(return_value=browser),
    )

    class AsyncPlaywrightContextManager:
        async def __aenter__(self):
            return SimpleNamespace(chromium=browser_type)

        async def __aexit__(self, exc_type, exc_value, traceback):
            return False

    async_api_module = ModuleType('playwright.async_api')
    async_api_module.async_playwright = AsyncPlaywrightContextManager

    errors_module = ModuleType('playwright._impl._errors')
    errors_module.TimeoutError = TimeoutError
    impl_module = ModuleType('playwright._impl')
    impl_module._errors = errors_module
    playwright_module = ModuleType('playwright')
    playwright_module._impl = impl_module

    monkeypatch.setitem(sys.modules, 'playwright', playwright_module)
    monkeypatch.setitem(sys.modules, 'playwright.async_api', async_api_module)
    monkeypatch.setitem(sys.modules, 'playwright._impl', impl_module)
    monkeypatch.setitem(sys.modules, 'playwright._impl._errors', errors_module)

    from changedetectionio.content_fetchers.playwright import fetcher

    with pytest.raises(ContextCreationStopped):
        asyncio.run(fetcher().run(request_headers={}, url='https://example.com'))

    assert browser.new_context.await_args.kwargs['bypass_csp'] is (configured_value == 'true')


@pytest.mark.parametrize('configured_value', ('true', 'false'))
def test_browser_steps_passes_bypass_csp_to_browser_context(monkeypatch, configured_value):
    monkeypatch.setenv('PLAYWRIGHT_BYPASS_CSP', configured_value)

    page = Mock()
    page.wait_for_timeout = AsyncMock()
    context = SimpleNamespace(new_page=AsyncMock(return_value=page))
    browser = SimpleNamespace(new_context=AsyncMock(return_value=context))
    browser_steps = browsersteps_live_ui(
        playwright_browser=browser, start_url='https://example.com'
    )

    asyncio.run(browser_steps.connect())

    assert browser.new_context.await_args.kwargs['bypass_csp'] is (configured_value == 'true')


