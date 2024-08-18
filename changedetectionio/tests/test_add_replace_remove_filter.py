#!/usr/bin/env python3

import os.path
import os

def set_original(datastore_path, excluding=None, add_line=None):
    test_return_data = """<html>
     <body>
     <p>Some initial text</p>
     <p>So let's see what happens.</p>
     <p>and a new line!</p>
     <p>The golden line</p>
     <p>A BREAK TO MAKE THE TOP LINE STAY AS "REMOVED" OR IT WILL GET COUNTED AS "CHANGED INTO"</p>
     <p>Something irrelevant</p>          
     </body>
     </html>
    """

    if add_line:
        c=test_return_data.splitlines()
        c.insert(5, add_line)
        test_return_data = "\n".join(c)

    if excluding:
        output = ""
        for i in test_return_data.splitlines():
            if not excluding in i:
                output += f"{i}\n"

        test_return_data = output

    with open(os.path.join(datastore_path, "endpoint-content.txt"), "w") as f:
        f.write(test_return_data)

# def test_setup(client, live_server, measure_memory_usage, datastore_path):
   #  live_server_setup(live_server) # Setup on conftest per function

