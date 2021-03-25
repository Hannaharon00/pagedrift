import io
import json
import os
import re
import shutil
import tempfile
import threading
import zipfile

from flask import Blueprint, render_template, flash, url_for, redirect, request
from flask_babel import gettext, lazy_gettext as _l
from wtforms import Form, BooleanField, SubmitField
from flask_wtf.file import FileField, FileAllowed
from loguru import logger

from changedetectionio.flask_app import login_optionally_required

