"""
Word count plugin for content analysis.
Provides word count metrics for snapshot content.
"""
import pluggy
from loguru import logger
from flask_babel import gettext as _, lazy_gettext as _l

# Support both plugin systems
conditions_hookimpl = pluggy.HookimplMarker("changedetectionio_conditions")
global_hookimpl = pluggy.HookimplMarker("changedetectionio")

def count_words_in_history(watch, incoming_text=None):
    """Count words in snapshot text"""
    try:
        if incoming_text is not None:
            # When called from add_data with incoming text
            return len(incoming_text.split())
        elif watch.history.keys():
            # When called from UI extras to count latest snapshot
            latest_key = list(watch.history.keys())[-1]
            latest_content = watch.get_history_snapshot(timestamp=latest_key)
            return len(latest_content.split())
        return 0
    except Exception as e:
        logger.error(f"Error counting words: {str(e)}")
        return 0

# Implement condition plugin hooks
@conditions_hookimpl
def register_operators():
    # No custom operators needed
    return {}

@conditions_hookimpl
def register_operator_choices():
    # No custom operator choices needed
    return []

