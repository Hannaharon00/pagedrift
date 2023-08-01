#!/usr/bin/env python3
"""
Tests for immediate commit-based persistence system.

Tests cover:
- Watch.commit() persistence to disk
- Concurrent commit safety (race conditions)
- Processor config separation
- Data loss prevention (settings, tags, watch modifications)
"""

def test_watch_commit_persists_to_disk(client, live_server):
    """Test that watch.commit() actually writes to watch.json immediately"""
    datastore = client.application.config.get('DATASTORE')

    # Create a watch
    uuid = datastore.add_watch(url='http://example.com', extras={'title': 'Original Title'})
    watch = datastore.data['watching'][uuid]

    # Modify and commit
    watch['title'] = 'Modified Title'
    watch['paused'] = True
    watch.commit()

    # Read directly from disk (bypass datastore cache)
    watch_json_path = os.path.join(watch.data_dir, 'watch.json')
    assert os.path.exists(watch_json_path), "watch.json should exist on disk"

    with open(watch_json_path, 'r') as f:
        disk_data = json.load(f)

    assert disk_data['title'] == 'Modified Title', "Title should be persisted to disk"
    assert disk_data['paused'] == True, "Paused state should be persisted to disk"
    assert disk_data['uuid'] == uuid, "UUID should match"


def test_watch_commit_survives_reload(client, live_server):
    """Test that committed changes survive datastore reload"""
    from changedetectionio.store import ChangeDetectionStore

    datastore = client.application.config.get('DATASTORE')
    datastore_path = datastore.datastore_path

    # Create and modify a watch
    uuid = datastore.add_watch(url='http://example.com', extras={'title': 'Test Watch'})
    watch = datastore.data['watching'][uuid]
    watch['title'] = 'Persisted Title'
    watch['paused'] = True
    watch['tags'] = ['tag-1', 'tag-2']
    watch.commit()

    # Simulate app restart - create new datastore instance
    datastore2 = ChangeDetectionStore(datastore_path=datastore_path)
    datastore2.reload_state(
        datastore_path=datastore_path,
        include_default_watches=False,
        version_tag='test'
    )

    # Check data survived
    assert uuid in datastore2.data['watching'], "Watch should exist after reload"
    reloaded_watch = datastore2.data['watching'][uuid]
    assert reloaded_watch['title'] == 'Persisted Title', "Title should survive reload"
    assert reloaded_watch['paused'] == True, "Paused state should survive reload"
    assert reloaded_watch['tags'] == ['tag-1', 'tag-2'], "Tags should survive reload"


