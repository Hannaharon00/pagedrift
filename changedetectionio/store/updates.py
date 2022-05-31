"""
Schema update migrations for the datastore.

This module contains all schema version upgrade methods (update_1 through update_N).
These are mixed into ChangeDetectionStore to keep the main store file focused.

import os
import re
import shutil
import tarfile
import time
from loguru import logger
from copy import deepcopy


