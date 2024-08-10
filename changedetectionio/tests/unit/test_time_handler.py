#!/usr/bin/env python3

Run from project root:
python3 -m pytest changedetectionio/tests/unit/test_time_handler.py -v
"""

import unittest
import unittest.mock
import arrow
from changedetectionio import time_handler


