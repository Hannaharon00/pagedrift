#!/usr/bin/env python3

"""
Comprehensive tests for time_handler module refactored to use arrow.

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

    def test_duration_60_minutes(self):
        """Test that duration of 60 minutes works correctly."""
        timezone_str = 'UTC'
        test_time = arrow.get('2024-01-01 12:30:00', 'YYYY-MM-DD HH:mm:ss').replace(tzinfo=timezone_str)
        day_of_week = test_time.format('dddd')

        with unittest.mock.patch('arrow.now', return_value=test_time):
            result = time_handler.am_i_inside_time(
                day_of_week=day_of_week,
                time_str="12:00",
                timezone_str=timezone_str,
                duration=60  # Exactly 60 minutes
            )
            self.assertTrue(result, "60-minute duration should work")

    def test_duration_at_exact_end_minute(self):
        """Test at exact end of 60-minute window."""
        timezone_str = 'UTC'
        # Exactly 13:00 (end of 12:00 + 60 minutes)
        test_time = arrow.get('2024-01-01 13:00:00', 'YYYY-MM-DD HH:mm:ss').replace(tzinfo=timezone_str)
        day_of_week = test_time.format('dddd')

        with unittest.mock.patch('arrow.now', return_value=test_time):
            result = time_handler.am_i_inside_time(
                day_of_week=day_of_week,
                time_str="12:00",
                timezone_str=timezone_str,
                duration=60
            )
            self.assertTrue(result, "Should include exact end minute")

    def test_one_second_after_schedule_ends(self):
        """Test one second after schedule should end."""
        timezone_str = 'UTC'
        # 13:00:01 (one second after 12:00 + 60 minutes)
        test_time = arrow.get('2024-01-01 13:00:01', 'YYYY-MM-DD HH:mm:ss').replace(tzinfo=timezone_str)
        day_of_week = test_time.format('dddd')

        with unittest.mock.patch('arrow.now', return_value=test_time):
            result = time_handler.am_i_inside_time(
                day_of_week=day_of_week,
                time_str="12:00",
                timezone_str=timezone_str,
                duration=60
            )
            self.assertFalse(result, "Should be False one second after schedule ends")

    def test_multi_day_schedule(self):
        """Test schedule longer than 24 hours (48 hours)."""
        timezone_str = 'UTC'
        # Tuesday 12:00 (36 hours after Monday 00:00)
        test_time = arrow.get('2024-01-02 12:00:00', 'YYYY-MM-DD HH:mm:ss').replace(tzinfo=timezone_str)
        monday = test_time.shift(days=-1).format('dddd')

        with unittest.mock.patch('arrow.now', return_value=test_time):
            result = time_handler.am_i_inside_time(
                day_of_week=monday,
                time_str="00:00",
                timezone_str=timezone_str,
                duration=2880  # 48 hours
            )
            self.assertTrue(result, "Should support multi-day schedules")

    def test_schedule_one_minute_duration(self):
        """Test very short 1-minute schedule."""
        timezone_str = 'UTC'
        test_time = arrow.get('2024-01-01 12:00:30', 'YYYY-MM-DD HH:mm:ss').replace(tzinfo=timezone_str)
        day_of_week = test_time.format('dddd')

        with unittest.mock.patch('arrow.now', return_value=test_time):
            result = time_handler.am_i_inside_time(
                day_of_week=day_of_week,
                time_str="12:00",
                timezone_str=timezone_str,
                duration=1  # Just 1 minute
            )
            self.assertTrue(result, "1-minute schedule should work")

    def test_schedule_at_exact_start_time(self):
        """Test at exact start time (00:00:00.000000)."""
        timezone_str = 'UTC'
        test_time = arrow.get('2024-01-01 12:00:00.000000', 'YYYY-MM-DD HH:mm:ss.SSSSSS').replace(tzinfo=timezone_str)
        day_of_week = test_time.format('dddd')

        with unittest.mock.patch('arrow.now', return_value=test_time):
            result = time_handler.am_i_inside_time(
                day_of_week=day_of_week,
                time_str="12:00",
                timezone_str=timezone_str,
                duration=30
            )
            self.assertTrue(result, "Should include exact start time")

    def test_schedule_one_microsecond_before_start(self):
        """Test one microsecond before schedule starts."""
        timezone_str = 'UTC'
        test_time = arrow.get('2024-01-01 11:59:59.999999', 'YYYY-MM-DD HH:mm:ss.SSSSSS').replace(tzinfo=timezone_str)
        day_of_week = test_time.format('dddd')

        with unittest.mock.patch('arrow.now', return_value=test_time):
            result = time_handler.am_i_inside_time(
                day_of_week=day_of_week,
                time_str="12:00",
                timezone_str=timezone_str,
                duration=30
            )
            self.assertFalse(result, "Should not include time before start")


