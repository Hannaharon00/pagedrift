"""
Diff rendering module for change detection.

This module provides functions for rendering differences between text content,
with support for various output formats and tokenization strategies.
"""

import difflib
from typing import List, Iterator, Union
from loguru import logger
import diff_match_patch as dmp_module
import re
import time

from .tokenizers import TOKENIZERS, tokenize_words_and_html

# Placemarker constants - these get replaced by apply_service_tweaks() in handler.py
# Something that cant get escaped to HTML by accident
REMOVED_PLACEMARKER_OPEN = '@removed_PLACEMARKER_OPEN'
REMOVED_PLACEMARKER_CLOSED = '@removed_PLACEMARKER_CLOSED'

ADDED_PLACEMARKER_OPEN = '@added_PLACEMARKER_OPEN'
ADDED_PLACEMARKER_CLOSED = '@added_PLACEMARKER_CLOSED'

CHANGED_PLACEMARKER_OPEN = '@changed_PLACEMARKER_OPEN'
CHANGED_PLACEMARKER_CLOSED = '@changed_PLACEMARKER_CLOSED'

# Regexes built from the constants above — no brittle hardcoded strings
_EXTRACT_REMOVED_RE = re.compile(
    re.escape(REMOVED_PLACEMARKER_OPEN) + r'(.*?)' + re.escape(REMOVED_PLACEMARKER_CLOSED)
    + r'|' +
    re.escape(CHANGED_PLACEMARKER_OPEN) + r'(.*?)' + re.escape(CHANGED_PLACEMARKER_CLOSED)
)
_EXTRACT_ADDED_RE = re.compile(
    re.escape(ADDED_PLACEMARKER_OPEN) + r'(.*?)' + re.escape(ADDED_PLACEMARKER_CLOSED)
    + r'|' +
    re.escape(CHANGED_INTO_PLACEMARKER_OPEN) + r'(.*?)' + re.escape(CHANGED_INTO_PLACEMARKER_CLOSED)
)


def extract_changed_from(raw_diff: str) -> str:
    """Extract only the removed/changed-from fragments from a raw diff string.

    Useful for {{diff_changed_from}} — gives just the old value (e.g. old price),
    not the full surrounding line. Multiple fragments joined with newlines.
    """
    return '\n'.join(next((g for g in m.groups() if g is not None), '') for m in _EXTRACT_REMOVED_RE.finditer(raw_diff))


def extract_changed_to(raw_diff: str) -> str:
    """Extract only the added/changed-into fragments from a raw diff string.

    Useful for {{diff_changed_to}} — gives just the new value (e.g. new price),
    not the full surrounding line. Multiple fragments joined with newlines.
    """
    return '\n'.join(next((g for g in m.groups() if g is not None), '') for m in _EXTRACT_ADDED_RE.finditer(raw_diff))


