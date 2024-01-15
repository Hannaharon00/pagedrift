#!/usr/bin/env python3
"""Test suite for the render/not render anchor tag content functionality"""

import time
from flask import url_for
from .util import live_server_setup, wait_for_all_checks, delete_all_watches
import os


def set_original_ignore_response(datastore_path):
    test_return_data = """<html>
       <body>
     Some initial text<br>
     <a href="/original_link"> Some More Text </a>
     <br>
     So let's see what happens.  <br>
     </body>
     </html>
    """

    with open(os.path.join(datastore_path, "endpoint-content.txt"), "w") as f:
        f.write(test_return_data)


# Should be the same as set_original_ignore_response(datastore_path=datastore_path) but with a different
# link
def set_modified_ignore_response(datastore_path):
    test_return_data = """<html>
       <body>
     Some initial text<br>
     <a href="/modified_link"> Some More Text </a>
     <br>
     So let's see what happens.  <br>
     </body>
     </html>
    """

    with open(os.path.join(datastore_path, "endpoint-content.txt"), "w") as f:
        f.write(test_return_data)

