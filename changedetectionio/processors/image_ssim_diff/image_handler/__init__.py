"""
Abstract base class for image processing operations.

All image operations for the image_ssim_diff processor must be implemented
through this interface to allow different backends (libvips, OpenCV, PIL, etc.).
"""

from abc import ABC, abstractmethod
from typing import Tuple, Optional, Any


class ImageDiffHandler(ABC):
    """
    Abstract base class for image processing operations.

    Implementations must handle all image operations needed for screenshot
    comparison including loading, cropping, resizing, diffing, and overlays.
    """

    @abstractmethod
    def load_from_bytes(self, img_bytes: bytes) -> Any:
        """
        Load image from bytes.

        Args:
            img_bytes: Image data as bytes (PNG, JPEG, etc.)

        Returns:
            Handler-specific image object
        """
        pass

    @abstractmethod
    def save_to_bytes(self, img: Any, format: str = 'png', quality: int = 85) -> bytes:
        """
        Save image to bytes.

        Args:
            img: Handler-specific image object
            format: Output format ('png' or 'jpeg')
            quality: Quality for JPEG (1-100)

        Returns:
            Image data as bytes
        """
        pass

    @abstractmethod
    def crop(self, img: Any, left: int, top: int, right: int, bottom: int) -> Any:
        """
        Crop image to specified region.

        Args:
            img: Handler-specific image object
            left: Left coordinate
            top: Top coordinate
            right: Right coordinate
            bottom: Bottom coordinate

        Returns:
            Cropped image object
        """
        pass

    @abstractmethod
    def resize(self, img: Any, max_width: int, max_height: int) -> Any:
        """
        Resize image maintaining aspect ratio.

        Args:
            img: Handler-specific image object
            max_width: Maximum width in pixels
            max_height: Maximum height in pixels

        Returns:
            Resized image object
        """
        pass

    @abstractmethod
    def get_dimensions(self, img: Any) -> Tuple[int, int]:
        """
        Get image dimensions.

        Args:
            img: Handler-specific image object

        Returns:
            Tuple of (width, height)
        """
        pass

    @abstractmethod
    def to_grayscale(self, img: Any) -> Any:
        """
        Convert image to grayscale.

        Args:
            img: Handler-specific image object

        Returns:
            Grayscale image object
        """
        pass

    @abstractmethod
    def gaussian_blur(self, img: Any, sigma: float) -> Any:
        """
        Apply Gaussian blur to image.

