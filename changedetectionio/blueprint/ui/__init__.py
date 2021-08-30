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

