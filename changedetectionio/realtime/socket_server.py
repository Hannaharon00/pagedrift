from flask_socketio import SocketIO
from flask_babel import gettext

import time
import os
from loguru import logger
from blinker import signal

from changedetectionio import strtobool


class SignalHandler:
    """A standalone class to receive signals"""

    def __init__(self, socketio_instance, datastore):
        self.socketio_instance = socketio_instance
        self.datastore = datastore

        # Connect to the watch_check_update signal
        from changedetectionio.flask_app import watch_check_update as wcc
        wcc.connect(self.handle_signal, weak=False)
        #        logger.info("SignalHandler: Connected to signal from direct import")

        # Connect to the queue_length signal
        queue_length_signal = signal('queue_length')
        queue_length_signal.connect(self.handle_queue_length, weak=False)
        #       logger.info("SignalHandler: Connected to queue_length signal")

        watch_delete_signal = signal('watch_deleted')
        watch_delete_signal.connect(self.handle_deleted_signal, weak=False)

        watch_favicon_bumped_signal = signal('watch_favicon_bump')
        watch_favicon_bumped_signal.connect(self.handle_watch_bumped_favicon_signal, weak=False)

        watch_small_status_comment_signal = signal('watch_small_status_comment')
        watch_small_status_comment_signal.connect(self.handle_watch_small_status_update, weak=False)

        # Connect to the notification_event signal
        notification_event_signal = signal('notification_event')
        notification_event_signal.connect(self.handle_notification_event, weak=False)
        logger.info("SignalHandler: Connected to notification_event signal")

        # One-shot stats refresh for bulk operations that deliberately skip the per-watch
        # signal (see set_last_viewed(send_signal=False)) — n signals would mean n full
        # rescans of every watch plus 3n broadcasts.
        general_stats_signal = signal('general_stats_update')
        general_stats_signal.connect(self.handle_general_stats_update, weak=False)


    def handle_general_stats_update(self, *args, **kwargs):
        """Emit the global counters once, without touching any individual row.

        Sent after a bulk operation. The tab that triggered it is usually reloading anyway;
        this is for OTHER open tabs so their unread/error counters don't sit stale.
        Note their ROWS still keep a stale 'unviewed' class until the row resync lands —
        tracked separately, this only fixes the counters.
        """
        try:
            errored_count = sum(1 for w in self.datastore.data['watching'].values() if w.get('last_error'))
            self.socketio_instance.emit("general_stats_update", {
                'count_errors': errored_count,
                'unread_changes_count': self.datastore.unread_changes_count,
            })
            logger.trace("Socket.IO: Emitted one-shot general_stats_update")
        except Exception as e:
            logger.error(f"Socket.IO error in handle_general_stats_update: {str(e)}")

    def handle_watch_small_status_update(self, *args, **kwargs):
        """Small simple status update, for example 'Connecting...'"""
        watch_uuid = kwargs.get('watch_uuid')
        status = kwargs.get('status')

        if watch_uuid and status:
            logger.debug(f"Socket.IO: Received watch small status update '{status}' for UUID {watch_uuid}")
            # Emit the status update to all connected clients
            self.socketio_instance.emit("watch_small_status_comment", {
                "uuid": watch_uuid,
                "status": status,
                "event_timestamp": time.time()
            })



    def handle_signal(self, *args, **kwargs):
        logger.trace(f"SignalHandler: Signal received with {len(args)} args and {len(kwargs)} kwargs")
        # Safely extract the watch UUID from kwargs
        watch_uuid = kwargs.get('watch_uuid')
        app_context = kwargs.get('app_context')

        if watch_uuid:
            # Get the watch object from the datastore
            watch = self.datastore.data['watching'].get(watch_uuid)
            if watch:
                if app_context:
                    # note
                    with app_context.app_context():
                        with app_context.test_request_context():
                            # Forward to handle_watch_update with the watch parameter
                            handle_watch_update(self.socketio_instance, watch=watch, datastore=self.datastore)
                else:
                    handle_watch_update(self.socketio_instance, watch=watch, datastore=self.datastore)

                logger.trace(f"Signal handler processed watch UUID {watch_uuid}")
            else:
                logger.warning(f"Watch UUID {watch_uuid} not found in datastore")

    def handle_watch_bumped_favicon_signal(self, *args, **kwargs):
        watch_uuid = kwargs.get('watch_uuid')
        if watch_uuid:
            # Emit the queue size to all connected clients
            self.socketio_instance.emit("watch_bumped_favicon", {
                "uuid": watch_uuid,
                "event_timestamp": time.time()
            })
        logger.debug(f"Watch UUID {watch_uuid} got its favicon updated")

    def handle_deleted_signal(self, *args, **kwargs):
        watch_uuid = kwargs.get('watch_uuid')
        if watch_uuid:
            # Emit the queue size to all connected clients
            self.socketio_instance.emit("watch_deleted", {
                "uuid": watch_uuid,
                "event_timestamp": time.time()
            })
        logger.debug(f"Watch UUID {watch_uuid} was deleted")

    def handle_queue_length(self, *args, **kwargs):
        """Handle queue_length signal and emit to all clients"""
        try:
            queue_length = kwargs.get('length', 0)
            logger.debug(f"SignalHandler: Queue length update received: {queue_length}")

            # Emit the queue size to all connected clients
            self.socketio_instance.emit("queue_size", {
                "q_length": queue_length,
                "event_timestamp": time.time()
            })

        except Exception as e:
            logger.error(f"Socket.IO error in handle_queue_length: {str(e)}")

    def handle_notification_event(self, *args, **kwargs):
        """Handle notification_event signal and emit to all clients"""
        try:
            watch_uuid = kwargs.get('watch_uuid')
            logger.debug(f"SignalHandler: Notification event received for watch UUID: {watch_uuid}")

            # Emit the notification event to all connected clients
            self.socketio_instance.emit("notification_event", {
                "watch_uuid": watch_uuid,
                "event_timestamp": time.time()
            })

            logger.trace(f"Socket.IO: Emitted notification_event for watch UUID {watch_uuid}")

        except Exception as e:
            logger.error(f"Socket.IO error in handle_notification_event: {str(e)}")



