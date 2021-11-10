import importlib
from concurrent.futures import ThreadPoolExecutor

from changedetectionio.processors.text_json_diff.processor import FilterNotFoundInResponse
from changedetectionio.store import ChangeDetectionStore

from functools import wraps

from flask import Blueprint
from changedetectionio.auth_decorator import login_optionally_required

STATUS_CHECKING = 0
STATUS_FAILED = 1
STATUS_OK = 2
THREADPOOL_MAX_WORKERS = 3
_DEFAULT_POOL = ThreadPoolExecutor(max_workers=THREADPOOL_MAX_WORKERS)


