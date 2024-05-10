"""A renderer crash must stay local to the tab that crashed.

pyppeteer emits Page 'error' (``PageError('Page crashed!')``) when the renderer dies, and pyee
re-raises an 'error' emission that has no listener. That raise escapes into
``Connection._onMessage``, whose catch-all disposes the whole connection - so one dead tab takes
the browser with it and every later call reports the misleading "Session closed. Most likely the
page has been closed." ``fetch_page()`` attaches a listener to keep the failure local.
"""

import asyncio
import sys
from types import ModuleType, SimpleNamespace
from unittest.mock import AsyncMock, Mock

