"""
Utility functions for RSS feed generation.
"""

from changedetectionio.notification.handler import process_notification
from changedetectionio.notification_service import NotificationContextData, _check_cascading_vars
from loguru import logger
import datetime
import pytz
import re


BAD_CHARS_REGEX = r'[\x00-\x08\x0B\x0C\x0E-\x1F]'


def scan_invalid_chars_in_rss(content):
    """
    Scan for invalid characters in RSS content.
    Returns True if invalid characters are found.
    """
    for match in re.finditer(BAD_CHARS_REGEX, content):
        i = match.start()
        bad_char = content[i]
        hex_value = f"0x{ord(bad_char):02x}"
        # Grab context
        start = max(0, i - 20)
        end = min(len(content), i + 21)
        context = content[start:end].replace('\n', '\\n').replace('\r', '\\r')
        logger.warning(f"Invalid char {hex_value} at pos {i}: ...{context}...")
        # First match is enough
        return True

    return False


