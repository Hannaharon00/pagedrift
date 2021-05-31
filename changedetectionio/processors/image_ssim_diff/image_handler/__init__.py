"""
Abstract base class for image processing operations.

All image operations for the image_ssim_diff processor must be implemented
through this interface to allow different backends (libvips, OpenCV, PIL, etc.).
"""

from abc import ABC, abstractmethod
from typing import Tuple, Optional, Any


