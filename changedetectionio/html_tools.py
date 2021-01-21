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

META_CT  = re.compile(r'<meta[^>]+http-equiv=["\']?content-type["\']?[^>]*content=["\'][^>]*charset=([a-z0-9_\-:+.]+)', re.I)

# 'price' , 'lowPrice', 'highPrice' are usually under here
# All of those may or may not appear on different websites - I didnt find a way todo case-insensitive searching here
LD_JSON_PRODUCT_OFFER_SELECTORS = ["json:$..offers", "json:$..Offers"]

class JSONNotFound(ValueError):
    def __init__(self, msg):
        ValueError.__init__(self, msg)


@lxml_guarded
def subtractive_xpath_selector(selectors: List[str], html_content: str) -> str:
    from lxml import etree
    # Parse the HTML content using lxml. Own parser, not etree.HTML()'s process-global default.
    html_tree = etree.fromstring(html_content, parser=lxml_html_parser())

    # First, collect all elements to remove
    elements_to_remove = []

    # Iterate over the list of XPath selectors
    for selector in selectors:
        # Collect elements for each selector
        elements_to_remove.extend(html_tree.xpath(selector))

    # If no elements were found, return the original HTML content
    if not elements_to_remove:
        return html_content

    # Then, remove them in a separate loop
    for element in elements_to_remove:
        if element.getparent() is not None:  # Ensure the element has a parent before removing
            element.getparent().remove(element)

    # Convert the modified HTML tree back to a string
    modified_html = etree.tostring(html_tree, method="html").decode("utf-8")
    return modified_html


def element_removal(selectors: List[str], html_content):
    """Removes elements that match a list of CSS or XPath selectors."""
    modified_html = html_content
    css_selectors = []
    xpath_selectors = []

    for selector in selectors:
        if selector.strip().startswith(('xpath:', 'xpath1:', '//')):
            # Handle XPath selectors separately
            xpath_selector = selector.removeprefix('xpath:').removeprefix('xpath1:')
            xpath_selectors.append(xpath_selector)
        else:
            # Collect CSS selectors as one "hit", see comment in subtractive_css_selector
            css_selectors.append(selector.strip().strip(","))

    if xpath_selectors:
        modified_html = subtractive_xpath_selector(xpath_selectors, modified_html)

    if css_selectors:
        # Remove duplicates, then combine all CSS selectors into one string, separated by commas
        # This stops the elements index shifting
        unique_selectors = list(set(css_selectors))  # Ensure uniqueness
        combined_css_selector = " , ".join(unique_selectors)
        modified_html = subtractive_css_selector(combined_css_selector, modified_html)


    return modified_html

def elementpath_tostring(obj):
    """
    change elementpath.select results to string type
    # The MIT License (MIT), Copyright (c), 2018-2021, SISSA (Scuola Internazionale Superiore di Studi Avanzati)
    # https://github.com/sissaschool/elementpath/blob/dfcc2fd3d6011b16e02bf30459a7924f547b47d0/elementpath/xpath_tokens.py#L1038
    """

    import elementpath
    from decimal import Decimal
    import math

    if obj is None:
        return ''
    # https://elementpath.readthedocs.io/en/latest/xpath_api.html#elementpath.select
    elif isinstance(obj, elementpath.XPathNode):
        return obj.string_value
    elif isinstance(obj, bool):
        return 'true' if obj else 'false'
    elif isinstance(obj, Decimal):
        value = format(obj, 'f')
        if '.' in value:
            return value.rstrip('0').rstrip('.')
        return value

    elif isinstance(obj, float):
        if math.isnan(obj):
            return 'NaN'
        elif math.isinf(obj):
            return str(obj).upper()

        value = str(obj)
        if '.' in value:
            value = value.rstrip('0').rstrip('.')
        if '+' in value:
            value = value.replace('+', '')
        if 'e' in value:
            return value.upper()
        return value

    return str(obj)

