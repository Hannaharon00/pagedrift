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

def levenshtein_ratio_recent_history(watch, incoming_text=None):
    try:
        from Levenshtein import ratio, distance
        k = list(watch.history.keys())
        a = None
        b = None

        # When called from ui_edit_stats_extras, we don't have incoming_text
        if incoming_text is None:
            a = watch.get_history_snapshot(timestamp=k[-1])  # Latest snapshot
            b = watch.get_history_snapshot(timestamp=k[-2])  # Previous snapshot

        # Needs atleast one snapshot
        elif len(k) >= 1: # Should be atleast one snapshot to compare against
            a = watch.get_history_snapshot(timestamp=k[-1]) # Latest saved snapshot
            b = incoming_text if incoming_text else k[-2]

        if a and b:
            distance_value = distance(a, b)
            ratio_value = ratio(a, b)
            return {
                'distance': distance_value,
                'ratio': ratio_value,
                'percent_similar': round(ratio_value * 100, 2)
            }
    except Exception as e:
        logger.warning(f"Unable to calc similarity: {str(e)}")

    return ''

@conditions_hookimpl
def register_operators():
    pass

@conditions_hookimpl
def register_operator_choices():
    pass


@conditions_hookimpl
def register_field_choices():
    return [
        ("levenshtein_ratio", _l("Levenshtein - Text similarity ratio")),
        ("levenshtein_distance", _l("Levenshtein - Text change distance")),
    ]

