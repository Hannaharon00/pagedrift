from blinker import signal
from loguru import logger
from typing import Dict, List, Any, Optional
import heapq
import queue
import threading

# Janus is no longer required - we use pure threading.Queue for multi-loop support
# try:
#     import janus
# except ImportError:
#     pass  # Not needed anymore


class RecheckPriorityQueue:
    """
    Thread-safe priority queue supporting multiple async event loops.

    ARCHITECTURE:
    - Multiple async workers, each with its own event loop in its own thread
    - Hybrid sync/async design for maximum scalability
    - Sync interface for ticker thread (threading.Queue)
    - Async interface for workers (asyncio.Event - NO executor threads!)

    SCALABILITY:
    - Scales to 100-200+ workers without executor thread exhaustion
    - Async workers wait on asyncio.Event (pure coroutines, no threads)
    - Sync callers use threading.Queue (backward compatible)

    WHY NOT JANUS:
    - Janus binds to ONE event loop at creation time
    - Our architecture has 15+ workers, each with separate event loops
    - Workers in different threads/loops cannot share janus async interface

    WHY NOT RUN_IN_EXECUTOR:
    - With 200 workers, run_in_executor() would block 200 threads
    - Exhausts ThreadPoolExecutor, starves Flask HTTP handlers
    - Pure async approach uses 0 threads while waiting
    """

    def __init__(self, maxsize: int = 0):
        try:
            import asyncio

            # Sync interface: threading.Queue for ticker thread and Flask routes
            self._notification_queue = queue.Queue(maxsize=maxsize if maxsize > 0 else 0)

            # Priority storage - thread-safe
            self._priority_items = []
            self._lock = threading.RLock()

            # No event signaling needed - pure polling approach
            # Workers check queue every 50ms (latency acceptable: 0-500ms)
            # Scales to 1000+ workers: each sleeping worker = ~4KB coroutine, not thread

            # Signals for UI updates
            self.queue_length_signal = signal('queue_length')

            logger.debug("RecheckPriorityQueue initialized successfully")
        except Exception as e:
            logger.critical(f"CRITICAL: Failed to initialize RecheckPriorityQueue: {str(e)}")
            raise
    
    # SYNC INTERFACE (for ticker thread)
    def put(self, item, block: bool = True, timeout: Optional[float] = None):
        """Thread-safe sync put with priority ordering"""
        logger.trace(f"RecheckQueue.put() called for item: {self._get_item_uuid(item)}, block={block}, timeout={timeout}")
        try:
            # Stamp an enqueue timestamp on the item if it doesn't already carry one
            # — gives the queue UI a "queued Ns ago" reading without all callers
            # having to opt in. setdefault preserves callers that DO supply their own.
            try:
                if hasattr(item, 'item') and isinstance(item.item, dict):
                    import time as _t
                    item.item.setdefault('enqueued_at', _t.time())
            except Exception:
                pass

            # CRITICAL: Add to both priority storage AND notification queue atomically
            # to prevent desynchronization where item exists but no notification
            with self._lock:
                heapq.heappush(self._priority_items, item)

                # Add notification - use blocking with timeout for safety
                # Notification queue is unlimited size, so should never block in practice
                # but timeout ensures we detect any unexpected issues (deadlock, etc)
                try:
                    self._notification_queue.put(True, block=True, timeout=5.0)
                except Exception as notif_e:
                    # Notification failed - MUST remove from priority_items to keep in sync
                    # This prevents "Priority queue inconsistency" errors in get()
                    logger.critical(f"CRITICAL: Notification queue put failed, removing from priority_items: {notif_e}")
                    self._priority_items.remove(item)
                    heapq.heapify(self._priority_items)
                    raise  # Re-raise to be caught by outer exception handler

            # Signal emission after successful queue - log but don't fail the operation
            # Item is already safely queued, so signal failure shouldn't affect queue state
            try:
                self._emit_put_signals(item)
            except Exception as signal_e:
                logger.error(f"Failed to emit put signals but item queued successfully: {signal_e}")

            logger.trace(f"Successfully queued item: {self._get_item_uuid(item)}")
            return True

        except Exception as e:
            logger.critical(f"CRITICAL: Failed to put item {self._get_item_uuid(item)}: {type(e).__name__}: {str(e)}")
            # Item should have been cleaned up in the inner try/except if notification failed
            return False
    
    def get(self, block: bool = True, timeout: Optional[float] = None):
        """Thread-safe sync get with priority ordering"""
        logger.trace(f"RecheckQueue.get() called, block={block}, timeout={timeout}")
        import queue as queue_module
        try:
            # Wait for notification (this doesn't return the actual item, just signals availability)
            self._notification_queue.get(block=block, timeout=timeout)

            # Get highest priority item
            with self._lock:
                if not self._priority_items:
                    logger.critical(f"CRITICAL: Queue notification received but no priority items available")
                    raise Exception("Priority queue inconsistency")
                item = heapq.heappop(self._priority_items)

            # Signal emission after successful retrieval - log but don't lose the item
            # Item is already retrieved, so signal failure shouldn't affect queue state
            try:
                self._emit_get_signals()
            except Exception as signal_e:
                logger.error(f"Failed to emit get signals but item retrieved successfully: {signal_e}")

            logger.trace(f"RecheckQueue.get() successfully retrieved item: {self._get_item_uuid(item)}")
            return item

        except queue_module.Empty:
            # Queue is empty with timeout - expected behavior
            logger.trace(f"RecheckQueue.get() timed out - queue is empty (timeout={timeout})")
            raise  # noqa
        except Exception as e:
            # Re-raise without logging - caller (worker) will handle and log appropriately
            logger.trace(f"RecheckQueue.get() failed with exception: {type(e).__name__}: {str(e)}")
            raise
    
    # ASYNC INTERFACE (for workers)
    async def async_put(self, item, executor=None):
        """Async put with priority ordering - uses thread pool to avoid blocking

        Args:
            item: Item to add to queue
            executor: Optional ThreadPoolExecutor. If None, uses default pool.
        """
        logger.trace(f"RecheckQueue.async_put() called for item: {self._get_item_uuid(item)}, executor={executor}")
        import asyncio
        try:
            # Use run_in_executor to call sync put without blocking event loop
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                executor,  # Use provided executor or default
                lambda: self.put(item, block=True, timeout=5.0)
            )

            logger.trace(f"RecheckQueue.async_put() successfully queued item: {self._get_item_uuid(item)}")
            return result

        except Exception as e:
            logger.critical(f"CRITICAL: Failed to async put item {self._get_item_uuid(item)}: {str(e)}")
            return False

    async def async_get(self, executor=None, timeout=1.0):
        """
        Efficient async get using executor for blocking call.

        HYBRID APPROACH: Best of both worlds
        - Uses run_in_executor for efficient blocking (no polling overhead)
        - Single timeout (no double-timeout race condition)
        - Scales well: executor sized to match worker count

        With FETCH_WORKERS=10: 10 threads blocked max (acceptable)
        With FETCH_WORKERS=200: Need executor with 200+ threads (see worker_pool.py)

        Args:
            executor: ThreadPoolExecutor (sized to match worker count)
            timeout: Maximum time to wait in seconds

        Returns:
            Item from queue

        Raises:
            queue.Empty: If timeout expires with no item available
        """
        logger.trace(f"RecheckQueue.async_get() called, timeout={timeout}")
        import asyncio
        try:
            # Use run_in_executor to call sync get efficiently
            # No outer asyncio.wait_for wrapper = no double timeout issue!
            loop = asyncio.get_event_loop()
            item = await loop.run_in_executor(
                executor,
                lambda: self.get(block=True, timeout=timeout)
            )

            logger.trace(f"RecheckQueue.async_get() successfully retrieved item: {self._get_item_uuid(item)}")
            return item

        except queue.Empty:
            logger.trace(f"RecheckQueue.async_get() timed out - queue is empty")
            raise
        except Exception as e:
            logger.critical(f"CRITICAL: Failed to async get item from queue: {type(e).__name__}: {str(e)}")
            raise
    
    # UTILITY METHODS
    def qsize(self) -> int:
        """Get current queue size"""
        try:
            with self._lock:
                return len(self._priority_items)
        except Exception as e:
            logger.critical(f"CRITICAL: Failed to get queue size: {str(e)}")
            return 0
    
