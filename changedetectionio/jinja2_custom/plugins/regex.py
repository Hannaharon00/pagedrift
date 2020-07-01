"""
Regex filter plugin for Jinja2 templates.

Provides regex_replace filter for pattern-based string replacements in templates.
"""
import re
import signal
from loguru import logger


