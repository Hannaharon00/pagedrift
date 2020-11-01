from changedetectionio.strtobool import strtobool
from flask_restful import abort, Resource
from flask import request
from functools import wraps
from . import auth, validate_openapi_request
from ..validate_url import is_safe_valid_url
import json

# Number of URLs above which import switches to background processing
IMPORT_SWITCH_TO_BACKGROUND_THRESHOLD = 20


