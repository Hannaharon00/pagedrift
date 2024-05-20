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

# Remember! gmail, outlook etc dont support <style> must be inline.
# Gmail: strips <ins> and <del> tags entirely.
# This is for the WHOLE line background style
REMOVED_STYLE = "background-color: #fadad7; color: #b30000;"
ADDED_STYLE = "background-color: #eaf2c2; color: #406619;"
HTML_REMOVED_STYLE = REMOVED_STYLE  # Export alias for handler.py
HTML_ADDED_STYLE = ADDED_STYLE      # Export alias for handler.py

# Darker backgrounds for nested highlighting (changed parts within lines)
REMOVED_INNER_STYLE = "background-color: #ff867a; color: #111;"
ADDED_INNER_STYLE = "background-color: #b2e841; color: #444;"
HTML_CHANGED_STYLE = REMOVED_STYLE
HTML_CHANGED_INTO_STYLE = ADDED_STYLE

# Placemarker constants - these get replaced by apply_service_tweaks() in handler.py
# Something that cant get escaped to HTML by accident
REMOVED_PLACEMARKER_OPEN = '@removed_PLACEMARKER_OPEN'
REMOVED_PLACEMARKER_CLOSED = '@removed_PLACEMARKER_CLOSED'

ADDED_PLACEMARKER_OPEN = '@added_PLACEMARKER_OPEN'
ADDED_PLACEMARKER_CLOSED = '@added_PLACEMARKER_CLOSED'

CHANGED_PLACEMARKER_OPEN = '@changed_PLACEMARKER_OPEN'
CHANGED_PLACEMARKER_CLOSED = '@changed_PLACEMARKER_CLOSED'

CHANGED_INTO_PLACEMARKER_OPEN = '@changed_into_PLACEMARKER_OPEN'
CHANGED_INTO_PLACEMARKER_CLOSED = '@changed_into_PLACEMARKER_CLOSED'

# Compiled regex patterns for performance
WHITESPACE_NORMALIZE_RE = re.compile(r'\s+')

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


def render_diff(
    previous_version_file_contents: str,
    newest_version_file_contents: str,
    include_equal: bool = False,
    include_removed: bool = True,
    include_added: bool = True,
    include_replaced: bool = True,
    include_change_type_prefix: bool = True,
    patch_format: bool = False,
    word_diff: bool = True,
    context_lines: int = 0,
    case_insensitive: bool = False,
    ignore_junk: bool = False,
    tokenizer: str = 'words_and_html'
) -> str:
    """
    Render the difference between two file contents.

    Args:
        previous_version_file_contents (str): Original file contents
        newest_version_file_contents (str): Modified file contents
        include_equal (bool): Include unchanged parts
        include_removed (bool): Include removed parts
        include_added (bool): Include added parts
        include_replaced (bool): Include replaced parts
        include_change_type_prefix (bool): Add prefixes to indicate change types
        patch_format (bool): Use patch format for output
        word_diff (bool): Use word-level diffing for replaced lines (controls inline rendering)
        context_lines (int): Number of unchanged lines to show around changes (like grep -C)
        case_insensitive (bool): Perform case-insensitive comparison, By default the test_json_diff/process.py is case sensitive, so this follows same logic
        ignore_junk (bool): Ignore whitespace-only changes
        tokenizer (str): Name of tokenizer to use from TOKENIZERS registry (default: 'words_and_html')

    Returns:
        str: Rendered difference
    """
    newest_lines = [line.rstrip() for line in (newest_version_file_contents or '').splitlines()]
    previous_lines = [line.rstrip() for line in (previous_version_file_contents or '').splitlines()]
    now = time.time()
    logger.debug(
        f"diff options: "
        f"include_equal={include_equal}, "
        f"include_removed={include_removed}, "
        f"include_added={include_added}, "
        f"include_replaced={include_replaced}, "
        f"include_change_type_prefix={include_change_type_prefix}, "
        f"patch_format={patch_format}, "
        f"word_diff={word_diff}, "
        f"context_lines={context_lines}, "
        f"case_insensitive={case_insensitive}, "
        f"ignore_junk={ignore_junk}, "
        f"tokenizer={tokenizer}"
    )
    if patch_format:
        patch = difflib.unified_diff(previous_lines, newest_lines)
        return "\n".join(patch)

    rendered_diff = customSequenceMatcher(
        before=previous_lines,
        after=newest_lines,
        include_equal=include_equal,
        include_removed=include_removed,
        include_added=include_added,
        include_replaced=include_replaced,
        include_change_type_prefix=include_change_type_prefix,
        word_diff=word_diff,
        context_lines=context_lines,
        case_insensitive=case_insensitive,
        ignore_junk=ignore_junk,
        tokenizer=tokenizer
    )

    def flatten(lst: List[Union[str, List[str]]]) -> str:
        result = []
        for x in lst:
            if isinstance(x, list):
                result.extend(x)
            else:
                result.append(x)
        return "\n".join(result)

    logger.debug(f"Diff generated in {time.time() - now:.2f}s")

    return flatten(rendered_diff)


# Export main public API
__all__ = [
    'render_diff',
    'customSequenceMatcher',
    'render_inline_word_diff',
    'render_nested_line_diff',
    'TOKENIZERS',
    'REMOVED_STYLE',
    'ADDED_STYLE',
    'REMOVED_INNER_STYLE',
    'ADDED_INNER_STYLE',
]
