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


def test_queue_includes_timestamps(client, live_server, measure_memory_usage, datastore_path):
    """Queue items carry enqueued_at; running items carry started_at."""
    update_q, worker_pool, qmeta = _quiesce(live_server)

    # Push something — enqueued_at should be ~now
    before = time.time()
    queued_uuid = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    _push(update_q, worker_pool, qmeta, queued_uuid, priority=1)
    after = time.time()

    snap = client.get(url_for("ui.ui_queue.queue_json")).get_json()
    assert len(snap["queued"]) == 1
    ts_q = snap["queued"][0]["enqueued_at"]
    assert isinstance(ts_q, float)
    assert before <= ts_q <= after + 0.5, f"enqueued_at out of range: {ts_q!r}"

    # Claim a synthetic running uuid — started_at should be ~now
    running_uuid = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
    before = time.time()
    assert worker_pool.claim_uuid_for_processing(running_uuid, worker_id=999)
    after = time.time()

    snap = client.get(url_for("ui.ui_queue.queue_json")).get_json()
    running_entry = next((r for r in snap["running"] if r["uuid"] == running_uuid), None)
    assert running_entry is not None
    ts_r = running_entry["started_at"]
    assert isinstance(ts_r, float)
    assert before <= ts_r <= after + 0.5, f"started_at out of range: {ts_r!r}"

    # Release clears the timestamp
    worker_pool.release_uuid_from_processing(running_uuid, worker_id=999)
    assert worker_pool.get_uuid_started_at(running_uuid) is None

    update_q.clear()


def test_queue_pagination(client, live_server, measure_memory_usage, datastore_path):
    """Page math: per_page from settings.pager_size, total_pages, page slicing."""
    update_q, worker_pool, qmeta = _quiesce(live_server)

    # Override pager_size for this test so we don't have to push 50+ items
    live_server.app.config['DATASTORE'].data['settings']['application']['pager_size'] = 2

    uuids = [f"{i:08d}-2222-3333-4444-555555555555" for i in range(5)]
    for u in uuids:
        _push(update_q, worker_pool, qmeta, u, priority=1)

    snap1 = client.get(url_for("ui.ui_queue.queue_json")).get_json()
    assert snap1["per_page"] == 2
    assert snap1["queued_count"] == 5
    assert snap1["total_pages"] == 3
    assert snap1["page"] == 1
    assert len(snap1["queued"]) == 2

    snap2 = client.get(url_for("ui.ui_queue.queue_json") + "?page=2").get_json()
    assert snap2["page"] == 2
    assert len(snap2["queued"]) == 2

    snap3 = client.get(url_for("ui.ui_queue.queue_json") + "?page=3").get_json()
    assert snap3["page"] == 3
    assert len(snap3["queued"]) == 1, f"last page should be partial: {snap3!r}"

    # Pages cover every uuid exactly once
    all_uuids = [w["uuid"] for w in snap1["queued"] + snap2["queued"] + snap3["queued"]]
    assert sorted(all_uuids) == sorted(uuids)

    # Restore + drain
    live_server.app.config['DATASTORE'].data['settings']['application']['pager_size'] = 50
    update_q.clear()


