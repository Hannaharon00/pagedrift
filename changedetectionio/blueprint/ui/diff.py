from flask import Blueprint, request, redirect, url_for, flash, render_template, make_response, send_from_directory
from flask_babel import gettext

import re
import importlib
from loguru import logger
from markupsafe import Markup

from changedetectionio.diff import (
    REMOVED_STYLE, ADDED_STYLE, REMOVED_INNER_STYLE, ADDED_INNER_STYLE,
    REMOVED_PLACEMARKER_OPEN, REMOVED_PLACEMARKER_CLOSED,
    ADDED_PLACEMARKER_OPEN, ADDED_PLACEMARKER_CLOSED,
    CHANGED_PLACEMARKER_OPEN, CHANGED_PLACEMARKER_CLOSED,
    CHANGED_INTO_PLACEMARKER_OPEN, CHANGED_INTO_PLACEMARKER_CLOSED
)
from changedetectionio.store import ChangeDetectionStore
from changedetectionio.blueprint import plaintext_response
from changedetectionio.auth_decorator import login_optionally_required


def _clean_litellm_error(exc) -> str:
    """Return a short, human-readable error string from a litellm exception.

    litellm embeds the raw provider JSON in str(exc), which can be hundreds of
    characters of verbose quota detail.  We try to pull just the provider's
    'message' field; failing that we return the first non-empty line with the
    'litellm.XxxError:' class prefix stripped.
    """
    import json, re
    raw = str(exc)
    # Try to parse the embedded JSON block (starts at first '{')
    brace = raw.find('{')
    if brace >= 0:
        try:
            payload = json.loads(raw[brace:])
            msg = (payload.get('error') or {}).get('message') or ''
            if msg:
                # Take only the first sentence / line — provider messages can be long
                return msg.split('\n')[0].split('. ')[0].strip() + '.'
        except Exception:
            pass
    # Fallback: strip the "litellm.XxxError: litellm.XxxError: providerException - " prefix
    first_line = raw.split('\n')[0]
    first_line = re.sub(r'^(litellm\.\w+:\s*)+', '', first_line)
    first_line = re.sub(r'\w+Exception\s*-\s*', '', first_line).strip()
    return first_line or raw.split('\n')[0]


