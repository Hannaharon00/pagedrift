#!/usr/bin/env python3
"""
Integration tests for AI Change Summary:
  - llm_change_summary field saved via watch edit form
  - llm_change_summary cascades from tag to watches
  - {{ diff }} replaced by AI summary in notifications
  - {{ raw_diff }} always contains original diff
  - summarise_change only runs when change is detected
"""

import json
import time
from unittest.mock import patch

