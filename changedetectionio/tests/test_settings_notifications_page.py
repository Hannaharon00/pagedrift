#!/usr/bin/env python3
"""
Tests for the /settings/notifications page (separated from the main /settings
form in 2026). The notification config lives at
    datastore.data['settings']['application']['notification_*']
and is now edited via its own form + route. The main settings page must NOT
clobber those values when an unrelated section (workers, RSS, etc.) is saved,
because both pages mutate the same `application` dict.
"""

from flask import url_for

