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

