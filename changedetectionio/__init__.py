#!/usr/bin/env python3

# Read more https://github.com/dgtlmoon/changedetection.io/wiki
# Semver means never use .01, or 00. Should be .1.
__version__ = '0.60.4'

from changedetectionio.strtobool import strtobool
from json.decoder import JSONDecodeError

from loguru import logger
import getopt
import logging
import os
import platform
import signal
import threading
import time

# Eventlet completely removed - using threading mode for SocketIO
# This provides better Python 3.12+ compatibility and eliminates eventlet/asyncio conflicts
# Note: store and changedetection_app are imported inside main() to avoid
# initialization before argument parsing (allows --help to work without loading everything)

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

# Limit glibc malloc arena count to prevent RSS growth from concurrent requests.
# Default: glibc creates up to 8×CPU_cores arenas. Each concurrent thread/connection
# can trigger a new arena, and freed memory stays mapped in those arenas as RSS forever.
# With MALLOC_ARENA_MAX=2, at most 2 arenas are used; freed pages return to the OS faster.
# Must be set before worker threads start; env var is read lazily by glibc on first arena creation.
if 'MALLOC_ARENA_MAX' not in os.environ:
    os.environ['MALLOC_ARENA_MAX'] = '2'
    try:
        import ctypes as _ctypes
        _ctypes.CDLL('libc.so.6').mallopt(-8, 2)  # M_ARENA_MAX = -8
    except Exception:
        pass

# Set spawn as global default (safety net - all our code uses explicit contexts anyway)
# Skip in tests to avoid breaking pytest-flask's LiveServer fixture (uses unpicklable local functions)
if 'pytest' not in sys.modules:
    try:
        if multiprocessing.get_start_method(allow_none=True) is None:
            multiprocessing.set_start_method('spawn', force=False)
            logger.debug("Set multiprocessing default to 'spawn' for thread safety (explicit contexts used everywhere)")
    except RuntimeError:
        logger.debug(f"Multiprocessing start method already set: {multiprocessing.get_start_method()}")

# Only global so we can access it in the signal handler
app = None
datastore = None

def get_version():
    return __version__

# Parent wrapper or OS sends us a SIGTERM/SIGINT, do everything required for a clean shutdown
def sigshutdown_handler(_signo, _stack_frame):
    name = signal.Signals(_signo).name
    logger.critical(f'Shutdown: Got Signal - {name} ({_signo}), Fast shutdown initiated')

    # Set exit flag immediately to stop all loops
    app.config.exit.set()
    datastore.stop_thread = True

    # Log memory consumption before shutting down workers (cross-platform)
    try:
        import psutil
        process = psutil.Process()
        mem_info = process.memory_info()
        rss_mb = mem_info.rss / 1024 / 1024
        vms_mb = mem_info.vms / 1024 / 1024
        logger.info(f"Memory consumption before worker shutdown: RSS={rss_mb:,.2f} MB, VMS={vms_mb:,.2f} MB")
    except Exception as e:
        logger.warning(f"Could not retrieve memory stats: {str(e)}")

    # Shutdown workers and queues immediately
    try:
        from changedetectionio import worker_pool
        worker_pool.shutdown_workers()
    except Exception as e:
        logger.error(f"Error shutting down workers: {str(e)}")
    
    # Close janus queues properly
    try:
        from changedetectionio.flask_app import update_q, notification_q
        update_q.close()
        notification_q.close()
        logger.debug("Queues closed successfully")
    except Exception as e:
        logger.critical(f"CRITICAL: Failed to close queues: {e}")
    
    # Shutdown socketio server fast
    from changedetectionio.flask_app import socketio_server
    if socketio_server and hasattr(socketio_server, 'shutdown'):
        try:
            socketio_server.shutdown()
        except Exception as e:
            logger.error(f"Error shutting down Socket.IO server: {str(e)}")
    
    # With immediate persistence, all data is already saved
    logger.success('All data already persisted (immediate commits enabled).')

    sys.exit()

