import os
import uuid

from changedetectionio import strtobool
from .persistence import EntityPersistenceMixin, _determine_entity_type

__all__ = ['EntityPersistenceMixin', 'watch_base']

from ..browser_steps.browser_steps import browser_steps_get_valid_steps

USE_SYSTEM_DEFAULT_NOTIFICATION_FORMAT_FOR_WATCH = 'System default'
CONDITIONS_MATCH_LOGIC_DEFAULT = 'ALL'


