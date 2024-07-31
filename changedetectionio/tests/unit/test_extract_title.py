#!/usr/bin/env python3
# coding=utf-8

"""Unit tests for html_tools.extract_title — including regression for #4217.

Issue #4217: extract_title silently returns None for pages where <title> is
pushed past the hard-coded 8 192-character scan window by large <head> content
(e.g. Amazon product pages where <title> can sit at character index 55 000+).
"""

import unittest

from changedetectionio.html_tools import extract_title


def _make_large_head_page(title: str, filler_count: int = 500) -> bytes:
    """Build a synthetic HTML page whose <title> is pushed far past 8 192 chars.

    Each filler line is ~126 bytes; 500 lines ≈ 63 000 bytes before <title>.
    """
    filler_line = '<meta name="x" content="' + "A" * 100 + '"/>\n'
    head_junk = filler_line * filler_count
    page = (
        f"<html><head>{head_junk}"
        f"<title>{title}</title>"
        f"</head><body></body></html>"
    )
    return page.encode("utf-8")


