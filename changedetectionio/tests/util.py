#!/usr/bin/env python3
from operator import truediv

from flask import make_response, request, current_app
from flask import url_for
import logging
import time
import os
import threading

# Thread-safe global storage for test endpoint content
# Avoids filesystem cache issues in parallel tests
_test_endpoint_content_lock = threading.Lock()
_test_endpoint_content = {}

def write_test_file_and_sync(filepath, content, mode='w'):
    """
    Write test data to file and ensure it's synced to disk.
    Also stores in thread-safe global dict to bypass filesystem cache.

    Critical for parallel tests where workers may read files immediately after write.
    Without fsync(), data may still be in OS buffers when workers try to read,
    causing race conditions where old data is seen.

    Args:
        filepath: Full path to file
        content: Content to write (str or bytes)
        mode: File mode ('w' for text, 'wb' for binary)
    """
    # Convert content to bytes if needed
    if isinstance(content, str):
        content_bytes = content.encode('utf-8')
    else:
        content_bytes = content

    # Store in thread-safe global dict for instant access
    with _test_endpoint_content_lock:
        _test_endpoint_content[os.path.basename(filepath)] = content_bytes

    # Also write to file for compatibility
    with open(filepath, mode) as f:
        f.write(content)
        f.flush()  # Flush Python buffer to OS
        os.fsync(f.fileno())  # Force OS to write to disk

def set_original_response(datastore_path, extra_title=''):
    test_return_data = f"""<html>
    <head><title>head title{extra_title}</title></head>
    <body>
     Some initial text<br>
     <p>Which is across multiple lines</p>
     <br>
     So let's see what happens.  <br>
     <span class="foobar-detection" style='display:none'></span>
     </body>
     </html>
    """

    write_test_file_and_sync(os.path.join(datastore_path, "endpoint-content.txt"), test_return_data)
    return None

def set_modified_response(datastore_path):
    test_return_data = """<html>
    <head><title>modified head title</title></head>
    <body>
     Some initial text<br>
     <p>which has this one new line</p>
     <br>
     So let's see what happens.  <br>
     </body>
     </html>
    """

    write_test_file_and_sync(os.path.join(datastore_path, "endpoint-content.txt"), test_return_data)
    return None
def set_longer_modified_response(datastore_path):
    test_return_data = """<html>
    <head><title>modified head title</title></head>
    <body>
     Some initial text<br>
     <p>which has this one new line</p>
     <br>
     So let's see what happens.  <br>
     So let's see what happens.  <br>
      So let's see what happens.  <br>
     So let's see what happens.  <br>
     </body>
     </html>
    """

    write_test_file_and_sync(os.path.join(datastore_path, "endpoint-content.txt"), test_return_data)
    return None

def set_more_modified_response(datastore_path):
    test_return_data = """<html>
    <head><title>modified head title</title></head>
    <body>
     Some initial text<br>
     <p>which has this one new line</p>
     <br>
     So let's see what happens.  <br>
     Ohh yeah awesome<br>
     </body>
     </html>
    """

    write_test_file_and_sync(os.path.join(datastore_path, "endpoint-content.txt"), test_return_data)
    return None


def set_empty_text_response(datastore_path):
    test_return_data = """<html><body></body></html>"""

    write_test_file_and_sync(os.path.join(datastore_path, "endpoint-content.txt"), test_return_data)

    return None

def wait_for_notification_endpoint_output(datastore_path):
    '''Apprise can take a few seconds to fire'''
    #@todo - could check the apprise object directly instead of looking for this file
    from os.path import isfile
    notification_file = os.path.join(datastore_path, "notification.txt")
    for i in range(1, 20):
        time.sleep(1)
        if isfile(notification_file):
            return True

    return False

# kinda funky, but works for now
def get_UUID_for_tag_name(client, name):
    app_config = client.application.config.get('DATASTORE').data
    for uuid, tag in app_config['settings']['application'].get('tags', {}).items():
        if name == tag.get('title', '').lower().strip():
            return uuid
    return None


# kinda funky, but works for now
def extract_rss_token_from_UI(client):
    return client.application.config.get('DATASTORE').data['settings']['application'].get('rss_access_token')
#    import re
#    res = client.get(
#        url_for("watchlist.index"),
#    )
#    m = re.search('token=(.+?)"', str(res.data))
#    token_key = m.group(1)
#    return token_key.strip()

# kinda funky, but works for now
def extract_UUID_from_client(client):
    import re
    res = client.get(
        url_for("watchlist.index"),
    )
    # <span id="api-key">{{api_key}}</span>

    m = re.search('edit/(.+?)[#"]', str(res.data))
    uuid = m.group(1)
    return uuid.strip()

def delete_all_watches(client=None):
    wait_for_all_checks(client)

    uuids = list(client.application.config.get('DATASTORE').data['watching'])
    for uuid in uuids:
        client.application.config.get('DATASTORE').delete(uuid)
    from changedetectionio.flask_app import update_q

    # Clear the queue to prevent leakage to next test
    # Use clear() method to ensure both priority_items and notification_queue are drained
    if hasattr(update_q, 'clear'):
        update_q.clear()
    else:
        # Fallback for old implementation
        while not update_q.empty():
            try:
                update_q.get_nowait()
            except:
                break

    time.sleep(0.2)

    # Delete any old watch metadata
    from pathlib import Path

    base_path = Path(
        client.application.config.get('DATASTORE').datastore_path
    ).resolve()

    max_depth = 2

    for file in base_path.rglob("*.json"):
        # Calculate depth relative to base path
        depth = len(file.relative_to(base_path).parts) - 1

        if depth <= max_depth and file.is_file():
            file.unlink()


