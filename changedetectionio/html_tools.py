from functools import lru_cache, wraps

from loguru import logger
from typing import List
import html
import json
import os
import re
import threading

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

