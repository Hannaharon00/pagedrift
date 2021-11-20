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


    @property
    def fetcher_supports_screenshots(self):
        """Return True if the fetcher configured for this watch supports screenshots.

        Resolves 'system' via self._datastore, then checks supports_screenshots on
        the actual fetcher class. Works for built-in and plugin fetchers alike.
        """
        from changedetectionio import content_fetchers
        from changedetectionio.content_fetchers.base import FetcherCapabilities

        fetcher_name = self.get_fetch_backend  # already handles is_pdf → html_requests
        if not fetcher_name or fetcher_name == 'system':
            fetcher_name = self._datastore['settings']['application'].get('fetch_backend', 'html_requests')

        # Shared capability model - handles an unknown/None fetcher class (all-False)
        fetcher_class = getattr(content_fetchers, fetcher_name, None)
        return FetcherCapabilities.from_fetcher(fetcher_class).supports_screenshots

    @property
    def is_pdf(self):
        url = str(self.get("url") or "").lower()
        content_type = str(self.get("content-type") or "").lower()

        if content_type in ("none", "null", ""):
            content_type = ""

        return (
                url.endswith(".pdf")
                or content_type.split(";")[0].strip() == "application/pdf"
        )

    @property
    def label(self):
        # Used for sorting, display, etc
        return self.get('title') or self.get('page_title') or self.link

    @property
    def last_changed(self):
        # last_changed will be the newest snapshot, but when we have just one snapshot, it should be 0
        if self.__history_n <= 1:
            return 0
        if self.__newest_history_key:
            return int(self.__newest_history_key)
        return 0

    @property
    def history_n(self):
        return self.__history_n

    @property
    def history(self):
        """History index is just a text file as a list
            {watch-uuid}/history.txt

            contains a list like

            {epoch-time},{filename}\n

            We read in this list as the history information

        """
        tmp_history = {}

        # In the case we are only using the watch for processing without history
        if not self.data_dir:
            return []

        # Read the history file as a dict
        fname = os.path.join(self.data_dir, self.history_index_filename)
        if os.path.isfile(fname):
            logger.debug(f"Reading watch history index for {self.get('uuid')}")
            with open(fname, "r", encoding='utf-8') as f:
                for i in f.readlines():
                    if ',' in i:
                        k, v = i.strip().split(',', 2)

                        # Always resolve history entries to within the watch's own data directory.
                        # Entries restored from backup could contain absolute or traversal paths —
                        # never trust them. Use realpath to also block symlink-based escapes.
                        safe_data_dir = os.path.realpath(self.data_dir)
                        snapshot_fname = os.path.basename(v.strip())
                        resolved_path = os.path.realpath(os.path.join(self.data_dir, snapshot_fname))

                        if not resolved_path.startswith(safe_data_dir + os.sep) and resolved_path != safe_data_dir:
                            logger.warning(f"Skipping unsafe history entry for {self.get('uuid')}: {v!r}")
                            continue

                        if not os.path.exists(resolved_path):
                            continue

                        tmp_history[k] = resolved_path

        if len(tmp_history):
            self.__newest_history_key = list(tmp_history.keys())[-1]
        else:
            self.__newest_history_key = None

        self.__history_n = len(tmp_history)

        return tmp_history

    @property
    def has_history(self):
        fname = os.path.join(self.data_dir, self.history_index_filename)
        return os.path.isfile(fname)

    @property
    def has_browser_steps(self):
        has_browser_steps = self.get('browser_steps') and list(filter(
            lambda s: (s['operation'] and len(s['operation']) and s['operation'] != 'Choose one' and s['operation'] != 'Goto site'),
            self.get('browser_steps')))

        return has_browser_steps

    @property
    def has_restock_info(self):
        if self.get('restock') and self['restock'].get('in_stock') != None:
                return True

        return False

