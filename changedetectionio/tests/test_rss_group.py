#!/usr/bin/env python3

import time
from flask import url_for
from .util import live_server_setup, wait_for_all_checks, wait_for_watch_history, extract_rss_token_from_UI, get_UUID_for_tag_name, delete_all_watches
import os


def set_original_response(datastore_path):
    test_return_data = """<html>
       <body>
     Some initial text<br>
     <p>Watch 1 content</p>
     <p>Watch 2 content</p>
     </body>
     </html>
    """

    with open(os.path.join(datastore_path, "endpoint-content.txt"), "w") as f:
        f.write(test_return_data)
    return None


