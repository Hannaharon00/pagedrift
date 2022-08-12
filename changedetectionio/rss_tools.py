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


# Jinja2 template for formatting RSS/Atom feed entries
# Covers all common feedparser entry fields including namespaced elements
# Outputs HTML that will be converted to text via html_to_text
# @todo - This could be a UI setting in the future
RSS_ENTRY_TEMPLATE = """<article class="rss-item" id="{{ entry.id|replace('"', '')|replace(' ', '-') }}">{%- if entry.title -%}Title: {{ entry.title }}<br>{%- endif -%}
{%- if entry.link -%}<strong>Link:</strong> <a href="{{ entry.link }}">{{ entry.link }}</a><br>
{%- endif -%}
{%- if entry.id -%}
<strong>Guid:</strong> {{ entry.id }}<br>
{%- endif -%}
{%- if entry.published -%}
<strong>PubDate:</strong> {{ entry.published }}<br>
{%- endif -%}
{%- if entry.updated and entry.updated != entry.published -%}
<strong>Updated:</strong> {{ entry.updated }}<br>
{%- endif -%}
{%- if entry.author -%}
<strong>Author:</strong> {{ entry.author }}<br>
{%- elif entry.author_detail and entry.author_detail.name -%}
<strong>Author:</strong> {{ entry.author_detail.name }}
{%- if entry.author_detail.email %} ({{ entry.author_detail.email }}){% endif -%}
<br>
{%- endif -%}
{%- if entry.contributors -%}
<strong>Contributors:</strong> {% for contributor in entry.contributors -%}
{{ contributor.name if contributor.name else contributor }}
{%- if not loop.last %}, {% endif -%}
{%- endfor %}<br>
{%- endif -%}
{%- if entry.publisher -%}
<strong>Publisher:</strong> {{ entry.publisher }}<br>
{%- endif -%}
{%- if entry.rights -%}
<strong>Rights:</strong> {{ entry.rights }}<br>
{%- endif -%}
{%- if entry.license -%}
<strong>License:</strong> {{ entry.license }}<br>
{%- endif -%}
{%- if entry.language -%}
<strong>Language:</strong> {{ entry.language }}<br>
{%- endif -%}
{%- if entry.tags -%}
<strong>Tags:</strong> {% for tag in entry.tags -%}
{{ tag.term if tag.term else tag }}
{%- if not loop.last %}, {% endif -%}
{%- endfor %}<br>
{%- endif -%}
{%- if entry.category -%}
<strong>Category:</strong> {{ entry.category }}<br>
{%- endif -%}
{%- if entry.comments -%}
<strong>Comments:</strong> <a href="{{ entry.comments }}">{{ entry.comments }}</a><br>
{%- endif -%}
{%- if entry.slash_comments -%}
<strong>Comment Count:</strong> {{ entry.slash_comments }}<br>
{%- endif -%}
{%- if entry.enclosures -%}
<strong>Enclosures:</strong><br>
{%- for enclosure in entry.enclosures %}
- <a href="{{ enclosure.href }}">{{ enclosure.href }}</a> ({{ enclosure.type if enclosure.type else 'unknown type' }}
{%- if enclosure.length %}, {{ enclosure.length }} bytes{% endif -%}
)<br>
{%- endfor -%}
{%- endif -%}
{%- if entry.media_content -%}
<strong>Media:</strong><br>
{%- for media in entry.media_content %}
- <a href="{{ media.url }}">{{ media.url }}</a>
{%- if media.type %} ({{ media.type }}){% endif -%}
{%- if media.width and media.height %} {{ media.width }}x{{ media.height }}{% endif -%}
<br>
{%- endfor -%}
{%- endif -%}
{%- if entry.media_thumbnail -%}
<strong>Thumbnail:</strong> <a href="{{ entry.media_thumbnail[0].url if entry.media_thumbnail[0].url else entry.media_thumbnail[0] }}">{{ entry.media_thumbnail[0].url if entry.media_thumbnail[0].url else entry.media_thumbnail[0] }}</a><br>
{%- endif -%}
{%- if entry.media_description -%}
<strong>Media Description:</strong> {{ entry.media_description }}<br>
{%- endif -%}
{%- if entry.itunes_duration -%}
<strong>Duration:</strong> {{ entry.itunes_duration }}<br>
{%- endif -%}
{%- if entry.itunes_author -%}
<strong>Podcast Author:</strong> {{ entry.itunes_author }}<br>
{%- endif -%}
{%- if entry.dc_identifier -%}
<strong>Identifier:</strong> {{ entry.dc_identifier }}<br>
{%- endif -%}
{%- if entry.dc_source -%}
<strong>DC Source:</strong> {{ entry.dc_source }}<br>
{%- endif -%}
{%- if entry.dc_type -%}
<strong>Type:</strong> {{ entry.dc_type }}<br>
{%- endif -%}
{%- if entry.dc_format -%}
<strong>Format:</strong> {{ entry.dc_format }}<br>
{%- endif -%}
{%- if entry.dc_relation -%}
<strong>Related:</strong> {{ entry.dc_relation }}<br>
{%- endif -%}
{%- if entry.dc_coverage -%}
<strong>Coverage:</strong> {{ entry.dc_coverage }}<br>
{%- endif -%}
{%- if entry.source and entry.source.title -%}
<strong>Source:</strong> {{ entry.source.title }}
{%- if entry.source.link %} (<a href="{{ entry.source.link }}">{{ entry.source.link }}</a>){% endif -%}
<br>
{%- endif -%}
{%- if entry.dc_content -%}
<strong>Content:</strong> {{ entry.dc_content | safe }}
{%- elif entry.content and entry.content[0].value -%}
<strong>Content:</strong> {{ entry.content[0].value | safe }}
{%- elif entry.summary -%}
<strong>Summary:</strong> {{ entry.summary | safe }}
{%- endif -%}</article>
"""


