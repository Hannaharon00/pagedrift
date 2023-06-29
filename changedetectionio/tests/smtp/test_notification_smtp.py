import time
from flask import url_for
from email import message_from_string
from email.policy import default as email_policy

from changedetectionio.diff import HTML_REMOVED_STYLE, HTML_ADDED_STYLE, HTML_CHANGED_STYLE, REMOVED_PLACEMARKER_OPEN, \
    CHANGED_PLACEMARKER_OPEN, ADDED_PLACEMARKER_OPEN
from changedetectionio.notification_service import NotificationContextData
from changedetectionio.tests.util import set_original_response, set_modified_response, set_more_modified_response, live_server_setup, \
    wait_for_all_checks, \
    set_longer_modified_response, delete_all_watches

import logging
import os

# NOTE - RELIES ON mailserver as hostname running, see github build recipes
smtp_test_server = os.getenv('SMTP_TEST_MAILSERVER', 'mailserver')

ALL_MARKUP_TOKENS = ''.join(f"TOKEN: '{t}'\n{{{{{t}}}}}\n" for t in NotificationContextData().keys())

def get_last_message_from_smtp_server():
    import requests
    time.sleep(1) # wait for any smtp connects to die off
    port = 11080  # HTTP server port number
    # Make HTTP GET request to Flask server
    response = requests.get(f'http://{smtp_test_server}:{port}/')
    data = response.text
    logging.info("get_last_message_from_smtp_server..")
    logging.info(data)
    return data


# Requires running the test SMTP server

