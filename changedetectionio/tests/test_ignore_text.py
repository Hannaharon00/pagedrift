#!/usr/bin/env python3

import time
from flask import url_for
from .util import live_server_setup, wait_for_all_checks, delete_all_watches
from changedetectionio import html_tools
import os



def set_modified_original_ignore_response(datastore_path, ver_stamp="123"):
    test_return_data = f"""<html>
       <body>
     Some NEW nice initial text<br>
     <p>Which is across multiple lines</p>
     <br>
     So let's see what happens.  <br>
     <link href="https://www.somesite/wp-content/themes/cooltheme/style2.css?v={ver_stamp}" rel="stylesheet"/>
     <p>new ignore stuff</p>
     <p>blah</p>
     </body>
     </html>

    """

    with open(os.path.join(datastore_path, "endpoint-content.txt"), "w") as f:
        f.write(test_return_data)


# Is the same but includes ZZZZZ, 'ZZZZZ' is the last line in ignore_text
def set_modified_ignore_response(datastore_path, ver_stamp="123"):
    test_return_data = f"""<html>
       <body>
     Some initial text<br>
     <p>Which is across multiple lines</p>
     <P>ZZZZz</P>
     <br>
     So let's see what happens.  <br>
     <link href="https://www.somesite/wp-content/themes/cooltheme/style2.css?v={ver_stamp}" rel="stylesheet"/>
     </body>
     </html>

    """

    with open(os.path.join(datastore_path, "endpoint-content.txt"), "w") as f:
        f.write(test_return_data)


# Ignore text now just removes it entirely, is a LOT more simpler code this way

