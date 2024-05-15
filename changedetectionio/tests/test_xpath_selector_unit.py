import sys
import os
import pytest

from changedetectionio import html_tools

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# test generation guide.
# 1. Do not include encoding in the xml declaration if the test object is a str type.
# 2. Always paraphrase test.

