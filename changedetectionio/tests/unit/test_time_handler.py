#!/usr/bin/env python3

Run from project root:
python3 -m pytest changedetectionio/tests/unit/test_time_handler.py -v
"""

import unittest
import unittest.mock
import arrow
from changedetectionio import time_handler


class TestAmIInsideTime(unittest.TestCase):
    """Tests for the am_i_inside_time function."""

    def test_current_time_within_schedule(self):
        """Test that current time is detected as within schedule."""
        # Get current time in a specific timezone
        timezone_str = 'Europe/Berlin'
        now = arrow.now(timezone_str)
        day_of_week = now.format('dddd')
        time_str = now.format('HH:00')  # Current hour, 0 minutes
        duration = 60  # 60 minutes

        result = time_handler.am_i_inside_time(
            day_of_week=day_of_week,
            time_str=time_str,
            timezone_str=timezone_str,
            duration=duration
        )

        self.assertTrue(result, f"Current time should be within {duration} minute window starting at {time_str}")

    def test_current_time_outside_schedule(self):
        """Test that time in the past is not within current schedule."""
        timezone_str = 'Europe/Berlin'
        # Get yesterday's date
        yesterday = arrow.now(timezone_str).shift(days=-1)
        day_of_week = yesterday.format('dddd')
        time_str = yesterday.format('HH:mm')
        duration = 30  # Only 30 minutes

        result = time_handler.am_i_inside_time(
            day_of_week=day_of_week,
            time_str=time_str,
            timezone_str=timezone_str,
            duration=duration
        )

        self.assertFalse(result, "Yesterday's time should not be within current schedule")

    def test_timezone_pacific_within_schedule(self):
        """Test with US/Pacific timezone."""
        timezone_str = 'US/Pacific'
        now = arrow.now(timezone_str)
        day_of_week = now.format('dddd')
        time_str = now.format('HH:00')
        duration = 120  # 2 hours

        result = time_handler.am_i_inside_time(
            day_of_week=day_of_week,
            time_str=time_str,
            timezone_str=timezone_str,
            duration=duration
        )

