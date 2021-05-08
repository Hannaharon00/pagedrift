"""
Core fast screenshot comparison processor.

Uses OpenCV with subprocess isolation for high-performance, low-memory
image processing. All operations run in isolated subprocesses for complete
memory cleanup and stability.
"""

import hashlib
import time
from loguru import logger
from changedetectionio.processors.exceptions import ProcessorException
from . import SCREENSHOT_COMPARISON_THRESHOLD_OPTIONS_DEFAULT, PROCESSOR_CONFIG_NAME, OPENCV_BLUR_SIGMA
from ..base import difference_detection_processor, SCREENSHOT_FORMAT_PNG

