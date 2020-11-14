"""
Custom Apprise HTTP Handlers with format= Parameter Support

IMPORTANT: This module works around a limitation in Apprise's @notify decorator.

THE PROBLEM:
-------------
When using Apprise's @notify decorator to create custom notification handlers, the
decorator creates a CustomNotifyPlugin that uses parse_url(..., simple=True) to parse
URLs. This simple parsing mode does NOT extract the format= query parameter from the URL
and set it as a top-level parameter that NotifyBase.__init__ can use to set notify_format.

