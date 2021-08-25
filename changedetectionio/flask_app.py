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

datastore = None

# Local
ticker_thread = None
extra_stylesheets = []

# Use bulletproof janus-based queues for sync/async reliability
update_q = RecheckPriorityQueue()
notification_q = NotificationQueue()
MAX_QUEUE_SIZE = 5000

app = Flask(__name__, static_url_path="", static_folder="static", template_folder="templates")

# Will be initialized in changedetection_app
socketio_server = None

# Enable CORS, especially useful for the Chrome extension to operate from anywhere
CORS(app)
from uuid import UUID

from werkzeug.routing import BaseConverter, ValidationError


class StrictUUIDConverter(BaseConverter):
    # Special sentinel values allowed in addition to strict UUIDs
    _ALLOWED_SENTINELS = frozenset({'first'})

    def to_python(self, value: str) -> str:
        if value in self._ALLOWED_SENTINELS:
            return value
        try:
            u = UUID(value)
        except ValueError as e:
            raise ValidationError() from e
        # Reject non-standard formats (braces, URNs, no-hyphens)
        if str(u) != value.lower():
            raise ValidationError()
        return str(u)

    def to_url(self, value) -> str:
        return str(value)


# app setup (once)
app.url_map.converters["uuid_str"] = StrictUUIDConverter

# Flask-Compress handles HTTP compression, Socket.IO compression disabled to prevent memory leak.
# There's also a bug between flask compress and socketio that causes some kind of slow memory leak
# It's better to use compression on your reverse proxy (nginx etc) instead.
if strtobool(os.getenv("FLASK_ENABLE_COMPRESSION")):
    from flask_compress import Compress as FlaskCompress

    app.config['COMPRESS_MIN_SIZE'] = 2096
    app.config['COMPRESS_MIMETYPES'] = [
        'text/html',
        'text/css',
        'text/javascript',
        'application/json',
        'application/javascript',
        'image/svg+xml',
    ]
    # Use gzip only - smaller memory footprint than zstd/brotli (4-8KB vs 200-500KB contexts)
    app.config['COMPRESS_ALGORITHM'] = ['gzip']
    compress = FlaskCompress()
    compress.init_app(app)

app.config['TEMPLATES_AUTO_RELOAD'] = False


# Stop browser caching of assets
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0
app.config.exit = Event()

app.config['NEW_VERSION_AVAILABLE'] = False

if os.getenv('FLASK_SERVER_NAME'):
    app.config['SERVER_NAME'] = os.getenv('FLASK_SERVER_NAME')

watch_api = Api(app, decorators=[csrf.exempt])


def init_app_secret(datastore_path):
    secret = ""

    path = os.path.join(datastore_path, "secret.txt")

    try:
        with open(path, encoding='utf-8') as f:
            secret = f.read()

    except FileNotFoundError:
        import secrets

        with open(path, "w", encoding='utf-8') as f:
            secret = secrets.token_hex(32)
            f.write(secret)

    return secret


@app.template_global()
def get_darkmode_state():
    css_dark_mode = request.cookies.get('css_dark_mode', 'false')
    return 'true' if css_dark_mode and strtobool(css_dark_mode) else 'false'


@app.template_global('filter_url')
def _filter_url(**overrides):
    """Watch-list filter link (shorthand for filtered_action_url('watchlist.index'))."""
    return _filtered_action_url('watchlist.index', **overrides)


@app.template_global()
def get_sidebar_mode_class():
    """Body class(es) that drive the left-rail behaviour (see parts/_action_sidebar.scss).

    Only the modes offered by MENU_SIDEBAR_ACTIONMODES are honoured - anything else in the
    datastore (a stale value from an older release, hand-edited JSON) falls back to
    MENU_SIDEBAR_ACTIONMODES_DEFAULT rather than leaking through as a body class.

    'expandable'      -> icon-only rail, rolls out over the content on hover/focus
    'pinned-expanded' -> rail always expanded, labels visible at rest
    'minimal'         -> icon-only rail that never expands
    """

    # 'actionsidebar-minimal'   - collapsed icon rail (hover-to-expand lives in CSS + static/js/sidebar.js)
    # 'actionsidebar-no-expand' - opts that rail out of hover-to-expand
    # 'actionside-bar-on'       - always-open rail
    # 'action-side-bar-expanded'- expanded logo/stats block
    body_classes = {
        'expandable': 'actionsidebar-minimal',
        'pinned-expanded': 'actionside-bar-on action-side-bar-expanded',
        'minimal': 'actionsidebar-minimal actionsidebar-no-expand',
    }

    mode = datastore.data['settings']['application'].get('ui', {}).get('sidebar_mode')
    if mode not in {choice for choice, _label in MENU_SIDEBAR_ACTIONMODES} or mode not in body_classes:
        mode = MENU_SIDEBAR_ACTIONMODES_DEFAULT

    return body_classes[mode]


