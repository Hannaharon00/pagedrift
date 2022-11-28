#!/usr/bin/env python3
import json
import os
from flask import url_for
from changedetectionio.tests.util import live_server_setup, wait_for_all_checks, extract_UUID_from_client, delete_all_watches


def set_response(datastore_path):
    import time
    data = """<html>
       <body>
     <h1>Awesome, you made it</h1>
     yeah the socks request worked
     </body>
     </html>
    """

    with open(os.path.join(datastore_path, "endpoint-content.txt"), "w") as f:
        f.write(data)
    time.sleep(1)

