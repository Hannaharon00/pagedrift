#!/usr/bin/env python3
"""
Integration tests: /edit/<uuid>/preview-rendered returns llm_evaluation when
llm_intent is submitted alongside the filter form data.

These tests verify the full backend path:
  JS POSTs llm_intent → prepare_filter_prevew() applies it to tmp_watch
  → preview_extract() is called → llm_evaluation appears in JSON response

The response uses {'found': bool, 'answer': str} — NOT the diff-evaluation
{'important', 'summary'} shape, because preview asks the LLM to extract from
the current content directly (e.g. "30 articles listed") rather than compare
a diff.
"""

import json
import time
from unittest.mock import patch

