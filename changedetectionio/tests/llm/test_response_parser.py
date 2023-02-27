"""
Unit tests for changedetectionio/llm/response_parser.py

All functions are pure — no external dependencies needed.
"""

import pytest

from changedetectionio.llm.response_parser import (
    _extract_json,
    parse_eval_response,
    parse_preview_response,
    parse_setup_response,
)


