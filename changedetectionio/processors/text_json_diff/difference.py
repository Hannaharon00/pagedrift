"""
History/diff rendering for text_json_diff processor.

This module handles the visualization of text/HTML/JSON changes by rendering
a side-by-side or unified diff view with syntax highlighting and change markers.
"""

import os
import time
from flask_babel import gettext
from loguru import logger

from changedetectionio import diff, strtobool
from changedetectionio.diff import (
    REMOVED_STYLE, ADDED_STYLE, REMOVED_INNER_STYLE, ADDED_INNER_STYLE,
    REMOVED_PLACEMARKER_OPEN, REMOVED_PLACEMARKER_CLOSED,
    ADDED_PLACEMARKER_OPEN, ADDED_PLACEMARKER_CLOSED,
    CHANGED_PLACEMARKER_OPEN, CHANGED_PLACEMARKER_CLOSED,
    CHANGED_INTO_PLACEMARKER_OPEN, CHANGED_INTO_PLACEMARKER_CLOSED
)
from changedetectionio.notification.handler import apply_html_color_to_body


