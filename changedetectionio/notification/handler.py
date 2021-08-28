
import time
import re
from loguru import logger
from urllib.parse import urlparse
from .email_helpers import as_monospaced_html_email
from ..diff import HTML_REMOVED_STYLE, REMOVED_PLACEMARKER_OPEN, REMOVED_PLACEMARKER_CLOSED, ADDED_PLACEMARKER_OPEN, HTML_ADDED_STYLE, \
    ADDED_PLACEMARKER_CLOSED, CHANGED_INTO_PLACEMARKER_OPEN, CHANGED_INTO_PLACEMARKER_CLOSED, CHANGED_PLACEMARKER_OPEN, \
    CHANGED_PLACEMARKER_CLOSED, HTML_CHANGED_STYLE, HTML_CHANGED_INTO_STYLE
import re

from ..notification_service import NotificationContextData, add_rendered_diff_to_notification_vars

newline_re = re.compile(r'\r\n|\r|\n')

def markup_text_links_to_html(body):
    """
    Convert plaintext to HTML with clickable links.
    Uses Jinja2's escape and Markup for XSS safety.
    """
    from linkify_it import LinkifyIt
    from markupsafe import Markup, escape

    linkify = LinkifyIt()

    # Match URLs in the ORIGINAL text (before escaping)
    matches = linkify.match(body)

    if not matches:
        # No URLs, just escape everything
        return Markup(escape(body))

    result = []
    last_index = 0

    # Process each URL match
    for match in matches:
        # Add escaped text before the URL
        if match.index > last_index:
            text_part = body[last_index:match.index]
            result.append(escape(text_part))

        # Add the link with escaped URL (both in href and display)
        url = match.url
        result.append(Markup(f'<a href="{escape(url)}">{escape(url)}</a>'))

        last_index = match.last_index

    # Add remaining escaped text
    if last_index < len(body):
        result.append(escape(body[last_index:]))

    # Join all parts
    return str(Markup(''.join(str(part) for part in result)))

def notification_format_align_with_apprise(n_format : str):
    """
    Correctly align changedetection's formats with apprise's formats
    Probably these are the same - but good to be sure.
    These set the expected OUTPUT format type
    :param n_format:
    :return:
    """
    from apprise import NotifyFormat

    if not n_format:
        return NotifyFormat.TEXT.value

    if n_format.startswith('html'):
        # Apprise only knows 'html' not 'htmlcolor' etc, which shouldnt matter here
        n_format = NotifyFormat.HTML.value
    elif n_format.startswith('markdown'):
        # probably the same but just to be safe
        n_format = NotifyFormat.MARKDOWN.value
    elif n_format.startswith('text'):
        # probably the same but just to be safe
        n_format = NotifyFormat.TEXT.value
    else:
        n_format = NotifyFormat.TEXT.value

    return n_format


def apply_html_color_to_body(n_body: str):
    # https://github.com/dgtlmoon/changedetection.io/issues/821#issuecomment-1241837050
    n_body = n_body.replace(REMOVED_PLACEMARKER_OPEN,
                            f'<span style="{HTML_REMOVED_STYLE}" role="deletion" aria-label="Removed text" title="Removed text">')
    n_body = n_body.replace(REMOVED_PLACEMARKER_CLOSED, f'</span>')
    n_body = n_body.replace(ADDED_PLACEMARKER_OPEN,
                            f'<span style="{HTML_ADDED_STYLE}" role="insertion" aria-label="Added text" title="Added text">')
    n_body = n_body.replace(ADDED_PLACEMARKER_CLOSED, f'</span>')
    # Handle changed/replaced lines (old → new)
    n_body = n_body.replace(CHANGED_PLACEMARKER_OPEN,
                            f'<span style="{HTML_CHANGED_STYLE}" role="note" aria-label="Changed text" title="Changed text">')
    n_body = n_body.replace(CHANGED_PLACEMARKER_CLOSED, f'</span>')
    n_body = n_body.replace(CHANGED_INTO_PLACEMARKER_OPEN,
                            f'<span style="{HTML_CHANGED_INTO_STYLE}" role="note" aria-label="Changed into" title="Changed into">')
    n_body = n_body.replace(CHANGED_INTO_PLACEMARKER_CLOSED, f'</span>')
    return n_body

