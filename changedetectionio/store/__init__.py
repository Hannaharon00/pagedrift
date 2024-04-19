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

# Import the base class and helpers
from .file_saving_datastore import (FileSavingDataStore, load_all_watches, load_all_tags, load_watch_from_file,
                                    save_json_atomic)
from .updates import DatastoreUpdatesMixin

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

        if HAS_ORJSON:
            with open(changedetection_json, 'rb') as f:
                return orjson.loads(f.read())
        else:
            with open(changedetection_json, 'r', encoding='utf-8') as f:
                return json.load(f)

    def _apply_settings(self, settings_data):
        """
        Apply loaded settings data to internal data structure.

        Args:
            settings_data: Dictionary loaded from changedetection.json
        """
        # Apply top-level fields
        if 'app_guid' in settings_data:
            self.__data['app_guid'] = settings_data['app_guid']
        if 'build_sha' in settings_data:
            self.__data['build_sha'] = settings_data['build_sha']
        if 'version_tag' in settings_data:
            self.__data['version_tag'] = settings_data['version_tag']

        # Apply settings sections
        if 'settings' in settings_data:
            if 'headers' in settings_data['settings']:
                self.__data['settings']['headers'].update(settings_data['settings']['headers'])
            if 'requests' in settings_data['settings']:
                self.__data['settings']['requests'].update(settings_data['settings']['requests'])
            if 'application' in settings_data['settings']:
                self.__data['settings']['application'].update(settings_data['settings']['application'])

                # Use our Tags dict with cleanup helpers etc
                # @todo Same for Watches
                existing_tags = settings_data.get('settings', {}).get('application', {}).get('tags') or {}
                self.__data['settings']['application']['tags'] = TagsDict(existing_tags, datastore_path=self.datastore_path)

        # More or less for the old format which had this data in the one url-watches.json
        # cant hurt to leave it here,
        if 'watching' in settings_data:
            self.__data['watching'].update(settings_data['watching'])

    def _rehydrate_tags(self):
        """Rehydrate tag entities from stored data into Tag objects with restock_diff processor."""
        from ..model import Tag

        for uuid, tag in self.__data['settings']['application']['tags'].items():
            # Force processor to restock_diff for override functionality (technical debt)
            tag['processor'] = 'restock_diff'

            self.__data['settings']['application']['tags'][uuid] = Tag.model(
                datastore_path=self.datastore_path,
                __datastore=self.__data,
                default=tag
            )
            logger.info(f"Tag: {uuid} {tag['title']}")

    def _rehydrate_watches(self):
        """Rehydrate watch entities from stored data (converts dicts to Watch objects)."""
        watch_count = len(self.__data.get('watching', {}))
        if watch_count == 0:
            return

        logger.info(f"Rehydrating {watch_count} watches...")
        watching_rehydrated = {}
        for uuid, watch_dict in self.__data.get('watching', {}).items():
            if isinstance(watch_dict, dict):
                watching_rehydrated[uuid] = self.rehydrate_entity(uuid, watch_dict)
            else:
                logger.error(f"Watch UUID {uuid} already rehydrated")

        self.__data['watching'] = watching_rehydrated
        logger.success(f"Rehydrated {watch_count} watches into Watch objects")


    def _load_state(self, main_settings_filename="changedetection.json"):
        """
        Load complete datastore state from storage.

        Orchestrates loading of settings, watches, and tags using polymorphic methods.
        """
        # Load settings
        settings_data = self._load_settings(filename=main_settings_filename)
        self._apply_settings(settings_data)

        # Load watches, scan them from the disk
        self._load_watches()
        self._rehydrate_watches()

        # Load tags from individual tag.json files
        # These will override any tags in settings (migration path)
        self._load_tags()

        # Rehydrate any remaining tags from settings (legacy/fallback)
        self._rehydrate_tags()

    def reload_state(self, datastore_path, include_default_watches, version_tag):
        """
        Load datastore from storage or create new one.

        Supports two scenarios:
        1. NEW format: changedetection.json exists → load and run updates if needed
        2. EMPTY: No changedetection.json → create new OR trigger migration from legacy

        Note: Legacy url-watches.json migration happens in update_26, not here.
        """
        logger.info(f"Datastore path is '{datastore_path}'")

        # CRITICAL: Update datastore_path (was using old path from __init__)
        self.datastore_path = datastore_path

        # Initialize data structure
        self.__data = App.model(datastore_path=datastore_path)
        self.json_store_path = os.path.join(self.datastore_path, "changedetection.json")

        # Base definition for all watchers (deepcopy part of #569)
        self.generic_definition = deepcopy(Watch.model(datastore_path=datastore_path, __datastore=self.__data, default={}))

        # Load build SHA if available (Docker deployments)
        if path.isfile('changedetectionio/source.txt'):
            with open('changedetectionio/source.txt') as f:
                self.__data['build_sha'] = f.read()

        # Check if datastore already exists
        changedetection_json = os.path.join(self.datastore_path, "changedetection.json")
        changedetection_json_old_schema = os.path.join(self.datastore_path, "url-watches.json")

