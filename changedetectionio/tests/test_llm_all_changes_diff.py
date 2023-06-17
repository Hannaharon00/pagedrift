#!/usr/bin/env python3
"""
Tests for the 'AI: every change between versions' (all_changes=1) feature.

Covers:
  - all_changes=1 builds a multi-segment diff (pairwise across intermediate snapshots)
  - all_changes=0 (default) uses a single from→to diff
  - the two modes are cached under separate keys (no cross-contamination)
  - a repeated all_changes=1 call returns the cached result without re-calling the LLM
"""

from unittest.mock import patch, call

