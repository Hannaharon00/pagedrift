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

