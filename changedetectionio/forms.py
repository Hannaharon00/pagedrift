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

