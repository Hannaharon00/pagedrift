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


def manage_user_agent(headers, current_ua=''):
    """
    Basic setting of user-agent

    NOTE!!!!!! The service that does the actual Chrome fetching should handle any anti-robot techniques
    THERE ARE MANY WAYS THAT IT CAN BE DETECTED AS A ROBOT!!
    This does not take care of
    - Scraping of 'navigator' (platform, productSub, vendor, oscpu etc etc) browser object (navigator.appVersion) etc
    - TCP/IP fingerprint JA3 etc
    - Graphic rendering fingerprinting
    - Your IP being obviously in a pool of bad actors
    - Too many requests
    - Scraping of SCH-UA browser replies (thanks google!!)
    - Scraping of ServiceWorker, new window calls etc

    See https://filipvitas.medium.com/how-to-set-user-agent-header-with-puppeteer-js-and-not-fail-28c7a02165da
    Puppeteer requests https://github.com/dgtlmoon/pyppeteerstealth

    :param page:
    :param headers:
    :return:
    """
    # Ask it what the user agent is, if its obviously ChromeHeadless, switch it to the default
    ua_in_custom_headers = headers.get('User-Agent')
    if ua_in_custom_headers:
        return ua_in_custom_headers

    if not ua_in_custom_headers and current_ua:
        current_ua = current_ua.replace('HeadlessChrome', 'Chrome')
        return current_ua

    return None

