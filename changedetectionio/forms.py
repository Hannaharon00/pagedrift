import os
import re
from loguru import logger
from wtforms.widgets.core import TimeInput
from flask_babel import lazy_gettext as _l, gettext

from changedetectionio.blueprint.menu_modes import MENU_SIDEBAR_ACTIONMODES, MENU_SIDEBAR_ACTIONMODES_DEFAULT
from changedetectionio.blueprint.rss import RSS_FORMAT_TYPES, RSS_TEMPLATE_TYPE_OPTIONS, RSS_TEMPLATE_HTML_DEFAULT
from changedetectionio.llm.ui_strings import LLM_INTENT_WATCH_PLACEHOLDER
from changedetectionio.llm.evaluator import (
    DEFAULT_CHANGE_SUMMARY_PROMPT,
    LLM_DEFAULT_MAX_SUMMARY_TOKENS,
    LLM_DEFAULT_THINKING_BUDGET,
    LLM_PROMPT_MODE_APPEND,
    LLM_PROMPT_MODE_REPLACE,
)
from changedetectionio.conditions.form import ConditionFormRow
from changedetectionio.notification_service import NotificationContextData
from changedetectionio.strtobool import strtobool
from changedetectionio import processors

from wtforms import (
    BooleanField,
    Form,
    Field,
    FloatField,
    HiddenField,
    IntegerField,
    PasswordField,
    RadioField,
    SelectField,
    StringField,
    SubmitField,
    TextAreaField,
    fields,
    validators,
    widgets
)
from flask_wtf.file import FileField, FileAllowed
from wtforms.fields import FieldList
from wtforms.utils import unset_value

from wtforms.validators import ValidationError

from changedetectionio.widgets import TernaryNoneBooleanField

# default
# each select <option data-enabled="enabled-0-0"
from changedetectionio.browser_steps.browser_steps import browser_step_ui_config

from changedetectionio import html_tools, content_fetchers

from changedetectionio.notification import (
    valid_notification_formats,
)

from wtforms.fields import FormField

default_method = 'GET'
allow_simplehost = not strtobool(os.getenv('BLOCK_SIMPLEHOSTS', 'False'))
REQUIRE_ATLEAST_ONE_TIME_PART_MESSAGE_DEFAULT=_l('At least one time interval (weeks, days, hours, minutes, or seconds) must be specified.')
REQUIRE_ATLEAST_ONE_TIME_PART_WHEN_NOT_GLOBAL_DEFAULT=_l('At least one time interval (weeks, days, hours, minutes, or seconds) must be specified when not using global settings.')

class StringListField(StringField):
    widget = widgets.TextArea()

    def _value(self):
        if self.data:
            # ignore empty lines in the storage
            data = list(filter(lambda x: len(x.strip()), self.data))
            # Apply strip to each line
            data = list(map(lambda x: x.strip(), data))
            return "\r\n".join(data)
        else:
            return u''

    # incoming
    def process_formdata(self, valuelist):
        if valuelist and len(valuelist[0].strip()):
            # Remove empty strings, stripping and splitting \r\n, only \n etc.
            self.data = valuelist[0].splitlines()
            # Remove empty lines from the final data
            self.data = list(filter(lambda x: len(x.strip()), self.data))
        else:
            self.data = []


class SaltyPasswordField(StringField):
    widget = widgets.PasswordInput()
    encrypted_password = ""

    def build_password(self, password):
        import base64
        import hashlib
        import secrets

        # Make a new salt on every new password and store it with the password
        salt = secrets.token_bytes(32)

        key = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100000)
        store = base64.b64encode(salt + key).decode('ascii')

        return store

    # incoming
    def process_formdata(self, valuelist):
        if valuelist:
            # Be really sure it's non-zero in length
            if len(valuelist[0].strip()) > 0:
                self.encrypted_password = self.build_password(valuelist[0])
                self.data = ""
        else:
            self.data = False

class StringTagUUID(StringField):

   # process_formdata(self, valuelist) handled manually in POST handler

    # Is what is shown when field <input> is rendered
    def _value(self):
        # Tag UUID to name, on submit it will convert it back (in the submit handler of init.py)
        if self.data and type(self.data) is list:
            tag_titles = []
            for i in self.data:
                tag = self.datastore.data['settings']['application']['tags'].get(i)
                if tag:
                    tag_title = tag.get('title')
                    if tag_title:
                        tag_titles.append(tag_title)

            return ', '.join(tag_titles)

        if not self.data:
            return ''

        return 'error'

class LabelAfterInputTableWidget(widgets.TableWidget):
    """
    Variant of WTForms' TableWidget that renders the input cell before the label cell,
    so each row is <td>input</td><th>label</th> instead of the default <th>label</th><td>input</td>.
    """

    def __call__(self, field, **kwargs):
        from markupsafe import Markup
        from wtforms.widgets import html_params

        html = []
        if self.with_table_tag:
            kwargs.setdefault("id", field.id)
            html.append(f"<table {html_params(**kwargs)}>")
        hidden = ""
        for subfield in field:
            if subfield.type in ("HiddenField", "CSRFTokenField"):
                hidden += str(subfield)
            else:
                html.append(
                    f"<tr><td>{hidden}{subfield}</td><th>{subfield.label}</th></tr>"
                )
                hidden = ""
        if self.with_table_tag:
            html.append("</table>")
        if hidden:
            html.append(hidden)
        return Markup("".join(html))


def validate_time_between_check_has_values(form):
    """
    Custom validation function for TimeBetweenCheckForm.
    Returns True if at least one time interval field has a value > 0.
    """
    res = any([
        form.weeks.data and int(form.weeks.data) > 0,
        form.days.data and int(form.days.data) > 0,
        form.hours.data and int(form.hours.data) > 0,
        form.minutes.data and int(form.minutes.data) > 0,
        form.seconds.data and int(form.seconds.data) > 0
    ])

    return res


class RequiredTimeInterval(object):
    """
    WTForms validator that ensures at least one time interval field has a value > 0.
    Use this with FormField(TimeBetweenCheckForm, validators=[RequiredTimeInterval()]).
    """
    def __init__(self, message=None):
        self.message = message or _l('At least one time interval (weeks, days, hours, minutes, or seconds) must be specified.')

    def __call__(self, form, field):
        if not validate_time_between_check_has_values(field.form):
            raise ValidationError(self.message)


