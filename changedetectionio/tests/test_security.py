import io
import os
import re
import time
import pytest

from flask import url_for
from zipfile import ZipFile, ZIP_DEFLATED

from changedetectionio.tests.util import set_modified_response
from .util import live_server_setup, wait_for_all_checks, delete_all_watches
from .. import strtobool


def set_original_response(datastore_path):
    test_return_data = """<html>
    <head><title>head title</title></head>
    <body>
     Some initial text<br>
     <p>Which is across multiple lines</p>
     <br>
     So let's see what happens.  <br>
     <span class="foobar-detection" style='display:none'></span>
     </body>
     </html>
    """

    with open(os.path.join(datastore_path, "endpoint-content.txt"), "w") as f:
        f.write(test_return_data)
    return None


def test_favicon(client, live_server, measure_memory_usage, datastore_path):
    # Attempt to fetch it, make sure that works
    SVG_BASE64 = 'PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAxIDEiLz4='
    uuid = client.application.config.get('DATASTORE').add_watch(url='https://localhost')
    live_server.app.config['DATASTORE'].data['watching'][uuid].bump_favicon(url="favicon-set-type.svg",
                                                                            favicon_base_64=SVG_BASE64
                                                                            )


    res = client.get(url_for('static_content', group='favicon', filename=uuid))
    assert res.status_code == 200
    assert len(res.data) > 10

    res = client.get(url_for('static_content', group='..', filename='__init__.py'))
    assert res.status_code != 200


    res = client.get(url_for('static_content', group='.', filename='../__init__.py'))
    assert res.status_code != 200

    # Traverse by filename protection
    res = client.get(url_for('static_content', group='js', filename='../styles/styles.css'))
    assert res.status_code != 200

def test_favicon_inline_data_uri(client, live_server, measure_memory_usage, datastore_path):
    """
    bump_favicon() must handle a data URI as the url parameter.
    Previously this logged "Cant work out file extension from 'data:image/png;base64,...'" and bailed.
    The mime_type from the data URI should be used to pick the correct extension.
    """
    import base64
    import os

    # 1x1 transparent PNG (minimal valid PNG bytes)
    PNG_BYTES = (
        b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01'
        b'\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01'
        b'\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82'
    )
    png_b64 = base64.b64encode(PNG_BYTES).decode()
    data_uri = f"data:image/png;base64,{png_b64}"

    uuid = client.application.config.get('DATASTORE').add_watch(url='https://localhost')
    watch = live_server.app.config['DATASTORE'].data['watching'][uuid]

    # Should NOT raise / bail — must save as favicon.png
    watch.bump_favicon(url=data_uri, favicon_base_64=png_b64, mime_type='image/png')

    favicon_fname = watch.get_favicon_filename()
    assert favicon_fname is not None, "Favicon should have been saved"
    assert favicon_fname.endswith('.png'), f"Expected .png extension, got: {favicon_fname}"

    full_path = os.path.join(watch.data_dir, favicon_fname)
    assert os.path.getsize(full_path) == len(PNG_BYTES)

    # Also verify it's served correctly via the static route
    res = client.get(url_for('static_content', group='favicon', filename=uuid))
    assert res.status_code == 200
    assert res.data == PNG_BYTES


def test_favicon_mime_type_overrides_url_extension(client, live_server, measure_memory_usage, datastore_path):
    """
    mime_type parameter takes precedence over the URL path extension.
    A URL ending in .ico but with mime_type='image/png' should save as .png.
    """
    import base64
    import os

    PNG_BYTES = (
        b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01'
        b'\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01'
        b'\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82'
    )
    png_b64 = base64.b64encode(PNG_BYTES).decode()

    uuid = client.application.config.get('DATASTORE').add_watch(url='https://localhost')
    watch = live_server.app.config['DATASTORE'].data['watching'][uuid]

    watch.bump_favicon(url='https://example.com/favicon.ico', favicon_base_64=png_b64, mime_type='image/png')

    favicon_fname = watch.get_favicon_filename()
    assert favicon_fname is not None
    assert favicon_fname.endswith('.png'), f"mime_type should override URL extension, got: {favicon_fname}"


def test_favicon_oversized_rejected(client, live_server, measure_memory_usage, datastore_path):
    """Favicons larger than 1 MB must be silently dropped."""
    import base64
    import os

    oversized = b'\x00' * (1 * 1024 * 1024 + 1)
    oversized_b64 = base64.b64encode(oversized).decode()

    uuid = client.application.config.get('DATASTORE').add_watch(url='https://localhost')
    watch = live_server.app.config['DATASTORE'].data['watching'][uuid]

    result = watch.bump_favicon(url='https://example.com/big.png', favicon_base_64=oversized_b64, mime_type='image/png')

    assert result is None, "bump_favicon should return None for oversized favicon"
    assert watch.get_favicon_filename() is None, "No favicon file should have been written"


def test_bad_access(client, live_server, measure_memory_usage, datastore_path):

    res = client.post(
        url_for("imports.import_page"),
        data={"urls": 'https://localhost'},
        follow_redirects=True
    )

    assert b"1 Imported" in res.data
    wait_for_all_checks(client)

    # Attempt to add a body with a GET method
    res = client.post(
        url_for("ui.ui_edit.edit_page", uuid="first"),
        data={
              "url": 'javascript:alert(document.domain)',
              "tags": "",
              "method": "GET",
              "fetch_backend": "html_requests",
              "body": "",
              "time_between_check_use_default": "y"},
        follow_redirects=True
    )

    assert b'Watch protocol is not permitted or invalid URL format' in res.data

    res = client.post(
        url_for("ui.ui_views.form_quick_watch_add"),
        data={"url": '            javascript:alert(123)', "tags": ''},
        follow_redirects=True
    )

    assert b'Watch protocol is not permitted or invalid URL format' in res.data

    res = client.post(
        url_for("ui.ui_views.form_quick_watch_add"),
        data={"url": '%20%20%20javascript:alert(123)%20%20', "tags": ''},
        follow_redirects=True
    )

    assert b'Watch protocol is not permitted or invalid URL format' in res.data


    res = client.post(
        url_for("ui.ui_views.form_quick_watch_add"),
        data={"url": ' source:javascript:alert(document.domain)', "tags": ''},
        follow_redirects=True
    )

    assert b'Watch protocol is not permitted or invalid URL format' in res.data

    res = client.post(
        url_for("ui.ui_views.form_quick_watch_add"),
        data={"url": 'https://i-wanna-xss-you.com?hereis=<script>alert(1)</script>', "tags": ''},
        follow_redirects=True
    )

    assert b'Watch protocol is not permitted or invalid URL format' in res.data

def _runner_test_various_file_slash(client, file_uri):

    client.post(
        url_for("ui.ui_views.form_quick_watch_add"),
        data={"url": file_uri, "tags": ''},
        follow_redirects=True
    )
    wait_for_all_checks(client)
    res = client.get(url_for("watchlist.index"))

    substrings = [b"URLs with hostname components are not permitted", b"No connection adapters were found for"]


    # If it is enabled at test time
    if strtobool(os.getenv('ALLOW_FILE_URI', 'false')):
        if file_uri.startswith('file:///'):
            # This one should be the full qualified path to the file and should get the contents of this file
            res = client.get(
                url_for("ui.ui_preview.preview_page", uuid="first"),
                follow_redirects=True
            )
            assert b'_runner_test_various_file_slash' in res.data
        else:
            # This will give some error from requests or if it went to chrome, will give some other error :-)
            assert any(s in res.data for s in substrings)

    delete_all_watches(client)

def test_file_slash_access(client, live_server, measure_memory_usage, datastore_path):
    

    # file: is NOT permitted by default, so it will be caught by ALLOW_FILE_URI check

    test_file_path = os.path.abspath(__file__)
    _runner_test_various_file_slash(client, file_uri=f"file://{test_file_path}")
#    _runner_test_various_file_slash(client, file_uri=f"file:/{test_file_path}")
#    _runner_test_various_file_slash(client, file_uri=f"file:{test_file_path}") # CVE-2024-56509

def test_xss(client, live_server, measure_memory_usage, datastore_path):
    
    from changedetectionio.notification import (
        default_notification_format
    )
    # the template helpers were named .jinja which meant they were not having jinja2 autoescape enabled.
    res = client.post(
        url_for("settings.notifications.apprise"),
        data={"notification_urls": '"><img src=x onerror=alert(document.domain)>',
              "notification_title": '"><img src=x onerror=alert(document.domain)>',
              "notification_body": '"><img src=x onerror=alert(document.domain)>',
              "notification_format": default_notification_format},
        follow_redirects=True
    )

    assert b"<img src=x onerror=alert(" not in res.data
    assert b"&lt;img" in res.data

    # Check that even forcing an update directly still doesnt get to the frontend
    set_original_response(datastore_path=datastore_path)
    XSS_HACK = 'javascript:alert(document.domain)'
    uuid = client.application.config.get('DATASTORE').add_watch(url=url_for('test_endpoint', _external=True))
    client.post(url_for("ui.form_watch_checknow"), follow_redirects=True)
    wait_for_all_checks(client)
    set_modified_response(datastore_path=datastore_path)
    client.post(url_for("ui.form_watch_checknow"), follow_redirects=True)
    wait_for_all_checks(client)

    live_server.app.config['DATASTORE'].data['watching'][uuid]['url']=XSS_HACK


    res = client.get(url_for("ui.ui_preview.preview_page", uuid=uuid))
    assert XSS_HACK.encode('utf-8') not in res.data and res.status_code == 200
    client.get(url_for("ui.ui_diff.diff_history_page", uuid=uuid))
    assert XSS_HACK.encode('utf-8') not in res.data and res.status_code == 200
    res = client.get(url_for("watchlist.index"))
    assert XSS_HACK.encode('utf-8') not in res.data and res.status_code == 200


def test_xss_watch_last_error(client, live_server, measure_memory_usage, datastore_path):
    set_original_response(datastore_path=datastore_path)
    # Add our URL to the import page
    res = client.post(
        url_for("imports.import_page"),
        data={"urls": url_for('test_endpoint', _external=True)},
        follow_redirects=True
    )

    assert b"1 Imported" in res.data

    wait_for_all_checks(client)
    res = client.post(
        url_for("ui.ui_edit.edit_page", uuid="first"),
        data={
            "include_filters": '<a href="https://foobar"></a><script>alert(123);</script>',
            "url": url_for('test_endpoint', _external=True),
            'fetch_backend': "html_requests",
            "time_between_check_use_default": "y"
        },
        follow_redirects=True
    )
    assert b"Updated watch." in res.data
    wait_for_all_checks(client)
    res = client.get(url_for("watchlist.index"))

    assert b"<script>alert(123);</script>" not in res.data  # this text should be there
    assert b'&lt;a href=&#34;https://foobar&#34;&gt;&lt;/a&gt;&lt;script&gt;alert(123);&lt;/script&gt;' in res.data
    assert b"https://foobar" in res.data # this text should be there


def test_login_redirect_safe_urls(client, live_server, measure_memory_usage, datastore_path):
    """
    Test that safe redirect URLs work correctly in login flow.
    This verifies the fix for open redirect vulnerabilities while maintaining
    legitimate redirect functionality for both authenticated and unauthenticated users.
    """

    # Test 1: Accessing /login?redirect=/settings when not logged in
    # Should show the login form with redirect parameter preserved
    res = client.get(
        url_for("login", redirect="/settings"),
        follow_redirects=False
    )
    # Should show login form
    assert res.status_code == 200
    # Check that the redirect is preserved in the hidden form field
    assert b'name="redirect"' in res.data

    # Test 2: Valid internal redirect with query parameters
    res = client.get(
        url_for("login", redirect="/settings?tab=notifications"),
        follow_redirects=False
    )
    assert res.status_code == 200
    # Check that the redirect is preserved
    assert b'value="/settings?tab=notifications"' in res.data

    # Test 3: Malicious external URL should be blocked and default to watchlist
    res = client.get(
        url_for("login", redirect="https://evil.com/phishing"),
        follow_redirects=False
    )
    # Should show login form
    assert res.status_code == 200
    # The redirect parameter in the form should NOT contain the evil URL
    # Check the actual input value, not just anywhere in the page
    assert b'value="https://evil.com' not in res.data
    assert b'value="/evil.com' not in res.data
    assert b'name="redirect"' in res.data

    # Test 4: Double-slash attack should be blocked
    res = client.get(
        url_for("login", redirect="//evil.com"),
        follow_redirects=False
    )
    assert res.status_code == 200
    # Should not have the malicious URL in the redirect input value
    assert b'value="//evil.com"' not in res.data

    # Test 5: Protocol handler exploit should be blocked
    res = client.get(
        url_for("login", redirect="javascript:alert(document.domain)"),
        follow_redirects=False
    )
    assert res.status_code == 200
    # Should not have javascript: in the redirect input value
    assert b'value="javascript:' not in res.data

    # Test 6: At-symbol obfuscation attack should be blocked
    res = client.get(
        url_for("login", redirect="//@evil.com"),
        follow_redirects=False
    )
    assert res.status_code == 200
    # Should not have the malicious URL in the redirect input value
    assert b'value="//@evil.com"' not in res.data

    # Test 7: Multiple slashes attack should be blocked
    res = client.get(
        url_for("login", redirect="////evil.com"),
        follow_redirects=False
    )
    assert res.status_code == 200
    # Should not have the malicious URL in the redirect input value
    assert b'value="////evil.com"' not in res.data


def test_login_redirect_with_password(client, live_server, measure_memory_usage, datastore_path):
    """
    Test that redirect functionality works correctly when a password is set.
    This ensures that notifications can always link to /login and users will
    be redirected to the correct page after authentication.
    """

    # Set a password
    from changedetectionio import store
    import base64
    import hashlib

    # Generate a test password
    password = "test123"
    salt = os.urandom(32)
    key = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100000)
    salted_pass = base64.b64encode(salt + key).decode('ascii')

    # Set the password in the datastore
    client.application.config['DATASTORE'].data['settings']['application']['password'] = salted_pass

    # Test 1: Try to access /login?redirect=/settings without being logged in
    # Should show login form and preserve redirect parameter
    res = client.get(
        url_for("login", redirect="/settings"),
        follow_redirects=False
    )
    assert res.status_code == 200
    assert b"Password" in res.data
    # Check that redirect parameter is preserved in the form
    assert b'name="redirect"' in res.data
    assert b'value="/settings"' in res.data

    # Test 2: Submit correct password with redirect parameter
    # Should redirect to /settings after successful login
    res = client.post(
        url_for("login"),
        data={"password": password, "redirect": "/settings"},
        follow_redirects=True
    )
    assert res.status_code == 200
    # Should be on settings page
    assert b"Settings" in res.data or b"settings" in res.data

    # Test 3: Now that we're logged in, accessing /login?redirect=/settings
    # should redirect immediately without showing login form
    res = client.get(
        url_for("login", redirect="/"),
        follow_redirects=True
    )
    assert res.status_code == 200
    assert b"Already logged in" in res.data

    # Test 4: Malicious redirect should be blocked even with correct password
    res = client.post(
        url_for("login"),
        data={"password": password, "redirect": "https://evil.com"},
        follow_redirects=True
    )
    # Should redirect to watchlist index instead of evil.com
    assert b"evil.com" not in res.data

    # Logout for cleanup
    client.post(url_for("logout"))

    # Test 5: Incorrect password with redirect should stay on login page
    res = client.post(
        url_for("login"),
        data={"password": "wrongpassword", "redirect": "/settings"},
        follow_redirects=True
    )
    assert res.status_code == 200
    assert b"Incorrect password" in res.data or b"password" in res.data

    # Clear the password
    del client.application.config['DATASTORE'].data['settings']['application']['password']


def test_login_redirect_from_protected_page(client, live_server, measure_memory_usage, datastore_path):
    """
    Test the complete redirect flow: accessing a protected page while logged out
    should redirect to login with the page URL, then redirect back after login.
    This is the real-world scenario where users try to access /edit/uuid or /settings
    and need to login first.
    """
    import base64
    import hashlib

    # Add a watch first
    set_original_response(datastore_path=datastore_path)
    res = client.post(
        url_for("imports.import_page"),
        data={"urls": url_for('test_endpoint', _external=True)},
        follow_redirects=True
    )
    assert b"1 Imported" in res.data
    wait_for_all_checks(client)

    # Set a password
    password = "test123"
    salt = os.urandom(32)
    key = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100000)
    salted_pass = base64.b64encode(salt + key).decode('ascii')
    client.application.config['DATASTORE'].data['settings']['application']['password'] = salted_pass

    # Logout to ensure we're not authenticated
    client.post(url_for("logout"))

    # Try to access a protected page (edit page for first watch)
    res = client.get(
        url_for("ui.ui_edit.edit_page", uuid="first"),
        follow_redirects=False
    )

    # Should redirect to login with the edit page as redirect parameter
    assert res.status_code in [302, 303]
    assert '/login' in res.location
    assert 'redirect=' in res.location or 'redirect=%2F' in res.location

    # Follow the redirect to login page
    res = client.get(res.location, follow_redirects=False)
    assert res.status_code == 200
    assert b'Password' in res.data

    # The redirect parameter should be preserved in the login form
    # It should contain the edit page URL
    assert b'name="redirect"' in res.data
    assert b'value="/edit/first"' in res.data or b'value="%2Fedit%2Ffirst"' in res.data

    # Now login with correct password and the redirect parameter
    res = client.post(
        url_for("login"),
        data={"password": password, "redirect": "/edit/first"},
        follow_redirects=False
    )

    # Should redirect to the edit page
    assert res.status_code in [302, 303]
    assert '/edit/first' in res.location

    # Follow the redirect to verify we're on the edit page
    res = client.get(res.location, follow_redirects=True)
    assert res.status_code == 200
    # Should see edit page content
    assert b'Edit' in res.data or b'Watching' in res.data

    # Cleanup
    client.post(url_for("logout"))
    del client.application.config['DATASTORE'].data['settings']['application']['password']


def test_logout_with_redirect(client, live_server, measure_memory_usage, datastore_path):
    """
    Test that logout preserves the current page URL, so after re-login
    the user returns to where they were before logging out.
    Example: User is on /edit/uuid, clicks logout, then logs back in and
    returns to /edit/uuid.
    """
    import base64
    import hashlib

    # Set a password and login
    password = "test123"
    salt = os.urandom(32)
    key = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100000)
    salted_pass = base64.b64encode(salt + key).decode('ascii')
    client.application.config['DATASTORE'].data['settings']['application']['password'] = salted_pass

    # Login
    res = client.post(
        url_for("login"),
        data={"password": password},
        follow_redirects=True
    )
    assert res.status_code == 200

    # Now logout with a redirect parameter (simulating logout from /settings)
    res = client.post(
        url_for("logout", redirect="/settings"),
        follow_redirects=False
    )

    # Should redirect to login with the redirect parameter
    assert res.status_code in [302, 303]
    assert '/login' in res.location
    assert 'redirect=' in res.location or 'redirect=%2F' in res.location

    # Follow the redirect to login page
    res = client.get(res.location, follow_redirects=False)
    assert res.status_code == 200
    assert b'Password' in res.data
    # The redirect parameter should be preserved
    assert b'value="/settings"' in res.data or b'value="%2Fsettings"' in res.data

    # Login again with the redirect
    res = client.post(
        url_for("login"),
        data={"password": password, "redirect": "/settings"},
        follow_redirects=False
    )

    # Should redirect back to settings
    assert res.status_code in [302, 303]
    assert '/settings' in res.location or 'settings' in res.location

    # Cleanup
    del client.application.config['DATASTORE'].data['settings']['application']['password']


def test_ghsa_8757_69j2_hx56_backup_restore_history_path_traversal(client, live_server, measure_memory_usage, datastore_path):
    """
    GHSA-8757-69j2-hx56: Crafted backup ZIP with absolute path in history.txt must not
    expose arbitrary local files through the preview or API endpoints.

    Attack chain:
    1. Attacker creates a backup ZIP with a malicious history.txt containing an absolute
       path (e.g. /etc/passwd) as a snapshot reference.
    2. Victim restores the backup.
    3. Attacker reads the targeted file via the Preview page.

    The fix ensures history entries are always resolved to os.path.basename() joined with
    the watch's data_dir, and rejects entries that escape that directory.
    """
    set_original_response(datastore_path=datastore_path)

    datastore = live_server.app.config['DATASTORE']
    watch_url = url_for('test_endpoint', _external=True)

    # Create a real watch and trigger a check so we have a valid backup structure
    uuid = datastore.add_watch(url=watch_url)
    client.post(url_for("ui.form_watch_checknow"), follow_redirects=True)
    wait_for_all_checks(client)

    # Download a legitimate backup to use as a template
    client.post(url_for("backups.request_backup"), follow_redirects=True)
    time.sleep(4)
    res = client.get(url_for("backups.download_backup", filename="latest"), follow_redirects=True)
    assert res.content_type == "application/zip"

    # Tamper: replace the history.txt inside the backup with a malicious entry
    # that points at /etc/passwd (a file that exists on any Unix system)
    original_zip = ZipFile(io.BytesIO(res.data))
    tampered_buf = io.BytesIO()
    with ZipFile(tampered_buf, 'w', ZIP_DEFLATED) as new_zip:
        for item in original_zip.infolist():
            data = original_zip.read(item.filename)
            # Replace the watch's history.txt with a malicious absolute path entry
            if item.filename.endswith('history.txt') and uuid in item.filename:
                data = b'1776969105,/etc/passwd\n'
            new_zip.writestr(item, data)

    tampered_buf.seek(0)
    tampered_zip_data = tampered_buf.read()

    # Restore the tampered backup
    res = client.post(
        url_for("backups.restore.backups_restore_start"),
        data={
            'zip_file': (io.BytesIO(tampered_zip_data), 'malicious_backup.zip'),
            'include_watches': 'y',
            'include_watches_replace_existing': 'y',
        },
        content_type='multipart/form-data',
        follow_redirects=True
    )
    assert res.status_code == 200
    time.sleep(2)

    # Now try to read the /etc/passwd contents via the Preview page using the injected timestamp
    res = client.get(
        url_for("ui.ui_preview.preview_page", uuid=uuid) + "?timestamp=1776969105",
        follow_redirects=True
    )

    # The preview must NOT contain typical /etc/passwd content
    assert b'root:' not in res.data, \
        "Preview must not expose /etc/passwd — history path traversal not blocked"
    assert b'/bin/' not in res.data or b'No history' in res.data or res.status_code in [404, 500], \
        "Preview must not serve arbitrary local files from a malicious history entry"
