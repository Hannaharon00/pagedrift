"""
Queue inspection UI.

Surfaces what's currently being processed and what's waiting so users can
make sense of the "Queued size: N" indicator (see issue #4077).

Priority conventions (see uses of PrioritizedItem across the codebase):
  1     - immediate / manual recheck
  5     - clone follow-up
  >100  - scheduler-enqueued (timestamp-based)
"""

