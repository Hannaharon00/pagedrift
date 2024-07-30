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

def _search_prop_by_value(matches, value):
    for properties in matches:
        for prop in properties:
            if value in prop[0]:
                return prop[1]  # Yield the desired value and exit the function

def _deduplicate_prices(data):
    import re

    '''
    Some price data has multiple entries, OR it has a single entry with ['$159', '159', 159, "$ 159"] or just "159"
    Get all the values, clean it and add it to a set then return the unique values
    '''
    unique_data = set()

    # Return the complete 'datum' where its price was not seen before
    for datum in data:

        if isinstance(datum.value, list):
            # Process each item in the list
            normalized_value = set([float(re.sub(r'[^\d.]', '', str(item))) for item in datum.value if str(item).strip()])
            unique_data.update(normalized_value)
        else:
            # Process single value
            v = float(re.sub(r'[^\d.]', '', str(datum.value)))
            unique_data.add(v)

    return list(unique_data)


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


def _extract_itemprop_availability_worker(pipe_conn):
    """
    Subprocess worker for itemprop extraction (Linux memory management).

    Uses spawn multiprocessing to isolate extruct/lxml memory allocations.
    When the subprocess exits, the OS reclaims ALL memory including lxml's
    C-level allocations that Python's GC cannot release.

    Args:
        pipe_conn: Pipe connection to receive HTML and send result
    """
    import json
    import gc

    html_content = None
    result_data = None

    try:
        # Receive HTML as raw bytes (no pickle)
        html_bytes = pipe_conn.recv_bytes()
        html_content = html_bytes.decode('utf-8')

        # Explicitly delete html_bytes to free memory
        del html_bytes
        gc.collect()

        # Perform extraction in subprocess (uses extruct/lxml)
        result_data = get_itemprop_availability(html_content)

        # Convert Restock object to dict for JSON serialization
        result = {
            'success': True,
            'data': dict(result_data) if result_data else {}
        }
        pipe_conn.send_bytes(json.dumps(result).encode('utf-8'))

        # Clean up before exit
        del result_data, html_content, result
        gc.collect()

    except MoreThanOnePriceFound:
        # Serialize the specific exception type
        result = {
            'success': False,
            'exception_type': 'MoreThanOnePriceFound'
        }
        pipe_conn.send_bytes(json.dumps(result).encode('utf-8'))

    except Exception as e:
        # Serialize other exceptions
        result = {
            'success': False,
            'exception_type': type(e).__name__,
            'exception_message': str(e)
        }
        pipe_conn.send_bytes(json.dumps(result).encode('utf-8'))

    finally:
        # Final cleanup before subprocess exits
        # Variables may already be deleted in try block, so use try/except
        try:
            del html_content
        except (NameError, UnboundLocalError):
            pass
        try:
            del result_data
        except (NameError, UnboundLocalError):
            pass
        gc.collect()
        pipe_conn.close()


# should return Restock()
# add casting?
def get_itemprop_availability(html_content) -> Restock:
    """
    Kind of funny/cool way to find price/availability in one many different possibilities.
    Use 'extruct' to find any possible RDFa/microdata/json-ld data, make a JSON string from the output then search it.
    """
    from jsonpath_ng import parse

    import re
    now = time.time()
    import extruct
    logger.trace(f"Imported extruct module in {time.time() - now:.3f}s")

    now = time.time()

    # Extruct is very slow, I'm wondering if some ML is going to be faster (800ms on my i7), 'rdfa' seems to be the heaviest.
    syntaxes = ['dublincore', 'json-ld', 'microdata', 'microformat', 'opengraph']
    try:
        data = extruct.extract(html_content, syntaxes=syntaxes)
    except Exception as e:
        logger.warning(f"Unable to extract data, document parsing with extruct failed with {type(e).__name__} - {str(e)}")
        return Restock()

    logger.trace(f"Extruct basic extract of all metadata done in {time.time() - now:.3f}s")

    # First phase, dead simple scanning of anything that looks useful
    value = Restock()
    if data:
        logger.debug("Using jsonpath to find price/availability/etc")
        price_parse = parse('$..(price|Price)')
        pricecurrency_parse = parse('$..(pricecurrency|currency|priceCurrency )')
        availability_parse = parse('$..(availability|Availability)')

        price_result = _deduplicate_prices(price_parse.find(data))
        if price_result:
            # Right now, we just support single product items, maybe we will store the whole actual metadata seperately in teh future and
            # parse that for the UI?
            if len(price_result) > 1 and len(price_result) > 1:
                # See of all prices are different, in the case that one product has many embedded data types with the same price
                # One might have $121.95 and another 121.95 etc
                logger.warning(f"More than one price found {price_result}, throwing exception, cant use this plugin.")
                raise MoreThanOnePriceFound()

            value['price'] = price_result[0]

        pricecurrency_result = pricecurrency_parse.find(data)
        if pricecurrency_result:
            value['currency'] = pricecurrency_result[0].value

        availability_result = availability_parse.find(data)
        if availability_result:
            value['availability'] = availability_result[0].value

        # Second, go dig OpenGraph which is something that jsonpath_ng cant do because of the tuples and double-dots (:)
        if not value.get('price') or not value.get('availability') or not value.get('currency'):
            logger.debug("Alternatively digging through OpenGraph properties for restock/price info..")
            jsonpath_expr = parse('$..properties')

            for match in jsonpath_expr.find(data):
                if not value.get('price'):
                    value['price'] = _search_prop_by_value([match.value], "price:amount")
                if not value.get('availability'):
                    value['availability'] = _search_prop_by_value([match.value], "product:availability")
                if not value.get('currency'):
                    value['currency'] = _search_prop_by_value([match.value], "price:currency")

        # Normalise after both sources have been tried, otherwise an availability that came from
        # OpenGraph stays raw. The OpenGraph vocabulary spells it "in stock" while the in-stock
        # matcher looks for "instock", so the spaces have to go too.
        if value.get('availability'):
            value['availability'] = re.sub(r'(?i)^(https|http)://schema.org/', '',
                                           value.get('availability').strip(' "\'').lower())
            value['availability'] = re.sub(r'\s+', '', value['availability'])
    logger.trace(f"Processed with Extruct in {time.time()-now:.3f}s")

    return value


