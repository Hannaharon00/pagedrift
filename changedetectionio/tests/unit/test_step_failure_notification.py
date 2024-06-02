"""
Unit test for send_step_failure_notification regression.

Before the fix, line 499 called self._check_cascading_vars('notification_format', watch)
which raises AttributeError because _check_cascading_vars is a module-level function,
not a method of NotificationService.
"""

import queue
from unittest.mock import MagicMock


def _make_datastore(watch_uuid, notification_url):
    """Minimal datastore mock that NotificationService and _check_cascading_vars need."""
    watch = MagicMock()
    watch.get = lambda key, default=None: {
        'uuid': watch_uuid,
        'url': 'https://example.com',
        'notification_urls': [notification_url],
        'notification_format': '',
        'notification_muted': False,
    }.get(key, default)
    watch.__getitem__ = lambda self, key: watch.get(key)

    datastore = MagicMock()
    datastore.data = {
        'watching': {watch_uuid: watch},
        'settings': {
            'application': {
                'notification_urls': [],
                'notification_format': 'text',
                'filter_failure_notification_threshold_attempts': 3,
            }
        }
    }
    datastore.get_all_tags_for_watch.return_value = {}
    return datastore, watch


