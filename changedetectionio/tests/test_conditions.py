#!/usr/bin/env python3
import json
import time
import os

def set_number_in_range_response(datastore_path, number="75"):
    test_return_data = f"""<html>
       <body>
     <h1>Test Page for Conditions</h1>
     <p>This page contains a number that will be tested with conditions.</p>
     <div class="number-container">Current value: {number}</div>
     </body>
     </html>
    """

    with open(os.path.join(datastore_path, "endpoint-content.txt"), "w") as f:
        f.write(test_return_data)

def set_number_out_of_range_response(datastore_path, number="150"):
    test_return_data = f"""<html>
       <body>
     <h1>Test Page for Conditions</h1>
     <p>This page contains a number that will be tested with conditions.</p>
     <div class="number-container">Current value: {number}</div>
     </body>
     </html>
    """

    with open(os.path.join(datastore_path, "endpoint-content.txt"), "w") as f:
        f.write(test_return_data)


