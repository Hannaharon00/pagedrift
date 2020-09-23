"""
Levenshtein distance and similarity plugin for text change detection.
Provides metrics for measuring text similarity between snapshots.
"""
import pluggy
from loguru import logger
from flask_babel import gettext as _, lazy_gettext as _l

LEVENSHTEIN_MAX_LEN_FOR_EDIT_STATS=100000

# Support both plugin systems
conditions_hookimpl = pluggy.HookimplMarker("changedetectionio_conditions")
global_hookimpl = pluggy.HookimplMarker("changedetectionio")

