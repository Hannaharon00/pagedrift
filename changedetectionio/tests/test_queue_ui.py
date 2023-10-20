"""
Tests for the queue inspection UI (blueprint/ui/queue.py).

Strategy: shut down all workers, pause the scheduler, then push synthetic
UUIDs directly into update_q. Synthetic UUIDs are immune to scheduler
interference. The HTTP test client + live_server share the same process,
so update_q is a single instance.
"""

