#!/usr/bin/env python3
# coding=utf-8

# run from dir above changedetectionio/ dir
# python3 -m unittest changedetectionio.tests.unit.test_content_type_detection

"""Unit tests for guess_stream_type() content-type classification.

Regression cover for #4302: a normal HTML page served as 'text/html;charset=utf-8' was
classified as plaintext, which made processor.py skip html_to_text() entirely and store the
raw filtered block as the snapshot (visible as literal '<br>' separators in every diff).

Two independent failures had to line up:
  1. The header test was an exact comparison ("text/html"), so any charset parameter missed it.
  2. has_html_patterns only sniffs content[:200], and the page put 241 bytes of HTML comments
     before <!DOCTYPE, so the content sniff could not rescue it either.
Falling through both landed on the `startswith('text/')` catch-all -> is_plaintext.
"""

import unittest

from changedetectionio.processors.magic import guess_stream_type

# Real-world shape from https://www.newbalancemexico.com/c/lo-mas-nuevo (Salesforce/ISML templates):
# blank lines and two long comments push <!DOCTYPE past the 200-byte sniff window.
COMMENT_PREAMBLE_HTML = (
    "\n\n\n\n\n\n"
    "<!-- Include Page Designer Campaign Banner JavaScript and Styles only once here rather than"
    " at component level. -->\n"
    "<!-- There should only be one Campagin Banner added on a PD page. Multiple Banners is"
    " unsupported at the moment. -->\n\n\n"
    '<!DOCTYPE html>\n<html lang="es">\n<head>\n<script>//common/scripts.isml</script>\n</head>\n'
    '<body><div class="product" data-pid="U204LMMA"></div></body></html>'
)

PLAIN_HTML = '<!DOCTYPE html><html><head><title>t</title></head><body><p>hi</p></body></html>'


