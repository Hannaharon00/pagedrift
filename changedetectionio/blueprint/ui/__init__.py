import time
import threading
from blinker import signal
from flask import Blueprint, request, redirect, url_for, flash, render_template, session, current_app
from flask_babel import gettext
from loguru import logger

from changedetectionio.store import ChangeDetectionStore
from changedetectionio.blueprint.ui.edit import construct_blueprint as construct_edit_blueprint
from changedetectionio.blueprint.ui.notification import construct_blueprint as construct_notification_blueprint
from changedetectionio.blueprint.ui.views import construct_blueprint as construct_views_blueprint
from changedetectionio.blueprint.ui.queue import construct_blueprint as construct_queue_blueprint
from changedetectionio.blueprint.ui import diff, preview

def _handle_operations(op, uuids, datastore, worker_pool, update_q, queuedWatchMetaData, watch_check_update, extra_data=None, emit_flash=True):
    """Apply a bulk operation to the given watch uuids.

    Returns a {'message': str, 'type': 'success'|'error'} result describing the outcome so callers
    (e.g. the socket.io handler) can surface server-driven feedback. When emit_flash is True the same
    message is also flashed for the classic form-POST + redirect path.
    """
    from flask import flash

    # Result feedback - 'success' unless a branch overrides it (e.g. invalid input)
    result_message = None
    result_type = 'success'

    if op == 'delete':
        for uuid in uuids:
            if datastore.data['watching'].get(uuid):
                datastore.delete(uuid)
        result_message = gettext("{} watches deleted").format(len(uuids))

    elif op == 'pause':
        for uuid in uuids:
            if datastore.data['watching'].get(uuid):
                datastore.data['watching'][uuid]['paused'] = True
                datastore.data['watching'][uuid].commit()
        result_message = gettext("{} watches paused").format(len(uuids))

    elif op == 'unpause':
        for uuid in uuids:
            if datastore.data['watching'].get(uuid):
                datastore.data['watching'][uuid.strip()]['paused'] = False
                datastore.data['watching'][uuid].commit()
        result_message = gettext("{} watches unpaused").format(len(uuids))

    elif (op == 'mark-viewed'):
        for uuid in uuids:
            if datastore.data['watching'].get(uuid):
                datastore.set_last_viewed(uuid, int(time.time()))
        result_message = gettext("{} watches updated").format(len(uuids))

    elif (op == 'mute'):
        for uuid in uuids:
            if datastore.data['watching'].get(uuid):
                datastore.data['watching'][uuid]['notification_muted'] = True
                datastore.data['watching'][uuid].commit()
        result_message = gettext("{} watches muted").format(len(uuids))

    elif (op == 'unmute'):
        for uuid in uuids:
            if datastore.data['watching'].get(uuid):
                datastore.data['watching'][uuid]['notification_muted'] = False
                datastore.data['watching'][uuid].commit()
        result_message = gettext("{} watches un-muted").format(len(uuids))

def construct_blueprint(datastore: ChangeDetectionStore, update_q, worker_pool, queuedWatchMetaData, watch_check_update):
    ui_blueprint = Blueprint('ui', __name__, template_folder="templates")
    
    # Register the edit blueprint
    edit_blueprint = construct_edit_blueprint(datastore, update_q, queuedWatchMetaData)
    ui_blueprint.register_blueprint(edit_blueprint)
    
    # Register the notification blueprint
    notification_blueprint = construct_notification_blueprint(datastore)
    ui_blueprint.register_blueprint(notification_blueprint)
    
    # Register the views blueprint
    views_blueprint = construct_views_blueprint(datastore, update_q, queuedWatchMetaData, watch_check_update)
    ui_blueprint.register_blueprint(views_blueprint)

    # Register diff and preview blueprints
    diff_blueprint = diff.construct_blueprint(datastore)
    ui_blueprint.register_blueprint(diff_blueprint)

    preview_blueprint = preview.construct_blueprint(datastore)
    ui_blueprint.register_blueprint(preview_blueprint)

    @ui_blueprint.route("/delete", methods=['POST'])
    @login_optionally_required
    def form_delete():
        uuid = request.args.get('uuid')
        # More for testing, possible to return the first/only
        if uuid == 'first':
            uuid = list(datastore.data['watching'].keys()).pop()

        if uuid != 'all' and not uuid in datastore.data['watching'].keys():
            flash(gettext('The watch by UUID {} does not exist.').format(uuid), 'error')
            return redirect(url_for('watchlist.index'))

        datastore.delete(uuid)
        flash(gettext('Deleted.'))

        return redirect(url_for('watchlist.index'))

    @ui_blueprint.route("/clone", methods=['POST'])
    @login_optionally_required
    def form_clone():
        uuid = request.args.get('uuid')

        if uuid == 'first':
            uuid = list(datastore.data['watching'].keys()).pop()

        new_uuid = datastore.clone(uuid)
        if not new_uuid:
            # Refused (e.g. PAGE_WATCH_LIMIT) - the reason is already flashed
            return redirect(url_for('watchlist.index'))

        if not datastore.data['watching'].get(uuid).get('paused'):
            worker_pool.queue_item_async_safe(update_q, queuedWatchMetaData.PrioritizedItem(priority=5, item={'uuid': new_uuid}))

        flash(gettext('Cloned, you are editing the new watch.'))

        return redirect(url_for("ui.ui_edit.edit_page", uuid=new_uuid))

    @ui_blueprint.route("/checknow", methods=['POST'])
    @login_optionally_required
    def form_watch_checknow():
        # Forced recheck will skip the 'skip if content is the same' rule (, 'reprocess_existing_data': True})))
        from changedetectionio.blueprint.watchlist import filters as wl_filters
        uuid = request.args.get('uuid')

        if uuid:
            # Single watch - check if already queued or running
            if worker_pool.is_watch_running(uuid) or uuid in update_q.get_queued_uuids():
                flash(gettext("Watch is already queued or being checked."))
            else:
                worker_pool.queue_item_async_safe(update_q, queuedWatchMetaData.PrioritizedItem(priority=1, item={'uuid': uuid}))
                flash(gettext("Queued 1 watch for rechecking."))
        else:
            # Multiple watches - operate on the SAME set the watch list is showing
            # (tag/processor/status/search) via the shared filter, skipping paused.
            list_filters = wl_filters.list_filters_from_args(datastore, request.args)
            watches_to_queue = []
            for k in sorted(datastore.data['watching'].items(), key=lambda item: item[1].get('last_checked', 0)):
                watch_uuid = k[0]
                watch = k[1]
                if not watch['paused'] and watch_uuid and wl_filters.watch_matches_filters(datastore, watch, list_filters):
                    watches_to_queue.append(watch_uuid)

            # If less than 20 watches, queue synchronously for immediate feedback
            if len(watches_to_queue) < 20:
                # Get already queued/running UUIDs once (efficient)
                queued_uuids = set(update_q.get_queued_uuids())
                running_uuids = set(worker_pool.get_running_uuids())

                # Filter out watches that are already queued or running
                watches_to_queue_filtered = []
                for watch_uuid in watches_to_queue:
                    if watch_uuid not in queued_uuids and watch_uuid not in running_uuids:
                        watches_to_queue_filtered.append(watch_uuid)

                # Queue only the filtered watches
                for watch_uuid in watches_to_queue_filtered:
                    worker_pool.queue_item_async_safe(update_q, queuedWatchMetaData.PrioritizedItem(priority=1, item={'uuid': watch_uuid}))

                # Provide feedback about skipped watches
                skipped_count = len(watches_to_queue) - len(watches_to_queue_filtered)
                if skipped_count > 0:
                    flash(gettext("Queued {count} watches for rechecking ({skipped_count} already queued or running).").format(
                        count=len(watches_to_queue_filtered), skipped_count=skipped_count))
                else:
                    if len(watches_to_queue_filtered) == 1:
                        flash(gettext("Queued 1 watch for rechecking."))
                    else:
                        flash(gettext("Queued {} watches for rechecking.").format(len(watches_to_queue_filtered)))
            else:
                # 20+ watches - queue in background thread to avoid blocking HTTP response
                # Capture queued/running state before background thread
                queued_uuids = set(update_q.get_queued_uuids())
                running_uuids = set(worker_pool.get_running_uuids())

