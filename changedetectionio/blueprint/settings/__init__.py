import os
from copy import deepcopy
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo, available_timezones
import secrets
import time
import flask_login
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_babel import gettext

from changedetectionio.store import ChangeDetectionStore
from changedetectionio.auth_decorator import login_optionally_required
from changedetectionio.model.LLMSettings import LLMSettings


