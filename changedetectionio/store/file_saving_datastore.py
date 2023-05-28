"""
File-based datastore with individual watch persistence and immediate commits.

This module provides the FileSavingDataStore abstract class that implements:
- Individual watch.json file persistence
- Immediate commit-based persistence (watch.commit(), datastore.commit())
- Atomic file writes safe for NFS/NAS
"""

import json
import os
import tempfile
import time
from loguru import logger

from .base import DataStore
from .. import strtobool

# Try to import orjson for faster JSON serialization
try:
    import orjson
    HAS_ORJSON = True
except ImportError:
    HAS_ORJSON = False

# Fsync configuration: Force file data to disk for crash safety
# Default False to match legacy behavior (write-and-rename without fsync)
# Set to True for mission-critical deployments requiring crash consistency
FORCE_FSYNC_DATA_IS_CRITICAL = bool(strtobool(os.getenv('FORCE_FSYNC_DATA_IS_CRITICAL', 'False')))

class _EntityFileMissing:
    """Sentinel: the directory exists but holds no file of this entity type."""
    __slots__ = ()
    def __repr__(self):
        return '<ENTITY_FILE_MISSING>'
    def __bool__(self):
        return False


ENTITY_FILE_MISSING = _EntityFileMissing()


def iter_entity_dirs(datastore_path):
    """
    Yield (uuid, dir_path) for every immediate subdirectory of the datastore.

    Replaces glob.glob(f"{datastore_path}/*/watch.json"). glob has to build a
    regex from the "*" component and fnmatch every name in the directory, then
    stat each candidate to test the literal "watch.json" part. With ~60k watches
    that measured as 238k allocations in fnmatch.filter plus one stat per
    directory, all to produce a list we then split back into uuid + path.

    scandir hands us the names directly, and entry.is_dir() is free on Linux
    because it reads d_type straight from the dirent (no stat syscall).
    Symlinked directories are followed, matching glob's behaviour.
    """
    try:
        with os.scandir(datastore_path) as it:
            for entry in it:
                try:
                    if entry.is_dir():
                        yield entry.name, entry.path
                except OSError:
                    # Raced with a delete, or a broken symlink - not loadable either way
                    continue
    except FileNotFoundError:
        return


def load_watch_from_file(watch_json, uuid, rehydrate_entity_func, missing_ok=False):
    """
    Load a watch from its JSON file.

    Args:
        watch_json: Path to the watch.json file
        uuid: Watch UUID
        rehydrate_entity_func: Function to convert dict to Watch object
        missing_ok: When True, a missing file returns ENTITY_FILE_MISSING instead of
                    logging an error. Used by load_all_watches, which walks every
                    datastore subdirectory - some of those are tag dirs, not watches.

    Returns:
        Watch object, ENTITY_FILE_MISSING if absent and missing_ok, else None
    """
    try:
        # Open first, then take the size from the already-open fd. Doing it this way
        # costs one syscall instead of stat()+open(), which matters when this is
        # called once per directory across a large datastore.
        try:
            f = open(watch_json, 'rb')
        except (FileNotFoundError, NotADirectoryError):
            if missing_ok:
                return ENTITY_FILE_MISSING
            logger.error(f"Watch file not found: {watch_json} for watch {uuid}")
            return None

        with f:
            file_size = os.fstat(f.fileno()).st_size
            MAX_WATCH_SIZE = 10 * 1024 * 1024  # 10MB
            if file_size > MAX_WATCH_SIZE:
                logger.critical(
                    f"CORRUPTED WATCH DATA: Watch {uuid} file is unexpectedly large: "
                    f"{file_size / 1024 / 1024:.2f}MB (max: {MAX_WATCH_SIZE / 1024 / 1024}MB). "
                    f"File: {watch_json}. This indicates a bug or data corruption. "
                    f"Watch will be skipped."
                )
                return None
            raw = f.read()

        watch_data = orjson.loads(raw) if HAS_ORJSON else json.loads(raw.decode('utf-8'))

        # Rehydrate and return watch object
        watch_obj = rehydrate_entity_func(uuid, watch_data)
        return watch_obj

    except json.JSONDecodeError as e:
        logger.critical(
            f"CORRUPTED WATCH DATA: Failed to parse JSON for watch {uuid}. "
            f"File: {watch_json}. Error: {e}. "
            f"Watch will be skipped and may need manual recovery from backup."
        )
        return None
    except ValueError as e:
        # orjson raises ValueError for invalid JSON
        if "invalid json" in str(e).lower() or HAS_ORJSON:
            logger.critical(
                f"CORRUPTED WATCH DATA: Failed to parse JSON for watch {uuid}. "
                f"File: {watch_json}. Error: {e}. "
                f"Watch will be skipped and may need manual recovery from backup."
            )
            return None
        # Re-raise if it's not a JSON parsing error
        raise
    except Exception as e:
        logger.error(f"Failed to load watch {uuid} from {watch_json}: {e}")
        return None


