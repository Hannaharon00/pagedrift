#!/usr/bin/env python3

from flask import url_for
from changedetectionio.tests.util import live_server_setup, wait_for_all_checks, extract_UUID_from_client, delete_all_watches
import os


