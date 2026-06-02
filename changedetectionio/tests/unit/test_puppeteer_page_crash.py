"""A renderer crash must stay local to the tab that crashed.

pyppeteer emits Page 'error' (``PageError('Page crashed!')``) when the renderer dies, and pyee
re-raises an 'error' emission that has no listener. That raise escapes into
``Connection._onMessage``, whose catch-all disposes the whole connection - so one dead tab takes
the browser with it and every later call reports the misleading "Session closed. Most likely the
page has been closed." ``fetch_page()`` attaches a listener to keep the failure local.
"""

import asyncio
import sys
from types import ModuleType, SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from loguru import logger
from pyee.asyncio import AsyncIOEventEmitter


class FakePage(AsyncIOEventEmitter):
    """Stands in for pyppeteer's Page, which is itself an AsyncIOEventEmitter."""

    def __init__(self):
        super().__init__()
        self.evaluate = AsyncMock(return_value='Mozilla/5.0')
        self.setUserAgent = AsyncMock()


def _fetch_page_until_csp(monkeypatch, page):
    """Drive fetch_page() up to the CSP step, then bail out and hand back the fetcher.

    The listener is attached straight after page creation, so aborting at the later CSP call
    is enough to get a fetcher wired to ``page``.
    """
    from changedetectionio.content_fetchers import puppeteer

    class StopAfterPageSetup(Exception):
        pass

    browser = SimpleNamespace(newPage=AsyncMock(return_value=page))
    pyppeteer_instance = SimpleNamespace(connect=AsyncMock(return_value=browser))

    pyppeteer_module = ModuleType('pyppeteer')
    pyppeteer_module.Pyppeteer = Mock(return_value=pyppeteer_instance)
    stealth_module = ModuleType('pyppeteerstealth')
    stealth_module.inject_evasions_into_page = AsyncMock()
    monkeypatch.setitem(sys.modules, 'pyppeteer', pyppeteer_module)
    monkeypatch.setitem(sys.modules, 'pyppeteerstealth', stealth_module)

    monkeypatch.setattr(
        puppeteer, '_configure_puppeteer_csp', AsyncMock(side_effect=StopAfterPageSetup)
    )

    f = puppeteer.fetcher()
    with pytest.raises(StopAfterPageSetup):
        asyncio.run(
            f.fetch_page(
                current_include_filters=None,
                empty_pages_are_a_change=False,
                fetch_favicon=False,
                ignore_status_codes=False,
                is_binary=False,
                request_body=None,
                request_headers={},
                request_method='GET',
                screenshot_format=None,
                timeout=45,
                url='https://example.com',
                watch_uuid='test-watch',
            )
        )
    return f


def test_page_crash_is_recorded_and_does_not_propagate(monkeypatch):
    page = FakePage()
    f = _fetch_page_until_csp(monkeypatch, page)

    assert f.page_errors == []

    crash = RuntimeError('Page crashed!')
    # No raise here is the whole point - an escaping raise is what disposed the connection
    page.emit('error', crash)

    assert f.page_errors == [crash]


