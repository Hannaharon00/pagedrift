
# HORRIBLE HACK BUT WORKS :-) PR anyone?
#
# Why?
# `browsersteps_playwright_browser_interface.chromium.connect_over_cdp()` will only run once without async()
# - this flask app is not async()
# - A single timeout/keepalive which applies to the session made at .connect_over_cdp()
#
# So it means that we must unfortunately for now just keep a single timer since .connect_over_cdp() was run
# and know when that reaches timeout/keepalive :( when that time is up, restart the connection and tell the user
# that their time is up, insert another coin. (reload)
#
#

from changedetectionio.strtobool import strtobool
from flask import Blueprint, request, make_response
import os

from changedetectionio.store import ChangeDetectionStore
from changedetectionio.blueprint import plaintext_response
from changedetectionio.flask_app import login_optionally_required
from changedetectionio.validate_url import validate_fetch_url_async
from loguru import logger

browsersteps_sessions = {}
browsersteps_watch_to_session = {}  # Maps watch_uuid -> browsersteps_session_id
io_interface_context = None
import json
import hashlib
from flask import Response
import asyncio
import threading
import time

# Dedicated event loop for ALL browser steps sessions
_browser_steps_loop = None
_browser_steps_thread = None
_browser_steps_loop_lock = threading.Lock()

def _start_browser_steps_loop():
    """Start a dedicated event loop for browser steps in its own thread"""
    global _browser_steps_loop

    # Create and set the event loop for this thread
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    _browser_steps_loop = loop

    logger.debug("Browser steps event loop started")

    try:
        # Run the loop forever - handles all browsersteps sessions
        loop.run_forever()
    except Exception as e:
        logger.error(f"Browser steps event loop error: {e}")
    finally:
        try:
            # Cancel all remaining tasks
            pending = asyncio.all_tasks(loop)
            for task in pending:
                task.cancel()

            # Wait for tasks to finish cancellation
            if pending:
                loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
        except Exception as e:
            logger.debug(f"Error during browser steps loop cleanup: {e}")
        finally:
            loop.close()
            logger.debug("Browser steps event loop closed")

def _ensure_browser_steps_loop():
    """Ensure the browser steps event loop is running"""
    global _browser_steps_loop, _browser_steps_thread

    with _browser_steps_loop_lock:
        if _browser_steps_thread is None or not _browser_steps_thread.is_alive():
            logger.debug("Starting browser steps event loop thread")
            _browser_steps_thread = threading.Thread(
                target=_start_browser_steps_loop,
                daemon=True,
                name="BrowserStepsEventLoop"
            )
            _browser_steps_thread.start()

            # Wait for the loop to be ready
            timeout = 5.0
            start_time = time.time()
            while _browser_steps_loop is None:
                if time.time() - start_time > timeout:
                    raise RuntimeError("Browser steps event loop failed to start")
                time.sleep(0.01)

            logger.debug("Browser steps event loop thread started and ready")

def run_async_in_browser_loop(coro):
    """Run async coroutine using the dedicated browser steps event loop"""
    _ensure_browser_steps_loop()

    if _browser_steps_loop and not _browser_steps_loop.is_closed():
        logger.debug("Browser steps using dedicated event loop")
        future = asyncio.run_coroutine_threadsafe(coro, _browser_steps_loop)
        return future.result()
    else:
        raise RuntimeError("Browser steps event loop is not available")

async def _close_session_resources(session_data, label=''):
    """Close all browser resources for a session in the correct order.

    browserstepper.cleanup() closes page+context but not the browser itself.
    For CloakBrowser, browser.close() is what stops the local Chromium process via pw.stop().
    For the default CDP path, playwright_context.stop() shuts down the playwright instance.
    """
    browserstepper = session_data.get('browserstepper')
    if browserstepper:
        try:
            await browserstepper.cleanup()
        except Exception as e:
            logger.error(f"Error cleaning up browserstepper{label}: {e}")

    browser = session_data.get('browser')
    if browser:
        try:
            await asyncio.wait_for(browser.close(), timeout=5.0)
        except Exception as e:
            logger.warning(f"Error closing browser{label}: {e}")

    playwright_context = session_data.get('playwright_context')
    if playwright_context:
        try:
            await playwright_context.stop()
        except Exception as e:
            logger.warning(f"Error stopping playwright context{label}: {e}")


async def acquire_browser_for_fetcher(fetcher_name, proxy=None, keepalive_ms=None):
    """Acquire a Playwright browser for the given fetcher backend.

    Mirrors normal fetching: fetchers that launch their own browser (e.g. CloakBrowser)
    provide get_browsersteps_browser(); otherwise we connect over CDP to the configured
    Playwright/sockpuppetbrowser driver. Returns (browser, playwright_context).
    """
    from changedetectionio import content_fetchers
    from playwright.async_api import async_playwright

    logger.debug(f"acquire_browser_for_fetcher: requested fetcher='{fetcher_name}', proxy={'yes' if proxy else 'no'}, keepalive_ms={keepalive_ms}")

    browser = None
    playwright_context = None

    # If the fetcher has its own browser launch (runs locally rather than via CDP), use it.
    fetcher_class = getattr(content_fetchers, fetcher_name, None) if fetcher_name else None
    if fetcher_class and hasattr(fetcher_class, 'get_browsersteps_browser'):
        logger.debug(f"acquire_browser_for_fetcher: fetcher '{fetcher_name}' provides its own browser, launching locally")
        result = await fetcher_class.get_browsersteps_browser(proxy=proxy, keepalive_ms=keepalive_ms)
        if result is not None:
            browser, playwright_context = result
            logger.info(f"acquire_browser_for_fetcher: using fetcher-specific browser for '{fetcher_name}'")
        else:
            logger.debug(f"acquire_browser_for_fetcher: '{fetcher_name}' returned no browser, falling back to CDP")
    else:
        logger.debug(f"acquire_browser_for_fetcher: fetcher '{fetcher_name}' has no get_browsersteps_browser(), using CDP")

    # Default: connect to the remote Playwright/sockpuppetbrowser via CDP
    if browser is None:
        base_url = os.getenv('PLAYWRIGHT_DRIVER_URL', '').strip('"')
        logger.debug(f"acquire_browser_for_fetcher: connecting over CDP to '{base_url}' for fetcher '{fetcher_name}'")
        playwright_context = await async_playwright().start()
        a = "?" if '?' not in base_url else '&'
        connect_url = base_url + a + f"timeout={keepalive_ms}"
        browser = await playwright_context.chromium.connect_over_cdp(connect_url, timeout=keepalive_ms)
        logger.info(f"acquire_browser_for_fetcher: connected over CDP for fetcher '{fetcher_name}'")

    return browser, playwright_context


