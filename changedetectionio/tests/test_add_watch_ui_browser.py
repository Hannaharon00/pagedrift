#!/usr/bin/env python3
"""The Add-Watch page's browser picker.

The live preview needs a browser that can render screenshots + xpath element data, and
whatever rendered the preview is what the saved watch must check with - otherwise you
visually pick an element with Chrome and the watch then re-checks it with the plain HTTP
client. These tests cover the offered list, the server-side gate, and that the browser
which rendered a parked snapshot wins over the posted form.
"""
import json
import os

from flask import url_for


