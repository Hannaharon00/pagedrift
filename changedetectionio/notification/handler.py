
import time
import re
from loguru import logger
from urllib.parse import urlparse
from .email_helpers import as_monospaced_html_email
from ..diff import HTML_REMOVED_STYLE, REMOVED_PLACEMARKER_OPEN, REMOVED_PLACEMARKER_CLOSED, ADDED_PLACEMARKER_OPEN, HTML_ADDED_STYLE, \
    ADDED_PLACEMARKER_CLOSED, CHANGED_INTO_PLACEMARKER_OPEN, CHANGED_INTO_PLACEMARKER_CLOSED, CHANGED_PLACEMARKER_OPEN, \
    CHANGED_PLACEMARKER_CLOSED, HTML_CHANGED_STYLE, HTML_CHANGED_INTO_STYLE
import re

from ..notification_service import NotificationContextData, add_rendered_diff_to_notification_vars

