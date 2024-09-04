#!/usr/bin/env python3
"""
Test that changing global settings or tag configurations forces reprocessing.

When settings or tag configurations change, all affected watches need to
reprocess even if their content hasn't changed, because configuration affects
the processing result.
"""

import os
import time
from flask import url_for
from .util import wait_for_all_checks


