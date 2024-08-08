#!/usr/bin/env python3

"""
Regression tests for the scheduler's default-timezone resolution.

The bug: model/App.py initialises 'scheduler_timezone_default' to None, so the
key ALWAYS EXISTS with a None value. Call sites used

    settings['application'].get('scheduler_timezone_default', os.getenv('TZ', 'UTC'))

which never reaches its fallback, because dict.get() only substitutes the
default when the key is ABSENT - not when its value is None. The resulting None
flowed into is_within_schedule(), which does `tz_name.strip()` and raised
AttributeError. That took out the edit page (HTTP 500) and, worse, the ticker
thread (which did `return False` inside its main loop and stopped scheduling
every watch until restart).

Run:  python3 -m unittest changedetectionio.tests.unit.test_scheduler_timezone_resolution
"""

import os
import unittest
from unittest.mock import patch

from changedetectionio.time_handler import default_timezone_name, is_within_schedule


class TestDefaultTimezoneName(unittest.TestCase):

    def test_none_falls_back_to_utc(self):
        """The exact bug: a present-but-None setting must not stay None."""
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop('TZ', None)
            self.assertEqual(default_timezone_name(None), 'UTC')

    def test_empty_string_falls_back(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop('TZ', None)
            self.assertEqual(default_timezone_name(''), 'UTC')
            self.assertEqual(default_timezone_name('   '), 'UTC')

    def test_configured_value_wins(self):
        self.assertEqual(default_timezone_name('Pacific/Kiritimati'), 'Pacific/Kiritimati')

    def test_configured_value_is_stripped(self):
        self.assertEqual(default_timezone_name('  Europe/Berlin  '), 'Europe/Berlin')

    def test_tz_env_used_when_unconfigured(self):
        with patch.dict(os.environ, {'TZ': 'Asia/Tokyo'}):
            self.assertEqual(default_timezone_name(None), 'Asia/Tokyo')

    def test_configured_beats_tz_env(self):
        with patch.dict(os.environ, {'TZ': 'Asia/Tokyo'}):
            self.assertEqual(default_timezone_name('Europe/Berlin'), 'Europe/Berlin')

    def test_never_returns_falsy(self):
        with patch.dict(os.environ, {'TZ': '   '}):
            self.assertEqual(default_timezone_name(None), 'UTC')
        for value in (None, '', '  ', 0, False, []):
            self.assertTrue(default_timezone_name(value),
                            f"default_timezone_name({value!r}) must never be falsy")

    def test_reproduces_the_original_crash(self):
        """Passing the un-resolved None straight through still raises - proving
        the resolver is what prevents it, not luck elsewhere."""
        schedule = {
            'enabled': True,
            'monday': {'enabled': True, 'start_time': '00:00',
                       'duration': {'hours': '24', 'minutes': '00'}},
        }
        with self.assertRaises(AttributeError):
            is_within_schedule(time_schedule_limit=schedule, default_tz=None)

        # ...and does not raise once resolved
        full = {'enabled': True}
        for day in ('monday', 'tuesday', 'wednesday', 'thursday',
                    'friday', 'saturday', 'sunday'):
            full[day] = {'enabled': True, 'start_time': '00:00',
                         'duration': {'hours': '24', 'minutes': '00'}}
        self.assertTrue(
            is_within_schedule(time_schedule_limit=full,
                               default_tz=default_timezone_name(None))
        )


