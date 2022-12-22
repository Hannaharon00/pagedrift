"""
Tests for the LLM restock fallback plugin.

All LLM calls are mocked — no real API key required.
"""
import json
import pytest
from unittest.mock import patch, MagicMock


