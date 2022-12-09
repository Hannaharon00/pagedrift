"""
Content Type Detection and Stream Classification

This module provides intelligent content-type detection for changedetection.io.
It addresses the common problem where HTTP Content-Type headers are missing, incorrect,
or too generic, which would otherwise cause the wrong processor to be used.

The guess_stream_type class combines:
1. HTTP Content-Type headers (when available and reliable)
2. Python-magic library for MIME detection (analyzing actual file content)
3. Content-based pattern matching for text formats (HTML tags, XML declarations, etc.)

This multi-layered approach ensures accurate detection of RSS feeds, JSON, HTML, PDF,
plain text, CSV, YAML, and XML formats - even when servers provide misleading headers.

Used by: processors/text_json_diff/processor.py and other content processors
"""

# When to apply the 'cdata to real HTML' hack
RSS_XML_CONTENT_TYPES = [
    "application/rss+xml",
    "application/rdf+xml",
    "application/atom+xml",
    "text/rss+xml",  # rare, non-standard
    "application/x-rss+xml",  # legacy (older feed software)
    "application/x-atom+xml",  # legacy (older Atom)
]

# JSON Content-types
JSON_CONTENT_TYPES = [
    "application/activity+json",
    "application/feed+json",
    "application/json",
    "application/ld+json",
    "application/vnd.api+json",
]


# Generic XML Content-types (non-RSS/Atom)
XML_CONTENT_TYPES = [
    "text/xml",
    "application/xml",
]

