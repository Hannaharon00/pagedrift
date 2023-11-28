#!/usr/bin/env python3
import io
import os
import time

from flask import url_for

from .util import live_server_setup, wait_for_all_checks, delete_all_watches


# def test_setup(client, live_server, measure_memory_usage, datastore_path):
   #  live_server_setup(live_server) # Setup on conftest per function

def test_import_distillio(client, live_server, measure_memory_usage, datastore_path):

    distill_data='''
{
    "client": {
        "local": 1
    },
    "data": [
        {
            "name": "Unraid | News",
            "uri": "https://unraid.net/blog",
            "config": "{\\"selections\\":[{\\"frames\\":[{\\"index\\":0,\\"excludes\\":[],\\"includes\\":[{\\"type\\":\\"xpath\\",\\"expr\\":\\"(//div[@id='App']/div[contains(@class,'flex')]/main[contains(@class,'relative')]/section[contains(@class,'relative')]/div[@class='container']/div[contains(@class,'flex')]/div[contains(@class,'w-full')])[1]\\"}]}],\\"dynamic\\":true,\\"delay\\":2}],\\"ignoreEmptyText\\":true,\\"includeStyle\\":false,\\"dataAttr\\":\\"text\\"}",
            "tags": ["nice stuff", "nerd-news"],
            "content_type": 2,
            "state": 40,
            "schedule": "{\\"type\\":\\"INTERVAL\\",\\"params\\":{\\"interval\\":4447}}",
            "ts": "2022-03-27T15:51:15.667Z"
        }
    ]
}		   

'''

    # Give the endpoint time to spin up
    time.sleep(1)
    delete_all_watches(client)
    res = client.post(
        url_for("imports.import_page"),
        data={
            "distill-io": distill_data,
            "urls" : ''
        },
        follow_redirects=True,
    )


    assert b"Unable to read JSON file, was it broken?" not in res.data
    assert b"1 Imported from Distill.io" in res.data

    res = client.get( url_for("ui.ui_edit.edit_page", uuid="first"))

    assert b"https://unraid.net/blog" in res.data
    assert b"Unraid | News" in res.data


    # flask/wtforms should recode this, check we see it
    # wtforms encodes it like id=&#39 ,but html.escape makes it like id=&#x27
    # - so just check it manually :(
    #import json
    #import html
    #d = json.loads(distill_data)
    # embedded_d=json.loads(d['data'][0]['config'])
    # x=html.escape(embedded_d['selections'][0]['frames'][0]['includes'][0]['expr']).encode('utf-8')
    assert b"xpath:(//div[@id=&#39;App&#39;]/div[contains(@class,&#39;flex&#39;)]/main[contains(@class,&#39;relative&#39;)]/section[contains(@class,&#39;relative&#39;)]/div[@class=&#39;container&#39;]/div[contains(@class,&#39;flex&#39;)]/div[contains(@class,&#39;w-full&#39;)])[1]" in res.data

    # did the tags work?
    res = client.get( url_for("watchlist.index"))

    # check tags
    assert b"nice stuff" in res.data
    assert b"nerd-news" in res.data

    delete_all_watches(client)
    # Clear flask alerts
    res = client.get(url_for("watchlist.index"))

