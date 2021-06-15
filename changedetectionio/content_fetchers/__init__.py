import sys
from changedetectionio.strtobool import strtobool
from loguru import logger
from changedetectionio.content_fetchers.exceptions import BrowserStepsStepException
import os

# Visual Selector scraper - 'Button' is there because some sites have <button>OUT OF STOCK</button>.
visualselector_xpath_selectors = 'div,span,form,table,tbody,tr,td,a,p,ul,li,h1,h2,h3,h4,header,footer,section,article,aside,details,main,nav,section,summary,button'

# Import hookimpl from centralized pluggy interface
from changedetectionio.pluggy_interface import hookimpl

SCREENSHOT_MAX_HEIGHT_DEFAULT = 20000
SCREENSHOT_DEFAULT_QUALITY = 40

# Maximum total height for the final image (When in stitch mode).
# We limit this to 16000px due to the huge amount of RAM that was being used
# Example: 16000 × 1400 × 3 = 67,200,000 bytes ≈ 64.1 MB (not including buffers in PIL etc)
SCREENSHOT_MAX_TOTAL_HEIGHT = int(os.getenv("SCREENSHOT_MAX_HEIGHT", SCREENSHOT_MAX_HEIGHT_DEFAULT))

# The size at which we will switch to stitching method, when below this (and
# MAX_TOTAL_HEIGHT which can be set by a user) we will use the default
# screenshot method.
# Increased from 8000 to 10000 for better performance (fewer chunks = faster)
# Most modern GPUs support 16384x16384 textures, so 1280x10000 is safe
SCREENSHOT_SIZE_STITCH_THRESHOLD = int(os.getenv("SCREENSHOT_CHUNK_HEIGHT", 10000))

# available_fetchers() will scan this implementation looking for anything starting with html_
# this information is used in the form selections
from changedetectionio.content_fetchers.requests import fetcher as html_requests


import importlib.resources
XPATH_ELEMENT_JS = importlib.resources.files("changedetectionio.content_fetchers.res").joinpath('xpath_element_scraper.js').read_text(encoding='utf-8')
INSTOCK_DATA_JS = importlib.resources.files("changedetectionio.content_fetchers.res").joinpath('stock-not-in-stock.js').read_text(encoding='utf-8')
FAVICON_FETCHER_JS = importlib.resources.files("changedetectionio.content_fetchers.res").joinpath('favicon-fetcher.js').read_text(encoding='utf-8')


