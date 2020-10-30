from os import getenv
from copy import deepcopy

from changedetectionio.blueprint.menu_modes import MENU_SIDEBAR_ACTIONMODES_DEFAULT
from changedetectionio.blueprint.rss import RSS_FORMAT_TYPES, RSS_CONTENT_FORMAT_DEFAULT
from changedetectionio.model.Tags import TagsDict

from changedetectionio.notification import (
    default_notification_body,
    default_notification_format,
    default_notification_title,
)

