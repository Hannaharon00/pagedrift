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

