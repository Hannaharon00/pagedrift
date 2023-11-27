#!/usr/bin/env python3

import time
import os

from flask import url_for

from ..html_tools import *
from .util import live_server_setup, wait_for_all_checks, delete_all_watches




def set_response_with_multiple_index(datastore_path):
    data= """<!DOCTYPE html>
<html>
<body>

<!-- NOTE!! CHROME WILL ADD TBODY HERE IF ITS NOT THERE!! -->
<table style="width:100%">
  <tr>
    <th>Person 1</th>
    <th>Person 2</th>
    <th>Person 3</th>
  </tr>
  <tr>
    <td>Emil</td>
    <td>Tobias</td>
    <td>Linus</td>
  </tr>
  <tr>
    <td>16</td>
    <td>14</td>
    <td>10</td>
  </tr>
</table>
</body>
</html>
"""
    with open(os.path.join(datastore_path, "endpoint-content.txt"), "w") as f:
        f.write(data)


def set_original_response(datastore_path):
    test_return_data = """<html>
    <header>
    <h2>Header</h2>
    </header>
    <nav>
    <ul>
      <li><a href="#">A</a></li>
      <li><a href="#">B</a></li>
      <li><a href="#">C</a></li>
    </ul>
    </nav>
       <body>
     Some initial text<br>
     <p>Which is across multiple lines</p>
     <br>
     So let's see what happens.  <br>
    <div id="changetext">Some text that will change</div>
     </body>
    <footer>
    <p>Footer</p>
    </footer>
     </html>
    """

    with open(os.path.join(datastore_path, "endpoint-content.txt"), "w") as f:
        f.write(test_return_data)


def set_modified_response(datastore_path):
    test_return_data = """<html>
    <header>
    <h2>Header changed</h2>
    </header>
    <nav>
    <ul>
      <li><a href="#">A changed</a></li>
      <li><a href="#">B</a></li>
      <li><a href="#">C</a></li>
    </ul>
    </nav>
       <body>
     Some initial text<br>
     <p>Which is across multiple lines</p>
     <br>
     So let's see what happens.  <br>
    <div id="changetext">Some text that changes</div>
     </body>
    <footer>
    <p>Footer changed</p>
    </footer>
     </html>
    """

    with open(os.path.join(datastore_path, "endpoint-content.txt"), "w") as f:
        f.write(test_return_data)


