"""
Prompt construction for LLM evaluation calls.
Pure functions — no side effects, fully testable.
"""

import re

from .bm25_trim import trim_to_relevant

