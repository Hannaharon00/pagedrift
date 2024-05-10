#!/usr/bin/env python3
import os

import time
from flask import url_for
from .util import set_original_response, set_modified_response, live_server_setup, wait_for_all_checks, extract_rss_token_from_UI, \
    extract_UUID_from_client, delete_all_watches


# Basic test to check inscriptus is not adding return line chars, basically works etc
def test_inscriptus():
    from inscriptis import get_text
    html_content = "<html><body>test!<br>ok man</body></html>"
    stripped_text_from_html = get_text(html_content)
    assert stripped_text_from_html == 'test!\nok man'



def test_check_basic_change_detection_functionality(client, live_server, measure_memory_usage, datastore_path):
    set_original_response(datastore_path=datastore_path)

    uuid = client.application.config.get('DATASTORE').add_watch(url=url_for('test_endpoint', _external=True))

    # Do this a few times.. ensures we dont accidently set the status
    for n in range(3):
        client.post(url_for("ui.form_watch_checknow"), follow_redirects=True)

        # Give the thread time to pick it up
        wait_for_all_checks(client)

        # It should report nothing found (no new 'has-unread-changes' class)
        res = client.get(url_for("watchlist.index"))
        assert b'has-unread-changes' not in res.data
        assert b'test-endpoint' in res.data

        # Default no password set, this stuff should be always available.

        assert b"Settings" in res.data
        assert b"Import" in res.data

    #####################

    # Check HTML conversion detected and workd
    res = client.get(
        url_for("ui.ui_preview.preview_page", uuid="first"),
        follow_redirects=True
    )
    # Check this class does not appear (that we didnt see the actual source)
    assert b'foobar-detection' not in res.data

    # Check POST preview
    res = client.post(
        url_for("ui.ui_preview.preview_page", uuid="first"),
        follow_redirects=True
    )
    # Check this class does not appear (that we didnt see the actual source)
    assert b'foobar-detection' not in res.data


    # Make a change
    set_modified_response(datastore_path=datastore_path)

    # Force recheck
    res = client.post(url_for("ui.form_watch_checknow"), follow_redirects=True)
    assert b'Queued 1 watch for rechecking.' in res.data

    wait_for_all_checks(client)

    uuid = next(iter(live_server.app.config['DATASTORE'].data['watching']))

    # Check the 'get latest snapshot works'
    res = client.get(url_for("ui.ui_edit.watch_get_latest_html", uuid=uuid))
    assert b'which has this one new line' in res.data

    # Now something should be ready, indicated by having a 'has-unread-changes' class
    res = client.get(url_for("watchlist.index"))
    assert b'has-unread-changes' in res.data

    # #75, and it should be in the RSS feed
    rss_token = extract_rss_token_from_UI(client)
    res = client.get(url_for("rss.feed", token=rss_token, _external=True))
    expected_url = url_for('test_endpoint', _external=True)
    assert b'<rss' in res.data

    # re #16 should have the diff in here too
    assert b'which has this one new line' in res.data
    assert b'CDATA' in res.data

#
    # Following the 'diff' link, it should no longer display as 'has-unread-changes' even after we recheck it a few times
    res = client.get(url_for("ui.ui_diff.diff_history_page", uuid=uuid))
    assert b'selected=""' in res.data, "Confirm diff history page loaded"

    assert b'Which is across multiple lines' in res.data
    # The linefeed should have been added ( @BR@ was replaced with a linefeed because this is htmlcolor kinda display )
    assert b'Which is across multiple lines</span>\n' in res.data

    # Check the [preview] pulls the right one
    res = client.get(
        url_for("ui.ui_preview.preview_page", uuid="first"),
        follow_redirects=True
    )
    assert b'which has this one new line' in res.data
    assert b'Which is across multiple lines' not in res.data

    wait_for_all_checks(client)


    # Do this a few times.. ensures we don't accidently set the status
    for n in range(2):
        res = client.post(url_for("ui.form_watch_checknow"), follow_redirects=True)
        # Give the thread time to pick it up
        wait_for_all_checks(client)

        # It should report nothing found (no new 'has-unread-changes' class)
        res = client.get(url_for("watchlist.index"))

        assert b'has-unread-changes' not in res.data
        assert b'class="has-unread-changes' not in res.data
        assert b'head title' in res.data  # Should be ON by default
        assert b'test-endpoint' in res.data

    # Recheck it but only with a title change, content wasnt changed
    set_original_response(datastore_path=datastore_path, extra_title=" and more")

    client.post(url_for("ui.form_watch_checknow"), follow_redirects=True)
    wait_for_all_checks(client)
    res = client.get(url_for("watchlist.index"))
    assert b'head title and more' in res.data

    # Be sure the last_viewed is going to be greater than the last snapshot
    time.sleep(1)

    # hit the mark all viewed link
    res = client.post(url_for("ui.mark_all_viewed"), follow_redirects=True)

    assert b'class="has-unread-changes' not in res.data
    assert b'has-unread-changes' not in res.data

    # #2458 "clear history" should make the Watch object update its status correctly when the first snapshot lands again
    client.post(url_for("ui.clear_watch_history", uuid=uuid))
    client.post(url_for("ui.form_watch_checknow"), follow_redirects=True)
    wait_for_all_checks(client)
    res = client.get(url_for("watchlist.index"))
    assert b'preview/' in res.data

    #
    # Cleanup everything
    delete_all_watches(client)

def test_title_scraper(client, live_server, measure_memory_usage, datastore_path):

    set_original_response(datastore_path=datastore_path)
    uuid = client.application.config.get('DATASTORE').add_watch(url=url_for('test_endpoint', _external=True))
    client.post(url_for("ui.form_watch_checknow"), follow_redirects=True)
    wait_for_all_checks()

    # It should report nothing found (no new 'has-unread-changes' class)
    res = client.get(url_for("watchlist.index"))

    assert b'head title' in res.data  # Should be ON by default

    # Recheck it but only with a title change, content wasnt changed
    set_original_response(datastore_path=datastore_path, extra_title=" and more")

    client.post(url_for("ui.form_watch_checknow"), follow_redirects=True)
    wait_for_all_checks(client)
    res = client.get(url_for("watchlist.index"))
    assert b'head title and more' in res.data

    # disable <title> pickup
    res = client.post(
        url_for("settings.settings_page"),
        data={"application-ui-use_page_title_in_list": "",
              "requests-time_between_check-minutes": 180,
              'application-fetch_backend': "html_requests"},
        follow_redirects=True
    )

    set_original_response(datastore_path=datastore_path, extra_title=" SHOULD NOT APPEAR")

    client.post(url_for("ui.form_watch_checknow"), follow_redirects=True)
    wait_for_all_checks(client)
    res = client.get(url_for("watchlist.index"))
    assert b'SHOULD NOT APPEAR' not in res.data

    delete_all_watches(client)

def test_title_scraper_html_only(client, live_server, measure_memory_usage, datastore_path):

    with open(os.path.join(datastore_path, "endpoint-content.txt"), "w") as f:
        f.write('"My text document\nWhere I talk about <title>\nwhich should not get registered\n</title>')

    test_url = url_for('test_endpoint', content_type="text/plain", _external=True)

    uuid = client.application.config.get('DATASTORE').add_watch(test_url)
    client.post(url_for("ui.form_watch_checknow"), follow_redirects=True)
    wait_for_all_checks()

    # It should report nothing found (no new 'has-unread-changes' class)
    res = client.get(url_for("watchlist.index"))

    assert b'which should not get registered' not in res.data  # Should be ON by default
    assert not live_server.app.config['DATASTORE'].data['watching'][uuid].get('title')




