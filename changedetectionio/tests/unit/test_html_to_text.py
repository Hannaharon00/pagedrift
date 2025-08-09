#!/usr/bin/env python3
# coding=utf-8

"""Unit tests for html_tools.html_to_text function."""

class TestHtmlToText(unittest.TestCase):
    """Test html_to_text function for correctness and thread-safety."""

    def test_basic_text_extraction(self):
        """Test basic HTML to text conversion."""
        html = '<html><body><h1>Title</h1><p>Paragraph text.</p></body></html>'
        text = html_to_text(html)

        assert 'Title' in text
        assert 'Paragraph text.' in text
        assert '<' not in text  # HTML tags should be stripped
        assert '>' not in text

    def test_empty_html(self):
        """Test handling of empty HTML."""
        html = '<html><body></body></html>'
        text = html_to_text(html)

        # Should return empty or whitespace only
        assert text.strip() == ''

    def test_nested_elements(self):
        """Test extraction from nested HTML elements."""
        html = '''
        <html>
            <body>
                <div>
                    <h1>Header</h1>
                    <div>
                        <p>First paragraph</p>
                        <p>Second paragraph</p>
                    </div>
                </div>
            </body>
        </html>
        '''
        text = html_to_text(html)

        assert 'Header' in text
        assert 'First paragraph' in text
        assert 'Second paragraph' in text

    def test_anchor_tag_rendering(self):
        """Test anchor tag rendering option."""
        html = '<html><body><a href="https://example.com">Link text</a></body></html>'

        # Without rendering anchors
        text_without = html_to_text(html, render_anchor_tag_content=False)
        assert 'Link text' in text_without
        assert 'https://example.com' not in text_without

        # With rendering anchors
        text_with = html_to_text(html, render_anchor_tag_content=True)
        assert 'Link text' in text_with
        assert 'https://example.com' in text_with or '[Link text]' in text_with

    def test_rss_mode(self):
        """Test RSS mode converts title tags to h1."""
        html = '<item><title>RSS Title</title><description>Content</description></item>'

