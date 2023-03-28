"""
Screenshot diff visualization for fast image comparison processor.

All image operations now use ImageDiffHandler abstraction for clean separation
of concerns and easy backend swapping (LibVIPS, OpenCV, PIL, etc.).
"""

import os
import json
import time
from flask_babel import gettext
from loguru import logger

from changedetectionio.processors.image_ssim_diff import SCREENSHOT_COMPARISON_THRESHOLD_OPTIONS_DEFAULT, PROCESSOR_CONFIG_NAME, \
    OPENCV_BLUR_SIGMA

# All image operations now use OpenCV via isolated_opencv subprocess handler
# No direct handler imports needed - subprocess isolation handles everything

# Maximum dimensions for diff visualization (can be overridden via environment variable)
# Large screenshots don't need full resolution for visual inspection
# Reduced defaults to minimize memory usage - 2000px height is plenty for diff viewing
MAX_DIFF_HEIGHT = int(os.getenv('MAX_DIFF_HEIGHT', '8000'))
MAX_DIFF_WIDTH = int(os.getenv('MAX_DIFF_WIDTH', '900'))


