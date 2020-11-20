import os
import time
import re
from random import randint
from loguru import logger

from changedetectionio.content_fetchers import SCREENSHOT_MAX_HEIGHT_DEFAULT
from changedetectionio.content_fetchers.base import get_playwright_bypass_csp, manage_user_agent
from changedetectionio.jinja2_custom import render as jinja_render
from changedetectionio.validate_url import validate_fetch_url_async

# Two flags, tell the JS which of the "Selector" or "Value" field should be enabled in the front end
# 0- off, 1- on
browser_step_ui_config = {'Choose one': '0 0',
                          #                 'Check checkbox': '1 0',
                          #                 'Click button containing text': '0 1',
                          #                 'Scroll to bottom': '0 0',
                          #                 'Scroll to element': '1 0',
                          #                 'Scroll to top': '0 0',
                          #                 'Switch to iFrame by index number': '0 1'
                          #                 'Uncheck checkbox': '1 0',
                          # @todo
                          'Check checkbox': '1 0',
                          'Click X,Y': '0 1',
                          'Click element if exists': '1 0',
                          'Click element': '1 0',
                          'Click element containing text': '0 1',
                          'Click element containing text if exists': '0 1',
                          'Enter text in field': '1 1',
                          'Execute JS': '0 1',
#                          'Extract text and use as filter': '1 0',
                          'Goto site': '0 0',
                          'Goto URL': '0 1',
                          'Make all child elements visible': '1 0',
                          'Press Enter': '0 0',
                          'Select by label': '1 1',
                          '<select> by option text': '1 1',
                          'Scroll down': '0 0',
                          'Uncheck checkbox': '1 0',
                          'Wait for seconds': '0 1',
                          'Wait for text': '0 1',
                          'Wait for text in element': '1 1',
                          'Remove elements': '1 0',
                          #                          'Press Page Down': '0 0',
                          #                          'Press Page Up': '0 0',
                          # weird bug, come back to it later
                          }


