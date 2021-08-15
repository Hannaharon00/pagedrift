"""
LLM fallback plugin for price and restock info extraction.

When the built-in structured-metadata extraction (JSON-LD, microdata, OpenGraph)
fails to produce both a price and availability, this plugin is called as a last
resort.  It sends a trimmed, HTML-stripped version of the page to the configured
LLM and asks it to return a structured JSON answer.

The module-level `datastore` variable is injected at startup by
`inject_datastore_into_plugins()` in pluggy_interface.py.
"""
import json
import os
import re
from loguru import logger
from changedetectionio.pluggy_interface import hookimpl
from changedetectionio.llm.evaluator import apply_local_token_multiplier

# Injected at startup by inject_datastore_into_plugins()
datastore = None

SYSTEM_PROMPT = (
    'You are an expert price and restock extraction utility. '
    'Your task is to analyse a product page and determine the price and stock status of the MAIN product only.\n\n'

    'AVAILABILITY — treat as "in stock":\n'
    '- Action buttons near the product: "Add to cart", "Add to basket", "Buy now", '
    '"Order now", "Purchase", "Import", "Add to bag", "Add to trolley", "In stock", '
    '"Available", "Ships in X days/weeks", "In store", "Pick up today".\n'
    '- "Pre-order" or "Reserve" — the item is orderable, treat as "in stock".\n'
    '- "Only X left", "Almost gone", "Low stock", "Limited availability" — still in stock.\n'
    '- "Request a quote" or "Contact us for pricing" — item is available, price is null.\n'
    '- IMPORTANT: Ignore cart/basket/bag links in the page HEADER or navigation bar '
    '(e.g. a shopping cart icon showing item count). That reflects what is already in '
    'the visitor\'s cart — it says nothing about whether THIS product is available.\n\n'

    'PRICE — what NOT to use:\n'
    '- A "$0.00" or "0" that appears near header/nav links such as "Login", "Wishlist", '
    '"Contact Us", "My Account" is an empty shopping-cart indicator, NOT the product price. '
    'Ignore it entirely — return null for price rather than 0 in this situation.\n'
    '- Only return 0 (free) when the page clearly states the product itself costs nothing '
    '(e.g. "Free", "Free download", "Price: $0").\n\n'

    'AVAILABILITY — treat as "out of stock":\n'
    '- "Out of stock", "Sold out", "Unavailable", "Currently unavailable", '
    '"Temporarily out of stock", "Discontinued", "No longer available", '
    '"Notify me when available", "Email me when back", "Join waitlist".\n\n'

    'AVAILABILITY — return null when uncertain:\n'
    '- The page asks the user to select a size, colour, or other variant first '
    '("Select an option", "Choose a size") — availability depends on the variant, so return null.\n'
    '- You cannot clearly tell from the page content whether the item is available.\n\n'

    'PRICE rules:\n'
    '- Extract the main selling price as a plain number, no currency symbol.\n'
    '- Prices may use any popular locale format — interpret them all correctly and return a plain decimal number. '
    'Examples: "10 000 Kč" = 10000, "1.299,95 €" = 1299.95, "1,299.95" = 1299.95, '
    '"10 000,50" = 10000.50, "£1.299" = 1299, "¥10000" = 10000.\n'
    '- If both an original (crossed-out) price and a sale/current price appear, use the sale price.\n'
    '- "From $X" or "Starting at $X" are teaser prices — prefer a definite price or return null.\n'
    '- A price of 0 (free) is valid — return 0, not null.\n'
    '- If pricing requires a quote or login, return null for price.\n'
    '- Ignore prices shown in search/filter UI elements (e.g. "Price from: — to:").\n'
    '- IMPORTANT: Ignore ALL prices that appear inside or below recommendation/discovery blocks '
    'such as: "Similar items", "You may also like", "Customers also bought", '
    '"Based on your browsing", "Based on your shopping", "Frequently bought together", '
    '"People also viewed", "Related products", "Sponsored products", "More like this", '
    '"Other sellers", "Compare with similar items". '
    'These sections contain prices for OTHER products, not the main product.\n'
    '- When multiple prices appear on the page, prefer the price that is positioned '
    'earliest/highest in the page content — it is almost always the main product price. '
    'Prices appearing after large blocks of descriptive text or review sections are '
    'likely from recommendation widgets and should be ignored.\n\n'

    'CLASSIFIEDS AND LISTING PAGES:\n'
    '- On classifieds or marketplace sites (e.g. eBay listings, Craigslist, Bazoš, Gumtree), '
    'if a price is shown alongside seller contact details or a "Contact seller" link, '
    'treat the item as "instock" — the listing being active means it is available.\n\n'

    'Return ONLY a JSON object with exactly these three keys:\n'
    '  "price"        — number or null\n'
    '  "currency"     — ISO-4217 code (USD, EUR, GBP …) or null\n'
    '  "availability" — exactly one of: "instock", "outofstock", or null\n'
    '                   Use "instock" when the product can be ordered/purchased.\n'
    '                   Use "outofstock" when it cannot.\n'
    '                   Use null when you genuinely cannot tell.\n'
    'No markdown, no backticks, no explanation — pure JSON only.'
)

# Max characters of page content (JSON-LD + stripped text) sent to the LLM.
# Some retailers (e.g. Amazon.de) place the buy-box price well past 8k chars,
# so this is env-configurable. Larger values increase input-token cost per
# check and may exceed local-model context windows (bump Ollama num_ctx to match).
# NOTE: this is only the default — the caller passes the app's datastore-configured
# "Max input characters" setting via _get_max_input_chars() below.
_MAX_CONTENT_CHARS = int(os.getenv('LLM_RESTOCK_MAX_CONTENT_CHARS', 15_000))

# Cache LLM extraction results keyed by the exact LLM input (model + url + stripped content +
# intent). Product pages re-fetch constantly with noisy raw HTML (analytics, nonces, CSRF
# tokens) that changes the watch's raw checksum every check — so the processor's checksum-skip
# rarely fires for them and the LLM would otherwise be billed on every check even when the
# price/stock content is identical. Keying on the actual prompt means we only spend tokens when
# the meaningful content changes. Bounded FIFO so it can't grow unbounded across many watches.
import hashlib
from collections import OrderedDict

_LLM_RESULT_CACHE = OrderedDict()
_LLM_RESULT_CACHE_MAX = 500


def _llm_cache_get(key):
    return _LLM_RESULT_CACHE.get(key)


def _llm_cache_put(key, value):
    _LLM_RESULT_CACHE[key] = value
    _LLM_RESULT_CACHE.move_to_end(key)
    while len(_LLM_RESULT_CACHE) > _LLM_RESULT_CACHE_MAX:
        _LLM_RESULT_CACHE.popitem(last=False)


