from changedetectionio import queuedWatchMetaData
from changedetectionio import worker_pool
from flask_restful import abort, Resource
from loguru import logger

import threading
from flask import request
from . import auth

from . import validate_openapi_request, strip_internal_api_fields


def validate_tag_colour(json_data):
    """Return an error message when tag_colour is set to anything but a hex colour.

    The value is rendered into a <style> block, so anything else is CSS injection.
    The OpenAPI schema carries the same pattern, this is the belt to that's braces.
    """
    from changedetectionio.blueprint.tags.colour import is_safe_css_colour

    tag_colour = json_data.get('tag_colour')
    if tag_colour and not is_safe_css_colour(tag_colour):
        return "tag_colour: must be a hex colour, for example #4f8ef7"

    return None


