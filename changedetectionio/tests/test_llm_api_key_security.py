#!/usr/bin/env python3
"""
Security tests: LLM API key must never appear in any API response.

The LLM API key is a secret credential stored in
datastore.data['settings']['application']['llm']['api_key'].
It must never be leaked through any API endpoint — watch GET/list,
tag GET/list, system-info, notifications — even when the calling client
has a valid API token (which is a different kind of credential).

These tests set a recognisable fake key and then exhaustively check every
API endpoint's response body for the key string.
"""

import json

from flask import url_for

from changedetectionio.tests.util import live_server_setup, delete_all_watches

CANARY_KEY = 'sk-CANARY-SECRET-DO-NOT-EXPOSE-12345'


def _configure_llm(datastore, api_key=CANARY_KEY):
    """Inject a recognisable API key into the datastore LLM settings."""
    app = datastore.data['settings']['application']
    if 'llm' not in app:
        app['llm'] = {}
    app['llm'].update({
        'model': 'gpt-4o-mini',
        'api_key': api_key,
    })


def _api_token(client):
    return client.application.config.get('DATASTORE').data['settings']['application'].get('api_access_token')


def _key_in_response(response, key=CANARY_KEY) -> bool:
    """Return True if the canary key appears anywhere in the response body."""
    body = response.data.decode('utf-8', errors='replace')
    return key in body


# ---------------------------------------------------------------------------
# Watch endpoints
# ---------------------------------------------------------------------------

def test_watch_get_does_not_expose_llm_api_key(
        client, live_server, measure_memory_usage, datastore_path):
    """GET /api/v1/watch/<uuid> must not contain the LLM API key."""
    ds = client.application.config.get('DATASTORE')
    _configure_llm(ds)
    api_token = _api_token(client)

    test_url = url_for('test_endpoint', _external=True)
    res = client.post(
        '/api/v1/watch',
        data=json.dumps({'url': test_url}),
        headers={'content-type': 'application/json', 'x-api-key': api_token},
        follow_redirects=True,
    )
    assert res.status_code == 201
    uuid = res.json.get('uuid')

    res = client.get(
        f'/api/v1/watch/{uuid}',
        headers={'x-api-key': api_token},
    )
    assert res.status_code == 200
    assert not _key_in_response(res), \
        "LLM API key leaked in GET /api/v1/watch/<uuid> response"

    delete_all_watches(client)


def test_watch_list_does_not_expose_llm_api_key(
        client, live_server, measure_memory_usage, datastore_path):
    """GET /api/v1/watches must not contain the LLM API key."""
    ds = client.application.config.get('DATASTORE')
    _configure_llm(ds)
    api_token = _api_token(client)

    test_url = url_for('test_endpoint', _external=True)
    client.post(
        '/api/v1/watch',
        data=json.dumps({'url': test_url}),
        headers={'content-type': 'application/json', 'x-api-key': api_token},
        follow_redirects=True,
    )

    res = client.get('/api/v1/watch', headers={'x-api-key': api_token})
    assert res.status_code == 200
    assert not _key_in_response(res), \
        "LLM API key leaked in GET /api/v1/watch (list) response"

    delete_all_watches(client)


def test_watch_put_response_does_not_expose_llm_api_key(
        client, live_server, measure_memory_usage, datastore_path):
    """PUT /api/v1/watch/<uuid> response must not echo back the LLM API key."""
    ds = client.application.config.get('DATASTORE')
    _configure_llm(ds)
    api_token = _api_token(client)

    test_url = url_for('test_endpoint', _external=True)
    res = client.post(
        '/api/v1/watch',
        data=json.dumps({'url': test_url}),
        headers={'content-type': 'application/json', 'x-api-key': api_token},
        follow_redirects=True,
    )
    assert res.status_code == 201
    uuid = res.json.get('uuid')

    res = client.put(
        f'/api/v1/watch/{uuid}',
        headers={'x-api-key': api_token, 'content-type': 'application/json'},
        data=json.dumps({'url': test_url, 'title': 'updated'}),
    )
    assert res.status_code == 200
    assert not _key_in_response(res), \
        "LLM API key leaked in PUT /api/v1/watch/<uuid> response"

    delete_all_watches(client)


# ---------------------------------------------------------------------------
# Tag endpoints
# ---------------------------------------------------------------------------

def test_tag_get_does_not_expose_llm_api_key(
        client, live_server, measure_memory_usage, datastore_path):
    """GET /api/v1/tag/<uuid> must not contain the LLM API key."""
    ds = client.application.config.get('DATASTORE')
    _configure_llm(ds)
    api_token = _api_token(client)

    tag_uuid = ds.add_tag('security-test-tag')

    res = client.get(
        f'/api/v1/tag/{tag_uuid}',
        headers={'x-api-key': api_token},
    )
    assert res.status_code == 200
    assert not _key_in_response(res), \
        "LLM API key leaked in GET /api/v1/tag/<uuid> response"

    delete_all_watches(client)


def test_tag_list_does_not_expose_llm_api_key(
        client, live_server, measure_memory_usage, datastore_path):
    """GET /api/v1/tags must not contain the LLM API key."""
    ds = client.application.config.get('DATASTORE')
    _configure_llm(ds)
    api_token = _api_token(client)

    res = client.get('/api/v1/tags', headers={'x-api-key': api_token})
    assert res.status_code == 200
    assert not _key_in_response(res), \
        "LLM API key leaked in GET /api/v1/tags response"

    delete_all_watches(client)


# ---------------------------------------------------------------------------
# System / global endpoints
# ---------------------------------------------------------------------------

def test_system_info_does_not_expose_llm_api_key(
        client, live_server, measure_memory_usage, datastore_path):
    """GET /api/v1/systeminfo must not contain the LLM API key."""
    ds = client.application.config.get('DATASTORE')
    _configure_llm(ds)
    api_token = _api_token(client)

    res = client.get('/api/v1/systeminfo', headers={'x-api-key': api_token})
    assert res.status_code == 200
    assert not _key_in_response(res), \
        "LLM API key leaked in GET /api/v1/systeminfo response"

    delete_all_watches(client)


def test_notifications_api_does_not_expose_llm_api_key(
        client, live_server, measure_memory_usage, datastore_path):
    """GET/POST/PUT /api/v1/notifications must not contain the LLM API key."""
    ds = client.application.config.get('DATASTORE')
    _configure_llm(ds)
    api_token = _api_token(client)

    # GET
    res = client.get('/api/v1/notifications', headers={'x-api-key': api_token})
    assert res.status_code == 200
    assert not _key_in_response(res), \
        "LLM API key leaked in GET /api/v1/notifications response"

    # POST — add a notification URL; response must not echo back LLM config
    res = client.post(
        '/api/v1/notifications',
        headers={'x-api-key': api_token, 'content-type': 'application/json'},
        data=json.dumps({'notification_urls': ['json://localhost/']}),
    )
    assert res.status_code in (200, 201, 400)  # 400 if URL invalid on server; still no key
    assert not _key_in_response(res), \
        "LLM API key leaked in POST /api/v1/notifications response"

    # PUT — replace notification URLs; response must not include LLM config
    res = client.put(
        '/api/v1/notifications',
        headers={'x-api-key': api_token, 'content-type': 'application/json'},
        data=json.dumps({'notification_urls': ['json://localhost/']}),
    )
    assert res.status_code in (200, 201, 400)
    assert not _key_in_response(res), \
        "LLM API key leaked in PUT /api/v1/notifications response"

    delete_all_watches(client)


def test_search_api_does_not_expose_llm_api_key(
        client, live_server, measure_memory_usage, datastore_path):
    """GET /api/v1/search must not contain the LLM API key."""
    ds = client.application.config.get('DATASTORE')
    _configure_llm(ds)
    api_token = _api_token(client)

    test_url = url_for('test_endpoint', _external=True)
    client.post(
        '/api/v1/watch',
        data=json.dumps({'url': test_url}),
        headers={'content-type': 'application/json', 'x-api-key': api_token},
        follow_redirects=True,
    )

    res = client.get('/api/v1/search?q=endpoint', headers={'x-api-key': api_token})
    assert res.status_code == 200
    assert not _key_in_response(res), \
        "LLM API key leaked in GET /api/v1/search response"

    delete_all_watches(client)


def test_openapi_spec_does_not_expose_llm_api_key(
        client, live_server, measure_memory_usage, datastore_path):
    """
    GET /api/v1/full-spec returns the static OpenAPI schema YAML.
    It must not embed any runtime secrets (LLM API key).
    """
    ds = client.application.config.get('DATASTORE')
    _configure_llm(ds)
    api_token = _api_token(client)

    # Spec endpoint has no auth requirement, but test with and without key
    res = client.get('/api/v1/full-spec')
    assert res.status_code == 200
    assert not _key_in_response(res), \
        "LLM API key leaked in GET /api/v1/full-spec response"

    delete_all_watches(client)


def test_no_api_settings_endpoint_exists(
        client, live_server, measure_memory_usage, datastore_path):
    """
    There is currently no /api/v1/settings endpoint.
    If one is added in the future it must be covered by its own
    security tests before reaching production.
    This test acts as a canary — it should FAIL if a settings endpoint
    is accidentally wired up without review.
    """
    api_token = _api_token(client)

    # GET and POST to /api/v1/settings must not succeed — no settings endpoint exists.
    # 404 = route not found; 405 = route exists for some methods but not this one.
    # Either means there is no working read/write settings endpoint.
    # A 200/201/400 would indicate a real endpoint was wired up.
    res_get = client.get('/api/v1/settings', headers={'x-api-key': api_token})
    assert res_get.status_code in (404, 405), \
        (f"Unexpected /api/v1/settings GET returned {res_get.status_code}. "
         "A settings endpoint must have explicit LLM key security tests before shipping.")

    res_post = client.post(
        '/api/v1/settings',
        headers={'x-api-key': api_token, 'content-type': 'application/json'},
        data=json.dumps({}),
    )
    assert res_post.status_code in (404, 405), \
        (f"Unexpected /api/v1/settings POST returned {res_post.status_code}. "
         "A settings endpoint must have explicit LLM key security tests before shipping.")

    delete_all_watches(client)


# ---------------------------------------------------------------------------
# Settings HTML page — key must not appear in the form source HTML
# ---------------------------------------------------------------------------

def test_settings_form_rejects_private_api_base(
        client, live_server, measure_memory_usage, datastore_path, monkeypatch):
    """The globalSettingsLLMForm validator must block private api_base values
    when ALLOW_IANA_RESTRICTED_ADDRESSES is not set, and must NOT persist them
    to the datastore."""
    monkeypatch.delenv('ALLOW_IANA_RESTRICTED_ADDRESSES', raising=False)

    ds = client.application.config.get('DATASTORE')
    # Make sure no stale api_base exists from previous tests.
    ds.data['settings']['application'].pop('llm', None)

    res = client.post(
        url_for('settings.settings_page'),
        data={
            'llm-model':    'gpt-4o',
            'llm-api_key':  '',
            'llm-api_base': 'http://127.0.0.1:11434',
            'application-pager_size': '50',
            'application-notification_format': 'System default',
            'requests-time_between_check-days': '0',
            'requests-time_between_check-hours': '0',
            'requests-time_between_check-minutes': '5',
            'requests-time_between_check-seconds': '0',
            'requests-time_between_check-weeks': '0',
            'requests-workers': '10',
            'requests-timeout': '60',
        },
        follow_redirects=True,
    )
    # Form re-renders with the validation error — page itself returns 200.
    assert res.status_code == 200
    body = res.data.decode('utf-8', errors='replace')
    assert 'ALLOW_IANA_RESTRICTED_ADDRESSES' in body, \
        "Settings page should surface the SSRF guard's bypass-env-var hint"

    saved = ds.data['settings']['application'].get('llm', {}).get('api_base', '')
    assert saved != 'http://127.0.0.1:11434', \
        f"Private api_base must not have been persisted (got {saved!r})"


# ---------------------------------------------------------------------------
# Credential exfiltration — stored api_key must NOT be auto-substituted when
# the caller points api_base at a different (potentially attacker-controlled)
# endpoint. GHSA-g36r-fm2p-87xm.
# ---------------------------------------------------------------------------

def test_llm_models_refuses_to_leak_stored_key_to_different_api_base(
        client, live_server, measure_memory_usage, datastore_path, monkeypatch):
    """If the request supplies an api_base that differs from the saved one but
    omits api_key, the endpoint must refuse — otherwise CSRF can ship the
    stored Authorization: Bearer <key> to an attacker-controlled URL."""
    monkeypatch.delenv('ALLOW_IANA_RESTRICTED_ADDRESSES', raising=False)
    ds = client.application.config.get('DATASTORE')
    _configure_llm(ds)   # stores CANARY_KEY, leaves api_base unset

    # Patch litellm.get_valid_models so that if the guard ever lets us through
    # we'd see it called — and we can assert it wasn't.
    import litellm
    calls = []
    monkeypatch.setattr(litellm, 'get_valid_models',
                        lambda **kwargs: calls.append(kwargs) or [])

    res = client.get(
        url_for('settings.llm.llm_get_models'),
        query_string={
            'provider': 'openai',
            'api_base': 'https://attacker.example/v1',
            # api_key intentionally omitted — this is the CSRF case
        },
    )
    assert res.status_code == 400, \
        "Endpoint should refuse to substitute stored key to a mismatched api_base"
    body = res.get_json()
    assert 'api_key' in body['error'], \
        f"Error should call out that api_key is required: {body['error']!r}"
    assert calls == [], "litellm must not have been invoked at all"


