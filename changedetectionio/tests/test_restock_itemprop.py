#!/usr/bin/env python3
import os
import time

from flask import url_for
from .util import live_server_setup, wait_for_all_checks, wait_for_notification_endpoint_output, extract_UUID_from_client, delete_all_watches
from ..notification import default_notification_format

instock_props = [
    # LD+JSON with non-standard list of 'type' https://github.com/dgtlmoon/changedetection.io/issues/1833
    '<script type=\'application/ld+json\'>{"@context": "http://schema.org","@type": ["Product", "SubType"],"name": "My test product","description":"","Offers": {    "@type": "Offer",    "offeredBy": {        "@type": "Organization",        "name":"Person",       "telephone":"+1 999 999 999"    },    "price": $$PRICE$$,    "priceCurrency": "EUR",    "url": "/some/url", "availability": "http://schema.org/InStock"}        }</script>',
    # LD JSON
    '<script id="product-jsonld" type="application/ld+json">{"@context":"https://schema.org","@type":"Product","brand":{"@type":"Brand","name":"Ubiquiti"},"name":"UniFi Express","sku":"UX","description":"Impressively compact UniFi Cloud Gateway and WiFi 6 access point that runs UniFi Network. Powers an entire network or simply meshes as an access point.","url":"https://store.ui.com/us/en/products/ux","image":{"@type":"ImageObject","url":"https://cdn.ecomm.ui.com/products/4ed25b4c-db92-4b98-bbf3-b0989f007c0e/123417a2-895e-49c7-ba04-b6cd8f6acc03.png","width":"1500","height":"1500"},"offers":{"@type":"Offer","availability":"https://schema.org/InStock","priceSpecification":{"@type":"PriceSpecification","price":$$PRICE$$,"priceCurrency":"USD","valueAddedTaxIncluded":false}}}</script>',
    '<script id="product-schema" type="application/ld+json">{"@context": "https://schema.org","@type": "Product","itemCondition": "https://schema.org/NewCondition","image": "//1.com/hmgo","name": "Polo MuscleFit","color": "Beige","description": "Polo","sku": "0957102010","brand": {"@type": "Brand","name": "H&M"},"category": {"@type": "Thing","name": "Polo"},"offers": [{"@type": "Offer","url": "https:/www2.xxxxxx.com/fr_fr/productpage.0957102010.html","priceCurrency": "EUR","price": $$PRICE$$,"availability": "http://schema.org/InStock","seller": {  "@type": "Organization", "name": "H&amp;M"}}]}</script>'
    # Microdata
    '<div itemscope itemtype="https://schema.org/Product"><h1 itemprop="name">Example Product</h1><p itemprop="description">This is a sample product description.</p><div itemprop="offers" itemscope itemtype="https://schema.org/Offer"><p>Price: <span itemprop="price">$$$PRICE$$</span></p><link itemprop="availability" href="https://schema.org/InStock" /></div></div>'
]

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

def test_restock_itemprop_minmax(client, live_server, measure_memory_usage, datastore_path):
    
    extras = {
        "processor_config_restock_diff-follow_price_changes": "y",
        "processor_config_restock_diff-price_change_min": 900.0,
        "processor_config_restock_diff-price_change_max": 1100.10
    }
    _run_test_minmax_limit(client, extra_watch_edit_form=extras, datastore_path=datastore_path)

