import asyncio
import gc
import json
import os
from urllib.parse import urlparse

from loguru import logger

from changedetectionio.content_fetchers import SCREENSHOT_MAX_HEIGHT_DEFAULT, visualselector_xpath_selectors, \
    SCREENSHOT_SIZE_STITCH_THRESHOLD, SCREENSHOT_MAX_TOTAL_HEIGHT, XPATH_ELEMENT_JS, INSTOCK_DATA_JS, FAVICON_FETCHER_JS
from changedetectionio.content_fetchers.base import Fetcher, get_playwright_bypass_csp, manage_user_agent
from changedetectionio.content_fetchers.exceptions import PageUnloadable, Non200ErrorCodeReceived, EmptyReply, ScreenshotUnavailable, \
    BrowserStepsStepException


async def capture_full_page_async(page, screenshot_format='JPEG', watch_uuid=None, lock_viewport_elements=False):
    import os
    import time

    start = time.time()
    watch_info = f"[{watch_uuid}] " if watch_uuid else ""

    setup_start = time.time()
    page_height = await page.evaluate("document.documentElement.scrollHeight")
    page_width = await page.evaluate("document.documentElement.scrollWidth")
    original_viewport = page.viewport_size
    dimensions_time = time.time() - setup_start

    logger.debug(f"{watch_info}Playwright viewport size {page.viewport_size} page height {page_height} page width {page_width} (got dimensions in {dimensions_time:.2f}s)")

    # Use an approach similar to puppeteer: set a larger viewport and take screenshots in chunks
    step_size = SCREENSHOT_SIZE_STITCH_THRESHOLD # Size that won't cause GPU to overflow
    screenshot_chunks = []
    y = 0
    elements_locked = False

    # Only lock viewport elements if explicitly enabled (for image_ssim_diff processor)
    # This prevents headers/ads from resizing when viewport changes
    if lock_viewport_elements and page_height > page.viewport_size['height']:
        lock_start = time.time()
        lock_elements_js_path = os.path.join(os.path.dirname(__file__), 'res', 'lock-elements-sizing.js')
        with open(lock_elements_js_path, 'r') as f:
            lock_elements_js = f.read()
        await page.evaluate(lock_elements_js)
        elements_locked = True
        lock_time = time.time() - lock_start
        logger.debug(f"{watch_info}Viewport element locking enabled (took {lock_time:.2f}s)")

    if page_height > page.viewport_size['height']:
        if page_height < step_size:
            step_size = page_height # Incase page is bigger than default viewport but smaller than proposed step size
        # Never set viewport taller than our max capture height - otherwise one screenshot chunk
        # captures the whole (e.g. 8098px) page even when SCREENSHOT_MAX_HEIGHT=1000
        step_size = min(step_size, SCREENSHOT_MAX_TOTAL_HEIGHT)
        viewport_start = time.time()
        logger.debug(f"{watch_info}Setting bigger viewport to step through large page width W{page.viewport_size['width']}xH{step_size} because page_height > viewport_size")
        # Set viewport to a larger size to capture more content at once
        await page.set_viewport_size({'width': page.viewport_size['width'], 'height': step_size})
        viewport_time = time.time() - viewport_start
        logger.debug(f"{watch_info}Viewport changed to {page.viewport_size['width']}x{step_size} (took {viewport_time:.2f}s)")

    # Capture screenshots in chunks up to the max total height
    capture_start = time.time()
    chunk_times = []
    # Use PNG for better quality (no compression artifacts), JPEG for smaller size
    screenshot_type = screenshot_format.lower() if screenshot_format else 'jpeg'
    # PNG should use quality 100, JPEG uses configurable quality
    screenshot_quality = 100 if screenshot_type == 'png' else int(os.getenv("SCREENSHOT_QUALITY", 72))

    while y < min(page_height, SCREENSHOT_MAX_TOTAL_HEIGHT):
        # Only scroll if not at the top (y > 0)
        if y > 0:
            await page.evaluate(f"window.scrollTo(0, {y})")

        # Request GC only before screenshot (not 3x per chunk)
        await page.request_gc()

        screenshot_kwargs = {
            'type': screenshot_type,
            'full_page': False
        }
        # Only pass quality parameter for jpeg (PNG doesn't support it in Playwright)
        if screenshot_type == 'jpeg':
            screenshot_kwargs['quality'] = screenshot_quality

        chunk_start = time.time()
        screenshot_chunks.append(await page.screenshot(**screenshot_kwargs))
        chunk_time = time.time() - chunk_start
        chunk_times.append(chunk_time)
        logger.debug(f"{watch_info}Chunk {len(screenshot_chunks)} captured in {chunk_time:.2f}s")
        y += step_size

    # Restore original viewport size
    await page.set_viewport_size({'width': original_viewport['width'], 'height': original_viewport['height']})

    # Unlock element dimensions if they were locked
    if elements_locked:
        unlock_elements_js_path = os.path.join(os.path.dirname(__file__), 'res', 'unlock-elements-sizing.js')
        with open(unlock_elements_js_path, 'r') as f:
            unlock_elements_js = f.read()
        await page.evaluate(unlock_elements_js)
        logger.debug(f"{watch_info}Element dimensions unlocked after screenshot capture")

    capture_time = time.time() - capture_start
    total_capture_time = sum(chunk_times)
    logger.debug(f"{watch_info}All {len(screenshot_chunks)} chunks captured in {capture_time:.2f}s (total chunk time: {total_capture_time:.2f}s)")

    # If we have multiple chunks, stitch them together
    if len(screenshot_chunks) > 1:
        stitch_start = time.time()
        logger.debug(f"{watch_info}Starting stitching of {len(screenshot_chunks)} chunks")

        # Always use spawn subprocess for ANY stitching (2+ chunks)
        # PIL allocates at C level and Python GC never releases it - subprocess exit forces OS to reclaim
        # Trade-off: 35MB resource_tracker vs 500MB+ PIL leak in main process
        from changedetectionio.content_fetchers.screenshot_handler import stitch_images_worker_raw_bytes
        import multiprocessing
        import struct

        ctx = multiprocessing.get_context('spawn')
        parent_conn, child_conn = ctx.Pipe()
        p = ctx.Process(target=stitch_images_worker_raw_bytes, args=(child_conn, page_height, SCREENSHOT_MAX_TOTAL_HEIGHT))
        p.start()

        # Send via raw bytes (no pickle)
        parent_conn.send_bytes(struct.pack('I', len(screenshot_chunks)))
        for chunk in screenshot_chunks:
            parent_conn.send_bytes(chunk)

        screenshot = parent_conn.recv_bytes()
        p.join()

        parent_conn.close()
        child_conn.close()
        del p, parent_conn, child_conn

        stitch_time = time.time() - stitch_start
        total_time = time.time() - start
        setup_time = total_time - capture_time - stitch_time
        logger.debug(
            f"{watch_info}Screenshot complete - Page height: {page_height}px, Capture height: {SCREENSHOT_MAX_TOTAL_HEIGHT}px | "
            f"Setup: {setup_time:.2f}s, Capture: {capture_time:.2f}s, Stitching: {stitch_time:.2f}s, Total: {total_time:.2f}s")
        return screenshot

    total_time = time.time() - start
    setup_time = total_time - capture_time
    logger.debug(
        f"{watch_info}Screenshot complete - Page height: {page_height}px, Capture height: {SCREENSHOT_MAX_TOTAL_HEIGHT}px | "
        f"Setup: {setup_time:.2f}s, Single chunk: {capture_time:.2f}s, Total: {total_time:.2f}s")

    return screenshot_chunks[0]

            if not empty_pages_are_a_change and len((await self.page.content()).strip()) == 0:
                logger.debug("Content Fetcher > Content was empty, empty_pages_are_a_change = False")
                await context.close()
                await browser.close()
                raise EmptyReply(url=url, status_code=response.status)

            # Wrap remaining operations in try/finally to ensure cleanup
            try:
                # Run Browser Steps here
                if self.browser_steps:
                    try:
                        await self.iterate_browser_steps(start_url=url)
                    except BrowserStepsStepException:
                        # Finally block will handle cleanup
                        raise

                    await self.page.wait_for_timeout(extra_wait * 1000)

                now = time.time()
                # So we can find an element on the page where its selector was entered manually (maybe not xPath etc)
                if current_include_filters is not None:
                    await self.page.evaluate("var include_filters={}".format(json.dumps(current_include_filters)))
                else:
                    await self.page.evaluate("var include_filters=''")
                await self.page.request_gc()

                # request_gc before and after evaluate to free up memory
                # @todo browsersteps etc
                MAX_TOTAL_HEIGHT = int(os.getenv("SCREENSHOT_MAX_HEIGHT", SCREENSHOT_MAX_HEIGHT_DEFAULT))
                self.xpath_data = await self.page.evaluate(XPATH_ELEMENT_JS, {
                    "visualselector_xpath_selectors": visualselector_xpath_selectors,
                    "max_height": MAX_TOTAL_HEIGHT
                })
                await self.page.request_gc()

                self.instock_data = await self.page.evaluate(INSTOCK_DATA_JS)
                await self.page.request_gc()

                self.content = await self.page.content()
                await self.page.request_gc()
                logger.debug(f"Scrape xPath element data in browser done in {time.time() - now:.2f}s")


                # Bug 3 in Playwright screenshot handling
                # Some bug where it gives the wrong screenshot size, but making a request with the clip set first seems to solve it
                # JPEG is better here because the screenshots can be very very large

                # Screenshots also travel via the ws:// (websocket) meaning that the binary data is base64 encoded
                # which will significantly increase the IO size between the server and client, it's recommended to use the lowest
                # acceptable screenshot quality here
                # The actual screenshot - this always base64 and needs decoding! horrible! huge CPU usage
                self.screenshot = await capture_full_page_async(page=self.page, screenshot_format=self.screenshot_format, watch_uuid=watch_uuid, lock_viewport_elements=self.lock_viewport_elements)

                # Force aggressive memory cleanup - screenshots are large and base64 decode creates temporary buffers
                await self.page.request_gc()
                gc.collect()

            except ScreenshotUnavailable:
                # Re-raise screenshot unavailable exceptions
                raise ScreenshotUnavailable(url=url, status_code=self.status_code)

            finally:
                # Clean up resources properly with timeouts to prevent hanging
                try:
                    if hasattr(self, 'page') and self.page:
                        await self.page.request_gc()
                        await asyncio.wait_for(self.page.close(), timeout=5.0)
                        logger.debug(f"Successfully closed page for {url}")
                except asyncio.TimeoutError:
                    logger.warning(f"Timed out closing page for {url} (5s)")
                except Exception as e:
                    logger.warning(f"Error closing page for {url}: {e}")
                finally:
                    self.page = None

                try:
                    if context:
                        await asyncio.wait_for(context.close(), timeout=5.0)
                        logger.debug(f"Successfully closed context for {url}")
                except asyncio.TimeoutError:
                    logger.warning(f"Timed out closing context for {url} (5s)")
                except Exception as e:
                    logger.warning(f"Error closing context for {url}: {e}")
                finally:
                    context = None

                try:
                    if browser:
                        await asyncio.wait_for(browser.close(), timeout=5.0)
                        logger.debug(f"Successfully closed browser connection for {url}")
                except asyncio.TimeoutError:
                    logger.warning(f"Timed out closing browser connection for {url} (5s)")
                except Exception as e:
                    logger.warning(f"Error closing browser for {url}: {e}")
                finally:
                    browser = None

                # Force Python GC to release Playwright resources immediately
                # Playwright objects can have circular references that delay cleanup
                gc.collect()


