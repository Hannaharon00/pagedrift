#!/usr/bin/env python3

"""
Tests for thread_supervisor.supervise().

Context: the ticker thread had `return False` buried inside its per-watch loop.
One watch with an unresolvable timezone made the whole loop return, the thread
ended, and no watch was ever checked again - with the process still up and
looking healthy. threading.Thread cannot be restarted (start() twice raises
RuntimeError), so recovery has to live inside the thread.

The two behaviours that matter:
  - a target that returns or raises is restarted, loudly
  - a target that exits during shutdown is NOT restarted

Run:  python3 -m unittest changedetectionio.tests.unit.test_thread_supervisor
"""

import threading
import time
import unittest

