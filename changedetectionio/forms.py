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


class validateTimeZoneName(object):
    """
       Flask wtform validators wont work with basic auth
    """

    def __init__(self, message=None):
        self.message = message

    def __call__(self, form, field):
        from zoneinfo import available_timezones
        python_timezones = available_timezones()
        if field.data and field.data not in python_timezones:
            raise ValidationError(_l("Not a valid timezone name"))

class ScheduleLimitDaySubForm(Form):
    enabled = BooleanField(_l("not set"), default=True)
    start_time = TimeStringField(_l("Start At"), default="00:00", validators=[validators.Optional()])
    duration = FormField(TimeDurationForm, label=_l("Run duration"), widget=LabelAfterInputTableWidget())

class ScheduleLimitForm(Form):
    enabled = BooleanField(_l("Use time scheduler"), default=False)
    # Because the label for=""" doesnt line up/work with the actual checkbox
    monday = FormField(ScheduleLimitDaySubForm, label="")
    tuesday = FormField(ScheduleLimitDaySubForm, label="")
    wednesday = FormField(ScheduleLimitDaySubForm, label="")
    thursday = FormField(ScheduleLimitDaySubForm, label="")
    friday = FormField(ScheduleLimitDaySubForm, label="")
    saturday = FormField(ScheduleLimitDaySubForm, label="")
    sunday = FormField(ScheduleLimitDaySubForm, label="")

    timezone = StringField(_l("Optional timezone to run in"),
                                  render_kw={"list": "timezones"},
                                  validators=[validateTimeZoneName()]
                                  )
    def __init__(
        self,
        formdata=None,
        obj=None,
        prefix="",
        data=None,
        meta=None,
        **kwargs,
    ):
        super().__init__(formdata, obj, prefix, data, meta, **kwargs)
        self.monday.form.enabled.label.text=_l("Monday")
        self.tuesday.form.enabled.label.text = _l("Tuesday")
        self.wednesday.form.enabled.label.text = _l("Wednesday")
        self.thursday.form.enabled.label.text = _l("Thursday")
        self.friday.form.enabled.label.text = _l("Friday")
        self.saturday.form.enabled.label.text = _l("Saturday")
        self.sunday.form.enabled.label.text = _l("Sunday")


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


class RequiredFormField(FormField):
    """
    A FormField that passes require_at_least_one=True to TimeBetweenCheckForm.
    Use this when you want the sub-form to always require at least one value.
    """

    widget = LabelAfterInputTableWidget()

    def __init__(self, form_class, label=None, validators=None, separator="-", **kwargs):
        super().__init__(form_class, label, validators, separator, **kwargs)

    def process(self, formdata, data=unset_value, extra_filters=None):
        if extra_filters:
            raise TypeError(
                "FormField cannot take filters, as the encapsulated"
                "data is not mutable."
            )

        if data is unset_value:
            try:
                data = self.default()
            except TypeError:
                data = self.default
            self._obj = data

        self.object_data = data

        prefix = self.name + self.separator
        # Pass require_at_least_one=True to the sub-form
        if isinstance(data, dict):
            self.form = self.form_class(formdata=formdata, prefix=prefix, require_at_least_one=True, **data)
        else:
            self.form = self.form_class(formdata=formdata, obj=data, prefix=prefix, require_at_least_one=True)

    @property
    def errors(self):
        """Include sub-form validation errors"""
        form_errors = self.form.errors
        # Add any general form errors to a special 'form' key
        if hasattr(self.form, '_formdata_errors') and self.form._formdata_errors:
            form_errors = dict(form_errors)  # Make a copy
            form_errors['form'] = self.form._formdata_errors
        return form_errors


# Separated by  key:value
class StringDictKeyValue(StringField):
    widget = widgets.TextArea()

    def _value(self):
        if self.data:
            output = ''
            for k, v in self.data.items():
                output += f"{k}: {v}\r\n"
            return output
        else:
            return ''

    # incoming data processing + validation
    def process_formdata(self, valuelist):
        self.data = {}
        errors = []
        if valuelist:
            # Remove empty strings (blank lines)
            cleaned = [line.strip() for line in valuelist[0].split("\n") if line.strip()]
            for idx, s in enumerate(cleaned, start=1):
                if ':' not in s:
                    errors.append(f"Line {idx} is missing a ':' separator.")
                    continue
                parts = s.split(':', 1)
                key = parts[0].strip()
                value = parts[1].strip()

                if not key:
                    errors.append(f"Line {idx} has an empty key.")
                if not value:
                    errors.append(f"Line {idx} has an empty value.")

                self.data[key] = value

        if errors:
            raise ValidationError("Invalid input:\n" + "\n".join(errors))

class ValidateContentFetcherIsReady(object):
    """
    Validates that anything that looks like a regex passes as a regex
    """
    def __init__(self, message=None):
        self.message = message

    def __call__(self, form, field):
        return

