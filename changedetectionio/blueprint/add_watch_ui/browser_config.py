"""Which content fetchers can drive the Add-Watch live preview / visual selector.

Single source of truth for "can this browser render a live preview": the Add-Watch
browser list, the /snapshot endpoint and the submit-time form validator all resolve
through here, so the UI can never offer - and the server can never accept - a fetcher
that is unable to produce what the visual selector needs.

The preview is rendered by browsersteps_live_ui() (see blueprint/browser_steps), so a
usable browser needs `supports_browser_steps` *as well as* screenshots and xpath
element data. That third flag is what rules out Selenium/WebDriver: it can screenshot
during a normal check, but it cannot drive the interactive session the preview needs
(acquire_browser_for_fetcher() would quietly connect to PLAYWRIGHT_DRIVER_URL instead,
which is not the browser the user picked). It also rules out settings.requests
extra_browsers, which are WebDriver connection URLs, so they are not offered here.
"""

from loguru import logger

