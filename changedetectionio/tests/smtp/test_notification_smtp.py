import time
from flask import url_for
from email import message_from_string
from email.policy import default as email_policy

import logging
import os

# NOTE - RELIES ON mailserver as hostname running, see github build recipes
smtp_test_server = os.getenv('SMTP_TEST_MAILSERVER', 'mailserver')

