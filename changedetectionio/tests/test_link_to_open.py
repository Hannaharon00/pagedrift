"""
Tests for the optional per-watch "Link to Open" (`link_to_open`).

A watch may point at something that is useless in a browser - an API endpoint or an RSS
feed - while the human-readable page lives somewhere else. `link_to_open` stores that page,
and every "go to the site" affordance (watch list, history/preview header, the
{{watch_open_url}} notification token) uses it in preference to the watched URL.
"""

import os

from flask import url_for

