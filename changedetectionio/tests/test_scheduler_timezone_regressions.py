#!/usr/bin/env python3

"""
Regression tests for two scheduler/timezone bugs.

BUG 1 - edit page returned HTTP 500
  ui/edit.py resolved the default timezone with
      .get('scheduler_timezone_default', os.getenv('TZ', 'UTC'))
  but App.py initialises that key to None, so the key EXISTS and dict.get()
  never uses its fallback. None reached is_within_schedule(), which does
  `tz_name.strip()` -> AttributeError -> the handler did `return False` -> Flask
  raised TypeError ("view function did not return a valid response ... it was a
  bool") -> HTTP 500. The watch was actually saved, so the user saw a 500 on a
  successful save.

BUG 2 - ticker thread died silently
  Same root cause, but flask_app.py's `return False` was inside the ticker
  thread's main loop. One watch with an unresolvable timezone ended the thread
  and NO watch was ever checked again until restart, with the process still up.

Run:  pytest changedetectionio/tests/test_scheduler_timezone_regressions.py
"""

import time

