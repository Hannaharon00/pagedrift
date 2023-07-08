"""
Guards against cross-watch snapshot contamination in the filter/extract chain.

Watch checks run run_changedetection() on a shared ThreadPoolExecutor, so different watches
parse HTML in parallel threads. A single check mixes two lxml parsers - xpath_filter() has its
own, html_to_text() -> inscriptis uses lxml's process-global one. Without html_tools' lxml lock
those races corrupt libxml2 state and one document's rendered text lands in another's output.

Reported by a hosted customer whose snapshots contained an entirely different university's staff
directory concatenated ahead of their own, at double the normal size.

These tests fail reliably (tens of failures, several whole-document leaks) with the lock removed.
"""
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest

