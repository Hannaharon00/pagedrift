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

def test_check_notification_html_color_format(client, live_server, measure_memory_usage, datastore_path):
    set_original_response(datastore_path=datastore_path)


    notification_url = f'mailto://changedetection@{smtp_test_server}:11025/?to=fff@home.com'

    #####################
    # Set this up for when we remove the notification from the watch, it should fallback with these details
    res = client.post(
        url_for("settings.notifications.apprise"),
        data={"notification_urls": notification_url,
              "notification_title": "fallback-title {{watch_title}} - diff_added_lines_test : '{{ diff_added.splitlines()[0] if diff_added else 'diff added didnt split' }}' " + default_notification_title,
              "notification_body": f"some text\n{default_notification_body}\nMore output test\n{ALL_MARKUP_TOKENS}",
              "notification_format": 'htmlcolor'},
        follow_redirects=True
    )

    assert b"Settings updated." in res.data

    # Add a watch and trigger a HTTP POST
    test_url = url_for('test_endpoint', _external=True)
    res = client.post(
        url_for("ui.ui_views.form_quick_watch_add"),
        data={"url": test_url, "tags": 'nice one'},
        follow_redirects=True
    )

    assert b"Watch added" in res.data

    wait_for_all_checks(client)
    set_longer_modified_response(datastore_path=datastore_path)
    time.sleep(2)

    client.post(url_for("ui.form_watch_checknow"), follow_redirects=True)
    wait_for_all_checks(client)

    time.sleep(3)

    msg_raw = get_last_message_from_smtp_server()
    assert len(msg_raw) >= 1

    # Parse the email properly using Python's email library
    msg = message_from_string(msg_raw, policy=email_policy)
    # Subject/title got marked up
    subject = msg['subject']
    # Subject should always be plaintext and never marked up to anything else
    assert REMOVED_PLACEMARKER_OPEN not in subject
    assert CHANGED_PLACEMARKER_OPEN not in subject
    assert ADDED_PLACEMARKER_OPEN not in subject
    assert 'diff added didnt split' not in subject
    assert '(changed) Which is across' in subject
    assert 'PLACEMARKER' not in subject
    assert 'head title' in subject
    assert "span" not in subject
    assert 'background-color' not in subject


    # The email should have two bodies (multipart/alternative with text/plain and text/html)
    assert msg.is_multipart()
    assert msg.get_content_type() == 'multipart/alternative'

    # Get the parts
    parts = list(msg.iter_parts())
    assert len(parts) == 2

    # First part should be text/plain (the auto-generated plaintext version)
    text_part = parts[0]
    assert text_part.get_content_type() == 'text/plain'
    text_content = text_part.get_content()
    assert 'So let\'s see what happens.\r\n' in text_content  # The plaintext part
    assert '(added)' not in text_content # Because apprise only dumb converts the html to text

    # Second part should be text/html with color styling
    html_part = parts[1]
    assert html_part.get_content_type() == 'text/html'
    html_content = html_part.get_content()
    assert HTML_CHANGED_STYLE or HTML_REMOVED_STYLE in html_content
    assert HTML_ADDED_STYLE in html_content
    assert '&lt;' not in html_content

    assert 'some text<br>' in html_content
    delete_all_watches(client)

def test_check_notification_markdown_format(client, live_server, measure_memory_usage, datastore_path):
    set_original_response(datastore_path=datastore_path)


    notification_url = f'mailto://changedetection@{smtp_test_server}:11025/?to=fff@home.com'

    #####################
    # Set this up for when we remove the notification from the watch, it should fallback with these details
    res = client.post(
        url_for("settings.notifications.apprise"),
        data={"notification_urls": notification_url,
              "notification_title": "fallback-title  diff_added_lines_test : '{{ diff_added.splitlines()[0] if diff_added else 'diff added didnt split' }}' " + default_notification_title,
              "notification_body": "*header*\n\nsome text\n" + default_notification_body,
              "notification_format": 'markdown'},
        follow_redirects=True
    )

    assert b"Settings updated." in res.data

    # Add a watch and trigger a HTTP POST
    test_url = url_for('test_endpoint', _external=True)
    res = client.post(
        url_for("ui.ui_views.form_quick_watch_add"),
        data={"url": test_url, "tags": 'nice one'},
        follow_redirects=True
    )

    assert b"Watch added" in res.data

    wait_for_all_checks(client)
    set_longer_modified_response(datastore_path=datastore_path)
    time.sleep(2)

    client.post(url_for("ui.form_watch_checknow"), follow_redirects=True)
    wait_for_all_checks(client)

    time.sleep(3)

    msg_raw = get_last_message_from_smtp_server()
    assert len(msg_raw) >= 1

    # Parse the email properly using Python's email library
    msg = message_from_string(msg_raw, policy=email_policy)

    # The email should have two bodies (multipart/alternative with text/plain and text/html)
    assert msg.is_multipart()
    assert msg.get_content_type() == 'multipart/alternative'
    subject = msg['subject']
    # Subject should always be plaintext and never marked up to anything else
    assert REMOVED_PLACEMARKER_OPEN not in subject
    assert CHANGED_PLACEMARKER_OPEN not in subject
    assert ADDED_PLACEMARKER_OPEN not in subject
    assert 'diff added didnt split' not in subject
    assert '(changed) Which is across' in subject


    # Get the parts
    parts = list(msg.iter_parts())
    assert len(parts) == 2

    # First part should be text/plain (the auto-generated plaintext version)
    text_part = parts[0]
    assert text_part.get_content_type() == 'text/plain'
    text_content = text_part.get_content()
    # We wont see anything in the "FALLBACK" text but that's OK (no added/strikethrough etc)
    assert 'So let\'s see what happens.\r\n' in text_content  # The plaintext part


    # Second part should be text/html and roughly converted from markdown to HTML
    html_part = parts[1]
    assert html_part.get_content_type() == 'text/html'
    html_content = html_part.get_content()
    assert '<p><em>header</em></p>' in html_content
    assert '<strong>So let\'s see what happens.</strong><br />' in html_content # Additions are <strong> in markdown
    # the '<br />' will come from apprises conversion, not from our code, we would rather use '<br>' correctly
    # the '<br />' is actually a nice way to know if apprise done the conversion.

    delete_all_watches(client)

