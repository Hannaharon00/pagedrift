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

