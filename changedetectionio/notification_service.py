#!/usr/bin/env python3

"""
Notification Service Module
Extracted from update_worker.py to provide standalone notification functionality
for both sync and async workers
"""
import datetime

import pytz
from loguru import logger
import time

from changedetectionio.notification import default_notification_format, valid_notification_formats


def _check_cascading_vars(datastore, var_name, watch):
    """
    Check notification variables in cascading priority:
    Individual watch settings > Tag settings > Global settings
    """
    from changedetectionio.notification import (
        USE_SYSTEM_DEFAULT_NOTIFICATION_FORMAT_FOR_WATCH,
        default_notification_body,
        default_notification_title
    )

    # Would be better if this was some kind of Object where Watch can reference the parent datastore etc
    v = watch.get(var_name)
    if v and not watch.get('notification_muted'):
        if var_name == 'notification_format' and v == USE_SYSTEM_DEFAULT_NOTIFICATION_FORMAT_FOR_WATCH:
            return datastore.data['settings']['application'].get('notification_format') or default_notification_format

        return v

    tags = datastore.get_all_tags_for_watch(uuid=watch.get('uuid'))
    if tags:
        for tag_uuid, tag in tags.items():
            v = tag.get(var_name)
            if v and not tag.get('notification_muted'):
                return v

    if datastore.data['settings']['application'].get(var_name):
        return datastore.data['settings']['application'].get(var_name)

    # Otherwise could be defaults
    if var_name == 'notification_format':
        return USE_SYSTEM_DEFAULT_NOTIFICATION_FORMAT_FOR_WATCH
    if var_name == 'notification_body':
        return default_notification_body
    if var_name == 'notification_title':
        return default_notification_title

    return None


def watch_will_send_content_changed_notification(datastore, watch):
    """Single source of truth for: will a *content changed* notification actually be
    delivered for this watch?

    This mirrors exactly the decision the worker + send_content_changed_notification()
    make together: the watch must not be muted, and a notification URL must resolve via
    the watch > tag > global cascade. Anything that wants to know "is a notification
    going to fire?" (e.g. the worker deciding whether to spend tokens pre-computing the
    LLM change summary that fills the notification body) should ask here, so the answer
    can never drift from what actually gets sent.
    """
    if not watch or watch.get('notification_muted'):
        return False
    return bool(_check_cascading_vars(datastore, 'notification_urls', watch))


class FormattableTimestamp(str):
    """
    A str subclass representing a formatted datetime. As a plain string it renders
    with the default format, but can also be called with a custom format argument
    in Jinja2 templates:

        {{ change_datetime }}                        → '2024-01-15 10:30:00 UTC'
        {{ change_datetime(format='%Y') }}           → '2024'
        {{ change_datetime(format='%A') }}           → 'Monday'
        {{ change_datetime(format='%Y-%m-%d') }}     → '2024-01-15'

    Being a str subclass means it is natively JSON serializable.
    """
    _DEFAULT_FORMAT = '%Y-%m-%d %H:%M:%S %Z'

    def __new__(cls, timestamp):
        dt = datetime.datetime.fromtimestamp(int(timestamp), tz=pytz.UTC)
        local_tz = datetime.datetime.now().astimezone().tzinfo
        dt_local = dt.astimezone(local_tz)
        try:
            formatted = dt_local.strftime(cls._DEFAULT_FORMAT)
        except Exception:
            formatted = dt_local.isoformat()
        instance = super().__new__(cls, formatted)
        instance._dt = dt_local
        return instance

    def __call__(self, format=_DEFAULT_FORMAT):
        try:
            return self._dt.strftime(format)
        except Exception:
            return self._dt.isoformat()


class FormattableExtract(str):
    """
    A str subclass that holds only the extracted changed fragments from a diff.
    Used for {{diff_changed_from}} and {{diff_changed_to}} tokens.

        {{ diff_changed_from }}   → old value(s) only, e.g. "$99.99"
        {{ diff_changed_to }}     → new value(s) only, e.g. "$109.99"

    Multiple changed fragments are joined with newlines.
    Being a str subclass means it is natively JSON serializable.
    """
    def __new__(cls, prev_snapshot, current_snapshot, extract_fn, escape_output=False):
        if prev_snapshot or current_snapshot:
            from changedetectionio import diff as diff_module
            # word_diff=True is required — placemarker extraction regexes only exist in word-diff output
            raw = diff_module.render_diff(prev_snapshot or '', current_snapshot or '', word_diff=True)
            extracted = extract_fn(raw)
        else:
            extracted = ''
        if escape_output and extracted:
            # Placemarkers (@removed_PLACEMARKER_OPEN etc) contain no HTML chars,
            # so html_escape leaves them intact — they still get swapped to <span>
            # tags later by apply_service_tweaks. See GHSA-q8xq-qg4x-wphg.
            from markupsafe import escape as html_escape
            extracted = str(html_escape(extracted))
        instance = super().__new__(cls, extracted)
        return instance


class FormattableDiff(str):
    """
    A str subclass representing a rendered diff. As a plain string it renders
    with the default options for that variant, but can be called with custom
    arguments in Jinja2 templates:

        {{ diff }}                                    → default diff output
        {{ diff(lines=5) }}                           → truncate to 5 lines
        {{ diff(added_only=true) }}                   → only show added lines
        {{ diff(removed_only=true) }}                 → only show removed lines
        {{ diff(context=3) }}                         → 3 lines of context around changes
        {{ diff(word_diff=false) }}                   → line-level diff instead of word-level
        {{ diff(lines=10, added_only=true) }}         → combine args
        {{ diff_added(lines=5) }}                     → works on any diff_* variant too

    Being a str subclass means it is natively JSON serializable.
    """
    def __new__(cls, prev_snapshot, current_snapshot, escape_output=False, **base_kwargs):
        if prev_snapshot or current_snapshot:
            from changedetectionio import diff as diff_module
            rendered = diff_module.render_diff(prev_snapshot, current_snapshot, **base_kwargs)
        else:
            rendered = ''
        if escape_output and rendered:
            # Placemarkers (@removed_PLACEMARKER_OPEN etc) contain no HTML chars,
            # so html_escape leaves them intact — they still get swapped to <span>
            # tags later by apply_service_tweaks. See GHSA-q8xq-qg4x-wphg.
            from markupsafe import escape as html_escape
            rendered = str(html_escape(rendered))
        instance = super().__new__(cls, rendered)
        instance._prev = prev_snapshot
        instance._current = current_snapshot
        instance._base_kwargs = base_kwargs
        instance._escape_output = escape_output
        return instance

    def __call__(self, lines=None, added_only=False, removed_only=False, context=0,
                 word_diff=None, case_insensitive=False, ignore_junk=False):
        from changedetectionio import diff as diff_module
        kwargs = dict(self._base_kwargs)

        if added_only:
            kwargs['include_removed'] = False
        if removed_only:
            kwargs['include_added'] = False
        if context:
            kwargs['context_lines'] = int(context)
        if word_diff is not None:
            kwargs['word_diff'] = bool(word_diff)
        if case_insensitive:
            kwargs['case_insensitive'] = True
        if ignore_junk:
            kwargs['ignore_junk'] = True

        result = diff_module.render_diff(self._prev or '', self._current or '', **kwargs)

        if lines is not None:
            result = '\n'.join(result.splitlines()[:int(lines)])

        if self._escape_output and result:
            from markupsafe import escape as html_escape
            result = str(html_escape(result))

        return result



# What is passed around as notification context, also used as the complete list of valid {{ tokens }}
class NotificationContextData(dict):
    def __init__(self, initial_data=None, **kwargs):
        # ValidateJinja2Template() validates against the keynames of this dict to check for valid tokens in the body (user submission)
        super().__init__({
            'base_url': None,
            'change_datetime': FormattableTimestamp(time.time()),
            'current_snapshot': None,
            'diff': FormattableDiff('', ''),
            'diff_clean': FormattableDiff('', '', include_change_type_prefix=False),
            'diff_added': FormattableDiff('', '', include_removed=False),
            'diff_added_clean': FormattableDiff('', '', include_removed=False, include_change_type_prefix=False),
            'diff_full': FormattableDiff('', '', include_equal=True),
            'diff_full_clean': FormattableDiff('', '', include_equal=True, include_change_type_prefix=False),
            'diff_patch': FormattableDiff('', '', patch_format=True),
            'diff_removed': FormattableDiff('', '', include_added=False),
            'diff_removed_clean': FormattableDiff('', '', include_added=False, include_change_type_prefix=False),
            'diff_changed_from': FormattableExtract('', '', extract_fn=lambda x: x),
            'diff_changed_to': FormattableExtract('', '', extract_fn=lambda x: x),
            'diff_url': None,
            # Always the raw +/- diff regardless of LLM summary override (populated in handler.py from {{diff}})
            'raw_diff': FormattableDiff('', ''),
            'markup_text_links_to_html_links': False, # If automatic conversion of plaintext to HTML should happen
            # Safe-empty default so restock tokens ({{ restock.price }} etc.) are a valid,
            # non-crashing token for every watch. Restock watches override this via
            # processors/restock_diff extra_notification_token_values().
            'restock': {}, #@TODO ! should be fixed in a refactor of all processor types, maybe fetching a empty key returns null or even restock (or similar) should actually come from the JSON in the datadir processor-restock-diff.json etc
            'notification_timestamp': time.time(),
            'prev_snapshot': None,
            'preview_url': None,
            'screenshot': None,
            'timestamp_from': None,
            'timestamp_to': None,
            'triggered_text': None,
            'llm_summary': None,     # AI plain-English summary of what changed (requires AI intent to be configured)
            'llm_intent': None,      # The intent that was evaluated (watch-level or inherited from tag)
            'uuid': 'XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX',  # Converted to 'watch_uuid' in create_notification_parameters
            'watch_mime_type': None,
            'watch_tag': None,
            'watch_title': None,
            'watch_url': 'https://WATCH-PLACE-HOLDER/',
            'watch_open_url': 'https://WATCH-PLACE-HOLDER/',  # watch['link_to_open'] when set, otherwise the same as watch_url
            'watch_uuid': 'XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX',  # Converted to 'watch_uuid' in create_notification_parameters
        })

        # Apply any initial data passed in
        self.update({'watch_uuid': self.get('uuid')})
        if initial_data:
            self.update(initial_data)

        # Apply any keyword arguments
        if kwargs:
            self.update(kwargs)

        n_format = self.get('notification_format')
        if n_format and not valid_notification_formats.get(n_format):
            raise ValueError(f'Invalid notification format: "{n_format}"')

    def set_random_for_validation(self):
        import random, string
        """Randomly fills all dict keys with random strings (for validation/testing). 
        So we can test the output in the notification body
        """
        for key in self.keys():
            if key in ['uuid', 'time', 'watch_uuid', 'change_datetime'] or key.startswith('diff'):
                continue
            rand_str = 'RANDOM-PLACEHOLDER-'+''.join(random.choices(string.ascii_letters + string.digits, k=12))
            self[key] = rand_str

    def __setitem__(self, key, value):
        if key == 'notification_format' and isinstance(value, str) and not value.startswith('RANDOM-PLACEHOLDER-'):
            if not valid_notification_formats.get(value):
                raise ValueError(f'Invalid notification format: "{value}"')

        super().__setitem__(key, value)

def add_rendered_diff_to_notification_vars(notification_scan_text:str, prev_snapshot:str, current_snapshot:str, word_diff:bool, escape_output:bool=False):
    """
    Efficiently renders only the diff placeholders that are actually used in the notification text.

    Scans the notification template for diff placeholder usage (diff, diff_added, diff_clean, etc.)
    and only renders those specific variants, avoiding expensive render_diff() calls for unused placeholders.
    Uses LRU caching to avoid duplicate renders when multiple placeholders share the same arguments.

    Args:
        notification_scan_text: The notification template text to scan for placeholders
        prev_snapshot: Previous version of content for diff comparison
        current_snapshot: Current version of content for diff comparison
        word_diff: Whether to use word-level (True) or line-level (False) diffing
        escape_output: If True, the rendered diff output is HTML-escaped. Used for HTML-format
            notifications so attacker-controlled page content can't inject live markup.
            Both the cached str representation and the result of {{ diff(...) }} calls are escaped.

    Returns:
        dict: Only the diff placeholders that were found in notification_scan_text, with rendered content
    """
    import re

    now = time.time()

    # Define base kwargs for each diff variant — these become the stored defaults
    # on the FormattableDiff object, so {{ diff(lines=5) }} overrides on top of them
    diff_specs = {
        'diff': {'word_diff': word_diff},
        'diff_clean': {'word_diff': word_diff, 'include_change_type_prefix': False},
        'diff_added': {'word_diff': word_diff, 'include_removed': False},
        'diff_added_clean': {'word_diff': word_diff, 'include_removed': False, 'include_change_type_prefix': False},
        'diff_full': {'word_diff': word_diff, 'include_equal': True},
        'diff_full_clean': {'word_diff': word_diff, 'include_equal': True, 'include_change_type_prefix': False},
        'diff_patch': {'word_diff': word_diff, 'patch_format': True},
        'diff_removed': {'word_diff': word_diff, 'include_added': False},
        'diff_removed_clean': {'word_diff': word_diff, 'include_added': False, 'include_change_type_prefix': False},
    }

    from changedetectionio.diff import extract_changed_from, extract_changed_to
    extract_specs = {
        'diff_changed_from': extract_changed_from,
        'diff_changed_to':   extract_changed_to,
    }

    ret = {}
    rendered_count = 0
    # Only create FormattableDiff/FormattableExtract objects for diff keys actually used in the notification text
    for key in NotificationContextData().keys():
        if not key.startswith('diff'):
            continue
        pattern = rf"(?<![A-Za-z0-9_]){re.escape(key)}(?![A-Za-z0-9_])"
        if not re.search(pattern, notification_scan_text, re.IGNORECASE):
            continue
        if key in diff_specs:
            ret[key] = FormattableDiff(prev_snapshot, current_snapshot, escape_output=escape_output, **diff_specs[key])
            rendered_count += 1
        elif key in extract_specs:
            ret[key] = FormattableExtract(prev_snapshot, current_snapshot, extract_fn=extract_specs[key], escape_output=escape_output)
            rendered_count += 1

    if rendered_count:
        logger.trace(f"Rendered {rendered_count} diff placeholder(s) {sorted(ret.keys())} in {time.time() - now:.3f}s")

    return ret

