#!/usr/bin/env python3

# Read more https://github.com/dgtlmoon/changedetection.io/wiki
# Semver means never use .01, or 00. Should be .1.
__version__ = '0.60.4'

from changedetectionio.strtobool import strtobool
from json.decoder import JSONDecodeError

# ==============================================================================
# Multiprocessing Configuration - CRITICAL for Thread Safety
# ==============================================================================
#
# PROBLEM: Python 3.12+ warns about fork() with multi-threaded processes:
#   "This process is multi-threaded, use of fork() may lead to deadlocks"
#
# WHY IT'S DANGEROUS:
#   1. This Flask app has multiple threads (HTTP handlers, workers, SocketIO)
#   2. fork() copies ONLY the calling thread to the child process
#   3. BUT fork() also copies all locks/mutexes in their current state
#   4. If another thread held a lock during fork() → child has locked lock with no owner
#   5. Result: PERMANENT DEADLOCK if child tries to acquire that lock
#
# SOLUTION: Use 'spawn' instead of 'fork'
#   - spawn starts a fresh Python interpreter (no inherited threads or locks)
#   - Slower (~200ms vs ~1ms) but safe with multi-threaded parent
#   - Consistent across all platforms (Windows already uses spawn by default)
#
# IMPLEMENTATION:
#   1. Explicit contexts everywhere (primary protection):
#      - playwright.py: ctx = multiprocessing.get_context('spawn')
#      - puppeteer.py: ctx = multiprocessing.get_context('spawn')
#      - isolated_opencv.py: ctx = multiprocessing.get_context('spawn')
#      - isolated_libvips.py: ctx = multiprocessing.get_context('spawn')
#
#   2. Global default (defense-in-depth, below):
#      - Safety net if future code forgets explicit context
#      - Protects against third-party libraries using Process()
#      - Costs nothing (explicit contexts always override it)
#
# WHY BOTH?
#   - Explicit contexts: Clear, self-documenting, always works
#   - Global default: Safety net for forgotten contexts or library code
#   - If someone writes "Process()" instead of "ctx.Process()", still safe!
#
# See: https://docs.python.org/3/library/multiprocessing.html#contexts-and-start-methods
# ==============================================================================

import multiprocessing
import os
import sys

