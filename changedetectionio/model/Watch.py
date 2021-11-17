"""
Watch domain model for change detection monitoring.

ARCHITECTURE NOTE: Configuration Override Hierarchy
===================================================

This module implements Watch objects that inherit from dict (technical debt).
The dream architecture would use Pydantic for:

1. CHAIN RESOLUTION (Watch → Tag → Global Settings)
   - Current: Manual resolution scattered across codebase
   - Future: @computed_field properties with automatic resolution
   - Examples: resolved_fetch_backend, resolved_restock_settings, etc.

2. DATABASE BACKEND ABSTRACTION
   - Current: Domain model tightly coupled to file-based JSON storage
   - Future: Domain model (Pydantic) separate from persistence layer
   - Enables: Easy migration to PostgreSQL, MongoDB, etc.

3. TYPE SAFETY & VALIDATION
   - Current: Dict access with no compile-time checks
   - Future: Type hints, IDE autocomplete, validation at boundaries

See class model docstring for detailed explanation and examples.
See: processors/restock_diff/processor.py:184-192 for manual resolution example
"""

from blinker import signal
from changedetectionio.validate_url import is_safe_valid_url

from changedetectionio.strtobool import strtobool
from changedetectionio.jinja2_custom import render as jinja_render
from . import watch_base
from .persistence import EntityPersistenceMixin
import os
import re
from pathlib import Path
from loguru import logger

from .. import jinja2_custom as safe_jinja
from ..html_tools import TRANSLATE_WHITESPACE_TABLE

FAVICON_RESAVE_THRESHOLD_SECONDS=86400
BROTLI_COMPRESS_SIZE_THRESHOLD = int(os.getenv('SNAPSHOT_BROTLI_COMPRESSION_THRESHOLD', 1024*20))

# Module-level favicon filename cache: data_dir → basename (or None)
# Keyed by data_dir so it survives Watch object recreation, deepcopy, and concurrent requests.
# Invalidated explicitly when the favicon is saved or the watch history is cleared.
_FAVICON_FILENAME_CACHE: dict = {}

minimum_seconds_recheck_time = int(os.getenv('MINIMUM_SECONDS_RECHECK_TIME', 3))
mtable = {'seconds': 1, 'minutes': 60, 'hours': 3600, 'days': 86400, 'weeks': 86400 * 7}

        # Compression failed
        if fallback_uncompressed:
            logger.warning(f"Brotli compression failed for {filepath}, saving uncompressed")
            fallback_path = filepath.replace('.br', '')
            with open(fallback_path, 'wb') as f:
                f.write(contents)
            return fallback_path
        else:
            raise Exception(f"Brotli compression failed for {filepath}: {e}")


