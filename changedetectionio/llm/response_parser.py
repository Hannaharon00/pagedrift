"""
Parse and validate LLM JSON responses.
Pure functions — no side effects, fully testable.

LLMs occasionally return JSON wrapped in markdown fences or with trailing
text. This module handles those cases gracefully.
"""

import json
import re

