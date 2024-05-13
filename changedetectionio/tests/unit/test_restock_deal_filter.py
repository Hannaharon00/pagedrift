#!/usr/bin/env python3
"""
Regression: the watch-list "deal" filter must not crash when a watch's `restock` field is a
plain dict rather than a Restock object.

The built-in extruct path stores a Restock, but plugin fallbacks (notably the LLM restock
scraper) store a plain dict. watch_is_deal() then called dict.get_price_change_percent() ->
AttributeError -> 500 on the whole watch-list page.

Run from the tests/ directory:
    python -m unittest unit/test_restock_deal_filter.py
"""
import shutil
import tempfile
import time
import unittest

