from flask import Blueprint, render_template, request, jsonify, make_response, flash, redirect, url_for
from flask_babel import gettext
from loguru import logger

from changedetectionio import forms
from changedetectionio.auth_decorator import login_optionally_required
from . import browser_config
from changedetectionio.store import ChangeDetectionStore
from changedetectionio.validate_url import is_fetch_url_allowed


