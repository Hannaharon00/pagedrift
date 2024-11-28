import hashlib

from changedetectionio.browser_steps.browser_steps import browser_steps_get_valid_steps
from changedetectionio.content_fetchers.base import Fetcher
from changedetectionio.validate_url import validate_fetch_url_async
from copy import deepcopy
from abc import abstractmethod
import os
from urllib.parse import urlparse
from loguru import logger

SCREENSHOT_FORMAT_JPEG = 'JPEG'
SCREENSHOT_FORMAT_PNG = 'PNG'

class difference_detection_processor():
    browser_steps = None
    datastore = None
    fetcher = None
    screenshot = None
    watch = None
    xpath_data = None
    preferred_proxy = None
    screenshot_format = SCREENSHOT_FORMAT_JPEG
    last_raw_content_checksum = None

    def __init__(self, datastore, watch_uuid):
        self.datastore = datastore
        self.watch_uuid = watch_uuid

        # Create a stable snapshot of the watch for processing
        # Why deepcopy?
        # 1. Prevents "dict changed during iteration" errors if watch is modified during processing
        # 2. Preserves Watch object with properties (.link, .is_pdf, etc.) - can't use dict()
        # 3. Safe now: Watch.__deepcopy__() shares datastore ref (no memory leak) but copies dict data
        self.watch = deepcopy(self.datastore.data['watching'].get(watch_uuid))

        # Generic fetcher that should be extended (requests, playwright etc)
        self.fetcher = Fetcher()

        # Load the last raw content checksum from file
        self.read_last_raw_content_checksum()

    def update_last_raw_content_checksum(self, checksum):
        """
        Save the raw content MD5 checksum to file.
        This is used for skip logic - avoid reprocessing if raw HTML unchanged.
        """
        if not checksum:
            return

        watch = self.datastore.data['watching'].get(self.watch_uuid)
        if not watch:
            return

        data_dir = watch.data_dir
        if not data_dir:
            return

        watch.ensure_data_dir_exists()
        checksum_file = os.path.join(data_dir, 'last-checksum.txt')

        try:
            with open(checksum_file, 'w', encoding='utf-8') as f:
                f.write(checksum)
            self.last_raw_content_checksum = checksum
        except IOError as e:
            logger.warning(f"Failed to write checksum file for {self.watch_uuid}: {e}")

    def read_last_raw_content_checksum(self):
        """
        Read the last raw content MD5 checksum from file.
        Returns None if file doesn't exist (first run) or can't be read.
        """
        watch = self.datastore.data['watching'].get(self.watch_uuid)
        if not watch:
            self.last_raw_content_checksum = None
            return

        data_dir = watch.data_dir
        if not data_dir:
            self.last_raw_content_checksum = None
            return

        checksum_file = os.path.join(data_dir, 'last-checksum.txt')

        if not os.path.isfile(checksum_file):
            self.last_raw_content_checksum = None
            return

        try:
            with open(checksum_file, 'r', encoding='utf-8') as f:
                self.last_raw_content_checksum = f.read().strip()
        except IOError as e:
            logger.warning(f"Failed to read checksum file for {self.watch_uuid}: {e}")
            self.last_raw_content_checksum = None

    async def validate_url_is_fetchable(self):
        """Pre-flight fetch gate for the regular check path (all fetchers, since they all come
        through call_browser()). The scheme/file:///private-IP rules live in
        validate_url.is_fetch_url_allowed() so that the fetch paths which do NOT come through
        here - the live Browser Steps UI, the Add Watch snapshot preview, and individual
        'Goto URL' browser steps - enforce exactly the same rules.
        """
        try:
            await validate_fetch_url_async(self.watch.link)
        except ValueError as e:
            # Re-raised as a plain Exception so it lands in the watch's last_error like every other
            # fetch failure, instead of looking like an internal type error.
            raise Exception(str(e)) from e

    def _consume_preloaded_fetch(self):
        """One-shot: if the Add Watch page parked a freshly-fetched snapshot for this
        watch (html + screenshot + xpath, see add_watch_ui/snapshot), populate self.fetcher
        from it instead of hitting the network. The marker file is deleted after use so
        every subsequent check fetches live.

        Returns True if a preload was consumed (caller should skip the network fetch).
        """
        import json, zlib

        data_dir = self.watch.data_dir
        if not data_dir:
            return False

        preload_path = os.path.join(data_dir, 'preload-fetch.json')
        if not os.path.isfile(preload_path):
            return False

        try:
            with open(preload_path, 'r', encoding='utf-8') as f:
                meta = json.load(f)
        except Exception as e:
            logger.warning(f"Could not read preloaded fetch for {self.watch.get('uuid')}: {e}")
            try:
                os.unlink(preload_path)
            except OSError:
                pass
            return False

        # Always delete first - this is one-shot regardless of what happens next.
        try:
            os.unlink(preload_path)
        except OSError:
            pass

        content = meta.get('content')
        self.fetcher.content = content
        self.fetcher.raw_content = content.encode('utf-8', errors='replace') if isinstance(content, str) else content
        self.fetcher.status_code = meta.get('status_code', 200)
        self.fetcher.headers = meta.get('headers') or {'content-type': 'text/html'}

        # Screenshot + xpath were migrated alongside in final on-disk format - reuse them.
        screenshot_path = os.path.join(data_dir, 'last-screenshot.png')
        if os.path.isfile(screenshot_path):
            with open(screenshot_path, 'rb') as f:
                self.fetcher.screenshot = f.read()

        elements_path = os.path.join(data_dir, 'elements.deflate')
        if os.path.isfile(elements_path):
            try:
                with open(elements_path, 'rb') as f:
                    self.fetcher.xpath_data = json.loads(zlib.decompress(f.read()))
            except Exception as e:
                logger.warning(f"Could not load preloaded xpath data for {self.watch.get('uuid')}: {e}")

        logger.info(f"Using preloaded Add-Watch snapshot for {self.watch.get('uuid')} - skipping network fetch")
        return True

    async def call_browser(self, preferred_proxy_id=None):

        from requests.structures import CaseInsensitiveDict

        url = self.watch.link

        # Scheme allowlist (file:// etc), parser-differential and private/reserved IP checks.
        await self.validate_url_is_fetchable()

        # Proxy ID "key"
        preferred_proxy_id = preferred_proxy_id if preferred_proxy_id else self.datastore.get_preferred_proxy_for_watch(
            uuid=self.watch.get('uuid'))

