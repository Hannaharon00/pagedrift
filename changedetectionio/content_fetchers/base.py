import os
from abc import abstractmethod
from loguru import logger
from pydantic import BaseModel

from changedetectionio.content_fetchers import BrowserStepsStepException
from changedetectionio.strtobool import strtobool


class FetcherCapabilities(BaseModel):
    """Typed view of what a content fetcher can do.

    Single source of truth for the fetcher capability flags. The flags live as
    class attributes on each fetcher (supports_browser_steps etc); build a
    validated instance from a fetcher class with FetcherCapabilities.from_fetcher(),
    and call .model_dump() where a plain dict is expected (templates, plugin API).
    """
    supports_browser_steps: bool = False       # Can execute browser automation steps
    supports_screenshots: bool = False         # Can capture page screenshots
    supports_xpath_element_data: bool = False  # Can extract xpath element positions for visual selector

    @classmethod
    def from_fetcher(cls, fetcher_class):
        """Build capabilities from a fetcher class (or None -> all False)."""
        return cls(**{
            name: getattr(fetcher_class, name, False)
            for name in cls.model_fields
        })


def get_playwright_bypass_csp():
    """Return whether Playwright-compatible browser contexts should bypass CSP.

    Bypassing CSP remains enabled by default for backward compatibility. Some
    remote CDP implementations do not support ``Page.setBypassCSP``; operators
    can disable the option by setting ``PLAYWRIGHT_BYPASS_CSP=false``.
    """
    return strtobool(os.getenv('PLAYWRIGHT_BYPASS_CSP', 'true'))


