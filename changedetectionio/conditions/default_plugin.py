import re

import pluggy
from loguru import logger
from flask_babel import lazy_gettext as _l

hookimpl = pluggy.HookimplMarker("changedetectionio_conditions")


@hookimpl
def register_operators():
    def starts_with(_, text, prefix):
        return text.lower().strip().startswith(str(prefix).strip().lower())

    def ends_with(_, text, suffix):
        return text.lower().strip().endswith(str(suffix).strip().lower())

    def length_min(_, text, strlen):
        return len(text) >= int(strlen)

    def length_max(_, text, strlen):
        return len(text) <= int(strlen)

    # Custom function for case-insensitive regex matching
    def contains_regex(_, text, pattern):
        """Returns True if `text` contains `pattern` (case-insensitive regex match)."""
        return bool(re.search(pattern, str(text), re.IGNORECASE))

    # Custom function for NOT matching case-insensitive regex
    def not_contains_regex(_, text, pattern):
        """Returns True if `text` does NOT contain `pattern` (case-insensitive regex match)."""
        return not bool(re.search(pattern, str(text), re.IGNORECASE))

    def not_contains(_, text, pattern):
        return not pattern in text

    return {
        "!in": not_contains,
        "!contains_regex": not_contains_regex,
        "contains_regex": contains_regex,
        "ends_with": ends_with,
        "length_max": length_max,
        "length_min": length_min,
        "starts_with": starts_with,
    }

