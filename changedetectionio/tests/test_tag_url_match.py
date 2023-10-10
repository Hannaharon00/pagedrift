#!/usr/bin/env python3
"""
Integration tests for auto-applying tags to watches by URL pattern matching.

Verifies:
 - A tag with url_match_pattern shows on the watch overview list (via get_all_tags_for_watch)
 - The auto-applied tag appears on the watch edit page
 - A watch whose URL does NOT match the pattern does not get the tag
"""

