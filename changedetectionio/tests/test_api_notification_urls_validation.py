#!/usr/bin/env python3

"""
Test notification_urls validation in Watch and Tag API endpoints.
Ensures that invalid AppRise URLs are rejected when setting notification_urls.

Valid AppRise notification URLs use specific protocols like:
- posts://example.com - POST to HTTP endpoint
- gets://example.com - GET to HTTP endpoint
- mailto://user@example.com - Email
- slack://token/channel - Slack
- discord://webhook_id/webhook_token - Discord
- etc.

Invalid notification URLs:
- https://example.com - Plain HTTPS is NOT a valid AppRise notification protocol
- ftp://example.com - FTP is NOT a valid AppRise notification protocol
- Plain URLs without proper AppRise protocol prefix
"""

from flask import url_for
import json


