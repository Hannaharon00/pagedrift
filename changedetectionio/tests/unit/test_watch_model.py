#!/usr/bin/env python3

# run from dir above changedetectionio/ dir
# python3 -m unittest changedetectionio.tests.unit.test_notification_diff

import unittest
import os
import pickle
import tempfile
from copy import deepcopy

