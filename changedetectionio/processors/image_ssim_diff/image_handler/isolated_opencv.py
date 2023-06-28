"""
OpenCV-based subprocess isolation for image comparison.

OpenCV is much more stable in multiprocessing contexts than LibVIPS.
No threading issues, no fork problems, picklable functions.
"""

import multiprocessing
import numpy as np
from .. import POLL_TIMEOUT_ABSOLUTE

# Public implementation name for logging
IMPLEMENTATION_NAME = "OpenCV"


def _worker_compare(conn, img_bytes_from, img_bytes_to, pixel_difference_threshold, blur_sigma, crop_region):
    """
    Worker function for image comparison (must be top-level for pickling with spawn).

    Args:
        conn: Pipe connection for sending results
        img_bytes_from: Previous screenshot bytes
        img_bytes_to: Current screenshot bytes
        pixel_difference_threshold: Pixel-level sensitivity (0-255) - how different must a pixel be to count as changed
        blur_sigma: Gaussian blur sigma
        crop_region: Optional (left, top, right, bottom) crop coordinates
    """
    import time
    try:
        import cv2

        # CRITICAL: Disable OpenCV threading to prevent thread explosion
        # With multiprocessing, each subprocess would otherwise spawn threads equal to CPU cores
        # This causes excessive thread counts and memory overhead
        # Research: https://medium.com/@rachittayal7/a-note-on-opencv-threads-performance-in-prod-d10180716fba
        cv2.setNumThreads(1)

        print(f"[{time.time():.3f}] [Worker] Compare worker starting (threads=1 for memory optimization)", flush=True)

        # Decode images from bytes
        print(f"[{time.time():.3f}] [Worker] Loading images (from={len(img_bytes_from)} bytes, to={len(img_bytes_to)} bytes)", flush=True)
        img_from = cv2.imdecode(np.frombuffer(img_bytes_from, np.uint8), cv2.IMREAD_COLOR)
        img_to = cv2.imdecode(np.frombuffer(img_bytes_to, np.uint8), cv2.IMREAD_COLOR)

        # Check if decoding succeeded
        if img_from is None:
            raise ValueError("Failed to decode 'from' image - may be corrupt or unsupported format")
        if img_to is None:
            raise ValueError("Failed to decode 'to' image - may be corrupt or unsupported format")

        print(f"[{time.time():.3f}] [Worker] Images loaded: from={img_from.shape}, to={img_to.shape}", flush=True)

        # Crop if region specified
        if crop_region:
            print(f"[{time.time():.3f}] [Worker] Cropping to region {crop_region}", flush=True)
            left, top, right, bottom = crop_region
            img_from = img_from[top:bottom, left:right]
            img_to = img_to[top:bottom, left:right]
            print(f"[{time.time():.3f}] [Worker] Cropped: from={img_from.shape}, to={img_to.shape}", flush=True)

        # Resize if dimensions don't match
        if img_from.shape != img_to.shape:
            print(f"[{time.time():.3f}] [Worker] Resizing to match dimensions", flush=True)
            img_from = cv2.resize(img_from, (img_to.shape[1], img_to.shape[0]))

        # Convert to grayscale
        print(f"[{time.time():.3f}] [Worker] Converting to grayscale", flush=True)
        gray_from = cv2.cvtColor(img_from, cv2.COLOR_BGR2GRAY)
        gray_to = cv2.cvtColor(img_to, cv2.COLOR_BGR2GRAY)

        # Optional Gaussian blur
        if blur_sigma > 0:
            print(f"[{time.time():.3f}] [Worker] Applying Gaussian blur (sigma={blur_sigma})", flush=True)
            # OpenCV uses kernel size, convert sigma to kernel size: size = 2 * round(3*sigma) + 1
            ksize = int(2 * round(3 * blur_sigma)) + 1
            if ksize % 2 == 0:  # Must be odd
                ksize += 1
            gray_from = cv2.GaussianBlur(gray_from, (ksize, ksize), blur_sigma)
            gray_to = cv2.GaussianBlur(gray_to, (ksize, ksize), blur_sigma)
            print(f"[{time.time():.3f}] [Worker] Blur applied (kernel={ksize}x{ksize})", flush=True)

        # Calculate absolute difference
        print(f"[{time.time():.3f}] [Worker] Calculating absolute difference", flush=True)
        diff = cv2.absdiff(gray_from, gray_to)

        # Apply threshold
        print(f"[{time.time():.3f}] [Worker] Applying pixel difference threshold ({pixel_difference_threshold})", flush=True)
        _, thresholded = cv2.threshold(diff, int(pixel_difference_threshold), 255, cv2.THRESH_BINARY)

        # Calculate change percentage
        total_pixels = thresholded.size
        changed_pixels = np.count_nonzero(thresholded)
        change_percentage = (changed_pixels / total_pixels) * 100.0

        print(f"[{time.time():.3f}] [Worker] Comparison complete: percentage={change_percentage:.2f}%", flush=True)
        # Return only the score - let the caller decide if it's a "change"
        conn.send(float(change_percentage))

    except Exception as e:
        print(f"[{time.time():.3f}] [Worker] Error: {e}", flush=True)
        import traceback
        traceback.print_exc()
        # Send error info as dict so parent can re-raise
        conn.send({'error': str(e), 'traceback': traceback.format_exc()})
    finally:
        conn.close()


def _worker_draw_bounding_box(conn, img_bytes, x, y, width, height, color, thickness):
    """
    Worker function for drawing bounding box on image.
    """
    import time
    try:
        import cv2

        cv2.setNumThreads(1)
        print(f"[{time.time():.3f}] [Worker] Draw bounding box worker starting", flush=True)

        # Decode image
        img = cv2.imdecode(np.frombuffer(img_bytes, np.uint8), cv2.IMREAD_COLOR)
        if img is None:
            print(f"[{time.time():.3f}] [Worker] Failed to decode image", flush=True)
            conn.send(None)
            return

        # Draw rectangle (BGR format)
        cv2.rectangle(img, (x, y), (x + width, y + height), color, thickness)

        # Encode back to PNG
        _, encoded = cv2.imencode('.png', img)
        result_bytes = encoded.tobytes()

        print(f"[{time.time():.3f}] [Worker] Bounding box drawn ({len(result_bytes)} bytes)", flush=True)
        conn.send(result_bytes)

    except Exception as e:
        print(f"[{time.time():.3f}] [Worker] Draw bounding box error: {e}", flush=True)
        import traceback
        traceback.print_exc()
        # Send error info as dict so parent can re-raise
        conn.send({'error': str(e), 'traceback': traceback.format_exc()})
    finally:
        conn.close()


