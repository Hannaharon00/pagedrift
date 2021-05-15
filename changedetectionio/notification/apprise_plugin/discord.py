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

# Discord embed sidebar colors for different change types
DISCORD_COLOR_UNCHANGED = 8421504   # Gray (#808080)
DISCORD_COLOR_REMOVED = 16711680    # Red (#FF0000)
DISCORD_COLOR_ADDED = 65280         # Green (#00FF00)
DISCORD_COLOR_CHANGED = 16753920    # Orange (#FFA500)
DISCORD_COLOR_CHANGED_INTO = 3447003  # Blue (#5865F2 - Discord blue)
DISCORD_COLOR_WARNING = 16776960    # Yellow (#FFFF00)


