from functools import lru_cache, wraps

from loguru import logger
from typing import List
import html
import json
import os
import re
import threading

# ---------------------------------------------------------------------------------------
# libxml2 (lxml) concurrency guard
#
# Watch checks run run_changedetection() on a shared ThreadPoolExecutor
# (worker_pool.queue_executor), so extraction for different watches parses HTML in parallel
# threads. A single check uses TWO different lxml parsers: xpath_filter() builds its own
# etree.HTMLParser(), while html_to_text() -> inscriptis parses with lxml's process-global
# html_parser. lxml locks per parser OBJECT, so many threads on the SAME parser serialise
# safely - but that lock does not span two DIFFERENT parsers, and they still share libxml2's
# interned-string dictionary. Concurrent parses corrupt it, and the rendered text of one
# watch's page ends up inside another watch's snapshot.
#
# lxml's FAQ sanctions exactly two patterns: "the default parser (which is replicated for
# each thread) or create a parser for each thread yourself". A parser per CALL is neither -
# but note that a parser per THREAD does not fix this either (measured: still leaks), because
# inscriptis picks its own parser internally and we cannot redirect it. Serialising is the
# only configuration measured clean.
#
# Serialising is measured to be free: extraction is ~80ms mean / 204ms p95 over real data,
# a ceiling of ~12 checks/sec against the ~0.5 checks/sec that browser fetches can feed.
# It also HALVES peak RSS on large pages (481MB -> 232MB on a 3.85MB page across 7 threads),
# because only one libxml2 document is ever live.
#
# EVERY lxml entry point in this process must go through here - a single unguarded parse in
# any thread (Flask request, worker) is enough to reintroduce the corruption.
#
# This is a threading lock, not an asyncio one, and that is deliberate: nothing here is called
# from a coroutine. The async workers hand run_changedetection() to a ThreadPoolExecutor
# (worker.py: "Run change detection in executor to avoid blocking event loop"), the requests
# fetcher does the same, and Flask is synchronous. If you ever call a guarded function directly
# from a coroutine you will stall that worker's event loop for the duration of someone else's
# parse - bounded and deadlock-free (the holder is pure CPU and never awaits), but avoid it.
#
# Re-entrant: these helpers call into each other (element_removal -> subtractive_xpath_selector).
#
# LXML_LOCK_DISABLED=true removes the guard. It exists so the corruption can be reproduced on
# demand (see tests/test_lxml_concurrency.py) - it is NOT a tuning option, it reinstates a
# data-integrity bug that silently writes one watch's page text into another watch's snapshot.
def _build_lxml_lock():
    from changedetectionio.strtobool import strtobool

    if not strtobool(os.getenv('LXML_LOCK_DISABLED', 'false')):
        return threading.RLock()

    logger.warning("LXML_LOCK_DISABLED=true - lxml parsing is unguarded. Under concurrency this "
                   "is known to leak one watch's rendered page text into another watch's "
                   "snapshot. For testing only, never run this in production.")

    class _NullLock:
        def __enter__(self): return self
        def __exit__(self, *a): return False

    return _NullLock()


_LXML_LOCK = _build_lxml_lock()


def lxml_guarded(fn):
    """Serialise a function's libxml2 work - parse, xpath traversal, tostring() and clear()
    all touch the document, so the whole call is held, not just the parse."""
    @wraps(fn)
    def wrapper(*args, **kwargs):
        with _LXML_LOCK:
            return fn(*args, **kwargs)
    return wrapper


def lxml_guard():
    """Context manager for code OUTSIDE this module that drives lxml directly, so it shares the
    same lock (e.g. XPath validation in forms.py, which runs on Flask request threads)."""
    return _LXML_LOCK


def lxml_html_parser():
    """A fresh parser for each call, freed immediately afterwards. Never lxml's process-global
    default parser, which is shared across every thread."""
    from lxml import etree
    return etree.HTMLParser()

# ---------------------------------------------------------------------------------------

# HTML added to be sure each result matching a filter (.example) gets converted to a new line by Inscriptis
TEXT_FILTER_LIST_LINE_SUFFIX = "<br>"
TRANSLATE_WHITESPACE_TABLE = str.maketrans('', '', '\r\n\t ')
PERL_STYLE_REGEX = r'^/(.*?)/([a-z]*)?$'

TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.I | re.S)
META_CS  = re.compile(r'<meta[^>]+charset=["\']?\s*([a-z0-9_\-:+.]+)', re.I)

