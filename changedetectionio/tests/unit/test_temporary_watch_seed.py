#!/usr/bin/env python3
"""
Unit tests for promoting an Add-Watch live snapshot into a real watch.

The Add Watch UI fetches a screenshot + xpath element data once (the "/snapshot"
endpoint), parks it under datastore/temporary/{uuid} in final on-disk format, and
on submit renames that directory into place as the new watch's data_dir - so the
watch is created without fetching the page a second time.

Run from the tests/ directory:
    python -m unittest unit/test_temporary_watch_seed.py
"""

import json
import os
import shutil
import tempfile
import time
import unittest
import uuid
import zlib

