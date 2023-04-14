import os
import time
from flask import url_for
from .util import set_original_response, wait_for_all_checks, wait_for_notification_endpoint_output, delete_all_watches
from ..notification import valid_notification_formats


def set_response_with_filter(datastore_path):
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

