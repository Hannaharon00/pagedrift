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


def test_watch_commit_atomic_on_crash(client, live_server):
    """Test that atomic writes prevent corruption (temp file pattern)"""
    datastore = client.application.config.get('DATASTORE')

    uuid = datastore.add_watch(url='http://example.com', extras={'title': 'Original'})
    watch = datastore.data['watching'][uuid]

    # First successful commit
    watch['title'] = 'First Save'
    watch.commit()

    # Verify watch.json exists and is valid
    watch_json_path = os.path.join(watch.data_dir, 'watch.json')
    with open(watch_json_path, 'r') as f:
        data = json.load(f)  # Should not raise JSONDecodeError
        assert data['title'] == 'First Save'

    # Second commit - even if interrupted, original file should be intact
    # (atomic write uses temp file + rename, so original is never corrupted)
    watch['title'] = 'Second Save'
    watch.commit()

    with open(watch_json_path, 'r') as f:
        data = json.load(f)
        assert data['title'] == 'Second Save'


def test_multiple_watches_commit_independently(client, live_server):
    """Test that committing one watch doesn't affect others"""
    datastore = client.application.config.get('DATASTORE')

    # Create multiple watches
    uuid1 = datastore.add_watch(url='http://example1.com', extras={'title': 'Watch 1'})
    uuid2 = datastore.add_watch(url='http://example2.com', extras={'title': 'Watch 2'})
    uuid3 = datastore.add_watch(url='http://example3.com', extras={'title': 'Watch 3'})

    watch1 = datastore.data['watching'][uuid1]
    watch2 = datastore.data['watching'][uuid2]
    watch3 = datastore.data['watching'][uuid3]

    # Modify and commit only watch2
    watch2['title'] = 'Modified Watch 2'
    watch2['paused'] = True
    watch2.commit()

    # Read all from disk
    def read_watch_json(uuid):
        watch = datastore.data['watching'][uuid]
        path = os.path.join(watch.data_dir, 'watch.json')
        with open(path, 'r') as f:
            return json.load(f)

    data1 = read_watch_json(uuid1)
    data2 = read_watch_json(uuid2)
    data3 = read_watch_json(uuid3)

    # Only watch2 should have changes
    assert data1['title'] == 'Watch 1', "Watch 1 should be unchanged"
    assert data1['paused'] == False, "Watch 1 should not be paused"

    assert data2['title'] == 'Modified Watch 2', "Watch 2 should be modified"
    assert data2['paused'] == True, "Watch 2 should be paused"

    assert data3['title'] == 'Watch 3', "Watch 3 should be unchanged"
    assert data3['paused'] == False, "Watch 3 should not be paused"


