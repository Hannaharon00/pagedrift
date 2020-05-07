from wtforms import (
    Form,
    RadioField,
    StringField,
    SubmitField,
    TextAreaField,
    validators,
)
from wtforms.fields.simple import BooleanField
from flask_babel import lazy_gettext as _l

from changedetectionio.blueprint.tags.colour import CSS_HEX_COLOUR_REGEX
from changedetectionio.widgets.ternary_boolean import TernaryNoneBooleanField
from changedetectionio.processors.restock_diff.forms import processor_settings_form as restock_settings_form
from changedetectionio.llm.ui_strings import LLM_INTENT_TAG_PLACEHOLDER
from changedetectionio.llm.evaluator import (
    DEFAULT_CHANGE_SUMMARY_PROMPT,
    LLM_PROMPT_MODE_APPEND,
    LLM_PROMPT_MODE_REPLACE,
)

