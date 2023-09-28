#!/usr/bin/env python3

import time
import arrow
from flask import url_for
from .util import live_server_setup, wait_for_all_checks
from ..jinja2_custom import render


# def test_setup(client, live_server, measure_memory_usage, datastore_path):
   # #  live_server_setup(live_server) # Setup on conftest per function

def test_add_weekday(mocker):
    """Verify that added weekday offset can be parsed."""

    timezone = 'utc'
    currentDate = arrow.now(timezone)
    arrowNowMock = mocker.patch("arrow.now")
    arrowNowMock.return_value = currentDate
    finalRender = render(f"{{% now '{timezone}' + 'weekday=1' %}}")

    assert finalRender == currentDate.shift(weekday=1).strftime('%a, %d %b %Y %H:%M:%S')


def test_substract_time(environment):
    """Verify that substracted time offset can be parsed."""

    finalRender = render("{% now 'utc' - 'minutes=11' %}")

    assert finalRender == "Wed, 09 Dec 2015 23:22:01"


def test_offset_with_format(environment):
    """Verify that offset works together with datetime format."""

    finalRender = render(
        "{% now 'utc' - 'days=2,minutes=33,seconds=1', '%d %b %Y %H:%M:%S' %}"
    )

    assert finalRender == "07 Dec 2015 23:00:00"

def test_default_timezone_empty_string(environment):
    """Verify that empty timezone string uses the default timezone (UTC in test environment)."""

    # Empty string should use the default timezone which is 'UTC' (or from application settings)
    finalRender = render("{% now '' %}")

    # Should render with default format and UTC timezone (matches environment fixture)
    assert finalRender == "Wed, 09 Dec 2015 23:33:01"

def test_default_timezone_with_offset(environment):
    """Verify that empty timezone works with offset operations."""

    # Empty string with offset should use default timezone
    finalRender = render("{% now '' + 'hours=2', '%d %b %Y %H:%M:%S' %}")

    assert finalRender == "10 Dec 2015 01:33:01"

def test_default_timezone_subtraction(environment):
    """Verify that empty timezone works with subtraction offset."""

    finalRender = render("{% now '' - 'minutes=11' %}")

    assert finalRender == "Wed, 09 Dec 2015 23:22:01"

