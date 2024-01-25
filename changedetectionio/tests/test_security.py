import io
import os
import re
import time
import pytest

from flask import url_for
from zipfile import ZipFile, ZIP_DEFLATED

from changedetectionio.tests.util import set_modified_response
from .util import live_server_setup, wait_for_all_checks, delete_all_watches
from .. import strtobool


def set_original_response(datastore_path):
    test_return_data = """<html>
    <head><title>head title</title></head>
    <body>
     Some initial text<br>
     <p>Which is across multiple lines</p>
     <br>
     So let's see what happens.  <br>
     <span class="foobar-detection" style='display:none'></span>
     </body>
     </html>
    """

    with open(os.path.join(datastore_path, "endpoint-content.txt"), "w") as f:
        f.write(test_return_data)
    return None


