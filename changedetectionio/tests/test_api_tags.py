#!/usr/bin/env python3

def test_api_tag_restock_processor_config(client, live_server, measure_memory_usage, datastore_path):
    """
    Test that a tag/group can be created and updated with processor_config_restock_diff via the API.
    Since Tag extends WatchBase, processor config fields injected into WatchBase are also valid for tags.
    """
    api_key = live_server.app.config['DATASTORE'].data['settings']['application'].get('api_access_token')

