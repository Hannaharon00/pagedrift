#!/usr/bin/env python3

from flask import url_for
from .util import set_original_response, set_modified_response, live_server_setup, wait_for_all_checks, delete_all_watches
from ..forms import REQUIRE_ATLEAST_ONE_TIME_PART_WHEN_NOT_GLOBAL_DEFAULT, REQUIRE_ATLEAST_ONE_TIME_PART_MESSAGE_DEFAULT


def test_recheck_time_field_validation_global_settings(client, live_server, measure_memory_usage, datastore_path):
    """
    Tests that the global settings time field has atleast one value for week/day/hours/minute/seconds etc entered
    class globalSettingsRequestForm(Form):
        time_between_check = RequiredFormField(TimeBetweenCheckForm)
    """
    res = client.post(
        url_for("settings.settings_page"),
        data={
              "requests-time_between_check-weeks": '',
              "requests-time_between_check-days": '',
              "requests-time_between_check-hours": '',
              "requests-time_between_check-minutes": '',
              "requests-time_between_check-seconds": '',
              },
        follow_redirects=True
    )


    assert REQUIRE_ATLEAST_ONE_TIME_PART_MESSAGE_DEFAULT.encode('utf-8') in res.data
    delete_all_watches(client)


def test_recheck_time_field_validation_single_watch(client, live_server, measure_memory_usage, datastore_path):
    """
    Tests that the global settings time field has atleast one value for week/day/hours/minute/seconds etc entered
    class globalSettingsRequestForm(Form):
        time_between_check = RequiredFormField(TimeBetweenCheckForm)
    """
    test_url = url_for('test_endpoint', _external=True)

    # Add our URL to the import page
    uuid = client.application.config.get('DATASTORE').add_watch(url=test_url)
    client.post(url_for("ui.form_watch_checknow"), follow_redirects=True)

    res = client.post(
        url_for("ui.ui_edit.edit_page", uuid="first"),
        data={
            "url": test_url,
            'fetch_backend': "html_requests",
            "time_between_check_use_default": "",  # OFF
            "time_between_check-weeks": '',
            "time_between_check-days": '',
            "time_between_check-hours": '',
            "time_between_check-minutes": '',
            "time_between_check-seconds": '',
        },
        follow_redirects=True
    )


    assert REQUIRE_ATLEAST_ONE_TIME_PART_WHEN_NOT_GLOBAL_DEFAULT.encode('utf-8') in res.data

    # Now set some time
    res = client.post(
        url_for("ui.ui_edit.edit_page", uuid="first"),
        data={
            "url": test_url,
            'fetch_backend': "html_requests",
            "time_between_check_use_default": "",  # OFF
            "time_between_check-weeks": '',
            "time_between_check-days": '',
            "time_between_check-hours": '',
            "time_between_check-minutes": '5',
            "time_between_check-seconds": '',
        },
        follow_redirects=True
    )

    assert b"Updated watch." in res.data
    assert REQUIRE_ATLEAST_ONE_TIME_PART_WHEN_NOT_GLOBAL_DEFAULT.encode('utf-8') not in res.data

    # Now set to use defaults
    res = client.post(
        url_for("ui.ui_edit.edit_page", uuid="first"),
        data={
            "url": test_url,
            'fetch_backend': "html_requests",
            "time_between_check_use_default": "y",  # ON YES
            "time_between_check-weeks": '',
            "time_between_check-days": '',
            "time_between_check-hours": '',
            "time_between_check-minutes": '',
            "time_between_check-seconds": '',
        },
        follow_redirects=True
    )

    assert b"Updated watch." in res.data
    assert REQUIRE_ATLEAST_ONE_TIME_PART_WHEN_NOT_GLOBAL_DEFAULT.encode('utf-8') not in res.data
    delete_all_watches(client)

