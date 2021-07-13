"""
RSS/Atom feed processing tools for changedetection.io
"""

from loguru import logger
import re


def cdata_in_document_to_text(html_content: str, render_anchor_tag_content=False) -> str:
    """
    Process CDATA sections in HTML/XML content - inline replacement.

    Args:
        html_content: The HTML/XML content to process
        render_anchor_tag_content: Whether to render anchor tag content

    Returns:
        Processed HTML/XML content with CDATA sections replaced inline
    """
    from xml.sax.saxutils import escape as xml_escape
    from .html_tools import html_to_text

    pattern = '<!\[CDATA\[(\s*(?:.(?<!\]\]>)\s*)*)\]\]>'

    def repl(m):
        text = m.group(1)
        return xml_escape(html_to_text(html_content=text, render_anchor_tag_content=render_anchor_tag_content)).strip()

    return re.sub(pattern, repl, html_content)


