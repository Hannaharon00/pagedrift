from wtforms import (
    BooleanField,
    validators,
    FloatField
)
from wtforms.fields.choices import RadioField
from wtforms.fields.form import FormField
from wtforms.form import Form
from flask_babel import lazy_gettext as _l

from changedetectionio.forms import processor_text_json_diff_form


