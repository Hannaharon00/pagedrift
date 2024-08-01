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


class MicrodataExtractor(HTMLParser):
    """
    Extract basic microdata attributes from HTML.

    Finds elements with itemprop attributes. This is a simplified extractor
    that doesn't handle nested itemscope/itemtype hierarchies - for complex
    cases, use extruct as fallback.
    """

    def __init__(self):
        super().__init__()
        self.microdata = {}
        self.current_itemprop = None

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)

        if 'itemprop' in attrs_dict:
            itemprop = attrs_dict['itemprop']

            # Price/currency/availability can be in content/href attributes
            if itemprop == 'price':
                if 'content' in attrs_dict:
                    self.microdata['price'] = attrs_dict['content']
                else:
                    self.current_itemprop = 'price'

            elif itemprop == 'priceCurrency':
                if 'content' in attrs_dict:
                    self.microdata['currency'] = attrs_dict['content']
                else:
                    self.current_itemprop = 'priceCurrency'

            elif itemprop == 'availability':
                # Can be in href (link) or content (meta)
                if 'href' in attrs_dict:
                    self.microdata['availability'] = attrs_dict['href']
                elif 'content' in attrs_dict:
                    self.microdata['availability'] = attrs_dict['content']
                else:
                    self.current_itemprop = 'availability'

    def handle_data(self, data):
        # Capture text content for itemprop elements
        if self.current_itemprop == 'price':
            # Try to extract numeric price from text
            try:
                price_text = re.sub(r'[^\d.]', '', data.strip())
                if price_text:
                    self.microdata['price'] = float(price_text)
            except ValueError:
                pass
        elif self.current_itemprop == 'priceCurrency':
            currency = data.strip()
            if currency:
                self.microdata['currency'] = currency
        elif self.current_itemprop == 'availability':
            availability = data.strip()
            if availability:
                self.microdata['availability'] = availability

    def handle_endtag(self, tag):
        # Reset current itemprop after closing tag
        self.current_itemprop = None


def extract_metadata_pure_python(html_content):
    """
    Extract structured metadata from HTML using pure Python parsers.

    Returns a dict with three keys:
    - 'json-ld': List of parsed JSON-LD objects
    - 'opengraph': Dict of OpenGraph properties
    - 'microdata': Dict of microdata properties

    Args:
        html_content: HTML string to parse

    Returns:
        dict: Extracted metadata in three formats
    """
    result = {
        'json-ld': [],
        'opengraph': {},
        'microdata': {}
    }

    # Extract JSON-LD
    try:
        jsonld_extractor = JSONLDExtractor()
        jsonld_extractor.feed(html_content)
        result['json-ld'] = jsonld_extractor.data
        logger.trace(f"Pure Python: Found {len(jsonld_extractor.data)} JSON-LD blocks")
    except Exception as e:
        logger.debug(f"JSON-LD extraction failed: {e}")

    # Extract OpenGraph
    try:
        og_extractor = OpenGraphExtractor()
        og_extractor.feed(html_content)
        result['opengraph'] = og_extractor.og_data
        if result['opengraph']:
            logger.trace(f"Pure Python: Found {len(og_extractor.og_data)} OpenGraph tags")
    except Exception as e:
        logger.debug(f"OpenGraph extraction failed: {e}")

    # Extract Microdata
    try:
        microdata_extractor = MicrodataExtractor()
        microdata_extractor.feed(html_content)
        result['microdata'] = microdata_extractor.microdata
        if result['microdata']:
            logger.trace(f"Pure Python: Found microdata: {result['microdata']}")
    except Exception as e:
        logger.debug(f"Microdata extraction failed: {e}")

    return result


