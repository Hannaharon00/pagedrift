from flask import Blueprint, request, url_for, flash, render_template, redirect
from flask_babel import gettext
import time
from loguru import logger

from changedetectionio.store import ChangeDetectionStore
from changedetectionio.auth_decorator import login_optionally_required
from changedetectionio import html_tools

