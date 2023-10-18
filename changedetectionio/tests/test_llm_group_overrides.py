#!/usr/bin/env python3
"""
Tests for the AI/LLM settings a group hands to its watches.

A group has exactly ONE AI control on its edit page — the ternary llm_backend_profile
("AI for watches in this group"):

  On                   the group's llm_intent / llm_change_summary apply to every watch in
                       it (unless the watch fills in its own), and AI is on for all of them
  Off                  AI off for every watch in the group; its prompts are never used
  Leave it to each     the group has no say; each watch's own AI settings apply

from flask import url_for

from changedetectionio.tests.util import live_server_setup, delete_all_watches


# The exact rendered string under test, from templates/edit/include_llm_intent.html:
#   {% set intent_placeholder = _("From group '%(name)s': %(value)s", ...) %}
def _from_group_text(name, value):
    return f"From group '{name}': {value}"


def _page_text(res):
    """Response body with HTML entities resolved, so we can match the placeholder as written."""
    return html.unescape(res.data.decode('utf-8', errors='replace'))


def _input_tags(body, name):
    """Every whole <input ...> tag carrying name="<name>", in document order."""
    tags = []
    pos = body.find(f'name="{name}"')
    while pos != -1:
        start = body.rfind('<input', 0, pos)
        end = body.find('>', pos)
        tags.append(body[start:end + 1])
        pos = body.find(f'name="{name}"', end)
    return tags


def _input_tag(body, name):
    """Return the first <input ...> tag carrying name="<name>", or '' if there isn't one."""
    tags = _input_tags(body, name)
    return tags[0] if tags else ''


def _checkbox_is_checked(body, name):
    """True when that checkbox renders as checked (attribute order is not guaranteed)."""
    tag = _input_tag(body, name)
    assert tag, f'no <input name="{name}"> in the page'
    return 'checked' in tag


