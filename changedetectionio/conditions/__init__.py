from json_logic.builtins import BUILTINS
from flask_babel import lazy_gettext as _l

from .exceptions import EmptyConditionRuleRowNotUsable
from .pluggy_interface import plugin_manager  # Import the pluggy plugin manager
from . import default_plugin
from loguru import logger
# List of all supported JSON Logic operators
operator_choices = [
    (None, _l("Choose one - Operator")),
    (">", _l("Greater Than")),
    ("<", _l("Less Than")),
    (">=", _l("Greater Than or Equal To")),
    ("<=", _l("Less Than or Equal To")),
    ("==", _l("Equals")),
    ("!=", _l("Not Equals")),
    ("in", _l("Contains")),
]

