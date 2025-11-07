#!/usr/bin/env python3

# run from dir above changedetectionio/ dir
# python3 -m unittest changedetectionio.tests.unit.test_notification_diff

import unittest
import os

from changedetectionio import diff
from changedetectionio.diff import (
    REMOVED_PLACEMARKER_OPEN,
    REMOVED_PLACEMARKER_CLOSED,
    ADDED_PLACEMARKER_OPEN,
    ADDED_PLACEMARKER_CLOSED,
    CHANGED_PLACEMARKER_OPEN,
    CHANGED_PLACEMARKER_CLOSED,
    CHANGED_INTO_PLACEMARKER_OPEN,
    CHANGED_INTO_PLACEMARKER_CLOSED,
    extract_changed_from,
    extract_changed_to,
)


# mostly
class TestDiffBuilder(unittest.TestCase):

    def test_expected_diff_output(self):
        base_dir = os.path.dirname(__file__)
        with open(base_dir + "/test-content/before.txt", 'r') as f:
            previous_version_file_contents = f.read()

        with open(base_dir + "/test-content/after.txt", 'r') as f:
            newest_version_file_contents = f.read()

        output = diff.render_diff(previous_version_file_contents=previous_version_file_contents,
                                  newest_version_file_contents=newest_version_file_contents)

        output = output.split("\n")

        # Check that placemarkers are present (they get replaced in apply_service_tweaks)
        self.assertTrue(any(CHANGED_PLACEMARKER_OPEN in line and 'ok' in line for line in output))
        self.assertTrue(any(CHANGED_INTO_PLACEMARKER_OPEN in line and 'xok' in line for line in output))
        self.assertTrue(any(CHANGED_INTO_PLACEMARKER_OPEN in line and 'next-x-ok' in line for line in output))
        self.assertTrue(any(ADDED_PLACEMARKER_OPEN in line and 'and something new' in line for line in output))

        with open(base_dir + "/test-content/after-2.txt", 'r') as f:
            newest_version_file_contents = f.read()
        output = diff.render_diff(previous_version_file_contents, newest_version_file_contents)
        output = output.split("\n")
        self.assertTrue(any(REMOVED_PLACEMARKER_OPEN in line and 'for having learned computerese,' in line for line in output))
        self.assertTrue(any(REMOVED_PLACEMARKER_OPEN in line and 'I continue to examine bits, bytes and words' in line for line in output))

        #diff_removed
        with open(base_dir + "/test-content/before.txt", 'r') as f:
            previous_version_file_contents = f.read()

        with open(base_dir + "/test-content/after.txt", 'r') as f:
            newest_version_file_contents = f.read()
        output = diff.render_diff(previous_version_file_contents, newest_version_file_contents, include_equal=False, include_removed=True, include_added=False)
        output = output.split("\n")
        self.assertTrue(any(CHANGED_PLACEMARKER_OPEN in line and 'ok' in line for line in output))
        self.assertTrue(any(CHANGED_INTO_PLACEMARKER_OPEN in line and 'xok' in line for line in output))
        self.assertTrue(any(CHANGED_INTO_PLACEMARKER_OPEN in line and 'next-x-ok' in line for line in output))
        self.assertFalse(any(ADDED_PLACEMARKER_OPEN in line and 'and something new' in line for line in output))

        #diff_removed
        with open(base_dir + "/test-content/after-2.txt", 'r') as f:
            newest_version_file_contents = f.read()
        output = diff.render_diff(previous_version_file_contents, newest_version_file_contents, include_equal=False, include_removed=True, include_added=False)
        output = output.split("\n")
        self.assertTrue(any(REMOVED_PLACEMARKER_OPEN in line and 'for having learned computerese,' in line for line in output))
        self.assertTrue(any(REMOVED_PLACEMARKER_OPEN in line and 'I continue to examine bits, bytes and words' in line for line in output))

    def test_expected_diff_patch_output(self):
        base_dir = os.path.dirname(__file__)
        with open(base_dir + "/test-content/before.txt", 'r') as f:
            before = f.read()
        with open(base_dir + "/test-content/after.txt", 'r') as f:
            after = f.read()

        output = diff.render_diff(previous_version_file_contents=before,
                                  newest_version_file_contents=after,
                                  patch_format=True)

        

        output = output.split("\n")

        self.assertIn('-ok', output)
        self.assertIn('+xok', output)
        self.assertIn('+next-x-ok', output)
        self.assertIn('+and something new', output)

        # @todo test blocks of changed, blocks of added, blocks of removed

    def test_word_level_diff(self):
        """Test word-level diff functionality"""
        before = "The quick brown fox jumps over the lazy dog"
        after = "The fast brown cat jumps over the lazy dog"

        # Test with word_diff enabled
        output = diff.render_diff(before, after, include_equal=False, word_diff=True)
        # Should highlight only changed words, not entire line
        self.assertIn(f'{REMOVED_PLACEMARKER_OPEN}quick{REMOVED_PLACEMARKER_CLOSED}', output)
        self.assertIn(f'{ADDED_PLACEMARKER_OPEN}fast{ADDED_PLACEMARKER_CLOSED}', output)
        self.assertIn(f'{REMOVED_PLACEMARKER_OPEN}fox{REMOVED_PLACEMARKER_CLOSED}', output)
        self.assertIn(f'{ADDED_PLACEMARKER_OPEN}cat{ADDED_PLACEMARKER_CLOSED}', output)
        # Unchanged words should appear without markers
        self.assertIn('brown', output)
        self.assertIn('jumps', output)

        # Test with word_diff disabled (line-level)
        output = diff.render_diff(before, after, include_equal=False, word_diff=False)
        # Should show full line changes
        self.assertIn(f'{CHANGED_PLACEMARKER_OPEN}The quick brown fox jumps over the lazy dog{CHANGED_PLACEMARKER_CLOSED}', output)
        self.assertIn(f'{CHANGED_INTO_PLACEMARKER_OPEN}The fast brown cat jumps over the lazy dog{CHANGED_INTO_PLACEMARKER_CLOSED}', output)

