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

# Babel/i18n configuration
#
# BABEL_TRANSLATION_DIRECTORIES is a ';' separated list. For each locale, Flask-Babel loads one
# catalog per directory and merges them in order (Domain.get_translations -> babel
# Translations.merge -> dict.update), so a later directory overrides an earlier one *per message*
# rather than replacing the catalog.
#
# That gives deployments an optional overlay layer: a catalog holding only the handful of msgids
# whose wording needs to differ (branding, or wording that makes no sense for that deployment,
# e.g. instructions to set an ENV var that the operator controls). Every other string in the same
# language still comes from the base catalog, and a language with no overlay file is untouched.
# Because the overlay keys off the upstream msgid, templates keep the upstream string verbatim and
# carry no diff at all.
#
# Absent or empty overlay directory == no behaviour change.
# See changedetectionio/translations_overlay/README.md
_translation_directories = [str(Path(__file__).parent / 'translations')]
_translation_overlay = os.getenv(
    'TRANSLATION_OVERLAY_DIR', str(Path(__file__).parent / 'translations_overlay')
)
if os.path.isdir(_translation_overlay):
    _translation_directories.append(_translation_overlay)
app.config['BABEL_TRANSLATION_DIRECTORIES'] = ';'.join(_translation_directories)
app.config['BABEL_DEFAULT_LOCALE'] = 'en_GB'

# Session configuration
# NOTE: Flask session (for locale, etc.) is separate from Flask-Login's remember-me cookie
# - Flask session stores data like session['locale'] in a signed cookie
# - Flask-Login's remember=True creates a separate authentication cookie
# - Setting PERMANENT_SESSION_LIFETIME controls how long the Flask session cookie lasts
from datetime import timedelta

app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=3650)  # ~10 years (effectively unlimited)

# app.config["EXPLAIN_TEMPLATE_LOADING"] = True


app.jinja_env.add_extension('jinja2.ext.loopcontrols')


# Configure Jinja2 to search for templates in plugin directories
def _configure_plugin_templates():
    """Configure Jinja2 loader to include plugin template directories."""
    from jinja2 import ChoiceLoader, FileSystemLoader

    from changedetectionio.pluggy_interface import get_plugin_template_paths

    # Get plugin template paths
    plugin_template_paths = get_plugin_template_paths()

    if plugin_template_paths:
        # Create a ChoiceLoader that searches app templates first, then plugin templates
        loaders = [app.jinja_loader]  # Keep the default app loader first
        for path in plugin_template_paths:
            loaders.append(FileSystemLoader(path))

        app.jinja_loader = ChoiceLoader(loaders)
        logger.info(
            f"Configured Jinja2 to search {len(plugin_template_paths)} plugin template directories"
        )


# Configure plugin templates (called after plugins are loaded)
_configure_plugin_templates()
csrf = CSRFProtect()
csrf.init_app(app)
notification_debug_log = []

# Locale for correct presentation of prices etc
default_locale = locale.getdefaultlocale()
logger.info(f"System locale default is {default_locale}")
try:
    locale.setlocale(locale.LC_ALL, default_locale)
except locale.Error:
    logger.warning(f"Unable to set locale {default_locale}, locale is not installed maybe?")

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


@app.template_global()
def get_blueprint_class():
    """Body class for the currently-executing blueprint, e.g. 'blueprint-watchlist'
    or 'blueprint-ui-ui_queue' (dots → dashes), so CSS can target a section. Empty
    when there's no blueprint (e.g. an error page)."""
    bp = request.blueprint or ''
    return ('blueprint-' + bp.replace('.', '-')) if bp else ''


@app.template_global()
def get_socketio_path():
    """Generate the correct Socket.IO path prefix for the client"""
    # If behind a proxy with a sub-path, we need to respect that path
    prefix = ""
    if os.getenv('USE_X_SETTINGS') and 'X-Forwarded-Prefix' in request.headers:
        prefix = request.headers['X-Forwarded-Prefix']

    # Socket.IO will be available at {prefix}/socket.io/
    return prefix


@app.template_filter('format_number_locale')
def _jinja2_filter_format_number_locale(value: float) -> str:
    "Formats for example 4000.10 to the local locale default of 4,000.10"
    # Format the number with two decimal places (locale format string will return 6 decimal)
    formatted_value = locale.format_string("%.2f", value, grouping=True)
    return formatted_value


@app.template_filter('format_int_locale')
def _jinja2_filter_format_int_locale(value) -> str:
    "Locale-grouped integer, e.g. 1000 -> 1,000 (no decimals — for counts)"
    return locale.format_string("%d", int(value), grouping=True)


@app.template_filter('regex_search')
def _jinja2_filter_regex_search(value, pattern):
    import re

    return re.search(pattern, str(value)) is not None


@app.template_filter('sanitize_tag_class')
def _jinja2_filter_sanitize_tag_class(tag_title):
    """Sanitize a tag title to create a valid CSS class name.
    Removes all non-alphanumeric characters and converts to lowercase.

    Args:
        tag_title: The tag title string

    Returns:
        str: A sanitized string suitable for use as a CSS class name
    """
    # Remove all non-alphanumeric characters and convert to lowercase
    sanitized = _RE_SANITIZE_TAG.sub('', tag_title).lower()
    # Ensure it starts with a letter (CSS requirement)
    if sanitized and not sanitized[0].isalpha():
        sanitized = 'tag' + sanitized
    return sanitized if sanitized else 'tag'


# Import login_optionally_required from auth_decorator
from changedetectionio.auth_decorator import (
    SHARED_DIFF_READ_ONLY_ENDPOINTS,
    login_optionally_required,
)


