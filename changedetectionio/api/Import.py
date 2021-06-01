from changedetectionio.strtobool import strtobool
from flask_restful import abort, Resource
from flask import request
from functools import wraps
from . import auth, validate_openapi_request
from ..validate_url import is_safe_valid_url
import json

# Number of URLs above which import switches to background processing
IMPORT_SWITCH_TO_BACKGROUND_THRESHOLD = 20


def default_content_type(content_type='text/plain'):
    """Decorator to set a default Content-Type header if none is provided."""
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if not request.content_type:
                # Set default content type in the request environment
                request.environ['CONTENT_TYPE'] = content_type
            return f(*args, **kwargs)
        return wrapper
    return decorator


