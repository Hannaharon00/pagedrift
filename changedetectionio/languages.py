"""
Language configuration for i18n support
Automatically discovers available languages from translations directory
"""
import os
from pathlib import Path


def get_timeago_locale(flask_locale, short=False):
    """
    Convert Flask-Babel locale codes to timeago library locale codes.

    The Python timeago library (https://github.com/hustcc/timeago) supports 48 locales
    but uses different naming conventions than Flask-Babel. This function maps between them.

    Notable differences:
    - Chinese: Flask uses 'zh', timeago uses 'zh_CN'
    - Portuguese: Flask uses 'pt', timeago uses 'pt_PT' or 'pt_BR'
    - Swedish: Flask uses 'sv', timeago uses 'sv_SE'
    - Norwegian: Flask uses 'no', timeago uses 'nb_NO' or 'nn_NO'
    - Hindi: Flask uses 'hi', timeago uses 'in_HI'
    - Indonesian: Flask uses 'id', timeago uses 'in_ID'
    - Czech: Flask uses 'cs', but timeago doesn't support Czech - fallback to English

    Args:
        flask_locale (str): Flask-Babel locale code (e.g., 'cs', 'zh', 'pt')
        short (bool): Return a compact "1m ago" style locale instead of "1 minute ago".
                      timeago only ships 'en_short'; the other short locales are registered
                      by register_short_timeago_locales() below. Unsupported languages fall
                      back to 'en_short' so short mode is always honoured.

    Returns:
        str: timeago library locale code (e.g., 'en', 'zh_CN', 'pt_PT', 'de_short')
    """
    if short:
        # Short forms are translated through the normal gettext (.po/.mo) workflow rather than
        # timeago's bundled per-language tables; build + register the table for this locale.
        return register_short_timeago_locale(flask_locale)

    locale_map = {
        'zh': 'zh_CN',          # Chinese Simplified
        # timeago library just hasn't been updated to use the more modern locale naming convention, before BCP 47 / RFC 5646.
        'zh_TW': 'zh_TW',       # Chinese Traditional (timeago uses zh_TW)
        'zh_Hant_TW': 'zh_TW',  # Flask-Babel normalizes zh_TW to zh_Hant_TW, map back to timeago's zh_TW
        'pt': 'pt_PT',          # Portuguese (Portugal)
        'pt_BR': 'pt_BR',       # Portuguese (Brasil)
        'sv': 'sv_SE',          # Swedish
        'no': 'nb_NO',          # Norwegian Bokmål
        'hi': 'in_HI',          # Hindi
        'id': 'in_ID',          # Indonesian
        'cs': 'en',             # Czech not supported by timeago, fallback to English
        'ja': 'ja',             # Japanese
        'uk': 'uk',             # Ukrainian
        'en_GB': 'en',          # British English - timeago uses 'en'
        'en_US': 'en',          # American English - timeago uses 'en'
    }
    return locale_map.get(flask_locale, flask_locale)


