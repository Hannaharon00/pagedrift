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

