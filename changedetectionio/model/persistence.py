"""
Entity persistence mixin for Watch and Tag models.

Provides file-based persistence using atomic writes.
"""

import functools
import inspect


