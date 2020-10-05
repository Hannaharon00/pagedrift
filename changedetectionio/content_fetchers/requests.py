from flask_babel import lazy_gettext as _l
from loguru import logger
from urllib.parse import urljoin, urlparse
import hashlib
import os
import re
import asyncio

from changedetectionio import strtobool
from changedetectionio.content_fetchers.exceptions import BrowserStepsInUnsupportedFetcher, EmptyReply, Non200ErrorCodeReceived
from changedetectionio.content_fetchers.base import Fetcher
from changedetectionio.validate_url import is_fetch_url_allowed, is_private_hostname, is_url_private_or_parser_confused


