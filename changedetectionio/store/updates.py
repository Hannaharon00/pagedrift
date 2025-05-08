"""
Schema update migrations for the datastore.

This module contains all schema version upgrade methods (update_1 through update_N).
These are mixed into ChangeDetectionStore to keep the main store file focused.

IMPORTANT: Each update could be run even when they have a new install and the schema is correct.
Therefore - each `update_n` should be very careful about checking if it needs to actually run.
"""

import os
import re
import shutil
import tarfile
import time
from loguru import logger
from copy import deepcopy


# Try to import orjson for faster JSON serialization
try:
    import orjson
    HAS_ORJSON = True
except ImportError:
    HAS_ORJSON = False

from ..html_tools import TRANSLATE_WHITESPACE_TABLE
from ..processors.restock_diff import Restock, get_price_from_history_str
from ..blueprint.rss import RSS_CONTENT_FORMAT_DEFAULT
from ..model import USE_SYSTEM_DEFAULT_NOTIFICATION_FORMAT_FOR_WATCH

def create_backup_tarball(datastore_path, update_number):
    """
    Create a tarball backup of the entire datastore structure before running an update.

    Includes:
    - All {uuid}/watch.json files
    - All {uuid}/tag.json files
    - changedetection.json (settings, if it exists)
    - url-watches.json (legacy format, if it exists)
    - Directory structure preserved

    Args:
        datastore_path: Path to datastore directory
        update_number: Update number being applied

    Returns:
        str: Path to created tarball, or None if backup failed

    Restoration:
    To restore from a backup:
        cd /path/to/datastore
        tar -xzf before-update-N-timestamp.tar.gz
    This will restore all watch.json and tag.json files and settings to their pre-update state.
    """
    timestamp = int(time.time())
    backup_filename = f"before-update-{update_number}-{timestamp}.tar.gz"
    backup_path = os.path.join(datastore_path, backup_filename)

    try:
        logger.info(f"Creating backup tarball: {backup_filename}")

        with tarfile.open(backup_path, "w:gz") as tar:
            # Backup changedetection.json if it exists (new format)
            changedetection_json = os.path.join(datastore_path, "changedetection.json")
            if os.path.isfile(changedetection_json):
                tar.add(changedetection_json, arcname="changedetection.json")
                logger.debug("Added changedetection.json to backup")

            # Backup url-watches.json if it exists (legacy format)
            url_watches_json = os.path.join(datastore_path, "url-watches.json")
            if os.path.isfile(url_watches_json):
                tar.add(url_watches_json, arcname="url-watches.json")
                logger.debug("Added url-watches.json to backup")

            # Backup all watch/tag directories with their JSON files
            # This preserves the UUID directory structure
            watch_count = 0
            tag_count = 0
            for entry in os.listdir(datastore_path):
                entry_path = os.path.join(datastore_path, entry)

                # Skip if not a directory
                if not os.path.isdir(entry_path):
                    continue

                # Skip hidden directories and backup directories
                if entry.startswith('.') or entry.startswith('before-update-'):
                    continue

                # Backup watch.json if exists
                watch_json = os.path.join(entry_path, "watch.json")
                if os.path.isfile(watch_json):
                    tar.add(watch_json, arcname=f"{entry}/watch.json")
                    watch_count += 1

                    if watch_count % 100 == 0:
                        logger.debug(f"Backed up {watch_count} watch.json files...")

                # Backup tag.json if exists
                tag_json = os.path.join(entry_path, "tag.json")
                if os.path.isfile(tag_json):
                    tar.add(tag_json, arcname=f"{entry}/tag.json")
                    tag_count += 1

            logger.success(f"Backup created: {backup_filename} ({watch_count} watches from disk, {tag_count} tags from disk)")
            return backup_path

    except Exception as e:
        logger.error(f"Failed to create backup tarball: {e}")
        # Try to clean up partial backup
        if os.path.exists(backup_path):
            try:
                os.unlink(backup_path)
            except:
                pass
        return None


class DatastoreUpdatesMixin:
    """
    Mixin class containing all schema update methods.

    This class is inherited by ChangeDetectionStore to provide schema migration functionality.
    Each update_N method upgrades the schema from version N-1 to version N.
    """

    def get_updates_available(self):
        """
        Discover all available update methods.

        Returns:
            list: Sorted list of update version numbers (e.g., [1, 2, 3, ..., 26])
        """
        import inspect
        updates_available = []
        for i, o in inspect.getmembers(self, predicate=inspect.ismethod):
            m = re.search(r'update_(\d+)$', i)
            if m:
                updates_available.append(int(m.group(1)))
        updates_available.sort()

        return updates_available

    def run_updates(self, current_schema_version=None):
        import sys
        """
        Run all pending schema updates sequentially.

        Args:
            current_schema_version: Optional current schema version. If provided, only run updates
                                   greater than this version. If None, uses the schema version from
                                   the datastore. If no schema version exists in datastore and it appears
                                   to be a fresh install, sets to latest update number (no updates needed).

        IMPORTANT: Each update could be run even when they have a new install and the schema is correct.
        Therefore - each `update_n` should be very careful about checking if it needs to actually run.

        Process:
        1. Get list of available updates
        2. For each update > current schema version:
           - Create backup of datastore
           - Run update method
           - Update schema version and commit settings
           - Commit all watches and tags
        3. If any update fails, stop processing
        4. All changes saved via individual .commit() calls
        """
        updates_available = self.get_updates_available()
        if self.data.get('watching'):
            test_watch = self.data['watching'].get(next(iter(self.data.get('watching', {}))))
            from ..model.Watch import model

            if not isinstance(test_watch, model):
                import sys
                logger.critical("Cannot run updates! Watch structure must be re-hydrated back to a Watch model object!")
                sys.exit(1)

        if self.data['settings']['application'].get('tags',{}):
            test_tag = self.data['settings']['application'].get('tags',{}).get(next(iter(self.data['settings']['application'].get('tags',{}))))
            from ..model.Tag import model as tag_model

            if not isinstance(test_tag, tag_model):
                import sys
                logger.critical("Cannot run updates! Watch tag/group structure must be re-hydrated back to a Tag model object!")
                sys.exit(1)

        # Determine current schema version
        if current_schema_version is None:
            # Check if schema_version exists in datastore
            current_schema_version = self.data['settings']['application'].get('schema_version')

            if current_schema_version is None:
                # No schema version found - could be a fresh install or very old datastore
                # If this is a fresh/new config with no watches, assume it's up-to-date
                # and set to latest update number (no updates needed)
                if len(self.data['watching']) == 0:
                    # Get the highest update number from available update methods
                    latest_update = updates_available[-1] if updates_available else 0
                    logger.info(f"No schema version found and no watches exist - assuming fresh install, setting schema_version to {latest_update}")
                    self.data['settings']['application']['schema_version'] = latest_update
                    self.commit()
                    return  # No updates needed for fresh install
                else:
                    # Has watches but no schema version - likely old datastore, run all updates
                    logger.warning("No schema version found but watches exist - running all updates from version 0")
                    current_schema_version = 0

            if os.path.exists(json_path):
                with open(json_path, "rb") as f_j:
                    with open(deflate_path, "wb") as f_d:
                        logger.debug(f"Compressing {str(json_path)} to {str(deflate_path)}..")
                        f_d.write(zlib.compress(f_j.read()))
                        os.unlink(json_path)

    def update_20(self):
        """Migrate extract_title_as_title to use_page_title_in_list."""
        for uuid, watch in self.data['watching'].items():
            if self.data['watching'][uuid].get('extract_title_as_title'):
                self.data['watching'][uuid]['use_page_title_in_list'] = self.data['watching'][uuid].get('extract_title_as_title')
                del self.data['watching'][uuid]['extract_title_as_title']

        if self.data['settings']['application'].get('extract_title_as_title'):
            # Ensure 'ui' key exists (defensive for edge cases where base_config merge didn't happen)
            if 'ui' not in self.data['settings']['application']:
                self.data['settings']['application']['ui'] = {
                    'use_page_title_in_list': True,
                    'open_diff_in_new_tab': True,
                    'socket_io_enabled': True,
                    'favicons_enabled': True
                }
            self.data['settings']['application']['ui']['use_page_title_in_list'] = self.data['settings']['application'].get('extract_title_as_title')

    def update_21(self):
        """Migrate timezone to scheduler_timezone_default."""
        if self.data['settings']['application'].get('timezone'):
            self.data['settings']['application']['scheduler_timezone_default'] = self.data['settings']['application'].get('timezone')
            del self.data['settings']['application']['timezone']

    def update_23(self):
        """Some notification formats got the wrong name type."""

        def re_run(formats):
            sys_n_format = self.data['settings']['application'].get('notification_format')
            key_exists_as_value = next((k for k, v in formats.items() if v == sys_n_format), None)
            if key_exists_as_value:  # key of "Plain text"
                logger.success(f"['settings']['application']['notification_format'] '{sys_n_format}' -> '{key_exists_as_value}'")
                self.data['settings']['application']['notification_format'] = key_exists_as_value

            for uuid, watch in self.data['watching'].items():
                n_format = self.data['watching'][uuid].get('notification_format')
                key_exists_as_value = next((k for k, v in formats.items() if v == n_format), None)
                if key_exists_as_value and key_exists_as_value != USE_SYSTEM_DEFAULT_NOTIFICATION_FORMAT_FOR_WATCH:  # key of "Plain text"
                    logger.success(f"['watching'][{uuid}]['notification_format'] '{n_format}' -> '{key_exists_as_value}'")
                    self.data['watching'][uuid]['notification_format'] = key_exists_as_value  # should be 'text' or whatever

            for uuid, tag in self.data['settings']['application']['tags'].items():
                n_format = self.data['settings']['application']['tags'][uuid].get('notification_format')
                key_exists_as_value = next((k for k, v in formats.items() if v == n_format), None)
                if key_exists_as_value and key_exists_as_value != USE_SYSTEM_DEFAULT_NOTIFICATION_FORMAT_FOR_WATCH:  # key of "Plain text"
                    logger.success(
                        f"['settings']['application']['tags'][{uuid}]['notification_format'] '{n_format}' -> '{key_exists_as_value}'")
                    self.data['settings']['application']['tags'][uuid][
                        'notification_format'] = key_exists_as_value  # should be 'text' or whatever

        from ..notification import valid_notification_formats
        formats = deepcopy(valid_notification_formats)
        re_run(formats)
        # And in previous versions, it was "text" instead of Plain text, Markdown instead of "Markdown to HTML"
        formats['text'] = 'Text'
        formats['markdown'] = 'Markdown'
        re_run(formats)

    def update_24(self):
        """RSS types should be inline with the same names as notification types."""
        rss_format = self.data['settings']['application'].get('rss_content_format')
        if not rss_format or 'text' in rss_format:
            # might have been 'plaintext, 'plain text' or something
            self.data['settings']['application']['rss_content_format'] = RSS_CONTENT_FORMAT_DEFAULT
        elif 'html' in rss_format:
            self.data['settings']['application']['rss_content_format'] = 'htmlcolor'
        else:
            # safe fallback to text
            self.data['settings']['application']['rss_content_format'] = RSS_CONTENT_FORMAT_DEFAULT

    def update_25(self):
        """Different processors now hold their own history.txt."""
        for uuid, watch in self.data['watching'].items():
            processor = self.data['watching'][uuid].get('processor')
            if processor != 'text_json_diff':
                old_history_txt = os.path.join(self.datastore_path, "history.txt")
                target_history_name = f"history-{processor}.txt"
                if os.path.isfile(old_history_txt) and not os.path.isfile(target_history_name):
                    new_history_txt = os.path.join(self.datastore_path, target_history_name)
                    logger.debug(f"Renaming history index {old_history_txt} to {new_history_txt}...")
                    shutil.move(old_history_txt, new_history_txt)

    def migrate_legacy_db_format(self):
        """
        Migration: Individual watch persistence (COPY-based, safe rollback).

        Loads legacy url-watches.json format and migrates to:
        - {uuid}/watch.json (per watch)
        - changedetection.json (settings only)

        IMPORTANT:
        - A tarball backup (before-update-26-timestamp.tar.gz) is created before migration
        - url-watches.json is LEFT INTACT for rollback safety
        - Users can roll back by simply downgrading to the previous version
        - Or restore from tarball: tar -xzf before-update-26-*.tar.gz

        This is a dedicated migration release - users upgrade at their own pace.
        """
        logger.critical("=" * 80)
        logger.critical("Running migration: Individual watch persistence (update_26)")
        logger.critical("COPY-based migration: url-watches.json will remain intact for rollback")
        logger.critical("=" * 80)

        # Populate settings from legacy data
        logger.info("Populating settings from legacy data...")
        watch_count = len(self.data['watching'])
        logger.success(f"Loaded {watch_count} watches from legacy format")

        # Phase 1: Save all watches to individual files
        logger.critical(f"Phase 1/4: Saving {watch_count} watches to individual watch.json files...")

        saved_count = 0
        for uuid, watch in self.data['watching'].items():
            try:
                watch.commit()
                saved_count += 1

                if saved_count % 100 == 0:
                    logger.info(f"  Progress: {saved_count}/{watch_count} watches migrated...")

            except Exception as e:
                logger.error(f"Failed to save watch {uuid}: {e}")
                raise Exception(
                    f"Migration failed: Could not save watch {uuid}. "
                    f"url-watches.json remains intact, safe to retry. Error: {e}"
                )

