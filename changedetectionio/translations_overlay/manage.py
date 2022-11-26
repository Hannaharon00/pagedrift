#!/usr/bin/env python3
"""Manage the deployment wording overlay catalogs.

The overlay is a second gettext tree merged on top of ``changedetectionio/translations`` at
runtime (see the BABEL_TRANSLATION_DIRECTORIES block in ``changedetectionio/flask_app.py``).
Flask-Babel merges the two catalogs per-locale, later directory winning per-message, so an
overlay catalog only needs the msgids whose wording this deployment changes.

The catch this tooling exists to manage: an override is keyed on the exact upstream msgid.
When upstream edits a string - even a typo fix - the override stops matching and that string
silently reverts to upstream wording. ``check`` turns that silent revert into a hard failure.

    python changedetectionio/translations_overlay/manage.py check
    python changedetectionio/translations_overlay/manage.py compile
    python changedetectionio/translations_overlay/manage.py add de
"""

import argparse
import os
import sys

from babel.messages.mofile import read_mo, write_mo
from babel.messages.pofile import read_po, write_po

OVERLAY_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.join(os.path.dirname(OVERLAY_DIR), 'translations')
POT_FILE = os.path.join(BASE_DIR, 'messages.pot')


def _po_path(root, locale):
    return os.path.join(root, locale, 'LC_MESSAGES', 'messages.po')


def _mo_path(root, locale):
    return os.path.join(root, locale, 'LC_MESSAGES', 'messages.mo')


def overlay_locales():
    """Locales that have an overlay catalog, sorted."""
    return sorted(d for d in os.listdir(OVERLAY_DIR) if os.path.isfile(_po_path(OVERLAY_DIR, d)))


