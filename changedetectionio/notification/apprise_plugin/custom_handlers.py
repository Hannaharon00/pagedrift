"""
Custom Apprise HTTP Handlers with format= Parameter Support

IMPORTANT: This module works around a limitation in Apprise's @notify decorator.

THE PROBLEM:
-------------
When using Apprise's @notify decorator to create custom notification handlers, the
decorator creates a CustomNotifyPlugin that uses parse_url(..., simple=True) to parse
URLs. This simple parsing mode does NOT extract the format= query parameter from the URL
and set it as a top-level parameter that NotifyBase.__init__ can use to set notify_format.

As a result:
1. URL: post://example.com/webhook?format=html
2. Apprise parses this and sees format=html in qsd (query string dictionary)
3. But it does NOT extract it and pass it to NotifyBase.__init__
4. NotifyBase defaults to notify_format=TEXT
5. When you call apobj.notify(body="<html>...", body_format="html"):
   - Apprise sees: input format = html, output format (notify_format) = text
   - Apprise calls convert_between("html", "text", body)
   - This strips all HTML tags, leaving only plain text
6. Your custom handler receives stripped plain text instead of HTML

THE SOLUTION:
-------------
Instead of using the @notify decorator directly, we:
1. Manually register custom plugins using plugins.N_MGR.add()
2. Create a CustomHTTPHandler class that extends CustomNotifyPlugin
3. Override __init__ to extract format= from qsd and set it as kwargs['format']
4. Call NotifyBase.__init__ which properly sets notify_format from kwargs['format']
5. Set up _default_args like CustomNotifyPlugin does for compatibility

This ensures that when format=html is in the URL:
- notify_format is set to HTML
- Apprise sees: input format = html, output format = html
- No conversion happens (convert_between returns content unchanged)
- Your custom handler receives the original HTML intact

TESTING:
--------
To verify this works:
>>> apobj = apprise.Apprise()
>>> apobj.add('post://localhost:5005/test?format=html')
>>> for server in apobj:
...     print(server.notify_format)  # Should print: html (not text)
>>> apobj.notify(body='<span>Test</span>', body_format='html')
# Your handler should receive '<span>Test</span>' not 'Test'
"""

import json
import os
import re
from urllib.parse import unquote_plus, urlparse

import requests
from apprise import plugins
from apprise.decorators.base import CustomNotifyPlugin
from apprise.utils.parse import parse_url as apprise_parse_url, url_assembly
from apprise.utils.logic import dict_full_update
from loguru import logger
from requests.structures import CaseInsensitiveDict

from changedetectionio.validate_url import is_private_hostname, is_url_private_or_parser_confused

SUPPORTED_HTTP_METHODS = {"get", "post", "put", "delete", "patch", "head"}


def notify_supported_methods(func):
    """Register custom HTTP method handlers that properly support format= parameter."""
    for method in SUPPORTED_HTTP_METHODS:
        _register_http_handler(method, func)
        _register_http_handler(f"{method}s", func)
    return func


def _register_http_handler(schema, send_func):
    """Register a custom HTTP handler that extracts format= from URL query parameters."""

    # Parse base URL
    base_url = f"{schema}://"
    base_args = apprise_parse_url(base_url, default_schema=schema, verify_host=False, simple=True)

    class CustomHTTPHandler(CustomNotifyPlugin):
        secure_protocol = schema
        service_name = f"Custom HTTP - {schema.upper()}"
        _base_args = base_args

        def __init__(self, **kwargs):
            # Extract format from qsd and set it as a top-level kwarg
            # This allows NotifyBase.__init__ to properly set notify_format
            if 'qsd' in kwargs and 'format' in kwargs['qsd']:
                kwargs['format'] = kwargs['qsd']['format']

            # Call NotifyBase.__init__ (skip CustomNotifyPlugin.__init__)
            super(CustomNotifyPlugin, self).__init__(**kwargs)

            # Set up _default_args like CustomNotifyPlugin does
            self._default_args = {}
            kwargs.pop("secure", None)
            dict_full_update(self._default_args, self._base_args)
            dict_full_update(self._default_args, kwargs)
            self._default_args["url"] = url_assembly(**self._default_args)

        __send = staticmethod(send_func)

        def send(self, body, title="", notify_type="info", *args, **kwargs):
            """Call the custom send function."""
            try:
                result = self.__send(
                    body, title, notify_type,
                    *args,
                    meta=self._default_args,
                    **kwargs
                )
                return True if result is None else bool(result)
            except Exception as e:
                self.logger.warning(f"Exception in custom HTTP handler: {e}")
                return False

    # Register the plugin
    plugins.N_MGR.add(
        plugin=CustomHTTPHandler,
        schemas=schema,
        send_func=send_func,
        url=base_url,
    )


def _get_auth(parsed_url: dict) -> str | tuple[str, str]:
    user: str | None = parsed_url.get("user")
    password: str | None = parsed_url.get("password")

    if user is not None and password is not None:
        return (unquote_plus(user), unquote_plus(password))

    if user is not None:
        return unquote_plus(user)

    return ""


