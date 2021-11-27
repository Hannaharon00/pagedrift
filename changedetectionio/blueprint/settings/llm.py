import json
import logging
import os
import re

from flask import Blueprint, jsonify, redirect, url_for, flash
from flask_babel import gettext
from loguru import logger

from changedetectionio.store import ChangeDetectionStore
from changedetectionio.auth_decorator import login_optionally_required


class _LiteLLMWarningCapture(logging.Handler):
    """Capture warnings emitted on the 'LiteLLM' stdlib logger during a single call.

    litellm.get_valid_models() catches HTTP/auth errors internally, logs a warning,
    and returns []. Without capturing that warning we can't tell the user *why*
    no models came back (bad key vs. offline vs. genuinely empty model list).
    """
    def __init__(self):
        super().__init__(level=logging.WARNING)
        self.messages = []

    def emit(self, record):
        try:
            self.messages.append(record.getMessage())
        except Exception:
            pass


