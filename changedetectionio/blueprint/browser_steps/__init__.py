
from changedetectionio.store import ChangeDetectionStore
from changedetectionio.blueprint import plaintext_response
from changedetectionio.flask_app import login_optionally_required
from changedetectionio.validate_url import validate_fetch_url_async
from loguru import logger

browsersteps_sessions = {}
browsersteps_watch_to_session = {}  # Maps watch_uuid -> browsersteps_session_id
io_interface_context = None
import json
import hashlib
from flask import Response
import asyncio
import threading
import time

