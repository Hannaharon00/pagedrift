#!/usr/bin/env python3
import os
import time

out_of_stock_props = [
    # out of stock AND contains multiples
    '<script type="application/ld+json">{"@context":"http://schema.org","@type":"WebSite","url":"https://www.medimops.de/","potentialAction":{"@type":"SearchAction","target":"https://www.medimops.de/produkte-C0/?fcIsSearch=1&searchparam={searchparam}","query-input":"required name=searchparam"}}</script><script type="application/ld+json">{"@context":"http://schema.org","@type":"Product","name":"Horsetrader: Robert Sangster and the Rise and Fall of the Sport of Kings","image":"https://images2.medimops.eu/product/43a982/M00002551322-large.jpg","productID":"isbn:9780002551328","gtin13":"9780002551328","category":"Livres en langue étrangère","offers":{"@type":"Offer","priceCurrency":"EUR","price":$$PRICE$$,"itemCondition":"UsedCondition","availability":"OutOfStock"},"brand":{"@type":"Thing","name":"Patrick Robinson","url":"https://www.momox-shop.fr/,patrick-robinson/"}}</script>'
]

def set_original_response(datastore_path, props_markup='', price="121.95"):
    props_markup=props_markup.replace('$$PRICE$$', price)
    test_return_data = f"""<html>
       <body>
     Some initial text<br>
     <p>Which is across multiple lines</p>
     <br>
     So let's see what happens.  <br>
     <div>price: ${price}</div>
     {props_markup}
     </body>
     </html>
    """

    with open(os.path.join(datastore_path, "endpoint-content.txt"), "w") as f:
        f.write(test_return_data)
    time.sleep(1)
    return None

def test_restock_itemprop_basic(client, live_server, measure_memory_usage, datastore_path):

    test_url = url_for('test_endpoint', _external=True)

    # By default it should enable ('in_stock_processing') == 'all_changes'

    for p in instock_props:
        set_original_response(props_markup=p, datastore_path=datastore_path)
        client.post(
            url_for("ui.ui_views.form_quick_watch_add"),
            data={"url": test_url, "tags": 'restock tests', 'processor': 'restock_diff'},
            follow_redirects=True
        )
        wait_for_all_checks(client)
        res = client.get(url_for("watchlist.index"))
        assert b'more than one price detected' not in res.data
        assert b'has-restock-info' in res.data
        assert b' in-stock' in res.data
        assert b' not-in-stock' not in res.data
        delete_all_watches(client)


    for p in out_of_stock_props:
        set_original_response(props_markup=p, datastore_path=datastore_path)
        client.post(
            url_for("ui.ui_views.form_quick_watch_add"),
            data={"url": test_url, "tags": '', 'processor': 'restock_diff'},
            follow_redirects=True
        )
        wait_for_all_checks(client)
        res = client.get(url_for("watchlist.index"))

        assert b'has-restock-info not-in-stock' in res.data

        delete_all_watches(client)

