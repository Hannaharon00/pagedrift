import os
import re
import threading

from changedetectionio.validate_url import is_safe_valid_url
from changedetectionio.favicon_utils import get_favicon_mime_type

from . import auth
from changedetectionio import queuedWatchMetaData, strtobool
from changedetectionio import worker_pool
from flask import request, make_response, send_from_directory
from flask_restful import abort, Resource
from loguru import logger
import copy

from . import validate_openapi_request, get_readonly_watch_fields, strip_internal_api_fields
from ..notification import valid_notification_formats
from ..notification.handler import newline_re


def validate_time_schedule_limit(json_data):
    """
    Validate the optional timezone inside time_schedule_limit.

    The edit form runs validateTimeZoneName on this field, but the API did not -
    the OpenAPI schema for time_schedule_limit does not declare a `timezone`
    property at all and does not set additionalProperties:false, so any string
    passed straight through and was stored.

    That matters because the scheduler resolves it with arrow.now(tz), which
    raises on an unknown zone. Before the ticker thread was hardened, a single
    authenticated PUT with a bogus timezone stopped scheduling for EVERY watch
    on the instance. It is now contained to the one watch, but that watch would
    still silently never be checked again, so reject it at the boundary.

    Returns None if valid, or an error message string if invalid.
    """
    schedule = json_data.get('time_schedule_limit')
    if not isinstance(schedule, dict):
        return None

    tz_name = schedule.get('timezone')
    if not tz_name:
        return None

    if not isinstance(tz_name, str):
        return "time_schedule_limit.timezone must be a string IANA timezone name, e.g. 'Europe/Berlin'."

    from zoneinfo import available_timezones
    if tz_name.strip() not in available_timezones():
        return (f"time_schedule_limit.timezone '{tz_name}' is not a valid timezone name. "
                f"Use an IANA name such as 'Europe/Berlin' or 'UTC'.")

    return None


