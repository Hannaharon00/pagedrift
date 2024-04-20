"""
Tests that {{ llm_summary }} and {{ llm_intent }} notification tokens
are correctly populated in the notification pipeline.

Covers:
  1. notification/handler.py — lazy population logic (lines 367-372)
  2. notification_service.py — _llm_result / _llm_intent from watch → n_object
  3. End-to-end: tokens render in notification body/title
"""
import pytest
from unittest.mock import MagicMock, patch
from changedetectionio.notification_service import NotificationContextData


def _make_n_object(**extra):
    n = NotificationContextData()
    n.update({
        'notification_body': '',
        'notification_title': '',
        'notification_format': 'text',
        'notification_urls': ['json://localhost/'],
        'uuid': 'test-uuid',
        'watch_uuid': 'test-uuid',
        'watch_url': 'https://example.com',
        'current_snapshot': 'current text',
        'prev_snapshot': 'previous text',
    })
    n.update(extra)
    return n


