#!/usr/bin/env python3
"""
Tests for immediate commit-based persistence system.

Tests cover:
- Watch.commit() persistence to disk
- Concurrent commit safety (race conditions)
- Processor config separation
- Data loss prevention (settings, tags, watch modifications)
"""

