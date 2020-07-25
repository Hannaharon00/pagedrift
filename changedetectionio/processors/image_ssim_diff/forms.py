"""
Configuration forms for fast screenshot comparison processor.
"""

from wtforms import SelectField, StringField, validators, ValidationError, IntegerField
from flask_babel import lazy_gettext as _l
from changedetectionio.forms import processor_text_json_diff_form
import re

