"""
Unit tests for SSRF protection in the Apprise custom HTTP notification handler.

The handler (notification/apprise_plugin/custom_handlers.py) must block requests
to private/IANA-reserved addresses unless ALLOW_IANA_RESTRICTED_ADDRESSES=true.
"""

