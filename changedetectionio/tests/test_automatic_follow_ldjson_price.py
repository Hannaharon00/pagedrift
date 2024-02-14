#!/usr/bin/env python3

import time
from flask import url_for
from .util import live_server_setup, extract_UUID_from_client, wait_for_all_checks, delete_all_watches
import os


def set_response_with_ldjson(datastore_path):
    test_return_data = """<html>
       <body>
     Some initial text<br>
     <p>Which is across multiple lines</p>
     <br>
     So let's see what happens.  <br>
     <div class="sametext">Some text thats the same</div>
     <div class="changetext">Some text that will change</div>
     <script type="application/ld+json">
        {
           "@context":"https://schema.org/",
           "@type":"Product",
           "@id":"https://www.some-virtual-phone-shop.com/celular-iphone-14/p",
           "name":"Celular Iphone 14 Pro Max 256Gb E Sim A16 Bionic",
           "brand":{
              "@type":"Brand",
              "name":"APPLE"
           },
           "image":"https://www.some-virtual-phone-shop.com/15509426/image.jpg",
           "description":"You dont need it",
           "mpn":"111111",
           "sku":"22222",
           "Offers":{
              "@type":"AggregateOffer",
              "lowPrice":8097000,
              "highPrice":8099900,
              "priceCurrency":"COP",
              "offers":[
                 {
                    "@type":"Offer",
                    "price":8097000,
                    "priceCurrency":"COP",
                    "availability":"http://schema.org/InStock",
                    "sku":"102375961",
                    "itemCondition":"http://schema.org/NewCondition",
                    "seller":{
                       "@type":"Organization",
                       "name":"ajax"
                    }
                 }
              ],
              "offerCount":1
           }
        }
       </script>
     </body>
     </html>
"""

    with open(os.path.join(datastore_path, "endpoint-content.txt"), "w") as f:
        f.write(test_return_data)
    return None

