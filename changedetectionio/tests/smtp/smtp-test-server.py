#!/usr/bin/env python3
import threading
import time
from aiosmtpd.controller import Controller
from flask import Flask, Response
from email import message_from_bytes
from email.policy import default

# Accept a SMTP message and offer a way to retrieve the last message via HTTP

last_received_message = b"SMTP Test Server - Nothing received yet."
active_smtp_connections = 0
smtp_lock = threading.Lock()


class CustomSMTPHandler:
    async def handle_DATA(self, server, session, envelope):
        global last_received_message, active_smtp_connections

        with smtp_lock:
            active_smtp_connections += 1

        try:
            last_received_message = envelope.content
            print('Receiving message from:', session.peer)
            print('Message addressed from:', envelope.mail_from)
            print('Message addressed to  :', envelope.rcpt_tos)
            print('Message length        :', len(envelope.content))
            print('*******************************')
            print(envelope.content.decode('utf8'))
            print('*******************************')

            # Parse the email message
            msg = message_from_bytes(envelope.content, policy=default)
            with open('/tmp/last.eml', 'wb') as f:
                f.write(envelope.content)

            # Write parts to files based on content type
            if msg.is_multipart():
                for part in msg.walk():
                    content_type = part.get_content_type()
                    payload = part.get_payload(decode=True)

                    if payload:
                        if content_type == 'text/plain':
                            with open('/tmp/last.txt', 'wb') as f:
                                f.write(payload)
                            print(f'Written text/plain part to /tmp/last.txt')
                        elif content_type == 'text/html':
                            with open('/tmp/last.html', 'wb') as f:
                                f.write(payload)
                            print(f'Written text/html part to /tmp/last.html')
            else:
                # Single part message
                content_type = msg.get_content_type()
                payload = msg.get_payload(decode=True)

                if payload:
                    if content_type == 'text/plain' or content_type.startswith('text/'):
                        with open('/tmp/last.txt', 'wb') as f:
                            f.write(payload)
                        print(f'Written single part message to /tmp/last.txt')

            return '250 Message accepted for delivery'
        finally:
            with smtp_lock:
                active_smtp_connections -= 1


