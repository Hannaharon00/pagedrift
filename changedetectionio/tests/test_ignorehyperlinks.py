#!/usr/bin/env python3
"""Test suite for the render/not render anchor tag content functionality"""

import time
from flask import url_for
from .util import live_server_setup, wait_for_all_checks, delete_all_watches
import os


