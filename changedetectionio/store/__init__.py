import shutil

from changedetectionio.strtobool import strtobool

from flask import (
    flash,
    has_request_context
)
from flask_babel import gettext

from ..model.Tags import TagsDict

from ..processors import get_custom_watch_obj_for_processor, find_processors

