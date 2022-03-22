"""
LibVIPS implementation of ImageDiffHandler.

Uses pyvips for high-performance image processing with streaming architecture
and low memory footprint. Ideal for large screenshots (8000px+).
"""

from __future__ import annotations
import os
from typing import Tuple, Any, TYPE_CHECKING
from loguru import logger

if TYPE_CHECKING:
    import pyvips

try:
    import pyvips
    PYVIPS_AVAILABLE = True
except ImportError:
    PYVIPS_AVAILABLE = False
    logger.warning("pyvips not available - install with: pip install pyvips")

from . import ImageDiffHandler


