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


