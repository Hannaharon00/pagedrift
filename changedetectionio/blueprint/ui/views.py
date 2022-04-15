import time
from flask import Blueprint, request, redirect, url_for, flash
from flask_babel import gettext
from loguru import logger
from changedetectionio.store import ChangeDetectionStore
from changedetectionio.auth_decorator import login_optionally_required
from changedetectionio import worker_pool


def run_preloaded_first_check(datastore, uuid):
    """Run the watch's chosen processor once against the snapshot the Add Watch page already
    fetched (parked as preload-fetch.json + screenshot + xpath in the watch dir), producing
    the first history snapshot WITHOUT any network IO.

    Processors are fast and CPU-only here, so we run them inline on submit. Best-effort:
    any failure (or no preload present) returns False and leaves the watch without history,
    so a normal queued check will populate it instead. Returns True if a snapshot was written.
    """
    from changedetectionio.processors import get_processor_module
    from changedetectionio import html_tools

    watch = datastore.data['watching'].get(uuid)
    if not watch:
        return False

    try:
        processor_module = get_processor_module(watch.get('processor', 'text_json_diff'))
        if not processor_module:
            return False

        handler = processor_module.perform_site_check(datastore=datastore, watch_uuid=uuid)

        # Populate the fetcher from the parked snapshot instead of hitting the network.
        if not handler._consume_preloaded_fetch():
            return False

        changed_detected, update_obj, contents = handler.run_changedetection(watch=watch)

        # Mirror the worker's first-snapshot save path (the parts that apply with no network).
        timestamp = int(time.time())
        update_obj['content-type'] = str(handler.fetcher.get_all_headers().get('content-type', '') or "").lower()
        update_obj['last_error'] = False
        update_obj['last_checked'] = timestamp
        watch.reset_watch_edited_flag()
        datastore.update_watch(uuid=uuid, update_obj=update_obj)

        watch.save_history_blob(contents=contents,
                                timestamp=timestamp,
                                snapshot_id=update_obj.get('previous_md5', 'none'))
        if handler.fetcher.content:
            watch.save_last_fetched_html(timestamp=timestamp, contents=handler.fetcher.content)

        # Page title is shown in the list / used in notifications.
        try:
            if 'html' in update_obj.get('content-type', ''):
                page_title = html_tools.extract_title(data=handler.fetcher.content)
                if page_title:
                    datastore.update_watch(uuid=uuid, update_obj={'page_title': page_title.strip()[:2000]})
        except Exception as e:
            logger.debug(f"Add Watch preloaded first-check: title extraction failed for {uuid}: {e}")

        logger.info(f"Add Watch: created first snapshot for {uuid} from preloaded fetch (no network)")
        return True

    except Exception as e:
        # Any processor error (empty text, no matching filters, etc.) - fall back to a normal check.
        logger.warning(f"Add Watch: preloaded first-check failed for {uuid}, falling back to a normal check: {e}")
        return False


