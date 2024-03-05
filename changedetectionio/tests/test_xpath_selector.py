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



