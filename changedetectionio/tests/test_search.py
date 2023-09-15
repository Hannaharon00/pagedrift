from flask import url_for
from .util import set_original_response, set_modified_response, live_server_setup
import time



def test_basic_search(client, live_server, measure_memory_usage, datastore_path):
    

    urls = ['https://localhost:12300?first-result=1',
            'https://localhost:5000?second-result=1'
            ]
    res = client.post(
        url_for("imports.import_page"),
        data={"urls": "\r\n".join(urls)},
        follow_redirects=True
    )

    assert b"2 Imported" in res.data

    # By URL
    res = client.get(url_for("watchlist.index") + "?q=first-res")
    assert urls[0].encode('utf-8') in res.data
    assert urls[1].encode('utf-8') not in res.data

    # By Title

    res = client.post(
        url_for("ui.ui_edit.edit_page", uuid="first"),
        data={"title": "xxx-title", "url": urls[0], "tags": "", "headers": "", 'fetch_backend': "html_requests", "time_between_check_use_default": "y"},
        follow_redirects=True
    )
    assert b"Updated watch." in res.data

    res = client.get(url_for("watchlist.index") + "?q=xxx-title")
    assert urls[0].encode('utf-8') in res.data
    assert urls[1].encode('utf-8') not in res.data


