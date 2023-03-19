#!/usr/bin/env python3
"""
Reflected XSS regression tests for /diff/<uuid>/download-patch (GHSA-23mp-8222-96fr).

get_history_snapshot() does a plain dict lookup on the history, so an unknown timestamp
raised KeyError whose str() carries the raw from_version/to_version query parameter. The
error path interpolated that into make_response(), which defaults to text/html - so the
parameter was reflected unescaped and executed in the victim's browser.

Two independent guarantees are asserted here, because either alone would have prevented
this bug and both are worth keeping:
  1. Unknown timestamps are rejected up front (404), so the exception never fires.
  2. Whatever the error path returns is text/plain and never echoes the input.

This is the third instance of the same pattern, after CVE-2026-27645 (/rss/watch/) and
CVE-2026-29038 (/rss/tag/).
"""

import os
from flask import url_for
from .util import wait_for_all_checks

