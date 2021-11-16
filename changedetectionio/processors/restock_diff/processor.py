from ..base import difference_detection_processor
from ..exceptions import ProcessorException
from . import Restock
from loguru import logger
from changedetectionio.content_fetchers.exceptions import checksumFromPreviousCheckWasTheSame

import urllib3
import time

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
# Translatable strings - extracted by pybabel, translated at runtime in __init__.py
# Use a marker function so pybabel can extract these strings
def _(x): return x  # Translation marker for extraction only
name = _('Re-stock & Price detection for pages with a SINGLE product')
description = _('Detects if the product goes back to in-stock')
del _  # Remove marker function
processor_weight = 1
list_badge_text = "Restock"  # _()

class UnableToExtractRestockData(Exception):
    def __init__(self, status_code):
        # Set this so we can use it in other parts of the app
        self.status_code = status_code
        return

class MoreThanOnePriceFound(Exception):
    def __init__(self):
        return

# =============================================================================
# MEMORY MANAGEMENT: Why We Use Multiprocessing (Linux Only)
# =============================================================================
#
# The get_itemprop_availability() function uses 'extruct' to parse HTML metadata
# (JSON-LD, microdata, OpenGraph, etc). Extruct internally uses lxml, which wraps
# libxml2 - a C library that allocates memory at the C level.
#
# Memory Leak Problem:
# --------------------
# 1. lxml's document_fromstring() creates thousands of Python objects backed by
#    C-level allocations (nodes, attributes, text content)
# 2. Python's garbage collector can mark these objects as collectible, but
#    cannot force the OS to reclaim the actual C-level memory
# 3. malloc/free typically doesn't return memory to OS - it just marks it as
#    "free in the process address space"
# 4. With repeated parsing of large HTML (5MB+ pages), memory accumulates even
#    after Python GC runs
#
# Why Multiprocessing Fixes This:
# --------------------------------
# When a subprocess exits, the OS forcibly reclaims ALL memory including C-level
# allocations that Python GC couldn't release. This ensures clean memory state
# after each extraction.
#
# Performance Impact:
# -------------------
# - Memray analysis showed 1.2M document_fromstring allocations per page
# - Without subprocess: memory grows by ~50-500MB per parse and lingers
# - With subprocess: ~35MB overhead but forces full cleanup after each run
# - Trade-off: 35MB resource_tracker vs 500MB+ accumulated leak = much better at scale
#
# References:
# -----------
# - lxml memory issues: https://medium.com/devopss-hole/python-lxml-memory-leak-b8d0b1000dc7
# - libxml2 caching behavior: https://www.mail-archive.com/lxml@python.org/msg00026.html
# - GC limitations with C extensions: https://benbernardblog.com/tracking-down-a-freaky-python-memory-leak-part-2/
#
# Additional Context:
# -------------------
# - jsonpath_ng (used to query the parsed data) is pure Python and doesn't leak
# - The leak is specifically from lxml's document parsing, not the JSONPath queries
# - Linux-only because multiprocessing spawn is well-tested there; other platforms
#   use direct call as fallback
#
# Alternative Solution (Future Optimization):
# -------------------------------------------
# This entire problem could be avoided by using regex to extract just the machine
# data blocks (JSON-LD, microdata, OpenGraph tags) BEFORE parsing with lxml:
#
#   1. Use regex to extract <script type="application/ld+json">...</script> blocks
#   2. Use regex to extract <meta property="og:*"> tags
#   3. Use regex to find itemprop/itemtype attributes and their containing elements
#   4. Parse ONLY those extracted snippets instead of the entire HTML document
#
# Benefits:
#   - Avoids parsing 5MB of HTML when we only need a few KB of metadata
#   - Eliminates the lxml memory leak entirely
#   - Faster extraction (regex is much faster than DOM parsing)
#   - No subprocess overhead needed
#
# Trade-offs:
#   - Regex for HTML is brittle (comments, CDATA, edge cases)
#   - Microdata extraction would be complex (need to track element boundaries)
#   - Would need extensive testing to ensure we don't miss valid data
#   - extruct is battle-tested; regex solution would need similar maturity
#
# For now, the subprocess approach is safer and leverages existing extruct code.
# =============================================================================


