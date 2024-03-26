from blinker import signal
from .processors.exceptions import ProcessorException
import changedetectionio.content_fetchers.exceptions as content_fetchers_exceptions
from changedetectionio.processors.text_json_diff.processor import FilterNotFoundInResponse
from changedetectionio import html_tools
from changedetectionio import worker_pool
from changedetectionio.queuedWatchMetaData import PrioritizedItem
from changedetectionio.pluggy_interface import apply_update_handler_alter, apply_update_finalize

import asyncio
import os
import re
import sys
import time

# Allow alphanumerics, space, and a small set of punctuation that appears in legitimate
# status strings ("Querying AI/LLM (intent)..", "Fetching..."). Anything that could
# be HTML-active (<, >, &, ", ', =, ;, {, }, `, \) is stripped.
_MINITEXT_STATUS_SAFE_RE = re.compile(r'[^A-Za-z0-9 ().,/:\-]')
_MINITEXT_STATUS_MAX_LEN = 80

from loguru import logger

IN_PYTEST = "pytest" in sys.modules or "PYTEST_CURRENT_TEST" in os.environ
DEFER_SLEEP_TIME_ALREADY_QUEUED = 0.3 if IN_PYTEST else 10.0


                logger.info(f"Worker {worker_id} processing watch UUID {uuid} Priority {queued_item_data.priority} URL {watch['url']}")

                try:
                    # Retrieve signal by name to ensure thread-safe access across worker threads
                    watch_check_update = signal('watch_check_update')
                    watch_check_update.send(watch_uuid=uuid)

                    # Processor is what we are using for detecting the "Change"
                    processor = watch.get('processor', 'text_json_diff')

                    # Init a new 'difference_detection_processor'
                    # Use get_processor_module() to support both built-in and plugin processors
                    from changedetectionio.processors import get_processor_module
                    processor_module = get_processor_module(processor)

                    if not processor_module:
                        error_msg = f"Processor module '{processor}' not found."
                        logger.error(error_msg)
                        raise ModuleNotFoundError(error_msg)

                    update_handler = processor_module.perform_site_check(datastore=datastore,
                                                                         watch_uuid=uuid)

                    # Allow plugins to modify/wrap the update_handler
                    update_handler = apply_update_handler_alter(update_handler, watch, datastore)

                    set_watch_minitext_status(watch, "Fetching...")

                    # All fetchers are now async, so call directly
                    await update_handler.call_browser()

                    # Run change detection in executor to avoid blocking event loop
                    # This includes CPU-intensive operations like HTML parsing (lxml/inscriptis)
                    # which can take 2-10ms and cause GIL contention across workers
                    loop = asyncio.get_event_loop()
                    changed_detected, update_obj, contents = await loop.run_in_executor(
                        executor,
                        lambda: update_handler.run_changedetection(watch=watch)
                    )

                except PermissionError as e:
                    logger.critical(f"File permission error updating file, watch: {uuid}")
                    logger.critical(str(e))
                    process_changedetection_results = False

                except ProcessorException as e:
                    if e.screenshot:
                        watch.save_screenshot(screenshot=e.screenshot)
                        e.screenshot = None  # Free memory immediately
                    if e.xpath_data:
                        watch.save_xpath_data(data=e.xpath_data)
                        e.xpath_data = None  # Free memory immediately
                    datastore.update_watch(uuid=uuid, update_obj={'last_error': e.message})
                    process_changedetection_results = False

                except content_fetchers_exceptions.ReplyWithContentButNoText as e:
                    extra_help = ""
                    if e.has_filters:
                        has_img = html_tools.include_filters(include_filters='img',
                                                             html_content=e.html_content)
                        if has_img:
                            extra_help = ", it's possible that the filters you have give an empty result or contain only an image."
                        else:
                            extra_help = ", it's possible that the filters were found, but contained no usable text."

                    datastore.update_watch(uuid=uuid, update_obj={
                        'last_error': f"Got HTML content but no text found (With {e.status_code} reply code){extra_help}"
                    })

                    if e.screenshot:
                        watch.save_screenshot(screenshot=e.screenshot, as_error=True)
                        e.screenshot = None  # Free memory immediately

                    if e.xpath_data:
                        watch.save_xpath_data(data=e.xpath_data)
                        e.xpath_data = None  # Free memory immediately
                        
                    process_changedetection_results = False

                except content_fetchers_exceptions.Non200ErrorCodeReceived as e:
                    if e.status_code == 403:
                        err_text = "Error - 403 (Access denied) received"
                    elif e.status_code == 404:
                        err_text = "Error - 404 (Page not found) received"
                    elif e.status_code == 407:
                        err_text = "Error - 407 (Proxy authentication required) received, did you need a username and password for the proxy?"
                    elif e.status_code == 500:
                        err_text = "Error - 500 (Internal server error) received from the web site"
                    else:
                        extra = ' (Access denied or blocked)' if str(e.status_code).startswith('4') else ''
                        err_text = f"Error - Request returned a HTTP error code {e.status_code}{extra}"

                    if e.screenshot:
                        watch.save_screenshot(screenshot=e.screenshot, as_error=True)
                        e.screenshot = None  # Free memory immediately
                    if e.xpath_data:
                        watch.save_xpath_data(data=e.xpath_data, as_error=True)
                        e.xpath_data = None  # Free memory immediately
                    if e.page_text:
                        watch.save_error_text(contents=e.page_text)

                    datastore.update_watch(uuid=uuid, update_obj={'last_error': err_text})
                    process_changedetection_results = False

                except FilterNotFoundInResponse as e:
                    if not datastore.data['watching'].get(uuid):
                        continue
                    logger.debug(f"Received FilterNotFoundInResponse exception for {uuid}")

                    err_text = "Warning, no filters were found, no change detection ran - Did the page change layout? update your Visual Filter if necessary."
                    datastore.update_watch(uuid=uuid, update_obj={'last_error': err_text})

                    # Filter wasnt found, but we should still update the visual selector so that they can have a chance to set it up again
                    if e.screenshot:
                        watch.save_screenshot(screenshot=e.screenshot)
                        e.screenshot = None  # Free memory immediately

                    if e.xpath_data:
                        watch.save_xpath_data(data=e.xpath_data)
                        e.xpath_data = None  # Free memory immediately

                    # Only when enabled, send the notification
                    if watch.get('filter_failure_notification_send', False):
                        c = watch.get('consecutive_filter_failures', 0)
                        c += 1
                        # Send notification if we reached the threshold?
                        threshold = datastore.data['settings']['application'].get('filter_failure_notification_threshold_attempts', 0)
                        logger.debug(f"FilterNotFoundInResponse - Filter for {uuid} not found, consecutive_filter_failures: {c} of threshold {threshold}")
                        if c >= threshold:
                            if not watch.get('notification_muted'):
                                logger.debug(f"FilterNotFoundInResponse - Sending filter failed notification for {uuid}")
                                await send_filter_failure_notification(uuid, notification_q, datastore)
                            c = 0
                            logger.debug(f"FilterNotFoundInResponse - Reset filter failure count back to zero")
                        else:
                            logger.debug(f"FilterNotFoundInResponse - {c} of threshold {threshold}..")

                        datastore.update_watch(uuid=uuid, update_obj={'consecutive_filter_failures': c})
                    else:
                        logger.trace(f"FilterNotFoundInResponse - {uuid} - filter_failure_notification_send not enabled, skipping")

                    process_changedetection_results = False

                except content_fetchers_exceptions.checksumFromPreviousCheckWasTheSame as e:
                    # Yes fine, so nothing todo, don't continue to process.
                    process_changedetection_results = False
                    changed_detected = False
                    logger.debug(f'[{uuid}] - checksumFromPreviousCheckWasTheSame - Checksum from previous check was the same, nothing todo here.')
                    # Reset the edited flag since we successfully completed the check
                    watch.reset_watch_edited_flag()
                    # Page was fetched successfully - clear any previous error state
                    datastore.update_watch(uuid=uuid, update_obj={'last_error': False})
                    cleanup_error_artifacts(uuid, datastore)
                    
                except content_fetchers_exceptions.BrowserConnectError as e:
                    datastore.update_watch(uuid=uuid,
                                         update_obj={'last_error': e.msg})
                    process_changedetection_results = False
                    
                except content_fetchers_exceptions.BrowserFetchTimedOut as e:
                    datastore.update_watch(uuid=uuid,
                                         update_obj={'last_error': e.msg})
                    process_changedetection_results = False
                    
                except content_fetchers_exceptions.BrowserStepsStepException as e:
                    if not datastore.data['watching'].get(uuid):
                        continue

                    error_step = e.step_n
                    from playwright._impl._errors import TimeoutError, Error

                    # Generally enough info for TimeoutError (couldnt locate the element after default seconds)
                    err_text = f"Browser step at position {error_step} could not run, check the watch, add a delay if necessary, view Browser Steps to see screenshot at that step."

                    if e.original_e.name == "TimeoutError":
                        # Just the first line is enough, the rest is the stack trace
                        err_text += " Could not find the target."
                    else:
                        # Other Error, more info is good.
                        err_text += " " + str(e.original_e).splitlines()[0]

                    logger.debug(f"BrowserSteps exception at step {error_step} {str(e.original_e)}")

                    datastore.update_watch(uuid=uuid,
                                         update_obj={'last_error': err_text,
                                                   'browser_steps_last_error_step': error_step})

                    if watch.get('filter_failure_notification_send', False):
                        c = watch.get('consecutive_filter_failures', 0)
                        c += 1
                        # Send notification if we reached the threshold?
                        threshold = datastore.data['settings']['application'].get('filter_failure_notification_threshold_attempts', 0)
                        logger.error(f"Step for {uuid} not found, consecutive_filter_failures: {c}")
                        if threshold > 0 and c >= threshold:
                            if not watch.get('notification_muted'):
                                await send_step_failure_notification(watch_uuid=uuid, step_n=e.step_n, notification_q=notification_q, datastore=datastore)
                            c = 0

                        datastore.update_watch(uuid=uuid, update_obj={'consecutive_filter_failures': c})

                    process_changedetection_results = False

                except content_fetchers_exceptions.EmptyReply as e:
                    # Some kind of custom to-str handler in the exception handler that does this?
                    err_text = "EmptyReply - try increasing 'Wait seconds before extracting text', Status Code {}".format(e.status_code)
                    datastore.update_watch(uuid=uuid, update_obj={'last_error': err_text,
                                                                'last_check_status': e.status_code})
                    process_changedetection_results = False
                    
                except content_fetchers_exceptions.ScreenshotUnavailable as e:
                    err_text = "Screenshot unavailable, page did not render fully in the expected time or page was too long - try increasing 'Wait seconds before extracting text'"
                    datastore.update_watch(uuid=uuid, update_obj={'last_error': err_text,
                                                                'last_check_status': e.status_code})
                    process_changedetection_results = False
                    
                except content_fetchers_exceptions.JSActionExceptions as e:
                    err_text = "Error running JS Actions - Page request - "+e.message
                    if e.screenshot:
                        watch.save_screenshot(screenshot=e.screenshot, as_error=True)
                        e.screenshot = None  # Free memory immediately
                    datastore.update_watch(uuid=uuid, update_obj={'last_error': err_text,
                                                                'last_check_status': e.status_code})
                    process_changedetection_results = False
                    
                except content_fetchers_exceptions.PageUnloadable as e:
                    err_text = "Page request from server didnt respond correctly"
                    if e.message:
                        err_text = "{} - {}".format(err_text, e.message)

                    if e.screenshot:
                        watch.save_screenshot(screenshot=e.screenshot, as_error=True)
                        e.screenshot = None  # Free memory immediately

