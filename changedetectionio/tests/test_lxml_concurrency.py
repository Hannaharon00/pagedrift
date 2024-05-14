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

from changedetectionio import html_tools

THREADS = 12
# The bug corrupted ~4.75% of extractions, so 600 jobs means ~28 expected failures with the
# guard removed - enough that this cannot pass by luck. Paths that were never affected only
# need enough volume to catch a future regression, hence JOBS_GUARD.
JOBS = 600
JOBS_GUARD = 200

# Distinct, mutually-identifiable documents. Each row carries a marker unique to its document so
# any foreign content is unambiguous - mirrors the real report, where the giveaway was another
# university's email domain appearing in the snapshot.
NAMES = ["hamline", "gwynedd", "thiel", "lbcc", "wabash", "baruch", "purdue", "butler"]


def _make_doc(name, rows=120):
    body = "\n".join(
        f"<tr><td>Person {i} {name}</td><td>p{i}@{name}.example</td></tr>" for i in range(rows)
    )
    return (
        f"<html><head><title>{name}</title>"
        f"<script>var pad=\"{'z' * 1200}\";</script><style>.a{{color:red}}</style></head>"
        f"<body><div class='ads'>AD-{name}</div>"
        f"<div id='staff'><table class='sidearm-table'>{body}</table></div>"
        f"<footer>END-{name}</footer></body></html>"
    )


DOCS = {n: _make_doc(n) for n in NAMES}


def _assert_no_contamination(pipeline, jobs=JOBS):
    """Run pipeline concurrently over distinct docs; output must be byte-identical to the
    single-threaded result and must never contain another document's marker."""
    expected = {n: pipeline(DOCS[n]) for n in NAMES}
    problems = []
    lock = threading.Lock()

    def job(i):
        name = NAMES[i % len(NAMES)]
        out = pipeline(DOCS[name])
        found = [o for o in NAMES if o != name and f"{o}.example" in out]
        if found:
            with lock:
                problems.append(f"{name} snapshot contains {found} (len {len(out)}, "
                                f"expected {len(expected[name])})")
        elif out != expected[name]:
            with lock:
                problems.append(f"{name} non-deterministic output: len {len(out)}, "
                                f"expected {len(expected[name])}")

    with ThreadPoolExecutor(max_workers=THREADS) as pool:
        list(pool.map(job, range(jobs)))

    assert not problems, (
        f"{len(problems)} of {jobs} concurrent extractions were corrupted "
        f"(html_tools lxml guard broken?):\n  " + "\n  ".join(problems[:10])
    )


def test_xpath_filter_with_html_to_text_is_not_contaminated():
    """The customer's exact filter shape - this is the combination that reproduced."""
    def pipeline(doc):
        return html_tools.html_to_text(
            html_tools.xpath_filter("//table[contains(@class,'sidearm-table')]", doc,
                                    append_pretty_line_formatting=True))
    _assert_no_contamination(pipeline)


def test_xpath1_filter_with_html_to_text_is_not_contaminated():
    def pipeline(doc):
        return html_tools.html_to_text(
            html_tools.xpath1_filter("//table[contains(@class,'sidearm-table')]", doc,
                                     append_pretty_line_formatting=True))
    _assert_no_contamination(pipeline)


