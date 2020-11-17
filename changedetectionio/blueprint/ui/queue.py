"""
Queue inspection UI.

Surfaces what's currently being processed and what's waiting so users can
make sense of the "Queued size: N" indicator (see issue #4077).

Priority conventions (see uses of PrioritizedItem across the codebase):
  1     - immediate / manual recheck
  5     - clone follow-up
  >100  - scheduler-enqueued (timestamp-based)
"""

from flask import Blueprint, jsonify, redirect, render_template, request, url_for, flash
from flask_babel import gettext
from flask_paginate import Pagination, get_page_parameter

from changedetectionio.auth_decorator import login_optionally_required
from changedetectionio.store import ChangeDetectionStore


PRIORITY_LABELS = {
    1: "immediate",
    5: "clone",
}


def _priority_label(priority):
    if priority in PRIORITY_LABELS:
        return PRIORITY_LABELS[priority]
    if priority > 100:
        return "scheduled"
    return f"p{priority}"


def _watch_brief(datastore, uuid):
    """Best-effort summary for a watch (placeholder if it's been deleted)."""
    watch = datastore.data['watching'].get(uuid)
    if not watch:
        return {'uuid': uuid, 'title': None, 'url': None, 'gone': True}
    return {
        'uuid': uuid,
        'title': watch.get('title') or watch.get('label') or None,
        'url': watch.get('url'),
        'last_checked': watch.get('last_checked', 0),
        'last_error': watch.get('last_error') or None,
        'paused': watch.get('paused', False),
        'gone': False,
    }


