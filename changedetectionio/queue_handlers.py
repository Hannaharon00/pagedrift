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

