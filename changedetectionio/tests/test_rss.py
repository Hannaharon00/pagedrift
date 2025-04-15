#!/usr/bin/env python3
import email.utils
import os
import time
import pytest
from flask import url_for
from .util import set_original_response, set_modified_response, live_server_setup, wait_for_all_checks, extract_rss_token_from_UI, \
    extract_UUID_from_client, delete_all_watches
from loguru import logger
from ..blueprint.rss import RSS_FORMAT_TYPES


def set_original_cdata_xml(datastore_path):
    test_return_data = """<rss xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:content="http://purl.org/rss/1.0/modules/content/" xmlns:media="http://search.yahoo.com/mrss/" xmlns:atom="http://www.w3.org/2005/Atom" version="2.0">
    <channel>
    <title>Gizi</title>
    <link>https://test.com</link>
    <atom:link href="https://testsite.com" rel="self" type="application/rss+xml"/>
    <description>
    <![CDATA[ The Future Could Be Here ]]>
    </description>
    <language>en</language>
    <item>
    <title>
    <![CDATA[ <img src="https://testsite.com/hacked.jpg"> Hackers can access your computer ]]>
    </title>
    <link>https://testsite.com/news/12341234234</link>
    <description>
    <![CDATA[ <img class="type:primaryImage" src="https://testsite.com/701c981da04869e.jpg"/><p>The days of Terminator and The Matrix could be closer. But be positive.</p><p><a href="https://testsite.com">Read more link...</a></p> ]]>
    </description>
    <category>cybernetics</category>
    <category>rand corporation</category>
    <pubDate>Tue, 17 Oct 2023 15:10:00 GMT</pubDate>
    <guid isPermaLink="false">1850933241</guid>
    <dc:creator>
    <![CDATA[ Mr Hacker News ]]>
    </dc:creator>
    <media:thumbnail url="https://testsite.com/thumbnail-c224e10d81488e818701c981da04869e.jpg"/>
    </item>

    <item>
        <title>    Some other title    </title>
        <link>https://testsite.com/news/12341234236</link>
        <description>
        Some other description
        </description>
    </item>    
    </channel>
    </rss>
            """

    with open(os.path.join(datastore_path, "endpoint-content.txt"), "w") as f:
        f.write(test_return_data)



def set_html_content(datastore_path, content):
    test_return_data = f"""<html>
       <body>
     Some initial text<br>
     <p>{content}</p>
     <br>
     So let's see what happens.  <br>
     </body>
     </html>
    """

    # Write as UTF-8 encoded bytes
    with open(os.path.join(datastore_path, "endpoint-content.txt"), "wb") as f:
        f.write(test_return_data.encode('utf-8'))


def test_rss_feed_empty(client, live_server, measure_memory_usage, datastore_path):

    rss_token = extract_rss_token_from_UI(client)

    res = client.get(
        url_for("rss.feed", token=rss_token, _external=True),
        follow_redirects=True
    )
    assert res.status_code == 200
    assert b'xml' in res.data

def test_rss_and_token(client, live_server, measure_memory_usage, datastore_path):
    #   #  live_server_setup(live_server) # Setup on conftest per function

    set_original_response(datastore_path=datastore_path)
    rss_token = extract_rss_token_from_UI(client)

    uuid = client.application.config.get('DATASTORE').add_watch(url=url_for('test_random_content_endpoint', _external=True))
    client.post(url_for("ui.form_watch_checknow"), follow_redirects=True)
    wait_for_all_checks(client)
    set_modified_response(datastore_path=datastore_path)
    client.post(url_for("ui.form_watch_checknow"), follow_redirects=True)
    wait_for_all_checks(client)

    # Add our URL to the import page
    res = client.get(
        url_for("rss.feed", token="bad token", _external=True),
        follow_redirects=True
    )

    assert b"Access denied, bad token" in res.data

    res = client.get(
        url_for("rss.feed", token=rss_token, _external=True),
        follow_redirects=True
    )
    assert b"Access denied, bad token" not in res.data
    assert b"Random content" in res.data

    delete_all_watches(client)

def test_basic_cdata_rss_markup(client, live_server, measure_memory_usage, datastore_path):
    

    set_original_cdata_xml(datastore_path)
    # Rarely do endpoints give the right header, usually just text/xml, so we check also for <rss
    # This also triggers the automatic CDATA text parser so the RSS goes back a nice content list
    test_url = url_for('test_endpoint', content_type="text/xml; charset=UTF-8", _external=True)

    # Add our URL to the import page
    uuid = client.application.config.get('DATASTORE').add_watch(url=test_url)
    client.post(url_for("ui.form_watch_checknow"), follow_redirects=True)

    wait_for_all_checks(client)

    res = client.get(
        url_for("ui.ui_preview.preview_page", uuid="first"),
        follow_redirects=True
    )
    assert b'CDATA' not in res.data
    assert b'<![' not in res.data
    assert b'Hackers can access your computer' in res.data
    assert b'The days of Terminator' in res.data
    delete_all_watches(client)

