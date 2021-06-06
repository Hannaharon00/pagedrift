"""
Pure Python metadata extractor - no lxml, no memory leaks.

This module provides a fast, memory-efficient alternative to extruct for common
e-commerce metadata extraction. It handles:
- JSON-LD (covers 80%+ of modern sites)
- OpenGraph meta tags
- Basic microdata attributes

Uses Python's built-in html.parser instead of lxml/libxml2, avoiding C-level
memory allocation issues. For edge cases, the main processor can fall back to
extruct (with subprocess isolation on Linux).
"""

from html.parser import HTMLParser
import json
import re
from loguru import logger


class JSONLDExtractor(HTMLParser):
    """
    Extract JSON-LD structured data from HTML.

    Finds all <script type="application/ld+json"> tags and parses their content.
    Handles multiple JSON-LD blocks on the same page.
    """

    def __init__(self):
        super().__init__()
        self.in_jsonld = False
        self.data = []  # List of all parsed JSON-LD objects
        self.current_script = []

    def handle_starttag(self, tag, attrs):
        if tag == 'script':
            # Check if this is a JSON-LD script tag
            for attr, value in attrs:
                if attr == 'type' and value == 'application/ld+json':
                    self.in_jsonld = True
                    self.current_script = []
                    break

    def handle_data(self, data):
        if self.in_jsonld:
            self.current_script.append(data)

    def handle_endtag(self, tag):
        if tag == 'script' and self.in_jsonld:
            # Parse the accumulated script content
            script_content = ''.join(self.current_script)
            if script_content.strip():
                try:
                    # Parse JSON (handles both objects and arrays)
                    parsed = json.loads(script_content)
                    if isinstance(parsed, list):
                        self.data.extend(parsed)
                    else:
                        self.data.append(parsed)
                except json.JSONDecodeError as e:
                    logger.debug(f"Failed to parse JSON-LD: {e}")
                    pass

            self.in_jsonld = False
            self.current_script = []


class OpenGraphExtractor(HTMLParser):
    """
    Extract OpenGraph meta tags from HTML.

    Finds <meta property="og:*"> tags commonly used for social media sharing.
    """

    def __init__(self):
        super().__init__()
        self.og_data = {}

    def handle_starttag(self, tag, attrs):
        if tag == 'meta':
            attrs_dict = dict(attrs)
            prop = attrs_dict.get('property', '')

            # Extract OpenGraph properties
            if prop.startswith('og:'):
                content = attrs_dict.get('content', '')
                if content:
                    self.og_data[prop] = content


