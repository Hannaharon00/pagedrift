#!/usr/bin/env python3

import time
from flask import url_for
from .util import live_server_setup, wait_for_all_checks
import os


def set_original_ignore_response(datastore_path):
    test_return_data = """<html>
       <body>
     Some initial text<br>
     <p>Which is across multiple lines</p>
     <br>
     So let's see what happens.  <br>
     and more<br>
     </body>
     </html>

    """

    with open(os.path.join(datastore_path, "endpoint-content.txt"), "w") as f:
        f.write(test_return_data)


def set_modified_original_ignore_response(datastore_path):
    test_return_data = """<html>
       <body>
     Some NEW nice initial text<br>
     <p>Which is across multiple lines</p>
     <br>
     So let's see what happens.  <br>
     and more<br>
     </body>
     </html>

    """

    with open(os.path.join(datastore_path, "endpoint-content.txt"), "w") as f:
        f.write(test_return_data)


