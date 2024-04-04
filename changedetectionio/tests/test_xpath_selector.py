# -*- coding: utf-8 -*-


from flask import url_for
from .util import  wait_for_all_checks, delete_all_watches
from ..processors.magic import RSS_XML_CONTENT_TYPES
import os


def set_rss_atom_feed_response(datastore_path, header='', ):
    test_return_data = f"""{header}<!-- Generated on Wed, 08 Oct 2025 08:42:33 -0700, really really honestly  -->
<rss xmlns:atom="http://www.w3.org/2005/Atom" version="2.0">
<channel>
    <atom:link href="https://store.waterpowered.com/news/collection//" rel="self" type="application/rss+xml"/>
    <title>RSS Feed</title>
    <link>
        <![CDATA[ https://store.waterpowered.com/news/collection// ]]>
    </link>
    <description>
        <![CDATA[ Events and Announcements for ]]>
    </description>
    <language>en-us</language>
    <generator>water News RSS</generator>
    <item>
        <title> 🍁 Lets go discount</title>
        <description><p class="bb_paragraph">ok heres the description</p></description>
        <link>
        <![CDATA[ https://store.waterpowered.com/news/app/1643320/view/511845698831908921 ]]>
        </link>
        <pubDate>Wed, 08 Oct 2025 15:28:55 +0000</pubDate>
        <guid isPermaLink="true">https://store.waterpowered.com/news/app/1643320/view/511845698831908921</guid>
        <enclosure url="https://clan.fastly.waterstatic.com/images/40721482/42822e5f00b2becf520ace9500981bb56f3a89f2.jpg" length="0" type="image/jpeg"/>
    </item>
</channel>
</rss>"""

    with open(os.path.join(datastore_path, "endpoint-content.txt"), "w") as f:
        f.write(test_return_data)

    return None



def test_check_markup_xpath_filter_restriction(client, live_server, measure_memory_usage, datastore_path):
    xpath_filter = "//*[contains(@class, 'sametext')]"

    set_original_response(datastore_path=datastore_path)

    # Add our URL to the import page
    test_url = url_for('test_endpoint', _external=True)
    uuid = client.application.config.get('DATASTORE').add_watch(url=test_url)
    client.post(url_for("ui.form_watch_checknow"), follow_redirects=True)

    # Give the thread time to pick it up
    wait_for_all_checks(client)

    # Goto the edit page, add our ignore text
    # Add our URL to the import page
    res = client.post(
        url_for("ui.ui_edit.edit_page", uuid="first"),
        data={"include_filters": xpath_filter, "url": test_url, "tags": "", "headers": "", 'fetch_backend': "html_requests", "time_between_check_use_default": "y"},
        follow_redirects=True
    )
    assert b"Updated watch." in res.data

    # Give the thread time to pick it up
    wait_for_all_checks(client)

    # view it/reset state back to viewed
    client.get(url_for("ui.ui_diff.diff_history_page", uuid="first"), follow_redirects=True)

    #  Make a change
    set_modified_response(datastore_path=datastore_path)

    # Trigger a check
    client.post(url_for("ui.form_watch_checknow"), follow_redirects=True)
    # Give the thread time to pick it up
    wait_for_all_checks(client)

    res = client.get(url_for("watchlist.index"))
    assert b'has-unread-changes' not in res.data
    delete_all_watches(client)


def test_xpath_validation(client, live_server, measure_memory_usage, datastore_path):
    # Add our URL to the import page
    test_url = url_for('test_endpoint', _external=True)
    uuid = client.application.config.get('DATASTORE').add_watch(url=test_url)
    client.post(url_for("ui.form_watch_checknow"), follow_redirects=True)
    wait_for_all_checks(client)

    res = client.post(
        url_for("ui.ui_edit.edit_page", uuid="first"),
        data={"include_filters": "/something horrible", "url": test_url, "tags": "", "headers": "", 'fetch_backend': "html_requests", "time_between_check_use_default": "y"},
        follow_redirects=True
    )
    assert b"is not a valid XPath expression" in res.data
    delete_all_watches(client)


def test_xpath1_validation(client, live_server, measure_memory_usage, datastore_path):
    # Add our URL to the import page
    test_url = url_for('test_endpoint', _external=True)
    uuid = client.application.config.get('DATASTORE').add_watch(url=test_url)
    client.post(url_for("ui.form_watch_checknow"), follow_redirects=True)
    wait_for_all_checks(client)

    res = client.post(
        url_for("ui.ui_edit.edit_page", uuid="first"),
        data={"include_filters": "xpath1:/something horrible", "url": test_url, "tags": "", "headers": "", 'fetch_backend': "html_requests", "time_between_check_use_default": "y"},
        follow_redirects=True
    )
    assert b"is not a valid XPath expression" in res.data
    delete_all_watches(client)


# actually only really used by the distll.io importer, but could be handy too
def test_check_with_prefix_include_filters(client, live_server, measure_memory_usage, datastore_path):
    delete_all_watches(client)

    set_original_response(datastore_path=datastore_path)
    wait_for_all_checks(client)
    # Add our URL to the import page
    test_url = url_for('test_endpoint', _external=True)
    uuid = client.application.config.get('DATASTORE').add_watch(url=test_url)
    client.post(url_for("ui.form_watch_checknow"), follow_redirects=True)
    wait_for_all_checks(client)

    res = client.post(
        url_for("ui.ui_edit.edit_page", uuid="first"),
        data={"include_filters": "xpath://*[contains(@class, 'sametext')]", "url": test_url, "tags": "", "headers": "",
              'fetch_backend': "html_requests", "time_between_check_use_default": "y"},
        follow_redirects=True
    )

    assert b"Updated watch." in res.data
    wait_for_all_checks(client)

    res = client.get(
        url_for("ui.ui_preview.preview_page", uuid="first"),
        follow_redirects=True
    )

    assert b"Some text thats the same" in res.data  # in selector
    assert b"Some text that will change" not in res.data  # not in selector

    delete_all_watches(client)


