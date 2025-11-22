#!/usr/bin/env python3

# run from dir above changedetectionio/ dir
# python3 -m unittest changedetectionio.tests.unit.test_notification_diff

import unittest
import os
import pickle
import tempfile
from copy import deepcopy

from changedetectionio.model import Watch, Tag

class TestLinkToOpen(unittest.TestCase):
    """`link_to_open` - the optional human-facing URL used instead of the watched URL."""

    def _make_watch(self, **fields):
        mock_datastore = {'settings': {'application': {}}, 'watching': {}}
        return Watch.model(datastore_path='/tmp', __datastore=mock_datastore, default=fields)

    def test_defaults_to_the_watched_url(self):
        watch = self._make_watch(url='https://example.com/feed.xml')
        assert watch.open_link_override == ''
        assert watch.open_link == 'https://example.com/feed.xml'
        assert watch.open_link == watch.link

    def test_override_wins_when_set(self):
        watch = self._make_watch(url='https://example.com/api/v1/items.json',
                                 link_to_open='https://example.com/shop/items')
        assert watch.link == 'https://example.com/api/v1/items.json'
        assert watch.open_link == 'https://example.com/shop/items'
        assert watch.open_link_override == 'https://example.com/shop/items'

    def test_whitespace_only_override_is_ignored(self):
        watch = self._make_watch(url='https://example.com/feed.xml', link_to_open='   ')
        assert watch.open_link_override == ''
        assert watch.open_link == 'https://example.com/feed.xml'

    def test_unsafe_override_falls_back_to_the_watched_url(self):
        watch = self._make_watch(url='https://example.com/feed.xml',
                                 link_to_open='javascript:alert(1)')
        assert watch.open_link_override == ''
        assert watch.open_link == 'https://example.com/feed.xml'

    def test_source_prefix_is_stripped_from_the_override(self):
        watch = self._make_watch(url='source:https://example.com/feed.xml',
                                 link_to_open='source:https://example.com/page')
        assert watch.open_link == 'https://example.com/page'

    def test_jinja2_in_the_override_is_rendered(self):
        watch = self._make_watch(url='https://example.com/feed.xml',
                                 link_to_open='https://example.com/page?id={{ 1+1 }}')
        assert watch.open_link == 'https://example.com/page?id=2'


