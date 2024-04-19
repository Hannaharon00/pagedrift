#!/usr/bin/env python3
"""
Unit tests for the LLM restock fallback's prompt-content building (no LLM call needed):

  * _extract_jsonld() keeps only JSON-LD blocks carrying price/stock info, dropping noise
    (breadcrumbs, site metadata) that otherwise crowds out the useful data.
  * _strip_html() sends the page's visible text IN ADDITION to that structured metadata —
    the real/visible price is often not in JSON-LD (placeholder "0").
  * the result cache evicts oldest-first and stays bounded.

Run from the tests/ directory:
    python -m unittest unit/test_llm_restock_content.py
"""
import unittest

from changedetectionio.processors.restock_diff.plugins import llm_restock as m


PRODUCT_LD = '{"@type":"Product","offers":{"price":"319.01","priceCurrency":"CZK","availability":"http://schema.org/InStock"}}'
BREADCRUMB_LD = '{"@type":"BreadcrumbList","itemListElement":[{"name":"a"},{"name":"b"}]}'

