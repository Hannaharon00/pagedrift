"""
Custom Discord plugin for changedetection.io
Extends Apprise's Discord plugin to support custom colored embeds for removed/added content
"""
from apprise.plugins.discord import NotifyDiscord
from apprise.decorators import notify
from apprise.common import NotifyFormat
from loguru import logger

# Import placeholders from changedetection's diff module
from ...diff import (
    REMOVED_PLACEMARKER_OPEN,
    REMOVED_PLACEMARKER_CLOSED,
    ADDED_PLACEMARKER_OPEN,
    ADDED_PLACEMARKER_CLOSED,
    CHANGED_PLACEMARKER_OPEN,
    CHANGED_PLACEMARKER_CLOSED,
    CHANGED_INTO_PLACEMARKER_OPEN,
    CHANGED_INTO_PLACEMARKER_CLOSED,
)

