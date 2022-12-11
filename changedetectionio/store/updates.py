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

