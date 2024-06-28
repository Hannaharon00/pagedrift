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


def validate_time_between_check_required(json_data):
    """
    Validate that at least one time interval is specified when not using default settings.
    Returns None if valid, or error message string if invalid.
    Defaults to using global settings if time_between_check_use_default is not provided.
    """
    # Default to using global settings if not specified
    use_default = json_data.get('time_between_check_use_default', True)

    # If using default settings, no validation needed
    if use_default:
        return None

    # If not using defaults, check if time_between_check exists and has at least one non-zero value
    time_check = json_data.get('time_between_check')
    if not time_check:
        # No time_between_check provided and not using defaults - this is an error
        return "At least one time interval (weeks, days, hours, minutes, or seconds) must be specified when not using global settings."

    # time_between_check exists, check if it has at least one non-zero value
    if any([
        (time_check.get('weeks') or 0) > 0,
        (time_check.get('days') or 0) > 0,
        (time_check.get('hours') or 0) > 0,
        (time_check.get('minutes') or 0) > 0,
        (time_check.get('seconds') or 0) > 0
    ]):
        return None

    # time_between_check exists but all values are 0 or empty - this is an error
    return "At least one time interval (weeks, days, hours, minutes, or seconds) must be specified when not using global settings."


class WatchHistory(Resource):
    def __init__(self, **kwargs):
        # datastore is a black box dependency
        self.datastore = kwargs['datastore']

    # Get a list of available history for a watch by UUID
    # curl http://localhost:5000/api/v1/watch/<uuid_str:uuid>/history
    @auth.check_token
    @validate_openapi_request('getWatchHistory')
    def get(self, uuid):
        """Get a list of all historical snapshots available for a watch."""
        watch = self.datastore.data['watching'].get(uuid)
        if not watch:
            abort(404, message='No watch exists with the UUID of {}'.format(uuid))
        return watch.history, 200

    # Delete all history/snapshots for a watch, but keep the watch itself
    # curl -X DELETE http://localhost:5000/api/v1/watch/<uuid_str:uuid>/history
    @auth.check_token
    @validate_openapi_request('deleteWatchHistory')
    def delete(self, uuid):
        """Clear all snapshot history for a watch (the watch itself is kept)."""
        if not self.datastore.data['watching'].get(uuid):
            abort(404, message='No watch exists with the UUID of {}'.format(uuid))

        # Same call as the UI "Clear history" button - wipes snapshots/screenshots and
        # resets last_checked etc, while preserving the watch and its processor config
        self.datastore.clear_watch_history(uuid)
        return 'OK', 204


class WatchSingleHistory(Resource):
    def __init__(self, **kwargs):
        # datastore is a black box dependency
        self.datastore = kwargs['datastore']

    @auth.check_token
    @validate_openapi_request('getWatchSnapshot')
    def get(self, uuid, timestamp):
        """Get single snapshot from watch."""
        watch = self.datastore.data['watching'].get(uuid)
        if not watch:
            abort(404, message=f"No watch exists with the UUID of {uuid}")

        if not len(watch.history):
            abort(404, message=f"Watch found but no history exists for the UUID {uuid}")

        if timestamp == 'latest':
            timestamp = list(watch.history.keys())[-1]

        # Validate that the timestamp exists in history
        if timestamp not in watch.history:
            abort(404, message=f"No history snapshot found for timestamp '{timestamp}'")

        if request.args.get('html'):
            content = watch.get_fetched_html(timestamp)
            if content:
                # XSS mitigation (GHSA-cgj8-g98g-4p9x): this is an API endpoint, not a
                # browser-rendered view. The bytes ARE HTML (that's what the caller asked
                # for) but a programmatic client doesn't need text/html — and serving
                # text/html lets attacker-planted <script> in a monitored site execute
                # in our origin if someone opens the URL in a browser.
                #
                # text/plain + explicit utf-8 + nosniff = browser shows inert text,
                # sniffing can't re-classify it as HTML, an absent charset can't be
                # auto-detected as UTF-7 (an alternative XSS vector). API clients
                # still get the raw bytes — they don't care about Content-Type.
                response = make_response(content, 200)
                response.headers['Content-Type'] = 'text/plain; charset=utf-8'
                response.headers['X-Content-Type-Options'] = 'nosniff'
                # Include the timestamp in the download name so downloading multiple
                # snapshots doesn't collide. No extension — the stored bytes are
                # "whatever the fetcher captured" (HTML, JSON, XML, text…), so
                # claiming .html on the download would be a false content-type label
                # for non-HTML watches. The user/curl can rename if needed.
                # Strip to safe filename chars (timestamp is already validated as a
                # watch.history key — this is defense in depth against header injection).
                safe_ts = re.sub(r'[^0-9A-Za-z_-]', '', str(timestamp))[:32] or 'snapshot'
                response.headers['Content-Disposition'] = f'attachment; filename="snapshot-{safe_ts}"'
            else:
                response = make_response("No content found", 404)
                response.mimetype = "text/plain"
        else:
            content = watch.get_history_snapshot(timestamp=timestamp)
            response = make_response(content, 200)
            response.mimetype = "text/plain"

        return response

class WatchHistoryDiff(Resource):
    """
    Generate diff between two historical snapshots.

    Note: This API endpoint currently returns text-based diffs and works best
    with the text_json_diff processor. Future processor types (like image_diff,
    restock_diff) may want to implement their own specialized API endpoints
    for returning processor-specific data (e.g., price charts, image comparisons).

    The web UI diff page (/diff/<uuid>) is processor-aware and delegates rendering
    to processors/{type}/difference.py::render() for processor-specific visualizations.
    """
    def __init__(self, **kwargs):
        # datastore is a black box dependency
        self.datastore = kwargs['datastore']

    @auth.check_token
    @validate_openapi_request('getWatchHistoryDiff')
    def get(self, uuid, from_timestamp, to_timestamp):
        """Generate diff between two historical snapshots."""
        from changedetectionio import diff
        from changedetectionio.notification.handler import apply_service_tweaks

        watch = self.datastore.data['watching'].get(uuid)
        if not watch:
            abort(404, message=f"No watch exists with the UUID of {uuid}")

        if not len(watch.history):
            abort(404, message=f"Watch found but no history exists for the UUID {uuid}")

        history_keys = list(watch.history.keys())

        # Handle 'latest' keyword for to_timestamp
        if to_timestamp == 'latest':
            to_timestamp = history_keys[-1]

        # Handle 'previous' keyword for from_timestamp (second-most-recent)
        if from_timestamp == 'previous':
            if len(history_keys) < 2:
                abort(404, message=f"Not enough history entries. Need at least 2 snapshots for 'previous'")
            from_timestamp = history_keys[-2]

        # Validate timestamps exist
        if from_timestamp not in watch.history:
            abort(404, message=f"From timestamp {from_timestamp} not found in watch history")
        if to_timestamp not in watch.history:
            abort(404, message=f"To timestamp {to_timestamp} not found in watch history")

        # Get the format parameter (default to 'text')
        output_format = request.args.get('format', 'text').lower()

        # Validate format
        if output_format not in valid_notification_formats.keys():
            abort(400, message=f"Invalid format. Must be one of: {', '.join(valid_notification_formats.keys())}")

        # Get the word_diff parameter (default to False - line-level mode)
        word_diff = strtobool(request.args.get('word_diff', 'false'))

        # Get the no_markup parameter (default to False)
        no_markup = strtobool(request.args.get('no_markup', 'false'))

        # Retrieve snapshot contents
        from_version_file_contents = watch.get_history_snapshot(from_timestamp)
        to_version_file_contents = watch.get_history_snapshot(to_timestamp)

        # Get diff preferences from query parameters (matching UI preferences in DIFF_PREFERENCES_CONFIG)
        # Support both 'type' (UI parameter) and 'word_diff' (API parameter) for backward compatibility
        diff_type = request.args.get('type', 'diffLines')
        if diff_type == 'diffWords':
            word_diff = True

        # Get boolean diff preferences with defaults from DIFF_PREFERENCES_CONFIG
        changes_only = strtobool(request.args.get('changesOnly', 'false'))
        ignore_whitespace = strtobool(request.args.get('ignoreWhitespace', 'false'))
        include_removed = strtobool(request.args.get('removed', 'true'))
        include_added = strtobool(request.args.get('added', 'true'))
        include_replaced = strtobool(request.args.get('replaced', 'true'))

        # Generate the diff with all preferences
        content = diff.render_diff(
            previous_version_file_contents=from_version_file_contents,
            newest_version_file_contents=to_version_file_contents,
            ignore_junk=ignore_whitespace,
            include_equal=not changes_only,
            include_removed=include_removed,
            include_added=include_added,
            include_replaced=include_replaced,
            word_diff=word_diff,
        )

        # Skip formatting if no_markup is set
        if no_markup:
            mimetype = "text/plain"
        else:
            # Apply formatting based on the requested format
            if output_format == 'htmlcolor':
                from changedetectionio.notification.handler import apply_html_color_to_body
                content = apply_html_color_to_body(n_body=content)
                mimetype = "text/html"
            else:
                # Apply service tweaks for text/html formats
                # Pass empty URL and title as they're not used for the placeholder replacement we need
                _, content, _ = apply_service_tweaks(
                    url='',
                    n_body=content,
                    n_title='',
                    requested_output_format=output_format
                )
                mimetype = "text/html" if output_format == 'html' else "text/plain"

            if 'html' in output_format:
                content = newline_re.sub('<br>\r\n', content)

        response = make_response(content, 200)
        response.mimetype = mimetype
        return response


