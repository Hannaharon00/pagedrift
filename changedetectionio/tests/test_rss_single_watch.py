#!/usr/bin/env python3

from .restock.test_restock import set_original_response
from .util import live_server_setup, wait_for_all_checks, extract_rss_token_from_UI, extract_UUID_from_client, delete_all_watches, set_modified_response
from ..notification import default_notification_format


