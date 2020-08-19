from flask import Blueprint, request, redirect, url_for, flash, render_template
from loguru import logger

from changedetectionio.store import ChangeDetectionStore
from changedetectionio.auth_decorator import login_optionally_required

