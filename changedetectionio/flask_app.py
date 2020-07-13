#!/usr/bin/env python3

import gc
import hashlib
import locale
import os
import queue
import re
import sys
import threading
import time
from pathlib import Path
from threading import Event

import flask_login
import timeago
from blinker import signal
from flask import (
    Flask,
    abort,
    flash,
    redirect,
    render_template,
    request,
    send_from_directory,
    session,
    url_for,
)
from flask_cors import CORS
from flask_restful import Api, abort

from changedetectionio import worker_pool
from changedetectionio.queue_handlers import NotificationQueue, RecheckPriorityQueue
from changedetectionio.strtobool import strtobool

# Create specific signals for application events
# Make this a global singleton to avoid multiple signal objects
watch_check_update = signal('watch_check_update', doc='Signal sent when a watch check is completed')
from flask_babel import Babel, get_locale, gettext
from flask_wtf import CSRFProtect
from loguru import logger

from changedetectionio import __version__, queuedWatchMetaData
from changedetectionio.api import (
    CreateWatch,
    Import,
    Notifications,
    Spec,
    SystemInfo,
    Tag,
    Tags,
    Watch,
    WatchFavicon,
    WatchHistory,
    WatchHistoryDiff,
    WatchSingleHistory,
)
from changedetectionio.api.Search import Search
from changedetectionio.blueprint.menu_modes import MENU_SIDEBAR_ACTIONMODES, MENU_SIDEBAR_ACTIONMODES_DEFAULT
from changedetectionio.favicon_utils import get_favicon_mime_type
from changedetectionio.languages import (
    get_available_languages,
    get_flag_for_locale,
    get_language_codes,
    get_timeago_locale,
)

from .thread_supervisor import start_supervised_thread
from .time_handler import default_timezone_name, is_within_schedule

IN_PYTEST = "pytest" in sys.modules or "PYTEST_CURRENT_TEST" in os.environ

