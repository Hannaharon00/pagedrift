import os
import time
import re
from random import randint
from loguru import logger

from changedetectionio.content_fetchers import SCREENSHOT_MAX_HEIGHT_DEFAULT
from changedetectionio.content_fetchers.base import get_playwright_bypass_csp, manage_user_agent
from changedetectionio.jinja2_custom import render as jinja_render
from changedetectionio.validate_url import validate_fetch_url_async

