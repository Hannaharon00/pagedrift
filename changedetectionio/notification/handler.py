
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

def apply_discord_markdown_to_body(n_body):
    """
    Discord does not support <del> but it supports non-standard ~~strikethrough~~
    :param n_body:
    :return:
    """
    import re
    # Define the mapping between your placeholders and markdown markers
    replacements = [
        (REMOVED_PLACEMARKER_OPEN, '~~', REMOVED_PLACEMARKER_CLOSED, '~~'),
        (ADDED_PLACEMARKER_OPEN, '**', ADDED_PLACEMARKER_CLOSED, '**'),
        (CHANGED_PLACEMARKER_OPEN, '~~', CHANGED_PLACEMARKER_CLOSED, '~~'),
        (CHANGED_INTO_PLACEMARKER_OPEN, '**', CHANGED_INTO_PLACEMARKER_CLOSED, '**'),
    ]
    # So that the markdown gets added without any whitespace following it which would break it
    for open_tag, open_md, close_tag, close_md in replacements:
        # Regex: match opening tag, optional whitespace, capture the content, optional whitespace, then closing tag
        pattern = re.compile(
            re.escape(open_tag) + r'(\s*)(.*?)?(\s*)' + re.escape(close_tag),
            flags=re.DOTALL
        )
        n_body = pattern.sub(lambda m: f"{m.group(1)}{open_md}{m.group(2)}{close_md}{m.group(3)}", n_body)
    return n_body

def apply_service_tweaks(url, n_body, n_title, requested_output_format):

    from .apprise_plugin.assets import APPRISE_AVATAR_URL
    logger.debug(f"Applying markup in '{requested_output_format}' mode")

    # Re 323 - Limit discord length to their 2000 char limit total or it wont send.
    # Because different notifications may require different pre-processing, run each sequentially :(
    # 2000 bytes minus -
    #     200 bytes for the overhead of the _entire_ json payload, 200 bytes for {tts, wait, content} etc headers
    #     Length of URL - Incase they specify a longer custom avatar_url

    if not n_body or not n_body.strip():
        return url, n_body, n_title

    # Normalize URL scheme to lowercase to prevent case-sensitivity issues
    # e.g., "Discord://webhook" -> "discord://webhook", "TGRAM://bot123" -> "tgram://bot123"
    scheme_separator_pos = url.find('://')
    if scheme_separator_pos > 0:
        url = url[:scheme_separator_pos].lower() + url[scheme_separator_pos:]

    # So if no avatar_url is specified, add one so it can be correctly calculated into the total payload
    parsed = urlparse(url)
    k = '?' if not parsed.query else '&'
    if url and not 'avatar_url' in url \
            and not url.startswith('mail') \
            and not url.startswith('post') \
            and not url.startswith('get') \
            and not url.startswith('delete') \
            and not url.startswith('put'):
        url += k + f"avatar_url={APPRISE_AVATAR_URL}"

    # Replace placemarkers in title first (this was the missing piece causing the bug)
    # Titles are ALWAYS plain text across all notification services (Discord embeds, Slack attachments,
    # email Subject headers, etc.), so we always use 'text' format for title placemarker replacement
    # Looking over apprise library it seems that all plugins only expect plain-text.
    n_title = replace_placemarkers_in_text(n_title, url, 'text')

    if url.startswith('tgram://'):
        # Telegram only supports a limit subset of HTML, remove the '<br>' we place in.
        # re https://github.com/dgtlmoon/changedetection.io/issues/555
        # @todo re-use an existing library we have already imported to strip all non-allowed tags
        n_body = n_body.replace('<br>', '\n')
        n_body = n_body.replace('</br>', '\n')
        n_body = newline_re.sub('\n', n_body)

        # Replace placemarkers for body
        n_body = replace_placemarkers_in_text(n_body, url, requested_output_format)

        # real limit is 4096, but minus some for extra metadata
        payload_max_size = 3600
        body_limit = max(0, payload_max_size - len(n_title))
        n_title = n_title[0:payload_max_size]
        n_body = n_body[0:body_limit]

    elif (url.startswith('discord://') or url.startswith('https://discordapp.com/api/webhooks')
          or url.startswith('https://discord.com/api'))\
            and 'html' in requested_output_format:
        # Discord doesn't render HTML — convert markup to plain text equivalents.
        # &nbsp; is injected upstream to preserve double-spaces for HTML email clients;
        # Discord displays it as the literal string "&nbsp;" so strip it here.
        n_body = n_body.strip().replace('<br>', '\n')
        n_body = n_body.replace('</br>', '\n')
        n_body = n_body.replace('&nbsp;', ' ')
        n_body = newline_re.sub('\n', n_body)

        # Don't replace placeholders or truncate here - let the custom Discord plugin handle it
        # The plugin will use embeds (6000 char limit across all embeds) if placeholders are present,
        # or plain content (2000 char limit) otherwise

        # Only do placeholder replacement if NOT using htmlcolor (which triggers embeds in custom plugin)
        if requested_output_format == 'html':
            # No diff placeholders, use Discord markdown for any other formatting
            # Use Discord markdown: strikethrough for removed, bold for added
            n_body = replace_placemarkers_in_text(n_body, url, requested_output_format)

            # Apply 2000 char limit for plain content
            payload_max_size = 1700
            body_limit = max(0, payload_max_size - len(n_title))
            n_title = n_title[0:payload_max_size]
            n_body = n_body[0:body_limit]
        # else: our custom Discord plugin will convert any placeholders left over into embeds with color bars

    # Is not discord/tgram and they want htmlcolor
    elif requested_output_format == 'htmlcolor':
        n_body = replace_placemarkers_in_text(n_body, url, requested_output_format)
        n_body = newline_re.sub('<br>\n', n_body)
    elif requested_output_format == 'html':
        n_body = replace_placemarkers_in_text(n_body, url, requested_output_format)
        n_body = newline_re.sub('<br>\n', n_body)
    elif requested_output_format == 'markdown':
        # Markdown to HTML - Apprise will convert this to HTML
        n_body = replace_placemarkers_in_text(n_body, url, requested_output_format)

    else: #plaintext etc default
        n_body = replace_placemarkers_in_text(n_body, url, requested_output_format)

    return url, n_body, n_title


