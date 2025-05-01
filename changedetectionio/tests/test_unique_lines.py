#!/usr/bin/env python3

import time
from flask import url_for
from .util import live_server_setup, wait_for_all_checks, delete_all_watches
import os


def set_original_ignore_response(datastore_path):
    test_return_data = """<html>
     <body>
     <p>Some initial text</p>
     <p>Which is across multiple lines</p>
     <p>So let's see what happens.</p>
     <p>&nbsp;  So let's see what happens.   <br> </p>
     <p>A - sortable line</p> 
     </body>
     </html>
    """

    with open(os.path.join(datastore_path, "endpoint-content.txt"), "w") as f:
        f.write(test_return_data)


# The same but just re-ordered the text
def set_modified_swapped_lines(datastore_path):
    # Re-ordered and with some whitespacing, should get stripped() too.
    test_return_data = """<html>
     <body>
     <p>Some initial text</p>
     <p>   So let's see what happens.</p>
     <p>&nbsp;Which is across multiple lines</p>     
     </body>
     </html>
    """

    with open(os.path.join(datastore_path, "endpoint-content.txt"), "w") as f:
        f.write(test_return_data)

def set_modified_swapped_lines_with_extra_text_for_sorting(datastore_path):
    test_return_data = """<html>
     <body>
     <p>&nbsp;Which is across multiple lines</p>     
     <p>Some initial text</p>
     <p>   So let's see what happens.</p>
     <p>Z last</p>
     <p>0 numerical</p>
     <p>A uppercase</p>
     <p>a lowercase</p>     
     </body>
     </html>
    """

    with open(os.path.join(datastore_path, "endpoint-content.txt"), "w") as f:
        f.write(test_return_data)


