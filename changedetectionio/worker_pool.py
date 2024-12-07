"""
Worker management module for changedetection.io

Handles asynchronous workers for dynamic worker scaling.
Each worker runs in its own thread with its own event loop for isolation.
"""

import asyncio
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from loguru import logger

# Global worker state - each worker has its own thread and event loop
worker_threads = []  # List of WorkerThread objects

# Track currently processing UUIDs for async workers - maps {uuid: worker_id}
currently_processing_uuids = {}
# When each currently-running UUID was claimed: {uuid: epoch_seconds}
# Lets the queue UI render "running for Ns" without reaching into worker internals.
_uuid_started_at = {}
_uuid_processing_lock = threading.Lock()  # Protects currently_processing_uuids + _uuid_started_at

# Configuration - async workers only
USE_ASYNC_WORKERS = True

# Custom ThreadPoolExecutor for queue operations with named threads
# Scale executor threads to match FETCH_WORKERS (no minimum, no maximum)
# Thread naming: "QueueGetter-N" for easy debugging in thread dumps/traces
# With FETCH_WORKERS=10: 10 workers + 10 executor threads = 20 threads total
# With FETCH_WORKERS=500: 500 workers + 500 executor threads = 1000 threads total (acceptable on modern systems)
_max_executor_workers = int(os.getenv("FETCH_WORKERS", "10"))
queue_executor = ThreadPoolExecutor(
    max_workers=_max_executor_workers,
    thread_name_prefix="QueueGetter-"  # Shows in thread dumps as "QueueGetter-0", "QueueGetter-1", etc.
)


class WorkerThread:
    """Container for a worker thread with its own event loop"""
    def __init__(self, worker_id, update_q, notification_q, app, datastore):
        self.worker_id = worker_id
        self.update_q = update_q
        self.notification_q = notification_q
        self.app = app
        self.datastore = datastore
        self.thread = None
        self.loop = None
        self.running = False

    def run(self):
        """Run the worker in its own event loop"""
        try:
            # Create a new event loop for this thread
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
            self.running = True

            # Run the worker coroutine
            self.loop.run_until_complete(
                start_single_async_worker(
                    self.worker_id,
                    self.update_q,
                    self.notification_q,
                    self.app,
                    self.datastore,
                    queue_executor
                )
            )
        except asyncio.CancelledError:
            # Normal shutdown - worker was cancelled
            import os
            in_pytest = "pytest" in os.sys.modules or "PYTEST_CURRENT_TEST" in os.environ
            if not in_pytest:
                logger.info(f"Worker {self.worker_id} shutting down gracefully")
        except RuntimeError as e:
            # Ignore expected shutdown errors
            if "Event loop stopped" not in str(e) and "Event loop is closed" not in str(e):
                logger.error(f"Worker {self.worker_id} runtime error: {e}")
        except Exception as e:
            logger.error(f"Worker {self.worker_id} thread error: {e}")
        finally:
            # Clean up
            if self.loop and not self.loop.is_closed():
                self.loop.close()
            self.running = False
            self.loop = None

    def start(self):
        """Start the worker thread with descriptive name for debugging"""
        self.thread = threading.Thread(
            target=self.run,
            daemon=True,
            name=f"PageFetchAsyncUpdateWorker-{self.worker_id}"  # Shows in thread dumps with worker ID
        )
        self.thread.start()

    def stop(self):
        """Stop the worker thread brutally - no waiting"""
        # Try to stop the event loop if it exists
        if self.loop and self.running:
            try:
                # Signal the loop to stop
                self.loop.call_soon_threadsafe(self.loop.stop)
            except RuntimeError:
                pass

        # Don't wait - thread is daemon and will die when needed


def start_workers(n_workers, update_q, notification_q, app, datastore):
    """Start async workers - sync workers are deprecated"""
    start_async_workers(n_workers, update_q, notification_q, app, datastore)


def _ensure_queue_executor():
    """Recreate queue_executor if a prior shutdown_workers() left it in the
    shutdown state. Without this, any add_worker() / start_async_workers()
    after a brutal shutdown spawns workers that immediately crash with
    'cannot schedule new futures after shutdown'."""
    global queue_executor
    if queue_executor is None or getattr(queue_executor, '_shutdown', False):
        queue_executor = ThreadPoolExecutor(
            max_workers=_max_executor_workers,
            thread_name_prefix="QueueGetter-",
        )


def add_worker(update_q, notification_q, app, datastore):
    """Add a new async worker (for dynamic scaling)"""
    global worker_threads

    _ensure_queue_executor()

    # Reuse lowest available ID to prevent unbounded growth over time
    used_ids = {w.worker_id for w in worker_threads}
    worker_id = 0
    while worker_id in used_ids:
        worker_id += 1
    logger.info(f"Adding async worker {worker_id}")

    try:
        worker = WorkerThread(worker_id, update_q, notification_q, app, datastore)
        worker.start()
        worker_threads.append(worker)
        return True
    except Exception as e:
        logger.error(f"Failed to add worker {worker_id}: {e}")
        return False


def remove_worker():
    """Remove an async worker (for dynamic scaling)"""
    global worker_threads

    if not worker_threads:
        return False

    # Stop the last worker
    worker = worker_threads.pop()
    worker.stop()
    logger.info(f"Removed async worker, {len(worker_threads)} workers remaining")
    return True


def get_worker_count():
    """Get current number of async workers"""
    return len(worker_threads)


def get_running_uuids():
    """Get list of UUIDs currently being processed by async workers"""
    with _uuid_processing_lock:
        return list(currently_processing_uuids.keys())


