#!/usr/bin/env python3
"""
Unit tests for XPath default namespace handling in RSS/Atom feeds.
Tests the fix for issue where //title/text() returns empty on feeds with default namespaces.

Real-world test data from https://github.com/microsoft/PowerToys/releases.atom
"""

import sys
import os
import pytest

