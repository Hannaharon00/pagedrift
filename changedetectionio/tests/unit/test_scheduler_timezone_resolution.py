#!/usr/bin/env python3

"""
Regression tests for the scheduler's default-timezone resolution.

The bug: model/App.py initialises 'scheduler_timezone_default' to None, so the
key ALWAYS EXISTS with a None value. Call sites used

    settings['application'].get('scheduler_timezone_default', os.getenv('TZ', 'UTC'))

