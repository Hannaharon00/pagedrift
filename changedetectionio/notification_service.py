#!/usr/bin/env python3

"""
Notification Service Module
Extracted from update_worker.py to provide standalone notification functionality
for both sync and async workers
"""
import datetime

import pytz
from loguru import logger
import time

from changedetectionio.notification import default_notification_format, valid_notification_formats


