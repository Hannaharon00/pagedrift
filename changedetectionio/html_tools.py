from functools import lru_cache, wraps

from loguru import logger
from typing import List
import html
import json
import os
import re
import threading

# ---------------------------------------------------------------------------------------
# libxml2 (lxml) concurrency guard
#
# Watch checks run run_changedetection() on a shared ThreadPoolExecutor
# (worker_pool.queue_executor), so extraction for different watches parses HTML in parallel
# threads. A single check uses TWO different lxml parsers: xpath_filter() builds its own
# etree.HTMLParser(), while html_to_text() -> inscriptis parses with lxml's process-global
# html_parser. lxml locks per parser OBJECT, so many threads on the SAME parser serialise
# safely - but that lock does not span two DIFFERENT parsers, and they still share libxml2's
# interned-string dictionary. Concurrent parses corrupt it, and the rendered text of one
# watch's page ends up inside another watch's snapshot.
#
# lxml's FAQ sanctions exactly two patterns: "the default parser (which is replicated for
# each thread) or create a parser for each thread yourself". A parser per CALL is neither -
# but note that a parser per THREAD does not fix this either (measured: still leaks), because
# inscriptis picks its own parser internally and we cannot redirect it. Serialising is the
# only configuration measured clean.
#
# Serialising is measured to be free: extraction is ~80ms mean / 204ms p95 over real data,
# a ceiling of ~12 checks/sec against the ~0.5 checks/sec that browser fetches can feed.
# It also HALVES peak RSS on large pages (481MB -> 232MB on a 3.85MB page across 7 threads),
# because only one libxml2 document is ever live.
#
# EVERY lxml entry point in this process must go through here - a single unguarded parse in
# any thread (Flask request, worker) is enough to reintroduce the corruption.
#
# This is a threading lock, not an asyncio one, and that is deliberate: nothing here is called
# from a coroutine. The async workers hand run_changedetection() to a ThreadPoolExecutor
# (worker.py: "Run change detection in executor to avoid blocking event loop"), the requests
# fetcher does the same, and Flask is synchronous. If you ever call a guarded function directly
# from a coroutine you will stall that worker's event loop for the duration of someone else's
# parse - bounded and deadlock-free (the holder is pure CPU and never awaits), but avoid it.
#
# Re-entrant: these helpers call into each other (element_removal -> subtractive_xpath_selector).
#
# LXML_LOCK_DISABLED=true removes the guard. It exists so the corruption can be reproduced on
# demand (see tests/test_lxml_concurrency.py) - it is NOT a tuning option, it reinstates a
# data-integrity bug that silently writes one watch's page text into another watch's snapshot.
def _build_lxml_lock():
    from changedetectionio.strtobool import strtobool

    if not strtobool(os.getenv('LXML_LOCK_DISABLED', 'false')):
        return threading.RLock()

    logger.warning("LXML_LOCK_DISABLED=true - lxml parsing is unguarded. Under concurrency this "
                   "is known to leak one watch's rendered page text into another watch's "
                   "snapshot. For testing only, never run this in production.")

    class _NullLock:
        def __enter__(self): return self
        def __exit__(self, *a): return False

    return _NullLock()


_LXML_LOCK = _build_lxml_lock()


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

# jq builtins that can leak sensitive data or cause harm when user-supplied expressions are executed.
# env/$ENV reads all process environment variables (passwords, API keys, etc.)
# include/import can read arbitrary files from disk
# input/inputs reads beyond the supplied JSON data
# debug/stderr leaks data to stderr
# halt/halt_error terminates the process (DoS)
_JQ_BLOCKED_PATTERNS = [
    (re.compile(r'\benv\b'),                    'env (reads environment variables)'),
    (re.compile(r'\$ENV\b'),                    '$ENV (reads environment variables)'),
    (re.compile(r'\binclude\b'),                'include (reads files from disk)'),
    (re.compile(r'\bimport\b'),                 'import (reads files from disk)'),
    (re.compile(r'\binputs?\b'),                'input/inputs (reads beyond provided data)'),
    (re.compile(r'\bdebug\b'),                  'debug (leaks data to stderr)'),
    (re.compile(r'\bstderr\b'),                 'stderr (leaks data to stderr)'),
    (re.compile(r'\bhalt(?:_error)?\b'),        'halt/halt_error (terminates the process)'),
    (re.compile(r'\$__loc__\b'),                '$__loc__ (leaks file path information)'),
    (re.compile(r'\bbuiltins\b'),               'builtins (enumerates available functions)'),
    (re.compile(r'\bmodulemeta\b'),             'modulemeta (leaks module information)'),
    (re.compile(r'\$JQ_BUILD_CONFIGURATION\b'), '$JQ_BUILD_CONFIGURATION (leaks build information)'),
]

def validate_jq_expression(expression: str) -> None:
    """Raise ValueError if the jq expression uses any dangerous builtin.

    User-supplied jq expressions are executed server-side. Without this check,
    builtins like `env` expose every process environment variable (SALTED_PASS,
    proxy credentials, API keys, etc.) as watch output.
    """
    from changedetectionio.strtobool import strtobool
    if strtobool(os.getenv('JQ_ALLOW_RISKY_EXPRESSIONS', 'false')):
        return

    for pattern, description in _JQ_BLOCKED_PATTERNS:
        if pattern.search(expression):
            msg = f"jq expression uses disallowed builtin: {description}"
            logger.critical(f"Security: blocked jq expression containing '{description}' - expression: {expression!r}")
            raise ValueError(msg)

META_CT  = re.compile(r'<meta[^>]+http-equiv=["\']?content-type["\']?[^>]*content=["\'][^>]*charset=([a-z0-9_\-:+.]+)', re.I)

# 'price' , 'lowPrice', 'highPrice' are usually under here
# All of those may or may not appear on different websites - I didnt find a way todo case-insensitive searching here
LD_JSON_PRODUCT_OFFER_SELECTORS = ["json:$..offers", "json:$..Offers"]

class JSONNotFound(ValueError):
    def __init__(self, msg):
        ValueError.__init__(self, msg)


_DEFAULT_UNSAFE_XPATH3_FUNCTIONS = [
    'unparsed-text',
    'unparsed-text-lines',
    'unparsed-text-available',
    'doc',
    'doc-available',
    'json-doc',
    'json-doc-available',
    'collection',           # XPath 2.0+: loads XML node collections from arbitrary URIs
    'uri-collection',       # XPath 3.0+: enumerates URIs from resource collections
    'transform',            # XPath 3.1: XSLT transformation (currently raises, block proactively)
    'load-xquery-module',   # XPath 3.1: loads XQuery modules (currently raises, block proactively)
    'environment-variable',
    'available-environment-variables',
]


def get_safe_xpath3_parser():
    """Return an XPath3Parser subclass with filesystem/environment access functions removed.

    XPath 3.0 includes functions that can read arbitrary files or environment variables:
      - unparsed-text / unparsed-text-lines / unparsed-text-available  (file read)
      - doc / doc-available                                             (XML fetch from URI)
      - environment-variable / available-environment-variables         (env var leakage)

    Subclassing gives us an independent symbol_table copy (not shared with the parent class),
    so removing entries here does not affect XPath3Parser itself.

    Override the blocked list via the XPATH_BLOCKED_FUNCTIONS environment variable
    (comma-separated, e.g. "unparsed-text,doc,environment-variable").
    """
    import os
    from elementpath.xpath3 import XPath3Parser

    class SafeXPath3Parser(XPath3Parser):
        pass

    env_override = os.getenv('XPATH_BLOCKED_FUNCTIONS')
    if env_override is not None:
        blocked = [f.strip() for f in env_override.split(',') if f.strip()]
    else:
        blocked = _DEFAULT_UNSAFE_XPATH3_FUNCTIONS

    for _fn in blocked:
        SafeXPath3Parser.symbol_table.pop(_fn, None)

    return SafeXPath3Parser


# Doesn't look like python supports forward slash auto enclosure in re.findall
# So convert it to inline flag "(?i)foobar" type configuration
@lru_cache(maxsize=100)
def perl_style_slash_enclosed_regex_to_options(regex):

    res = re.search(PERL_STYLE_REGEX, regex, re.IGNORECASE)

    if res:
        flags = res.group(2) if res.group(2) else 'i'
        regex = f"(?{flags}){res.group(1)}"
    else:
        # Fall back to just ignorecase as an option
        regex = f"(?i){regex}"

    return regex

# Given a CSS Rule, and a blob of HTML, return the blob of HTML that matches
def include_filters(include_filters, html_content, append_pretty_line_formatting=False):
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html_content, "html.parser")
    html_block = ""
    r = soup.select(include_filters, separator="")

    for element in r:
        # When there's more than 1 match, then add the suffix to separate each line
        # And where the matched result doesn't include something that will cause Inscriptis to add a newline
        # (This way each 'match' reliably has a new-line in the diff)
        # Divs are converted to 4 whitespaces by inscriptis
        if append_pretty_line_formatting and len(html_block) and not element.name in (['br', 'hr', 'div', 'p']):
            html_block += TEXT_FILTER_LIST_LINE_SUFFIX

        html_block += str(element)

    return html_block

def subtractive_css_selector(css_selector, content):
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(content, "html.parser")

    # So that the elements dont shift their index, build a list of elements here which will be pointers to their place in the DOM
    elements_to_remove = soup.select(css_selector)

    if not elements_to_remove:
        # Better to return the original that rebuild with BeautifulSoup
        return content

    # Then, remove them in a separate loop
    for item in elements_to_remove:
        item.decompose()

    return str(soup)

@lxml_guarded
def subtractive_xpath_selector(selectors: List[str], html_content: str) -> str:
    from lxml import etree
    # Parse the HTML content using lxml. Own parser, not etree.HTML()'s process-global default.
    html_tree = etree.fromstring(html_content, parser=lxml_html_parser())

    # First, collect all elements to remove
    elements_to_remove = []

    # Iterate over the list of XPath selectors
    for selector in selectors:
        # Collect elements for each selector
        elements_to_remove.extend(html_tree.xpath(selector))

    # If no elements were found, return the original HTML content
    if not elements_to_remove:
        return html_content

    # Then, remove them in a separate loop
    for element in elements_to_remove:
        if element.getparent() is not None:  # Ensure the element has a parent before removing
            element.getparent().remove(element)

    # Convert the modified HTML tree back to a string
    modified_html = etree.tostring(html_tree, method="html").decode("utf-8")
    return modified_html


def element_removal(selectors: List[str], html_content):
    """Removes elements that match a list of CSS or XPath selectors."""
    modified_html = html_content
    css_selectors = []
    xpath_selectors = []

    for selector in selectors:
        if selector.strip().startswith(('xpath:', 'xpath1:', '//')):
            # Handle XPath selectors separately
            xpath_selector = selector.removeprefix('xpath:').removeprefix('xpath1:')
            xpath_selectors.append(xpath_selector)
        else:
            # Collect CSS selectors as one "hit", see comment in subtractive_css_selector
            css_selectors.append(selector.strip().strip(","))

    if xpath_selectors:
        modified_html = subtractive_xpath_selector(xpath_selectors, modified_html)

    if css_selectors:
        # Remove duplicates, then combine all CSS selectors into one string, separated by commas
        # This stops the elements index shifting
        unique_selectors = list(set(css_selectors))  # Ensure uniqueness
        combined_css_selector = " , ".join(unique_selectors)
        modified_html = subtractive_css_selector(combined_css_selector, modified_html)


    return modified_html

def elementpath_tostring(obj):
    """
    change elementpath.select results to string type
    # The MIT License (MIT), Copyright (c), 2018-2021, SISSA (Scuola Internazionale Superiore di Studi Avanzati)
    # https://github.com/sissaschool/elementpath/blob/dfcc2fd3d6011b16e02bf30459a7924f547b47d0/elementpath/xpath_tokens.py#L1038
    """

    import elementpath
    from decimal import Decimal
    import math

    if obj is None:
        return ''
    # https://elementpath.readthedocs.io/en/latest/xpath_api.html#elementpath.select
    elif isinstance(obj, elementpath.XPathNode):
        return obj.string_value
    elif isinstance(obj, bool):
        return 'true' if obj else 'false'
    elif isinstance(obj, Decimal):
        value = format(obj, 'f')
        if '.' in value:
            return value.rstrip('0').rstrip('.')
        return value

    elif isinstance(obj, float):
        if math.isnan(obj):
            return 'NaN'
        elif math.isinf(obj):
            return str(obj).upper()

        value = str(obj)
        if '.' in value:
            value = value.rstrip('0').rstrip('.')
        if '+' in value:
            value = value.replace('+', '')
        if 'e' in value:
            return value.upper()
        return value

    return str(obj)

# Extract/find element
def extract_element(find='title', html_content=''):
    from bs4 import BeautifulSoup

    #Re #106, be sure to handle when its not found
    element_text = None

    soup = BeautifulSoup(html_content, 'html.parser')
    result = soup.find(find)
    if result and result.string:
        element_text = result.string.strip()

    return element_text

# Any surrogate still present after json.loads() is a lone one - the decoder already folds
# well-formed pairs (😀 -> a single emoji character) before we see them. Lone ones
# come from escapes like \uD800 in the source document, which travel as plain ASCII and so
# pass straight through the fetched-content sanitizer in processors/base.py.
_LONE_SURROGATE_RE = re.compile(r'[\ud800-\udfff]')

def _has_lone_surrogate(value):
    if isinstance(value, str):
        return bool(_LONE_SURROGATE_RE.search(value))
    if isinstance(value, dict):
        return any(_has_lone_surrogate(k) or _has_lone_surrogate(v) for k, v in value.items())
    if isinstance(value, list):
        return any(_has_lone_surrogate(v) for v in value)
    return False

def _sanitize_lone_surrogate_str(value: str) -> str:
    return _LONE_SURROGATE_RE.sub('\ufffd', value)

def _sanitize_lone_surrogates(value):
    if isinstance(value, str):
        return _sanitize_lone_surrogate_str(value)
    if isinstance(value, dict):
        # JSON object keys are always strings, so they only need the substitution - recursing on a
        # key would (in theory) hand back an unhashable dict/list
        return {_sanitize_lone_surrogate_str(k) if isinstance(k, str) else k: _sanitize_lone_surrogates(v)
                for k, v in value.items()}
    if isinstance(value, list):
        return [_sanitize_lone_surrogates(v) for v in value]
    return value

#
def _parse_json(json_data, json_filter):
    from jsonpath_ng.ext import parse

    # Replace lone surrogates with U+FFFD, matching what processors/base.py already does for
    # fetched content. Two separate failures otherwise, neither of which is confined to the
    # offending value: jq re-serializes the whole document for its own C parser, which rejects
    # a lone high surrogate, so every jq:/jqraw: filter on the page errors even when it points
    # at an unrelated field; and on the json: path the surrogate reaches the caller intact and
    # raises UnicodeEncodeError later in checksums and history writes.
    # See: https://github.com/dgtlmoon/changedetection.io/issues/4273
    if _has_lone_surrogate(json_data):
        logger.warning("Lone unicode surrogate(s) in JSON document, replacing with U+FFFD before filtering")
        json_data = _sanitize_lone_surrogates(json_data)

    if json_filter.startswith("json:"):
        jsonpath_expression = parse(json_filter.replace('json:', ''))
        match = jsonpath_expression.find(json_data)
        return _get_stripped_text_from_json_match(match)

    if json_filter.startswith("jq:") or json_filter.startswith("jqraw:"):

        try:
            import jq
        except ModuleNotFoundError:
            # `jq` requires full compilation in windows and so isn't generally available
            raise Exception("jq not support not found")

        if json_filter.startswith("jq:"):
            expr = json_filter.removeprefix("jq:")
            validate_jq_expression(expr)
            jq_expression = jq.compile(expr)
            match = jq_expression.input(json_data).all()
            return _get_stripped_text_from_json_match(match)

        if json_filter.startswith("jqraw:"):
            expr = json_filter.removeprefix("jqraw:")
            validate_jq_expression(expr)
            jq_expression = jq.compile(expr)
            match = jq_expression.input(json_data).all()
            return '\n'.join(str(item) for item in match)

def _get_stripped_text_from_json_match(match):
    s = []
    # More than one result, we will return it as a JSON list.
    if len(match) > 1:
        for i in match:
            s.append(i.value if hasattr(i, 'value') else i)

    # Single value, use just the value, as it could be later used in a token in notifications.
    if len(match) == 1:
        s = match[0].value if hasattr(match[0], 'value') else match[0]

    # Re #257 - Better handling where it does not exist, in the case the original 's' value was False..
    if not match:
        # Re 265 - Just return an empty string when filter not found
        return ''

    # Ticket #462 - allow the original encoding through, usually it's UTF-8 or similar
    stripped_text_from_html = json.dumps(s, indent=4, ensure_ascii=False)

    return stripped_text_from_html

def extract_json_blob_from_html(content, ensure_is_ldjson_info_type, json_filter):
    from bs4 import BeautifulSoup
    stripped_text_from_html = ''

    # Foreach <script json></script> blob.. just return the first that matches json_filter
    # As a last resort, try to parse the whole <body>
    soup = BeautifulSoup(content, 'html.parser')

    if ensure_is_ldjson_info_type:
        bs_result = soup.find_all('script', {"type": "application/ld+json"})
    else:
        bs_result = soup.find_all('script')
    bs_result += soup.find_all('body')

    bs_jsons = []

    for result in bs_result:
        # result.text is how bs4 magically strips JSON from the body
        content_start = result.text.lstrip("\ufeff").strip()[:100] if result.text else ''
        # Skip empty tags, and things that dont even look like JSON
        if not result.text or not (content_start[0] == '{' or content_start[0] == '['):
            continue
        try:
            json_data = json.loads(result.text)
            bs_jsons.append(json_data)
        except json.JSONDecodeError:
            # Skip objects which cannot be parsed
            continue

    if not bs_jsons:
        raise JSONNotFound("No parsable JSON found in this document")

    for json_data in bs_jsons:
        stripped_text_from_html = _parse_json(json_data, json_filter)

        if ensure_is_ldjson_info_type:
            # Could sometimes be list, string or something else random
            if isinstance(json_data, dict):
                # If it has LD JSON 'key' @type, and @type is 'product', and something was found for the search
                # (Some sites have multiple of the same ld+json @type='product', but some have the review part, some have the 'price' part)
                # @type could also be a list although non-standard ("@type": ["Product", "SubType"],)
                # LD_JSON auto-extract also requires some content PLUS the ldjson to be present
                # 1833 - could be either str or dict, should not be anything else

                t = json_data.get('@type')
                if t and stripped_text_from_html:

                    if isinstance(t, str) and t.lower() == ensure_is_ldjson_info_type.lower():
                        break
                    # The non-standard part, some have a list
                    elif isinstance(t, list):
                        if ensure_is_ldjson_info_type.lower() in [x.lower().strip() for x in t]:
                            break

        elif stripped_text_from_html:
            break

    return stripped_text_from_html

