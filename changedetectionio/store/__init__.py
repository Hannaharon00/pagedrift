import shutil

from changedetectionio.strtobool import strtobool

from changedetectionio.validate_url import is_safe_valid_url

from flask import (
    flash,
    has_request_context
)
from flask_babel import gettext

from ..model import App, Watch
from copy import deepcopy
from os import path, unlink
import json
import os
import re
import secrets
import sys
import time
import uuid as uuid_builder
from loguru import logger
from blinker import signal

from ..model.Tags import TagsDict

# Try to import orjson for faster JSON serialization
try:
    import orjson

    HAS_ORJSON = True
except ImportError:
    HAS_ORJSON = False

from ..processors import get_custom_watch_obj_for_processor, find_processors

# Because the server will run as a daemon and wont know the URL for notification links when firing off a notification
BASE_URL_NOT_SET_TEXT = '("Base URL" not set - see settings - notifications)'

dictfilt = lambda x, y: dict([(i, x[i]) for i in x if i in set(y)])


class ChangeDetectionStore(DatastoreUpdatesMixin, FileSavingDataStore):
    __version_check = True

    def __init__(self, datastore_path="/datastore", include_default_watches=True, version_tag="0.0.0"):
        # Initialize parent class
        super().__init__()

        # Should only be active for docker
        # logging.basicConfig(filename='/dev/stdout', level=logging.INFO)
        self.datastore_path = datastore_path
        self.start_time = time.time()
        self.save_version_copy_json_db(version_tag)
        self.reload_state(datastore_path=datastore_path, include_default_watches=include_default_watches, version_tag=version_tag)

    def save_version_copy_json_db(self, version_tag):
        """
        Create version-tagged backup of changedetection.json.

        This is called on version upgrades to preserve a backup in case
        the new version has issues.
        """
        import re

        version_text = re.sub(r'\D+', '-', version_tag)
        db_path = os.path.join(self.datastore_path, "changedetection.json")
        db_path_version_backup = os.path.join(self.datastore_path, f"changedetection-{version_text}.json")

        if not os.path.isfile(db_path_version_backup) and os.path.isfile(db_path):
            from shutil import copyfile
            logger.info(f"Backing up changedetection.json due to new version to '{db_path_version_backup}'.")
            copyfile(db_path, db_path_version_backup)

    def _load_settings(self, filename="changedetection.json"):
        """
        Load settings from storage.

        File backend implementation: reads from changedetection.json

        Returns:
            dict: Settings data loaded from storage
        """
        changedetection_json = os.path.join(self.datastore_path, filename)

        logger.info(f"Loading settings from {changedetection_json}")

