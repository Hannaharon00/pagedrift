#!/usr/bin/env python3

# https://www.reddit.com/r/selfhosted/comments/wa89kp/comment/ii3a4g7/?context=3
import os
import time
from flask import url_for
from .util import set_original_response, live_server_setup, wait_for_notification_endpoint_output
from changedetectionio.model import App


def set_response_without_filter(datastore_path):
    test_return_data = """<html>
       <body>
     Some initial text<br>
     <p>Which is across multiple lines</p>
     <br>
     So let's see what happens.  <br>
     <div id="nope-doesnt-exist">Some text thats the same</div>
     </body>
     </html>
    """

    with open(os.path.join(datastore_path, "endpoint-content.txt"), "w") as f:
        f.write(test_return_data)
    return None


def set_response_with_filter(datastore_path):
    test_return_data = """<html>
       <body>
     Some initial text<br>
     <p>Which is across multiple lines</p>
     <br>
     So let's see what happens.  <br>
     <div class="ticket-available">Ticket now on sale!</div>
     </body>
     </html>
    """

    with open(os.path.join(datastore_path, "endpoint-content.txt"), "w") as f:
        f.write(test_return_data)
    return None

