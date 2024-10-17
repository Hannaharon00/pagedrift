#!/usr/bin/env python3
"""
Tests for the AI/LLM settings a group hands to its watches.

A group has exactly ONE AI control on its edit page — the ternary llm_backend_profile
("AI for watches in this group"):

  On                   the group's llm_intent / llm_change_summary apply to every watch in
                       it (unless the watch fills in its own), and AI is on for all of them
  Off                  AI off for every watch in the group; its prompts are never used
  Leave it to each     the group has no say; each watch's own AI settings apply

Only "On" makes anything cascade, so it decides both:

  * whether the evaluator inherits the group's prompts (resolve_llm_field /
    get_effective_summary_prompt), and
  * whether the watch edit page shows the inherited value as a
    "From group '<name>': <value>" placeholder.

So every UI assertion here is paired: group On → "From group ..." visible, group Off or
undecided → not a trace of it. On a watch the same field is a plain on/off checkbox (#4204).
"""

import html
import json

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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _configure_llm(datastore):
    """Enable a fake LLM so the AI section is visible in the edit form."""
    app = datastore.data['settings']['application']
    if 'llm' not in app:
        app['llm'] = {}
    app['llm'].update({'model': 'gpt-4o-mini', 'api_key': 'sk-test'})


def _create_watch(client, test_url, api_token):
    res = client.post(
        '/api/v1/watch',
        data=json.dumps({'url': test_url}),
        headers={'content-type': 'application/json', 'x-api-key': api_token},
        follow_redirects=True,
    )
    assert res.status_code == 201
    return res.json['uuid']


def _api_token(client):
    return client.application.config.get('DATASTORE').data['settings']['application'].get('api_access_token')


# ---------------------------------------------------------------------------
# Tag setup
# ---------------------------------------------------------------------------

def _add_tag_with_llm(datastore, title, llm_intent='', llm_change_summary='', ai=True):
    """Create a tag with LLM fields set directly in the datastore.

    `ai` is the group's single AI control (llm_backend_profile): True = On, False = Off,
    None = leave it to each watch. Defaults to True because most cases here are about what
    a group set to "On" hands down.
    """
    tag_uuid = datastore.add_tag(title)
    tag = datastore.data['settings']['application']['tags'][tag_uuid]
    if llm_intent:
        tag['llm_intent'] = llm_intent
    if llm_change_summary:
        tag['llm_change_summary'] = llm_change_summary
    tag['llm_backend_profile'] = ai
    return tag_uuid


