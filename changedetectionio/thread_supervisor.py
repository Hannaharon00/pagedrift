"""
Keep critical background threads alive.

A threading.Thread cannot be restarted. Once its target returns, the thread is
finished and calling start() again raises RuntimeError("threads can only be
started once"). There is no built-in "respawn on death" option. So recovery has
to be built into the target itself.

This matters because a background loop can die in two ways that look identical
from outside, and both are silent:

  - it raises, and the traceback goes nowhere because nobody joins a daemon thread
  - it simply `return`s, e.g. a stray `return False` deep inside the loop body

The second is how the ticker thread stopped scheduling every watch in the app:
one watch with an unresolvable timezone hit `return False`, the whole loop
exited, and no watch was ever checked again until the process restarted. Nothing
was logged above ERROR, and the process stayed up and healthy-looking.

supervise() wraps a target so that any exit which is NOT a real shutdown is
logged CRITICAL and the target is re-entered, with exponential backoff so a
target that fails instantly cannot spin the CPU.
"""

import time

from loguru import logger

# Back off 1, 2, 4 ... up to this many seconds between restarts.
DEFAULT_MAX_BACKOFF_SECONDS = 60

