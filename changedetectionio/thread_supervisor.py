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

