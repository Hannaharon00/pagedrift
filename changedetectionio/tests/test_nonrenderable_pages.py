#!/usr/bin/env python3

from flask import url_for
from .util import set_original_response, set_modified_response, live_server_setup, wait_for_all_checks, delete_all_watches
import time
import os


def set_nonrenderable_response(datastore_path):
    test_return_data = """<html>
    <head><title>modified head title</title></head>
    <!-- like when some angular app was broken and doesnt render or whatever -->
    <body>
     </body>
     </html>
    """
    with open(os.path.join(datastore_path, "endpoint-content.txt"), "w") as f:
        f.write(test_return_data)
    time.sleep(1)

    return None

def set_zero_byte_response(datastore_path):
    with open(os.path.join(datastore_path, "endpoint-content.txt"), "w") as f:
        f.write("")
    time.sleep(1)
    return None

