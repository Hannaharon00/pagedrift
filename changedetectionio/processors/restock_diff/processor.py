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

class MoreThanOnePriceFound(Exception):
    def __init__(self):
        return

