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


def _draw_bounding_box_if_configured(img_bytes, watch, datastore):
    """
    Draw blue bounding box on image if configured in processor settings.
    Uses isolated subprocess to prevent memory leaks from large images.

    Supports two modes:
    - "Select by element": Use include_filter to find xpath element bbox
    - "Draw area": Use manually drawn bounding_box from config

    Args:
        img_bytes: Image bytes (PNG)
        watch: Watch object
        datastore: Datastore object

    Returns:
        Image bytes (possibly with bounding box drawn)
    """
    try:
        # Get processor configuration
        from changedetectionio import processors
        processor_instance = processors.difference_detection_processor(datastore, watch.get('uuid'))
        processor_name = watch.get('processor', 'default')
        config_filename = f'{processor_name}.json'
        processor_config = processor_instance.get_extra_watch_config(config_filename)

        if not processor_config:
            return img_bytes

        selection_mode = processor_config.get('selection_mode', 'draw')
        x, y, width, height = None, None, None, None

        # Mode 1: Select by element (use include_filter + xpath_data)
        if selection_mode == 'element':
            include_filters = watch.get('include_filters', [])

            if include_filters and len(include_filters) > 0:
                first_filter = include_filters[0].strip()

                # Get xpath_data from watch history
                history_keys = list(watch.history.keys())
                if history_keys:
                    latest_snapshot = watch.get_history_snapshot(timestamp=history_keys[-1])
                    xpath_data_path = watch.get_xpath_data_filepath(timestamp=history_keys[-1])

                    try:
                        import gzip
                        with gzip.open(xpath_data_path, 'rt') as f:
                            xpath_data = json.load(f)

                        # Find matching element
                        for element in xpath_data.get('size_pos', []):
                            if element.get('xpath') == first_filter and element.get('highlight_as_custom_filter'):
                                x = element.get('left', 0)
                                y = element.get('top', 0)
                                width = element.get('width', 0)
                                height = element.get('height', 0)
                                logger.debug(f"Found element bbox for filter '{first_filter}': x={x}, y={y}, w={width}, h={height}")
                                break
                    except Exception as e:
                        logger.warning(f"Failed to load xpath_data for element selection: {e}")

        # Mode 2: Draw area (use manually configured bbox)
        else:
            bounding_box = processor_config.get('bounding_box')
            if bounding_box:
                # Parse bounding box: "x,y,width,height"
                parts = [int(p.strip()) for p in bounding_box.split(',')]
                if len(parts) == 4:
                    x, y, width, height = parts
                else:
                    logger.warning(f"Invalid bounding box format: {bounding_box}")

        # If no bbox found, return original image
        if x is None or y is None or width is None or height is None:
            return img_bytes

        # Use isolated subprocess to prevent memory leaks from large images
        from .image_handler import isolated_opencv
        import asyncio
        import threading

        # Async-safe wrapper: runs coroutine in new thread with its own event loop
        # This prevents blocking when called from async context (update worker)
        def run_async_in_thread():
            return asyncio.run(
                isolated_opencv.draw_bounding_box_isolated(
                    img_bytes, x, y, width, height,
                    color=(255, 0, 0),  # Blue in BGR format
                    thickness=3
                )
            )

        # Always run in thread to avoid blocking event loop if called from async context
        result_container = [None]
        exception_container = [None]

        def thread_target():
            try:
                result_container[0] = run_async_in_thread()
            except Exception as e:
                exception_container[0] = e

        thread = threading.Thread(target=thread_target, daemon=True, name="ImageDiff-BoundingBox")
        thread.start()
        thread.join(timeout=15)

        if exception_container[0]:
            raise exception_container[0]

        result = result_container[0]

        # Return result or original if subprocess failed
        return result if result else img_bytes

    except Exception as e:
        logger.warning(f"Failed to draw bounding box: {e}")
        import traceback
        logger.debug(traceback.format_exc())
        return img_bytes


