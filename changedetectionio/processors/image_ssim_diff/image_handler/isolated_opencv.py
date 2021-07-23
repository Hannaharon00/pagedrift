"""
OpenCV-based subprocess isolation for image comparison.

OpenCV is much more stable in multiprocessing contexts than LibVIPS.
No threading issues, no fork problems, picklable functions.
"""

import multiprocessing
import numpy as np
from .. import POLL_TIMEOUT_ABSOLUTE

