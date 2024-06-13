#!/usr/bin/env python3

from flask import url_for
from .util import live_server_setup, wait_for_all_checks


def test_zh_TW(client, live_server, measure_memory_usage, datastore_path):
    import time
    test_url = url_for('test_endpoint', _external=True)

    # Be sure we got a session cookie
    res = client.get(url_for("watchlist.index"), follow_redirects=True)

    res = client.post(
        url_for("set_language", locale="zh_Hant_TW"), # Traditional
        follow_redirects=True
    )
    # HTML follows BCP 47 language tag rules, not underscore-based locale formats.
    assert b'<html lang="zh-Hant-TW"' in res.data
    assert b'Cannot set language without session cookie' not in res.data
    assert '選擇語言'.encode() in res.data

    # Check second set works
    res = client.post(
        url_for("set_language", locale="en_GB"),
        follow_redirects=True
    )
    assert b'Cannot set language without session cookie' not in res.data
    res = client.get(url_for("watchlist.index"), follow_redirects=True)
    assert b"Select Language" in res.data, "Second set of language worked"

    # Check arbitration between zh_Hant_TW<->zh
    res = client.post(
        url_for("set_language", locale="zh"), # Simplified chinese
        follow_redirects=True
    )
    res = client.get(url_for("watchlist.index"), follow_redirects=True)
    assert "选择语言".encode() in res.data, "Simplified chinese worked and it means the flask-babel cache worked"


# timeago library just hasn't been updated to use the more modern locale naming convention, before BCP 47 / RFC 5646.
# The Python timeago library (https://github.com/hustcc/timeago) supports 48 locales but uses different naming conventions than Flask-Babel.
def test_zh_Hant_TW_timeago_integration():
    """Test that zh_Hant_TW mapping works and timeago renders Traditional Chinese correctly"""
    import timeago
    from datetime import datetime, timedelta
    from changedetectionio.languages import get_timeago_locale

    # 1. Test the mapping
    mapped_locale = get_timeago_locale('zh_Hant_TW')
    assert mapped_locale == 'zh_TW', "zh_Hant_TW should map to timeago's zh_TW"
    assert get_timeago_locale('zh_TW') == 'zh_TW', "zh_TW should also map to zh_TW"

    # 2. Test timeago library renders Traditional Chinese with the mapped locale
    now = datetime.now()

    # Test various time periods with Traditional Chinese strings
    result_15s = timeago.format(now - timedelta(seconds=15), now, mapped_locale)
    assert '秒前' in result_15s, f"Expected '秒前' in '{result_15s}'"

    result_5m = timeago.format(now - timedelta(minutes=5), now, mapped_locale)
    assert '分鐘前' in result_5m, f"Expected '分鐘前' in '{result_5m}'"

    result_2h = timeago.format(now - timedelta(hours=2), now, mapped_locale)
    assert '小時前' in result_2h, f"Expected '小時前' in '{result_2h}'"

    result_3d = timeago.format(now - timedelta(days=3), now, mapped_locale)
    assert '天前' in result_3d, f"Expected '天前' in '{result_3d}'"


def test_language_switching(client, live_server, measure_memory_usage, datastore_path, monkeypatch):
    """
    Test that the language switching functionality works correctly.

    1. Switch to Italian using the /set-language endpoint
    2. Verify that Italian text appears on the page
    3. Switch back to English and verify English text appears
    """

    # The Add-Watch page is only served when a browser that can render a live preview is
    # installed (it is the page this test reads translated processor labels off). A plain
    # test container has none - without PLAYWRIGHT_DRIVER_URL html_webdriver is Selenium,
    # which cannot - so pretend one exists rather than assert against a redirect.
    from changedetectionio.blueprint.add_watch_ui import browser_config
    monkeypatch.setattr(browser_config, 'list_visual_browser_choices',
                        lambda datastore: [('html_webdriver', 'WebDriver Chrome/Javascript')])

    # Establish session cookie
    client.get(url_for("add_watch_ui.add_watch_ui_index"), follow_redirects=True)

    # Step 1: Set the language to Italian using the /set-language endpoint
    res = client.post(
        url_for("set_language", locale="it"),
        follow_redirects=True
    )

    assert res.status_code == 200

    # Step 2: Request the index page - should be in Italian
    # The session cookie should be maintained by the test client
    res = client.get(
        url_for("add_watch_ui.add_watch_ui_index"),
        follow_redirects=True
    )

    assert res.status_code == 200

    # Check rendering switched to Italian. <html lang="..."> is set directly
    # from get_locale() so it can't be a translation accident — use it as the
    # canonical "what locale rendered?" signal instead of free-text sentinels
    # like 'Cancel', which can silently match a substring of a translated word
    # in another language (e.g. Italian 'Cancella' contains 'Cancel').
    assert b'<html lang="it"' in res.data, "Expected <html lang=\"it\"> after switching to Italian"
    # One strong content check too — confirms the catalogue was actually loaded
    # and the substitution happened, not just the lang attribute.
    assert b'Modifiche testo/HTML, JSON e PDF' in res.data, "Expected italian from processors.available_processors()"

    # Step 3: Switch back to English
    # NB: use 'en_GB' not 'en' — only the variants are in language_codes; the
    # plain 'en' code is silently rejected by set_language and the locale would
    # remain at 'it', defeating the round-trip assertion below.
    res = client.post(
        url_for("set_language", locale="en_GB"),
        follow_redirects=True
    )

    assert res.status_code == 200

    # Request the index page - should now be in English
    res = client.get(
        url_for("add_watch_ui.add_watch_ui_index"),
        follow_redirects=True
    )

    assert res.status_code == 200

    # Round-tripped back to English — assert via the lang attribute (the only
    # signal that can't be tricked by substring overlap from another locale).
    assert b'<html lang="en-GB"' in res.data, "Expected <html lang=\"en-GB\"> after switching back to English"


def test_invalid_locale(client, live_server, measure_memory_usage, datastore_path):
    """
    Test that setting an invalid locale doesn't break the application.
    The app should ignore invalid locales and continue working.
    """

    # Establish session cookie
    client.get(url_for("watchlist.index"), follow_redirects=True)

    # First set to English. Use the BCP 47 region-tagged form 'en_GB' — the
    # bare 'en' is NOT in language_codes and is silently rejected by
    # set_language, so passing it here would leave the session locale unset
    # and let the (unrelated) Accept-Language fallback decide what renders.
    res = client.post(
        url_for("set_language", locale="en_GB"),
        follow_redirects=True
    )

    assert res.status_code == 200

    # Try to set an invalid locale
    res = client.post(
        url_for("set_language", locale="invalid_locale_xyz"),
        follow_redirects=True
    )

    assert res.status_code == 200

    # Should still be able to access the page (should stay in English since invalid locale was ignored)
    res = client.get(
        url_for("watchlist.index"),
        follow_redirects=True
    )

    assert res.status_code == 200
    # Check via the lang attribute — the only signal that can't be tricked
    # by substring overlap with another locale's translations.
    assert b'<html lang="en-GB"' in res.data, \
        "Should remain in en-GB when an invalid locale is provided"


def test_accept_language_header_zh_tw(client, live_server, measure_memory_usage, datastore_path):
    """
    Test that browsers sending zh-TW in Accept-Language header get Traditional Chinese.
    This tests the locale alias mapping for issue #3779.
    """
    from flask import url_for

    # Clear any session data to simulate a fresh visitor
    with client.session_transaction() as sess:
        sess.clear()

    # Request the index page with zh-TW in Accept-Language header (what browsers send)
    res = client.get(
        url_for("watchlist.index"),
        headers={'Accept-Language': 'zh-TW,zh;q=0.9,en;q=0.8'},
        follow_redirects=True
    )

    assert res.status_code == 200

    # Should get Traditional Chinese content, not Simplified Chinese
    # Traditional: 選擇語言, Simplified: 选择语言
    assert '選擇語言'.encode() in res.data, "Expected Traditional Chinese '選擇語言' (Select Language)"
    assert '选择语言'.encode() not in res.data, "Should not get Simplified Chinese '选择语言'"

    # Check HTML lang attribute uses BCP 47 format
    assert b'<html lang="zh-Hant-TW"' in res.data, "Expected BCP 47 language tag zh-Hant-TW in HTML"

    # Check that the correct flag icon is shown (Taiwan flag for Traditional Chinese)
    assert b'<span class="fi fi-tw fis" id="language-selector-flag">' in res.data, \
        "Expected Taiwan flag 'fi fi-tw' for Traditional Chinese"
    assert b'<span class="fi fi-cn fis" id="language-selector-flag">' not in res.data, \
        "Should not show China flag 'fi fi-cn' for Traditional Chinese"

    # Verify we're getting Traditional Chinese text throughout the page
    res = client.get(
        url_for("settings.settings_page"),
        headers={'Accept-Language': 'zh-TW,zh;q=0.9,en;q=0.8'},
        follow_redirects=True
    )

    assert res.status_code == 200

    # Check Traditional Chinese translations (not English)
    assert "小時".encode() in res.data, "Expected Traditional Chinese '小時' for Hours"
    assert "分鐘".encode() in res.data, "Expected Traditional Chinese '分鐘' for Minutes"
    assert b"Hours" not in res.data or "小時".encode() in res.data, "Should have Traditional Chinese, not English"


