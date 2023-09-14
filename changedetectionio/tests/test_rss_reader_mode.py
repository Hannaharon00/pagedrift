#!/usr/bin/env python3

import time
import os

from flask import url_for
from .util import set_original_response, set_modified_response, live_server_setup, wait_for_all_checks, extract_rss_token_from_UI, \
    extract_UUID_from_client, delete_all_watches

def set_xmlns_purl_content(datastore_path, extra=""):
    data=f"""<rss xmlns:content="http://purl.org/rss/1.0/modules/content/" xmlns:dc="https://purl.org/dc/elements/1.1/" xmlns:media="http://search.yahoo.com/mrss/" xmlns:atom="http://www.w3.org/2005/Atom" version="2.0">
<channel>
<atom:link href="https://www.xxxxxxxtechxxxxx.com/feeds.xml" rel="self" type="application/rss+xml"/>
<title>
<![CDATA[ Latest from xxxxxxxtechxxxxx ]]>
</title>
<link>https://www.xxxxx.com</link>
<description>
<![CDATA[ All the latest content from the xxxxxxxtechxxxxx team ]]>
</description>
<lastBuildDate>Wed, 19 Nov 2025 15:00:00 +0000</lastBuildDate>
<language>en</language>
<item>
<title>
<![CDATA[ Sony Xperia 1 VII review: has Sony’s long-standing Xperia family lost what it takes to compete? ]]>
</title>
<dc:content>
<![CDATA[  {{extra}}  a little harder, dc-content. blue often quite tough and purple usually very difficult.</p><p>On the plus side, you don't technically need to solve the final one, as you'll be able to answer that one by a process of elimination. What's more, you can make up to four mistakes, which gives you a little bit of breathing room.</p><p>It's a little more involved than something like Wordle, however, and there are plenty of opportunities for the game to trip you up with tricks. For instance, watch out for homophones and other word games that could disguise the answers.</p><p>It's playable for free via the <a href="https://www.nytimes.com/games/strands" target="_blank">NYT Games site</a> on desktop or mobile.</p></article></section> ]]>
</dc:content>
<link>https://www.xxxxxxx.com/gaming/nyt-connections-today-answers-hints-20-november-2025</link>
<description>
<![CDATA[ Looking for NYT Connections answers and hints? Here's all you need to know to solve today's game, plus my commentary on the puzzles. ]]>
</description>
<guid isPermaLink="false">N2C2T6DztpWdxSdKpSUx89</guid>
<enclosure url="https://cdn.mos.cms.futurecdn.net/RCGfdf3yhQ9W3MHbTRT6yk-1280-80.jpg" type="image/jpeg" length="0"/>
<pubDate>Wed, 19 Nov 2025 15:00:00 +0000</pubDate>
<category>
<![CDATA[ Gaming ]]>
</category>
<dc:creator>
<![CDATA[ Johnny Dee ]]>
</dc:creator>
<media:content type="image/jpeg" url="https://cdn.mos.cms.futurecdn.net/RCGfdf3yhQ9W3MHbTRT6yk-1280-80.jpg">
<media:credit>
<![CDATA[ New York Times ]]>
</media:credit>
<media:text>
<![CDATA[ NYT Connections homescreen on a phone, on a purple background ]]>
</media:text>
<media:title type="plain">
<![CDATA[ NYT Connections homescreen on a phone, on a purple background ]]>
</media:title>
</media:content>
<media:thumbnail url="https://cdn.mos.cms.futurecdn.net/RCGfdf3yhQ9W3MHbTRT6yk-1280-80.jpg"/>
</item>
    </channel>
    </rss>
            """

    with open(os.path.join(datastore_path, "endpoint-content.txt"), "w") as f:
        f.write(data)




def set_original_cdata_xml(datastore_path):
    test_return_data = """<rss xmlns:atom="http://www.w3.org/2005/Atom" version="2.0">
<channel>
<title>Security Bulletins on wetscale</title>
<link>https://wetscale.com/security-bulletins/</link>
<description>Recent security bulletins from wetscale</description>
<lastBuildDate>Fri, 10 Oct 2025 14:58:11 GMT</lastBuildDate>
<docs>https://validator.w3.org/feed/docs/rss2.html</docs>
<generator>wetscale.com</generator>
<language>en-US</language>
<copyright>© 2025 wetscale Inc. All rights reserved.</copyright>
<atom:link href="https://wetscale.com/security-bulletins/index.xml" rel="self" type="application/rss+xml"/>
<item>
<title>TS-2025-005</title>
<link>https://wetscale.com/security-bulletins/#ts-2025-005</link>
<guid>https://wetscale.com/security-bulletins/#ts-2025-005</guid>
<pubDate>Thu, 07 Aug 2025 00:00:00 GMT</pubDate>
<description><p>Wet noodles escape<br><p>they also found themselves outside</p> </description>
</item>


