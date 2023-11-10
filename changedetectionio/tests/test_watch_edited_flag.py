#!/usr/bin/env python3
"""
Test the watch edited flag functionality.

This tests the private __watch_was_edited flag that tracks when writable
watch fields are modified, which prevents skipping reprocessing when the
watch configuration has changed.
"""

import os
import time
from flask import url_for
from .util import live_server_setup, wait_for_all_checks


