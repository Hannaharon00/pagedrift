#!/usr/bin/env python3
"""
Simple unit tests for TimeExtension that mimic how safe_jinja.py uses it.
These tests demonstrate that the environment.default_timezone override works
exactly as intended in the actual application code.
"""

import arrow
from jinja2.sandbox import ImmutableSandboxedEnvironment
from changedetectionio.jinja2_custom.extensions.TimeExtension import TimeExtension


