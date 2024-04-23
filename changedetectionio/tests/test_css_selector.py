#!/usr/bin/env python3

import time
from flask import url_for
from .util import live_server_setup, wait_for_all_checks
import os

from ..html_tools import *



def set_original_response(datastore_path):
    test_return_data = """<html>
       <body>
     Some initial text<br>
     <p>Which is across multiple lines</p>
     <br>
     So let's see what happens.  <br>
     <div id="sametext">Some text thats the same</div>
     <div id="changetext">Some text that will change</div>
     </body>
     </html>
    """

    with open(os.path.join(datastore_path, "endpoint-content.txt"), "w") as f:
        f.write(test_return_data)
    return None

def set_modified_response(datastore_path):
    test_return_data = """<html>
       <body>
     Some initial text<br>
     <p>which has this one new line</p>
     <br>
     So let's see what happens.  <br>
     <div id="sametext">Some text thats the same</div>
     <div id="changetext">Some text that changes</div>
     </body>
     </html>
    """

    with open(os.path.join(datastore_path, "endpoint-content.txt"), "w") as f:
        f.write(test_return_data)

    return None


# Test that the CSS extraction works how we expect, important here is the right placing of new lines \n's
def test_include_filters_output():
    from inscriptis import get_text

    # Check text with sub-parts renders correctly
    content = """<html> <body><div id="thingthing" >  Some really <b>bold</b> text  </div> </body> </html>"""
    html_blob = include_filters(include_filters="#thingthing", html_content=content)
    text = get_text(html_blob)
    assert text == "  Some really bold text"

    content = """<html> <body>
    <p>foo bar blah</p>
    <DIV class="parts">Block A</DiV> <div class="parts">Block B</DIV></body> 
    </html>
"""

    # in xPath this would be //*[@class='parts']
    html_blob = include_filters(include_filters=".parts", html_content=content)
    text = get_text(html_blob)

    # Divs are converted to 4 whitespaces by inscriptis
    assert text == "    Block A\n    Block B"


