#!/usr/bin/env python3

import time
from flask import url_for
from .util import live_server_setup, wait_for_all_checks, delete_all_watches
import os

from ..html_tools import *


def set_original_response(datastore_path):
    test_return_data = """<html>
       <body>
     Some initial text<br>
     <p>Which is across multiple lines</p>
     <br>
     So let's see what happens.  <br>
     <div id="sametext">Some text thats the same</div>
     <div class="changetext">Some text that will change</div>     
     </body>
     </html>
    """

    with open(os.path.join(datastore_path, "endpoint-content.txt"), "w") as f:
        f.write(test_return_data)
    return None


def set_modified_response(datastore_path):
    test_return_data = """<html>
       <body>
     Some initial text<br>
     <p>which has this one new line</p>
     <br>
     So let's see what happens.  <br>
     <div id="sametext">Some text thats the same</div>
     <div class="changetext">Some text that did change ( 1000 online <br> 80 guests<br>  2000 online )</div>
     <div class="changetext">SomeCase insensitive 3456</div>
     </body>
     </html>
    """

    with open(os.path.join(datastore_path, "endpoint-content.txt"), "w") as f:
        f.write(test_return_data)

    return None


# def test_setup(client, live_server, measure_memory_usage, datastore_path):
   #  live_server_setup(live_server) # Setup on conftest per function

def test_check_filter_multiline(client, live_server, measure_memory_usage, datastore_path):
   ##  live_server_setup(live_server) # Setup on conftest per function
    set_multiline_response(datastore_path=datastore_path)

    # Add our URL to the import page
    test_url = url_for('test_endpoint', _external=True)
    uuid = client.application.config.get('DATASTORE').add_watch(url=test_url)
    client.post(url_for("ui.form_watch_checknow"), follow_redirects=True)

    wait_for_all_checks(client)

    # Goto the edit page, add our ignore text
    # Add our URL to the import page
    res = client.post(
        url_for("ui.ui_edit.edit_page", uuid="first"),
        data={"include_filters": '',
              # Test a regex and a plaintext
              'extract_text': '/something.+?6 billion.+?lines/si\r\nand this should be',
              "url": test_url,
              "tags": "",
              "headers": "",
              'fetch_backend': "html_requests",
              "time_between_check_use_default": "y"
              },
        follow_redirects=True
    )

    assert b"Updated watch." in res.data
    wait_for_all_checks(client)

    res = client.get(url_for("watchlist.index"))

    # Issue 1828
    assert b'not at the start of the expression' not in res.data

    res = client.get(
        url_for("ui.ui_preview.preview_page", uuid="first"),
        follow_redirects=True
    )
    # Plaintext that doesnt look like a regex should match also
    assert b'and this should be' in res.data

    assert b'Something' in res.data
    assert b'across 6 billion multiple' in res.data
    assert b'lines' in res.data

    # but the last one, which also says 'lines' shouldnt be here (non-greedy match checking)
    assert b'aaand something lines' not in res.data

