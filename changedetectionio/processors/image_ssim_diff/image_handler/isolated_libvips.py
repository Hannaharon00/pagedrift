"""
Subprocess-isolated image operations for memory leak prevention.

LibVIPS accumulates C-level memory in long-running processes that cannot be
reclaimed by Python's GC or libvips cache management. Using subprocess isolation
ensures complete memory cleanup when the process exits.

This module wraps LibvipsImageDiffHandler operations in multiprocessing for
complete memory isolation without code duplication.

Research: https://github.com/libvips/pyvips/issues/234
"""

import multiprocessing

def generate_diff_isolated(img_bytes_from, img_bytes_to, threshold, blur_sigma, max_width, max_height):
    """
    Generate diff visualization in isolated subprocess for memory leak prevention.

    Args:
        img_bytes_from: Previous screenshot bytes
        img_bytes_to: Current screenshot bytes
        threshold: Pixel difference threshold
        blur_sigma: Gaussian blur sigma
        max_width: Maximum width for diff
        max_height: Maximum height for diff

    Returns:
        bytes: JPEG diff image or None on failure
    """
    ctx = multiprocessing.get_context('spawn')
    parent_conn, child_conn = ctx.Pipe()

    p = ctx.Process(
        target=_worker_generate_diff,
        args=(child_conn, img_bytes_from, img_bytes_to, threshold, blur_sigma, max_width, max_height)
    )
    p.start()

    result = None
    try:
        # Wait for result (30 second timeout)
        if parent_conn.poll(30):
            result = parent_conn.recv()
    except Exception as e:
        print(f"[Parent] Error receiving result: {e}", flush=True)
    finally:
        # Always close pipe first
        try:
            parent_conn.close()
        except:
            pass

        # Try graceful shutdown
        p.join(timeout=5)
        if p.is_alive():
            print("[Parent] Process didn't exit gracefully, terminating", flush=True)
            p.terminate()
            p.join(timeout=3)

        # Force kill if still alive
        if p.is_alive():
            print("[Parent] Process didn't terminate, killing", flush=True)
            p.kill()
            p.join(timeout=1)

    return result


def calculate_change_percentage_isolated(img_bytes_from, img_bytes_to, threshold, blur_sigma, max_width, max_height):
    """
    Calculate change percentage in isolated subprocess using handler.

    Returns:
        float: Change percentage
    """
    ctx = multiprocessing.get_context('spawn')
    parent_conn, child_conn = ctx.Pipe()

    def _worker_calculate(conn):
        try:
            # Import handler inside worker
            from .libvips_handler import LibvipsImageDiffHandler

            handler = LibvipsImageDiffHandler()

            # Load images
            img_from = handler.load_from_bytes(img_bytes_from)
            img_to = handler.load_from_bytes(img_bytes_to)

            # Ensure same size
            w1, h1 = handler.get_dimensions(img_from)
            w2, h2 = handler.get_dimensions(img_to)
            if (w1, h1) != (w2, h2):
                img_from = handler.resize(img_from, w2, h2)

            # Downscale
            img_from = handler.resize(img_from, max_width, max_height)
            img_to = handler.resize(img_to, max_width, max_height)

            # Convert to grayscale
            gray_from = handler.to_grayscale(img_from)
            gray_to = handler.to_grayscale(img_to)

            # Optional blur
            gray_from = handler.gaussian_blur(gray_from, blur_sigma)
            gray_to = handler.gaussian_blur(gray_to, blur_sigma)

            # Calculate difference
            diff = handler.absolute_difference(gray_from, gray_to)

            # Threshold and get percentage
            change_percentage, _ = handler.threshold(diff, int(threshold))

            conn.send(float(change_percentage))

        except Exception as e:
            print(f"[Worker] Calculate error: {e}", flush=True)
            conn.send(0.0)
        finally:
            conn.close()

    p = ctx.Process(target=_worker_calculate, args=(child_conn,))
    p.start()

    result = 0.0
    try:
        if parent_conn.poll(30):
            result = parent_conn.recv()
    except Exception as e:
        print(f"[Parent] Calculate error receiving result: {e}", flush=True)
    finally:
        # Always close pipe first
        try:
            parent_conn.close()
        except:
            pass

        # Try graceful shutdown
        p.join(timeout=5)
        if p.is_alive():
            print("[Parent] Calculate process didn't exit gracefully, terminating", flush=True)
            p.terminate()
            p.join(timeout=3)

        # Force kill if still alive
        if p.is_alive():
            print("[Parent] Calculate process didn't terminate, killing", flush=True)
            p.kill()
            p.join(timeout=1)

    return result


