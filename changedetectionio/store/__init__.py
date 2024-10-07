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

        if os.path.exists(changedetection_json):
            # Run schema updates if needed
            # Pass current schema version from loaded datastore (defaults to 0 if not set)
            # Load existing datastore (changedetection.json + watch.json files)
            logger.info("Loading existing datastore")
            self._load_state()
            current_schema = self.data['settings']['application'].get('schema_version', 0)
            self.run_updates(current_schema_version=current_schema)

        # Legacy datastore detected - trigger migration, even works if the schema is much before the migration step.
        elif os.path.exists(changedetection_json_old_schema):

            logger.critical(f"Legacy datastore detected at {changedetection_json_old_schema}, loading and running updates")
            self._load_state(main_settings_filename="url-watches.json")
            # update 26 will load the whole old config from disk to __data
            current_schema = self.__data['settings']['application'].get('schema_version', 0)
            self.run_updates(current_schema_version=current_schema)
            # Probably tags were also shifted to disk and many other changes, so best to reload here.
            self._load_state()

        else:
            # No datastore yet - check if this is a fresh install or legacy migration
            self.init_fresh_install(include_default_watches=include_default_watches,
                                    version_tag=version_tag)
            # Maybe they copied a bunch of watch subdirs across too
            self._load_state()

    def init_fresh_install(self, include_default_watches, version_tag):
      # Generate app_guid FIRST (required for all operations)
        if "pytest" in sys.modules or "PYTEST_CURRENT_TEST" in os.environ:
            self.__data['app_guid'] = "test-" + str(uuid_builder.uuid4())
        else:
            self.__data['app_guid'] = str(uuid_builder.uuid4())

        # Generate RSS access token
        self.__data['settings']['application']['rss_access_token'] = secrets.token_hex(16)

        # Generate API access token
        self.__data['settings']['application']['api_access_token'] = secrets.token_hex(16)
        logger.warning(f"No datastore found, creating new datastore at {self.datastore_path}")

        # Set schema version to latest (no updates needed)
        latest_update_available = self.get_updates_available().pop()
        logger.info(f"Marking fresh install to schema version {latest_update_available}")
        self.__data['settings']['application']['schema_version'] = latest_update_available

        # Add default watches if requested
        if include_default_watches:
            self.add_watch(
                url='https://news.ycombinator.com/',
                tag='Tech news',
                extras={'fetch_backend': 'html_requests'}
            )
            self.add_watch(
                url='https://changedetection.io/CHANGELOG.txt',
                tag='changedetection.io',
                extras={'fetch_backend': 'html_requests'}
            )

        # Create changedetection.json immediately
        try:
            self._save_settings()
            logger.info("Created changedetection.json for new datastore")
        except Exception as e:
            logger.error(f"Failed to create initial changedetection.json: {e}")



        # Set version tag
        self.__data['version_tag'] = version_tag

        # Validate proxies.json if it exists
        _ = self.proxy_list  # Just to test parsing

        # Ensure app_guid exists (for datastores loaded from existing files)
        if 'app_guid' not in self.__data:
            if "pytest" in sys.modules or "PYTEST_CURRENT_TEST" in os.environ:
                self.__data['app_guid'] = "test-" + str(uuid_builder.uuid4())
            else:
                self.__data['app_guid'] = str(uuid_builder.uuid4())
            self.commit()

        # Ensure RSS access token exists
        if not self.__data['settings']['application'].get('rss_access_token'):
            secret = secrets.token_hex(16)
            self.__data['settings']['application']['rss_access_token'] = secret
            self.commit()

        # Ensure API access token exists
        if not self.__data['settings']['application'].get('api_access_token'):
            secret = secrets.token_hex(16)
            self.__data['settings']['application']['api_access_token'] = secret
            self.commit()

        # Handle password reset lockfile
        password_reset_lockfile = os.path.join(self.datastore_path, "removepassword.lock")
        if path.isfile(password_reset_lockfile):
            self.remove_password()
            unlink(password_reset_lockfile)

    def rehydrate_entity(self, uuid, entity, processor_override=None):
        """Set the dict back to the dict Watch object"""
        entity['uuid'] = uuid

        if processor_override:
            watch_class = get_custom_watch_obj_for_processor(processor_override)
            entity['processor'] = processor_override
        else:
            watch_class = get_custom_watch_obj_for_processor(entity.get('processor'))

        if entity.get('processor') != 'text_json_diff':
            logger.trace(f"Loading Watch object '{watch_class.__module__}.{watch_class.__name__}' for UUID {uuid}")

        entity = watch_class(datastore_path=self.datastore_path, __datastore=self.__data, default=entity)
        return entity

    # ============================================================================
    # FileSavingDataStore Abstract Method Implementations
    # ============================================================================

    def _watch_exists(self, uuid):
        """Check if watch exists in datastore."""
        return uuid in self.__data['watching']

    def _get_watch_dict(self, uuid):
        """Get watch as dictionary."""
        return dict(self.__data['watching'][uuid])

    def _build_settings_data(self):
        """
        Build settings data structure for saving.

        Tags behavior depends on schema version:
        - Before update_28 (schema < 28): Tags saved in settings for migration
        - After update_28 (schema >= 28): Tags excluded from settings (in individual files)

        Returns:
            dict: Settings data ready for serialization
        """
        import copy

        # Deep copy settings to avoid modifying the original
        settings_copy = copy.deepcopy(self.__data['settings'])

        # Is saved as {uuid}/tag.json
        settings_copy['application']['tags'] = {}

        return {
            'note': 'Settings file - watches are in {uuid}/watch.json, tags are in {uuid}/tag.json',
            'app_guid': self.__data.get('app_guid'),
            'settings': settings_copy,
            'build_sha': self.__data.get('build_sha'),
            'version_tag': self.__data.get('version_tag')
        }

    def _save_settings(self):
        """
        Save settings to storage.

        File backend implementation: saves to changedetection.json
        Implementation of abstract method from FileSavingDataStore.
        Uses the generic save_json_atomic helper.

        Raises:
            OSError: If disk is full or other I/O error
        """
        settings_data = self._build_settings_data()
        changedetection_json = os.path.join(self.datastore_path, "changedetection.json")
        save_json_atomic(changedetection_json, settings_data, label="settings")

    def _load_watches(self):
        """
        Load all watches from storage.

        File backend implementation: reads individual watch.json files
        Implementation of abstract method from FileSavingDataStore.
        Delegates to helper function and stores results in internal data structure.
        """

        # Store loaded data
        # @note this will also work for the old legacy format because self.__data['watching'] should already have them loaded by this point.
        self.__data['watching'].update(load_all_watches(
            self.datastore_path,
            self.rehydrate_entity
        ))
        logger.debug(f"Loaded {len(self.__data['watching'])} watches")

    def _load_tags(self):
        """
        Load all tags from storage.

        File backend implementation: reads individual tag.json files.
        Tags loaded from files override any tags in settings (migration path).
        """
        from ..model import Tag

        def rehydrate_tag(uuid, entity_dict):
            """Rehydrate tag as Tag object with forced restock_diff processor."""
            entity_dict['uuid'] = uuid
            entity_dict['processor'] = 'restock_diff'  # Force processor for override functionality

            return Tag.model(
                datastore_path=self.datastore_path,
                __datastore=self.__data,
                default=entity_dict
            )

        tags = load_all_tags(
            self.datastore_path,
            rehydrate_tag
        )

        # Override settings tags with loaded tags
        # This ensures tag.json files take precedence over settings
        if tags:
            self.__data['settings']['application']['tags'].update(tags)
            logger.info(f"Loaded {len(tags)} tags from individual tag.json files")

    def _delete_watch(self, uuid):
        """
        Delete a watch from storage.

        File backend implementation: deletes entire {uuid}/ directory recursively.
        Implementation of abstract method from FileSavingDataStore.

        Args:
            uuid: Watch UUID to delete
        """
        watch_dir = os.path.join(self.datastore_path, uuid)
        if os.path.exists(watch_dir):
            shutil.rmtree(watch_dir)
            logger.info(f"Deleted watch directory: {watch_dir}")

    # ============================================================================
    # Watch Management Methods
    # ============================================================================

    def set_last_viewed(self, uuid, timestamp, send_signal=True):
        logger.debug(f"Setting watch UUID: {uuid} last viewed to {int(timestamp)}")
        self.data['watching'][uuid].update({'last_viewed': int(timestamp)})
        self.data['watching'][uuid].commit()

        # Bulk callers (mark-all-viewed) pass send_signal=False and emit one summary event
        # afterwards instead. Each signal fans out to handle_watch_update(), which rescans
        # EVERY watch twice (errored_count + unread_changes_count), takes the queue and
        # worker-pool locks, and broadcasts 3 socket events — so signalling per watch makes
        # a bulk mark O(n^2) with 3n emits, and floods every connected browser with n
        # row updates it will immediately re-render anyway.
        if send_signal:
            watch_check_update = signal('watch_check_update')
            if watch_check_update:
                watch_check_update.send(watch_uuid=uuid)

    def remove_password(self):
        self.__data['settings']['application']['password'] = False
        self.commit()

    def clear_all_last_checksums(self):
        """
        Delete all last-checksum.txt files to force reprocessing of all watches.

        This should be called when global settings change, since watches inherit
        configuration and need to reprocess even if their individual watch dict
        hasn't been modified.

        Note: We delete the checksum file rather than setting was_edited=True because:
        - was_edited is not persisted across restarts
        - File deletion ensures reprocessing works across app restarts
        """
        deleted_count = 0
        for uuid in self.__data['watching'].keys():
            watch = self.__data['watching'][uuid]
            if watch.data_dir:
                checksum_file = os.path.join(watch.data_dir, 'last-checksum.txt')
                if os.path.isfile(checksum_file):
                    try:
                        os.remove(checksum_file)
                        deleted_count += 1
                        logger.debug(f"Cleared checksum for watch {uuid}")
                    except OSError as e:
                        logger.warning(f"Failed to delete checksum file for {uuid}: {e}")

