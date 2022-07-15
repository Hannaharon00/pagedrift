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

