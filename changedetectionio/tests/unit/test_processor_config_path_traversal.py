#!/usr/bin/env python3

# run from dir above changedetectionio/ dir
# python3 -m unittest changedetectionio.tests.unit.test_processor_config_path_traversal

"""Regression tests for GHSA-mh42-m7cg-49fr - arbitrary file write via the watch `processor` field.

A watch's `processor` is enum-validated by the API, but /imports/import puts
request.values.get('processor') into the watch verbatim. save_processor_config() then uses that
value as a filename (f'{processor}.json') and update_extra_watch_config() did
os.path.join(data_dir, filename) + open(filepath, 'w') with no containment - so a value like
'../../../../tmp/pwned' escaped the watch directory and wrote an attacker-named JSON file
anywhere the app user could reach. get_extra_watch_config() had the same traversal on read.

Three layers are asserted here: path containment in base.py (the security boundary), the filename
sanity check in save_processor_config(), and add_watch() refusing to persist an unknown processor
at all - which also covers the share-link import path, where 'processor' arrives in JSON fetched
from a remote URL.
"""

import os
import tempfile
import unittest

from changedetectionio.processors.base import difference_detection_processor


class TestWatchConfigPathContainment(unittest.TestCase):
    """The containment helper is the security boundary - every caller goes through it."""

    def setUp(self):
        self.base = tempfile.mkdtemp()
        self.data_dir = os.path.join(self.base, 'datastore', 'some-watch-uuid')
        os.makedirs(self.data_dir)

    def _resolve(self, filename):
        return difference_detection_processor._resolve_watch_config_path(self.data_dir, filename)

    def test_normal_processor_filenames_are_allowed(self):
        for filename in ('text_json_diff.json', 'restock_diff.json', 'visual_ssim_score.json'):
            with self.subTest(filename=filename):
                got = self._resolve(filename)
                self.assertEqual(got, os.path.join(os.path.realpath(self.data_dir), filename))

    def test_traversal_is_refused(self):
        # The exact shape from the advisory PoC, plus the usual variants
        attempts = (
            '../../../../../../tmp/pwned.json',
            '../pwned.json',
            '..',
            '.',
            '',
            None,
            '/etc/cron.d/pwned.json',
            'subdir/pwned.json',
            '..\\..\\pwned.json',
        )
        for filename in attempts:
            with self.subTest(filename=filename):
                self.assertIsNone(self._resolve(filename),
                                  f"{filename!r} must not resolve to a writable path")

    def test_symlink_inside_the_watch_dir_cannot_redirect_the_write(self):
        """A bare filename is not enough - it must still land inside the directory."""
        outside = os.path.join(self.base, 'outside.json')
        link = os.path.join(self.data_dir, 'evil.json')
        os.symlink(outside, link)
        self.assertIsNone(self._resolve('evil.json'))


