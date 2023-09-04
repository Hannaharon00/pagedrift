#!/usr/bin/env python3
"""
OpenAPI validation tests for ChangeDetection.io API

This test file specifically verifies that OpenAPI validation is working correctly
by testing various scenarios that should trigger validation errors.
"""

import time
import json
from flask import url_for
from .util import live_server_setup, wait_for_all_checks, delete_all_watches


def test_openapi_merged_spec_contains_restock_fields():
    """
    Unit test: verify that build_merged_spec_dict() correctly merges the
    restock_diff processor api.yaml into the base spec so that
    WatchBase.properties includes processor_config_restock_diff with all
    expected sub-fields.  No live server required.
    """
    from changedetectionio.api import build_merged_spec_dict

    spec = build_merged_spec_dict()
    schemas = spec['components']['schemas']

    # The merged schema for processor_config_restock_diff should exist
    assert 'processor_config_restock_diff' in schemas, \
        "processor_config_restock_diff schema missing from merged spec"

    restock_schema = schemas['processor_config_restock_diff']
    props = restock_schema.get('properties', {})

    expected_fields = {
        'in_stock_processing',
        'follow_price_changes',
        'price_change_min',
        'price_change_max',
        'price_change_threshold_percent',
    }
    missing = expected_fields - set(props.keys())
    assert not missing, f"Missing fields in processor_config_restock_diff schema: {missing}"

    # in_stock_processing must be an enum with the three valid values
    enum_values = set(props['in_stock_processing'].get('enum', []))
    assert enum_values == {'in_stock_only', 'all_changes', 'off'}, \
        f"Unexpected enum values for in_stock_processing: {enum_values}"

    # WatchBase.properties must carry a $ref to the restock schema so the
    # validation middleware can enforce it on every POST/PUT to /watch
    watchbase_props = schemas['WatchBase']['properties']
    assert 'processor_config_restock_diff' in watchbase_props, \
        "processor_config_restock_diff not wired into WatchBase.properties"
    ref = watchbase_props['processor_config_restock_diff'].get('$ref', '')
    assert 'processor_config_restock_diff' in ref, \
        f"WatchBase.processor_config_restock_diff should $ref the schema, got: {ref}"


def test_openapi_validation_invalid_content_type_on_create_watch(client, live_server, measure_memory_usage, datastore_path):
    """Test that creating a watch with invalid content-type triggers OpenAPI validation error."""
    api_key = live_server.app.config['DATASTORE'].data['settings']['application'].get('api_access_token')

    # Try to create a watch with JSON data but without proper content-type header
    res = client.post(
        url_for("createwatch"),
        data=json.dumps({"url": "https://example.com", "title": "Test Watch"}),
        headers={'x-api-key': api_key},  # Missing 'content-type': 'application/json'
        follow_redirects=True
    )

    # Should get 400 error due to OpenAPI validation failure
    assert res.status_code == 400, f"Expected 400 but got {res.status_code}"
    assert b"Validation failed" in res.data, "Should contain validation error message"
    delete_all_watches(client)


