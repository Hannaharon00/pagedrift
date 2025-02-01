#!/usr/bin/env python3
import json
import time
import os

from flask import url_for
from .util import live_server_setup, wait_for_all_checks, delete_all_watches
from ..model import CONDITIONS_MATCH_LOGIC_DEFAULT


def set_original_response(datastore_path, number="50"):
    test_return_data = f"""<html>
       <body>
     <h1>Test Page for Conditions</h1>
     <p>This page contains a number that will be tested with conditions.</p>
     <div class="number-container">Current value: {number}</div>
     </body>
     </html>
    """

    with open(os.path.join(datastore_path, "endpoint-content.txt"), "w") as f:
        f.write(test_return_data)

def set_number_in_range_response(datastore_path, number="75"):
    test_return_data = f"""<html>
       <body>
     <h1>Test Page for Conditions</h1>
     <p>This page contains a number that will be tested with conditions.</p>
     <div class="number-container">Current value: {number}</div>
     </body>
     </html>
    """

    with open(os.path.join(datastore_path, "endpoint-content.txt"), "w") as f:
        f.write(test_return_data)

def set_number_out_of_range_response(datastore_path, number="150"):
    test_return_data = f"""<html>
       <body>
     <h1>Test Page for Conditions</h1>
     <p>This page contains a number that will be tested with conditions.</p>
     <div class="number-container">Current value: {number}</div>
     </body>
     </html>
    """

    with open(os.path.join(datastore_path, "endpoint-content.txt"), "w") as f:
        f.write(test_return_data)


# The 'validate' button next to each rule row
def test_condition_validate_rule_row(client, live_server, measure_memory_usage, datastore_path):

    set_original_response(datastore_path=datastore_path, number="50")

    test_url = url_for('test_endpoint', _external=True)

    # Add our URL to the import page
    uuid = client.application.config.get('DATASTORE').add_watch(url=test_url)
    client.post(url_for("ui.form_watch_checknow"), follow_redirects=True)
    wait_for_all_checks(client)


    # the front end submits the current form state which should override the watch in a temporary copy
    res = client.post(
        url_for("conditions.verify_condition_single_rule", watch_uuid=uuid),  # Base URL
        query_string={"rule": json.dumps({"field": "extracted_number", "operator": "==", "value": "50"})},
        data={'include_filter': ""},
        follow_redirects=True
    )
    assert res.status_code == 200
    assert b'success' in res.data

    # Now a number that does not equal what is found in the last fetch
    res = client.post(
        url_for("conditions.verify_condition_single_rule", watch_uuid=uuid),  # Base URL
        query_string={"rule": json.dumps({"field": "extracted_number", "operator": "==", "value": "111111"})},
        data={'include_filter': ""},
        follow_redirects=True
    )
    assert res.status_code == 200
    assert b'false' in res.data

    # Now custom filter that exists
    res = client.post(
        url_for("conditions.verify_condition_single_rule", watch_uuid=uuid),  # Base URL
        query_string={"rule": json.dumps({"field": "extracted_number", "operator": "==", "value": "50"})},
        data={'include_filter': ".number-container"},
        follow_redirects=True
    )
    assert res.status_code == 200
    assert b'success' in res.data

    # Now custom filter that DOES NOT exists
    res = client.post(
        url_for("conditions.verify_condition_single_rule", watch_uuid=uuid),  # Base URL
        query_string={"rule": json.dumps({"field": "extracted_number", "operator": "==", "value": "50"})},
        data={'include_filters': ".NOT-container"},
        follow_redirects=True
    )
    assert res.status_code == 200
    assert b'false' in res.data

    delete_all_watches(client)


# If there was only a change in the whitespacing, then we shouldnt have a change detected
def test_wordcount_conditions_plugin(client, live_server, measure_memory_usage, datastore_path):
    

    test_return_data = """<html>
       <body>
     Some initial text<br>
     <p>Which is across multiple lines</p>
     <br>
     So let's see what happens.  <br>
     </body>
     </html>
    """

    with open(os.path.join(datastore_path, "endpoint-content.txt"), "w") as f:
        f.write(test_return_data)

    # Add our URL to the import page
    test_url = url_for('test_endpoint', _external=True)
    uuid = client.application.config.get('DATASTORE').add_watch(url=test_url)
    client.post(url_for("ui.form_watch_checknow"), follow_redirects=True)

    # Give the thread time to pick it up
    wait_for_all_checks(client)

    # Check it saved
    res = client.get(
        url_for("ui.ui_edit.edit_page", uuid=uuid),
    )

    # Assert the word count is counted correctly
    assert b'<td>13</td>' in res.data
    delete_all_watches(client)

