"""
Subprocess-isolated image operations for memory leak prevention.

LibVIPS accumulates C-level memory in long-running processes that cannot be
reclaimed by Python's GC or libvips cache management. Using subprocess isolation
ensures complete memory cleanup when the process exits.

This module wraps LibvipsImageDiffHandler operations in multiprocessing for
complete memory isolation without code duplication.

