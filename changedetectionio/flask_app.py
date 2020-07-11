#!/usr/bin/env python3

import gc
import hashlib
import locale
import os
import queue
import re
import sys
import threading
import time
from pathlib import Path
from threading import Event

import flask_login
import timeago
from blinker import signal
from flask import (
    Flask,
    abort,
    flash,
    redirect,
    render_template,
    request,
    send_from_directory,
    session,
    url_for,
)
from flask_cors import CORS
from flask_restful import Api, abort

from changedetectionio import worker_pool
from changedetectionio.queue_handlers import NotificationQueue, RecheckPriorityQueue
from changedetectionio.strtobool import strtobool

from .thread_supervisor import start_supervised_thread
from .time_handler import default_timezone_name, is_within_schedule

IN_PYTEST = "pytest" in sys.modules or "PYTEST_CURRENT_TEST" in os.environ

