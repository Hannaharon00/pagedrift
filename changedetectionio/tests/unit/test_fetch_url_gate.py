#!/usr/bin/env python3

"""Tests for the shared "may the server fetch this URL?" gate.

# run from dir above changedetectionio/ dir
# python3 -m unittest changedetectionio.tests.unit.test_fetch_url_gate

Every server-side fetch entry point routes through validate_url.is_fetch_url_allowed(). Before it
existed, the file:// and private-IP rules were enforced inline in call_browser() only, so any fetch
path that did not go through call_browser() was unprotected:

  * a "Goto URL" browser step could read file:///etc/passwd     (GHSA-hm22-wg2m-35v4)
  * /add-watch-ui/snapshot url= could fetch internal hosts       (GHSA-56fq-63vj-9992)

These tests pin the gate's rules AND the browser-step choke point, so a future fetch path that
forgets to call the gate is the only way to regress it.
"""

import asyncio
import unittest
from unittest.mock import patch

from changedetectionio.browser_steps.browser_steps import steppable_browser_interface
from changedetectionio.validate_url import (
    is_fetch_url_allowed,
    is_special_purpose_ip,
    validate_fetch_url,
    validate_fetch_url_async,
)

