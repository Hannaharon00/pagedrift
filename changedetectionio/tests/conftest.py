#!/usr/bin/env python3
import psutil
import time
from threading import Thread
import multiprocessing

import pytest
import arrow
from changedetectionio import store
import os
import sys

# CRITICAL: Set short timeout for tests to prevent 45-second hangs
# When test server is slow/unresponsive, workers fail fast instead of holding UUIDs for 45s
# This prevents exponential priority growth from repeated deferrals (priority × 10 each defer)
os.environ['DEFAULT_SETTINGS_REQUESTS_TIMEOUT'] = '5'
# Test server runs on localhost (127.0.0.1) which is a private IP.
# Allow it globally so all existing tests keep working; test_ssrf_protection
# uses monkeypatch to temporarily override this for its own assertions.
os.environ['ALLOW_IANA_RESTRICTED_ADDRESSES'] = 'true'

from changedetectionio.flask_app import init_app_secret, changedetection_app
from changedetectionio.tests.util import live_server_setup, new_live_server_setup

# https://github.com/pallets/flask/blob/1.1.2/examples/tutorial/tests/test_auth.py
# Much better boilerplate than the docs
# https://www.python-boilerplate.com/py3+flask+pytest/

global app

