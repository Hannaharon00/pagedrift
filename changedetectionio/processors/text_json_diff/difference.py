"""
History/diff rendering for text_json_diff processor.

This module handles the visualization of text/HTML/JSON changes by rendering
a side-by-side or unified diff view with syntax highlighting and change markers.
"""

import os
import time
from flask_babel import gettext
from loguru import logger

