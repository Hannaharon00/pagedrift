# HTML to TEXT/JSON DIFFERENCE self.fetcher

import hashlib
import json
import os
import re
import urllib3

from changedetectionio.conditions import execute_ruleset_against_all_plugins
from changedetectionio.content_fetchers.exceptions import checksumFromPreviousCheckWasTheSame
from ..base import difference_detection_processor
from changedetectionio.html_tools import PERL_STYLE_REGEX, cdata_in_document_to_text, TRANSLATE_WHITESPACE_TABLE
from changedetectionio import html_tools, content_fetchers
from changedetectionio.blueprint.price_data_follower import PRICE_DATA_TRACK_ACCEPT
from loguru import logger

from changedetectionio.processors.magic import guess_stream_type

