import queue
import asyncio
from blinker import signal
from loguru import logger


class NotificationQueue(queue.Queue):
    """
    Extended Queue that sends a 'notification_event' signal when notifications are added.
    
    This class extends the standard Queue and adds a signal emission after a notification
    is put into the queue. The signal includes the watch UUID if available.
    """
    
    def __init__(self, maxsize=0):
        super().__init__(maxsize)
        try:
            self.notification_event_signal = signal('notification_event')
        except Exception as e:
            logger.critical(f"Exception creating notification_event signal: {e}")

    def put(self, item, block=True, timeout=None):
        # Call the parent's put method first
        super().put(item, block, timeout)
        
        # After putting the notification in the queue, emit signal with watch UUID
        try:
            if self.notification_event_signal and isinstance(item, dict):
                watch_uuid = item.get('uuid')
                if watch_uuid:
                    # Send the notification_event signal with the watch UUID
                    self.notification_event_signal.send(watch_uuid=watch_uuid)
                    logger.trace(f"NotificationQueue: Emitted notification_event signal for watch UUID {watch_uuid}")
                else:
                    # Send signal without UUID for system notifications
                    self.notification_event_signal.send()
                    logger.trace("NotificationQueue: Emitted notification_event signal for system notification")
        except Exception as e:
            logger.error(f"Exception emitting notification_event signal: {e}")

class SignalPriorityQueue(queue.PriorityQueue):
    """
    Extended PriorityQueue that sends a signal when items with a UUID are added.
    
    This class extends the standard PriorityQueue and adds a signal emission
    after an item is put into the queue. If the item contains a UUID, the signal
    is sent with that UUID as a parameter.
    """
    
