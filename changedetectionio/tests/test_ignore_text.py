#!/usr/bin/env python3

import time
from flask import url_for
from .util import live_server_setup, wait_for_all_checks, delete_all_watches
from changedetectionio import html_tools
import os



# Unit test of the stripper
# Always we are dealing in utf-8
def test_strip_text_func():
    test_content = """
    Some content
    is listed here

    but sometimes we want to remove the lines.

    but not always."""

    ignore_lines = ["sometimes"]

    stripped_content = html_tools.strip_ignore_text(test_content, ignore_lines)
    assert "sometimes" not in stripped_content
    assert "Some content" in stripped_content

    # Check that line feeds dont get chewed up when something is found
    test_content = "Some initial text\n\nWhich is across multiple lines\n\nZZZZz\n\n\nSo let's see what happens."
    ignore = ['something irrelevent but just to check', 'XXXXX', 'YYYYY', 'ZZZZZ']

    stripped_content = html_tools.strip_ignore_text(test_content, ignore)
    assert stripped_content == "Some initial text\n\nWhich is across multiple lines\n\n\n\nSo let's see what happens."

def set_original_ignore_response(datastore_path, ver_stamp="123"):
    test_return_data = f"""<html>
       <body>
     Some initial text<br>
     <p>Which is across multiple lines</p>
     <br>
     So let's see what happens.  <br>
     <link href="https://www.somesite/wp-content/themes/cooltheme/style2.css?v={ver_stamp}" rel="stylesheet"/>
     </body>
     </html>

    """

    with open(os.path.join(datastore_path, "endpoint-content.txt"), "w") as f:
        f.write(test_return_data)


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

