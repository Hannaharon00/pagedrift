"""
Worker management module for changedetection.io

Handles asynchronous workers for dynamic worker scaling.
Each worker runs in its own thread with its own event loop for isolation.
"""

