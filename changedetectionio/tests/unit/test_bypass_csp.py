import asyncio
import sys
from types import ModuleType, SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from changedetectionio.browser_steps.browser_steps import browsersteps_live_ui
from changedetectionio.content_fetchers.base import get_playwright_bypass_csp


