#!/usr/bin/env python3

"""
Regression tests for two scheduler/timezone bugs.

BUG 1 - edit page returned HTTP 500
  ui/edit.py resolved the default timezone with
      .get('scheduler_timezone_default', os.getenv('TZ', 'UTC'))
  but App.py initialises that key to None, so the key EXISTS and dict.get()
  never uses its fallback. None reached is_within_schedule(), which does
  `tz_name.strip()` -> AttributeError -> the handler did `return False` -> Flask
  raised TypeError ("view function did not return a valid response ... it was a
  bool") -> HTTP 500. The watch was actually saved, so the user saw a 500 on a
  successful save.

BUG 2 - ticker thread died silently
  Same root cause, but flask_app.py's `return False` was inside the ticker
  thread's main loop. One watch with an unresolvable timezone ended the thread
  and NO watch was ever checked again until restart, with the process still up.

Run:  pytest changedetectionio/tests/test_scheduler_timezone_regressions.py
"""

import time

from flask import url_for

from .util import live_server_setup, wait_for_all_checks, set_original_response


DAYS = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']


def _schedule_form(url, enabled_days=('monday',)):
    data = {
        "url": url,
        "fetch_backend": "html_requests",
        "time_between_check_use_default": "",
        "time_between_check-seconds": 1,
        "time_schedule_limit-enabled": 'y',
    }
    for day in DAYS:
        data[f"time_schedule_limit-{day}-start_time"] = "00:00"
        data[f"time_schedule_limit-{day}-duration-hours"] = 24
        data[f"time_schedule_limit-{day}-duration-minutes"] = 0
        if day in enabled_days:
            data[f"time_schedule_limit-{day}-enabled"] = 'y'
    return data


def _full_schedule(enabled=True, timezone=None):
    sched = {'enabled': True}
    for day in DAYS:
        sched[day] = {'enabled': enabled, 'start_time': '00:00',
                      'duration': {'hours': '24', 'minutes': '00'}}
    if timezone is not None:
        sched['timezone'] = timezone
    return sched


def test_edit_page_saves_when_no_default_timezone_configured(client, live_server, measure_memory_usage, datastore_path):
    """BUG 1: enabling the scheduler with scheduler_timezone_default unset 500'd."""
    set_original_response(datastore_path=datastore_path)
    test_url = url_for('test_endpoint', _external=True)
    datastore = live_server.app.config['DATASTORE']

    # This is the default state from model/App.py - key present, value None.
    datastore.data['settings']['application']['scheduler_timezone_default'] = None

    uuid = datastore.add_watch(url=test_url)
    wait_for_all_checks(client)

    res = client.post(
        url_for("ui.ui_edit.edit_page", uuid=uuid),
        data=_schedule_form(test_url),
        follow_redirects=True,
    )

    assert res.status_code == 200, f"expected 200, got {res.status_code}"
    assert b"Internal Server Error" not in res.data
    assert b"Updated watch." in res.data

    # and the schedule really was saved
    assert datastore.data['watching'][uuid]['time_schedule_limit']['enabled'] is True


def test_edit_page_saves_with_unresolvable_timezone(client, live_server, measure_memory_usage, datastore_path):
    """A garbage timezone must degrade to 'skip the recheck', not 500."""
    set_original_response(datastore_path=datastore_path)
    test_url = url_for('test_endpoint', _external=True)
    datastore = live_server.app.config['DATASTORE']
    datastore.data['settings']['application']['scheduler_timezone_default'] = 'Not/ARealZone'

    uuid = datastore.add_watch(url=test_url)
    wait_for_all_checks(client)

    res = client.post(
        url_for("ui.ui_edit.edit_page", uuid=uuid),
        data=_schedule_form(test_url),
        follow_redirects=True,
    )
    assert res.status_code == 200, f"expected 200, got {res.status_code}"
    assert b"Updated watch." in res.data


def test_ticker_survives_a_watch_with_a_broken_timezone(client, live_server, measure_memory_usage, datastore_path):
    """
    BUG 2: one bad watch used to kill the ticker thread, stopping every other
    watch. Prove a healthy watch still gets checked alongside a broken one.
    """
    set_original_response(datastore_path=datastore_path)
    test_url = url_for('test_endpoint', _external=True)
    datastore = live_server.app.config['DATASTORE']
    datastore.data['settings']['application']['scheduler_timezone_default'] = None

    broken_uuid = datastore.add_watch(url=test_url)
    healthy_uuid = datastore.add_watch(url=test_url)
    wait_for_all_checks(client)

    # Broken watch: scheduler on, timezone that arrow cannot resolve
    datastore.data['watching'][broken_uuid]['time_between_check_use_default'] = False
    datastore.data['watching'][broken_uuid]['time_schedule_limit'] = _full_schedule(
        timezone='Not/ARealZone'
    )

    # Healthy watch: no schedule limit, short interval so the ticker must pick it up
    datastore.data['watching'][healthy_uuid]['time_between_check_use_default'] = False
    datastore.data['watching'][healthy_uuid]['time_between_check'] = {
        'weeks': None, 'days': None, 'hours': None, 'minutes': None, 'seconds': 2
    }
    before = datastore.data['watching'][healthy_uuid]['last_checked']

    # Give the ticker several passes over the broken watch
    deadline = time.time() + 30
    while time.time() < deadline:
        if datastore.data['watching'][healthy_uuid]['last_checked'] != before:
            break
        time.sleep(0.5)

    assert datastore.data['watching'][healthy_uuid]['last_checked'] != before, (
        "the healthy watch was never rechecked - the ticker thread most likely "
        "died on the broken watch's timezone"
    )


