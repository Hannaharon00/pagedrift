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

dictfilt = lambda x, y: dict([ (i,x[i]) for i in x if i in set(y) ])

valid_method = {
    'GET',
    'POST',
    'PUT',
    'PATCH',
    'DELETE',
    'OPTIONS',
}

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


class TimeDurationForm(Form):
    hours = SelectField(choices=[(f"{i}", f"{i}") for i in range(0, 25)], default="24",  validators=[validators.Optional()])
    minutes = SelectField(choices=[(f"{i}", f"{i}") for i in range(0, 60)], default="00", validators=[validators.Optional()])

class TimeStringField(Field):
    """
    A WTForms field for time inputs (HH:MM) that stores the value as a string.
    """
    widget = TimeInput()  # Use the built-in time input widget

    def _value(self):
        """
        Returns the value for rendering in the form.
        """
        return self.data if self.data is not None else ""

    def process_formdata(self, valuelist):
        """
        Processes the raw input from the form and stores it as a string.
        """
        if valuelist:
            time_str = valuelist[0]
            # Simple validation for HH:MM format
            if not time_str or len(time_str.split(":")) != 2:
                raise ValidationError(_l("Invalid time format. Use HH:MM."))
            self.data = time_str


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


class TimeBetweenCheckForm(Form):
    weeks = IntegerField(_l('Weeks'), validators=[validators.Optional(), validators.NumberRange(min=0, message=_l("Should contain zero or more seconds"))])
    days = IntegerField(_l('Days'), validators=[validators.Optional(), validators.NumberRange(min=0, message=_l("Should contain zero or more seconds"))])
    hours = IntegerField(_l('Hours'), validators=[validators.Optional(), validators.NumberRange(min=0, message=_l("Should contain zero or more seconds"))])
    minutes = IntegerField(_l('Minutes'), validators=[validators.Optional(), validators.NumberRange(min=0, message=_l("Should contain zero or more seconds"))])
    seconds = IntegerField(_l('Seconds'), validators=[validators.Optional(), validators.NumberRange(min=0, message=_l("Should contain zero or more seconds"))])
    # @todo add total seconds minimum validatior = minimum_seconds_recheck_time

    def __init__(self, formdata=None, obj=None, prefix="", data=None, meta=None, **kwargs):
        super().__init__(formdata, obj, prefix, data, meta, **kwargs)
        self.require_at_least_one = kwargs.get('require_at_least_one', False)
        self.require_at_least_one_message = kwargs.get('require_at_least_one_message', REQUIRE_ATLEAST_ONE_TIME_PART_MESSAGE_DEFAULT)

    def validate(self, **kwargs):
        """Custom validation that can optionally require at least one time interval."""
        # Run normal field validation first
        if not super().validate(**kwargs):
            return False

        # Apply optional "at least one" validation
        if self.require_at_least_one:
            if not validate_time_between_check_has_values(self):
                # Add error to the form's general errors (not field-specific)
                if not hasattr(self, '_formdata_errors'):
                    self._formdata_errors = []
                self._formdata_errors.append(self.require_at_least_one_message)
                return False

        return True


class EnhancedFormField(FormField):
    """
    An enhanced FormField that supports conditional validation with top-level error messages.
    Adds a 'top_errors' property for validation errors at the FormField level.
    """

    widget = LabelAfterInputTableWidget()

    def __init__(self, form_class, label=None, validators=None, separator="-",
                 conditional_field=None, conditional_message=None, conditional_test_function=None, **kwargs):
        """
        Initialize EnhancedFormField with optional conditional validation.

        :param conditional_field: Name of the field this FormField depends on (e.g. 'time_between_check_use_default')
        :param conditional_message: Error message to show when validation fails
        :param conditional_test_function: Custom function to test if FormField has valid values.
                                        Should take self.form as parameter and return True if valid.
        """
        super().__init__(form_class, label, validators, separator, **kwargs)
        self.top_errors = []
        self.conditional_field = conditional_field
        self.conditional_message = conditional_message or "At least one field must have a value when not using defaults."
        self.conditional_test_function = conditional_test_function

    def validate(self, form, extra_validators=()):
        """
        Custom validation that supports conditional logic and stores top-level errors.
        """
        self.top_errors = []

        # First run the normal FormField validation
        base_valid = super().validate(form, extra_validators)

        # Apply conditional validation if configured
        if self.conditional_field and hasattr(form, self.conditional_field):
            conditional_field_obj = getattr(form, self.conditional_field)

            # If the conditional field is False/unchecked, check if this FormField has any values
            if not conditional_field_obj.data:
                # Use custom test function if provided, otherwise use generic fallback
                if self.conditional_test_function:
                    has_any_value = self.conditional_test_function(self.form)
                else:
                    # Generic fallback - check if any field has truthy data
                    has_any_value = any(field.data for field in self.form if hasattr(field, 'data') and field.data)

                if not has_any_value:
                    self.top_errors.append(self.conditional_message)
                    base_valid = False

        return base_valid


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

# AttributeError: module 'changedetectionio.content_fetcher' has no attribute 'extra_browser_unlocked<>ASDF213r123r'
        # Better would be a radiohandler that keeps a reference to each class
        # if field.data is not None and field.data != 'system':
        #     klass = getattr(content_fetcher, field.data)
        #     some_object = klass()
        #     try:
        #         ready = some_object.is_ready()
        #
        #     except urllib3.exceptions.MaxRetryError as e:
        #         driver_url = some_object.command_executor
        #         message = field.gettext('Content fetcher \'%s\' did not respond.' % (field.data))
        #         message += '<br>' + field.gettext(
        #             'Be sure that the selenium/webdriver runner is running and accessible via network from this container/host.')
        #         message += '<br>' + field.gettext('Did you follow the instructions in the wiki?')
        #         message += '<br><br>' + field.gettext('WebDriver Host: %s' % (driver_url))
        #         message += '<br><a href="https://github.com/dgtlmoon/changedetection.io/wiki/Fetching-pages-with-WebDriver">Go here for more information</a>'
        #         message += '<br>'+field.gettext('Content fetcher did not respond properly, unable to use it.\n %s' % (str(e)))
        #
        #         raise ValidationError(message)
        #
        #     except Exception as e:
        #         message = field.gettext('Content fetcher \'%s\' did not respond properly, unable to use it.\n %s')
        #         raise ValidationError(message % (field.data, e))


class ValidateKnownContentFetcher(object):
    """The posted fetch_backend has to name a fetcher this install actually has.

    Deliberately *not* a live-preview capability check. This validator sits on the
    shared quick-add form, whose POST endpoint is also how the watch list (and tests,
    and scripts) add a watch with any legal backend - 'html_requests' included. Which
    browsers the Add-Watch page *offers* is a rendering decision (see the add_watch_ui
    blueprint's browser_config), and whether one can render a live preview is enforced
    where that matters, in /snapshot.

    Optional: no value posted means "leave it on the system default", as before.
    """

    def __init__(self, message=None):
        self.message = message

    def __call__(self, form, field):
        from flask import current_app
        from changedetectionio import content_fetchers

        if not field.data:
            return

        allowed = {'system'} | {name for name, _description in content_fetchers.available_fetchers()}
        datastore = current_app.config.get('DATASTORE')
        if datastore:
            allowed |= {value for value, _label in datastore.extra_browsers}

        if field.data not in allowed:
            logger.warning(f"Rejected unknown fetch_backend {field.data!r} - known: {sorted(allowed)}")
            raise ValidationError(self.message or gettext("Unknown fetch method."))


class validateURL(object):

    """
       Flask wtform validators wont work with basic auth
    """

    def __init__(self, message=None):
        self.message = message

    def __call__(self, form, field):
        # This should raise a ValidationError() or not
        validate_url(field.data)


def validate_url(test_url):
    from changedetectionio.validate_url import is_safe_valid_url
    if not is_safe_valid_url(test_url):
        # This should be wtforms.validators.
        raise ValidationError('Watch protocol is not permitted or invalid URL format')


class validateLLMApiBaseSafe(object):
    """Block private/loopback/reserved api_base values (SSRF) unless the operator
    has opted in via ALLOW_IANA_RESTRICTED_ADDRESSES=true."""

    def __call__(self, form, field):
        from changedetectionio.validate_url import is_llm_api_base_safe
        ok, reason = is_llm_api_base_safe(field.data)
        if not ok:
            raise ValidationError(reason)


class ValidateSinglePythonRegexString(object):
    def __init__(self, message=None):
        self.message = message

    def __call__(self, form, field):
        try:
            re.compile(field.data)
        except re.error:
            message = field.gettext('RegEx \'%s\' is not a valid regular expression.')
            raise ValidationError(message % (field.data))


class ValidateStartsWithRegex(object):
    def __init__(self, regex, *, flags=0, message=None, allow_empty=True, split_lines=True):
        # compile with given flags (we’ll pass re.IGNORECASE below)
        self.pattern = re.compile(regex, flags) if isinstance(regex, str) else regex
        self.message = message
        self.allow_empty = allow_empty
        self.split_lines = split_lines

    def __call__(self, form, field):
        data = field.data
        if not data:
            return

        # normalize into list of lines
        if isinstance(data, str) and self.split_lines:
            lines = data.splitlines()
        elif isinstance(data, (list, tuple)):
            lines = data
        else:
            lines = [data]

        for line in lines:
            stripped = line.strip()
            if not stripped:
                if self.allow_empty:
                    continue
                raise ValidationError(self.message or _l("Empty value not allowed."))
            if not self.pattern.match(stripped):
                raise ValidationError(self.message or _l("Invalid value."))

def visual_browser_choices():
    """Browsers that can render the Add-Watch live preview, as RadioField choices.

    Lazy import (the add_watch_ui blueprint imports this module) and empty outside an
    app context, because WTForms evaluates a choices callable on field construction.
    """
    from flask import current_app, has_app_context
    from changedetectionio.blueprint.add_watch_ui import browser_config

    if not has_app_context():
        return []
    datastore = current_app.config.get('DATASTORE')
    return browser_config.radio_choices(datastore) if datastore else []


# Not true anymore but keep the validate_ hook for future use, we convert color tags
#    def validate_notification_urls(self, field):
#        """Validate that HTML Color format is not used with Telegram"""
#        if self.notification_format.data == 'HTML Color' and field.data:
#            for url in field.data:
#                if url and ('tgram://' in url or 'discord://' in url or 'discord.com/api/webhooks' in url):
#                    raise ValidationError('HTML Color format is not supported by Telegram and Discord. Please choose another Notification Format (Plain Text, HTML, or Markdown to HTML).')


# Standalone form for the /settings/notifications/apprise page. Holds only the
# global apprise-notification fields (the macro
# `notification_part_render_common_settings_form` in _common_fields.html expects
# these exact field names) plus base_url, which powers the {{base_url}} token
# in notification templates.
#
# This is intentionally not a sub-form of globalSettingsForm — the notifications
# page POSTs to its own route so the broader settings form's validators (worker
# count, RSS limits, etc.) don't run when the user only wants to tweak alerts.
#
# Named for the backend (apprise) on purpose: future backends (simple_email,
# webhook, etc.) will land as their own forms next to this one.
class globalSettingsAppriseNotificationForm(Form):
    def __init__(self, formdata=None, obj=None, prefix="", data=None, meta=None, **kwargs):
        super().__init__(formdata, obj, prefix, data, meta, **kwargs)
        extra = kwargs.get('extra_notification_tokens', {})
        self.notification_body.extra_notification_tokens = extra
        self.notification_title.extra_notification_tokens = extra
        self.notification_urls.extra_notification_tokens = extra

    notification_urls = StringListField(_l('Notification URL List'),
                                        validators=[validators.Optional(), ValidateAppRiseServers(), ValidateJinja2Template()])
    notification_title = StringField(_l('Notification Title'),
                                     default='ChangeDetection.io Notification - {{ watch_url }}',
                                     validators=[validators.Optional(), ValidateJinja2Template()])
    notification_body = TextAreaField(_l('Notification Body'),
                                      default='{{ watch_url }} had a change.',
                                      validators=[validators.Optional(), ValidateJinja2Template()])
    notification_format = SelectField(_l('Notification format'),
                                      choices=list(valid_notification_formats.items()))
    base_url = StringField(_l('Notification base URL override'),
                           validators=[validators.Optional()],
                           render_kw={"placeholder": os.getenv('BASE_URL', _l('Not set'))})
    save_button = SubmitField(_l('Save'), render_kw={"class": "pure-button pure-button-primary"})


class importForm(Form):
    processor = RadioField(_l('Processor'), choices=lambda: processors.available_processors(), default=processors.get_default_processor)
    urls = TextAreaField(_l('URLs'))
    xlsx_file = FileField(_l('Upload .xlsx file'), validators=[FileAllowed(['xlsx'], _l('Must be .xlsx file!'))])
    file_mapping = SelectField(_l('File mapping'), [validators.DataRequired()], choices={('wachete', 'Wachete mapping'), ('custom','Custom mapping')})

