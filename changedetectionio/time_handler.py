import os
from functools import lru_cache

from enum import IntEnum


def default_timezone_name(configured=None):
    """
    Resolve the scheduler's default IANA timezone name. Never returns None/''.

    `scheduler_timezone_default` is initialised to None in model/App.py, so the
    key always EXISTS with a None value. That makes the common idiom

        settings['application'].get('scheduler_timezone_default', os.getenv('TZ', 'UTC'))

    silently return None - dict.get() only falls back when the key is absent,
    not when its value is None. The None then reaches is_within_schedule(),
    which does `tz_name.strip()` and raises AttributeError.

    Args:
        configured: the stored setting value (may be None or empty)

    Returns:
        str: a non-empty timezone name, falling back to $TZ then 'UTC'
    """
    return (configured or os.getenv('TZ') or 'UTC').strip() or 'UTC'


class Weekday(IntEnum):
    """Enumeration for days of the week."""
    Monday = 0
    Tuesday = 1
    Wednesday = 2
    Thursday = 3
    Friday = 4
    Saturday = 5
    Sunday = 6

