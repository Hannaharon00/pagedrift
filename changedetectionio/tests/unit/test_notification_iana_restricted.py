"""
Unit tests for SSRF protection in the Apprise custom HTTP notification handler.

The handler (notification/apprise_plugin/custom_handlers.py) must block requests
to private/IANA-reserved addresses unless ALLOW_IANA_RESTRICTED_ADDRESSES=true.
"""

import pytest
from unittest.mock import patch, MagicMock


def _make_meta(url: str) -> dict:
    """Build a minimal Apprise meta dict that apprise_http_custom_handler expects."""
    from apprise.utils.parse import parse_url as apprise_parse_url
    schema = url.split("://")[0]
    parsed = apprise_parse_url(url, default_schema=schema, verify_host=False, simple=True)
    parsed["url"] = url
    parsed["schema"] = schema
    return parsed


