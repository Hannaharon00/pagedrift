"""
Tests for the queue inspection UI (blueprint/ui/queue.py).

Strategy: shut down all workers, pause the scheduler, then push synthetic
UUIDs directly into update_q. Synthetic UUIDs are immune to scheduler
interference. The HTTP test client + live_server share the same process,
so update_q is a single instance.
"""

import time
from flask import url_for


def _quiesce(live_server, timeout=3.0):
    """Pause scheduler, shut down all workers, wait for in-flight async workers
    to fully drain, clear queue. Returns (update_q, worker_pool, queuedWatchMetaData).

    The "brutal" shutdown registers stop-flags but workers blocked in
    update_q.async_get() can still complete one more pop after shutdown is
    requested. We poll for a quiet period where consecutive clear()s show no
    new items being deposited.
    """
    from changedetectionio import worker_pool, queuedWatchMetaData
    from changedetectionio.flask_app import update_q

    live_server.app.config['DATASTORE'].data['settings']['application']['all_paused'] = True
    live_server.app.set_workers(0)

    deadline = time.time() + timeout
    while time.time() < deadline:
        if worker_pool.get_worker_count() == 0:
            break
        time.sleep(0.05)
    assert worker_pool.get_worker_count() == 0, "workers did not shut down in time"

    # Push a sentinel and watch for it to remain in the queue across consecutive reads.
    # If a lingering coroutine pops it, we requeue and wait. Once it survives a settle
    # window the queue is genuinely quiescent.
    sentinel_uuid = "00000000-0000-0000-0000-0000sent1nel0"
    sentinel = queuedWatchMetaData.PrioritizedItem(priority=1, item={'uuid': sentinel_uuid})

    update_q.clear()
    settle_deadline = time.time() + timeout
    while time.time() < settle_deadline:
        worker_pool.queue_item_async_safe(update_q, sentinel)
        time.sleep(0.15)
        if sentinel_uuid in update_q.get_queued_uuids():
            break
        # Was popped by a lingering worker — try again
    else:
        raise AssertionError("Could not get queue to a quiescent state")

    update_q.clear()
    return update_q, worker_pool, queuedWatchMetaData


