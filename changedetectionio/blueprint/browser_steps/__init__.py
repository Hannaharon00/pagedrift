
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

