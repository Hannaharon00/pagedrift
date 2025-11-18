#!/usr/bin/env python3
"""
Unit tests for XPath default namespace handling in RSS/Atom feeds.
Tests the fix for issue where //title/text() returns empty on feeds with default namespaces.

Real-world test data from https://github.com/microsoft/PowerToys/releases.atom
"""

import sys
import os
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import html_tools


# Real-world Atom feed with default namespace from GitHub PowerToys releases
# This is the actual format that was failing before the fix
atom_feed_with_default_ns = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom" xmlns:media="http://search.yahoo.com/mrss/" xml:lang="en-US">
  <id>tag:github.com,2008:https://github.com/microsoft/PowerToys/releases</id>
  <link type="text/html" rel="alternate" href="https://github.com/microsoft/PowerToys/releases"/>
  <link type="application/atom+xml" rel="self" href="https://github.com/microsoft/PowerToys/releases.atom"/>
  <title>Release notes from PowerToys</title>
  <updated>2025-10-23T08:53:12Z</updated>
  <entry>
    <id>tag:github.com,2008:Repository/184456251/v0.95.1</id>
    <updated>2025-10-24T14:20:14Z</updated>
    <link rel="alternate" type="text/html" href="https://github.com/microsoft/PowerToys/releases/tag/v0.95.1"/>
    <title>Release 0.95.1</title>
    <content type="html">&lt;p&gt;This patch release fixes several important stability issues.&lt;/p&gt;</content>
    <author>
      <name>Jaylyn-Barbee</name>
    </author>
  </entry>
  <entry>
    <id>tag:github.com,2008:Repository/184456251/v0.95.0</id>
    <updated>2025-10-17T12:51:21Z</updated>
    <link rel="alternate" type="text/html" href="https://github.com/microsoft/PowerToys/releases/tag/v0.95.0"/>
    <title>Release v0.95.0</title>
    <content type="html">&lt;p&gt;New features, stability, optimization improvements.&lt;/p&gt;</content>
    <author>
      <name>Jaylyn-Barbee</name>
    </author>
  </entry>
</feed>"""

# RSS feed without default namespace
rss_feed_no_default_ns = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Channel Title</title>
    <description>Channel Description</description>
    <item>
      <title>Item 1 Title</title>
      <description>Item 1 Description</description>
    </item>
    <item>
      <title>Item 2 Title</title>
      <description>Item 2 Description</description>
    </item>
  </channel>
</rss>"""

# RSS 2.0 feed with namespace prefix (not default)
rss_feed_with_ns_prefix = """<?xml version="1.0" encoding="UTF-8"?>
<rss xmlns:dc="http://purl.org/dc/elements/1.1/"
     xmlns:content="http://purl.org/rss/1.0/modules/content/"
     xmlns:atom="http://www.w3.org/2005/Atom"
     version="2.0">
  <channel>
    <title>Channel Title</title>
    <atom:link href="http://example.com/feed" rel="self" type="application/rss+xml"/>
    <item>
      <title>Item Title</title>
      <dc:creator>Author Name</dc:creator>
    </item>
  </channel>
</rss>"""


