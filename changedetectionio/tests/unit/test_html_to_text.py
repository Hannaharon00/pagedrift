#!/usr/bin/env python3
# coding=utf-8

"""Unit tests for html_tools.html_to_text function."""

import hashlib
import threading
import unittest
from queue import Queue

from changedetectionio.html_tools import html_to_text


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

        # is_rss=True should convert <title> to <h1>
        text = html_to_text(html, is_rss=True)

        assert 'RSS Title' in text
        assert 'Content' in text

    def test_special_characters(self):
        """Test handling of special characters and entities."""
        html = '<html><body><p>Test &amp; &lt;special&gt; characters</p></body></html>'
        text = html_to_text(html)

        # Entities should be decoded
        assert 'Test &' in text or 'Test &amp;' in text
        assert 'special' in text

    def test_whitespace_handling(self):
        """Test that whitespace is properly handled."""
        html = '<html><body><p>Line 1</p><p>Line 2</p></body></html>'
        text = html_to_text(html)

        # Should have some separation between lines
        assert 'Line 1' in text
        assert 'Line 2' in text
        assert text.count('\n') >= 1  # At least one newline

    def test_deterministic_output(self):
        """Test that the same HTML always produces the same text."""
        html = '<html><body><h1>Test</h1><p>Content here</p></body></html>'

        # Extract text multiple times
        results = [html_to_text(html) for _ in range(10)]

        # All results should be identical
        assert len(set(results)) == 1, "html_to_text should be deterministic"

    def test_thread_safety_determinism(self):
        """
        Test that html_to_text produces deterministic output under high concurrency.

        This verifies that lxml's default parser (used by inscriptis.get_text)
        is thread-safe and produces consistent results when called from multiple
        threads simultaneously.
        """
        html = '''
        <html>
            <head><title>Test Page</title></head>
            <body>
                <h1>Main Heading</h1>
                <div class="content">
                    <p>First paragraph with <b>bold text</b>.</p>
                    <p>Second paragraph with <i>italic text</i>.</p>
                    <ul>
                        <li>Item 1</li>
                        <li>Item 2</li>
                        <li>Item 3</li>
                    </ul>
                </div>
            </body>
        </html>
        '''

        results_queue = Queue()

        def worker(worker_id, iterations=10):
            """Worker that converts HTML to text multiple times."""
            for i in range(iterations):
                text = html_to_text(html)
                md5 = hashlib.md5(text.encode('utf-8')).hexdigest()
                results_queue.put((worker_id, i, md5))

        # Launch many threads simultaneously
        num_threads = 50
        threads = []

        for i in range(num_threads):
            t = threading.Thread(target=worker, args=(i,))
            threads.append(t)
            t.start()

        # Wait for all threads to complete
        for t in threads:
            t.join()

        # Collect all MD5 results
        md5_values = []
        while not results_queue.empty():
            _, _, md5 = results_queue.get()
            md5_values.append(md5)

        # All MD5s should be identical
        unique_md5s = set(md5_values)

        assert len(unique_md5s) == 1, (
            f"Thread-safety issue detected! Found {len(unique_md5s)} different MD5 values: {unique_md5s}. "
            "The thread-local parser fix may not be working correctly."
        )

        print(f"✓ Thread-safety test passed: {len(md5_values)} conversions, all identical")

    def test_thread_safety_basic(self):
        """Verify basic thread safety - multiple threads can call html_to_text simultaneously."""
        results = []
        errors = []

        def worker():
            """Worker that converts HTML to text."""
            try:
                html = '<html><body><h1>Test</h1><p>Content</p></body></html>'
                text = html_to_text(html)
                results.append(text)
            except Exception as e:
                errors.append(e)

        The fix strips display:none and visibility:hidden styles from the body tag before
        processing, allowing text extraction from client-side rendered applications.
        """
        # Test case 1: Basic display:none
        html1 = '''<!DOCTYPE html>
<html lang="en">
<head><title>What's New – Fluxguard</title></head>
<body style="display:none">
    <h1>Important Heading</h1>
    <p>This is actual content that should be extracted.</p>
    <div>
        <p>First paragraph with meaningful text.</p>
        <p>Second paragraph with more content.</p>
    </div>
</body>
</html>'''

        text1 = html_to_text(html1)

        # Before fix: would return ~33 newlines, len(text) ~= 33
        # After fix: should extract actual content, len(text) > 100
        assert len(text1) > 100, f"Expected substantial text output, got {len(text1)} chars"
        assert 'Important Heading' in text1, "Failed to extract heading from display:none body"
        assert 'actual content' in text1, "Failed to extract paragraph from display:none body"
        assert 'First paragraph' in text1, "Failed to extract nested content"

        # Should not be mostly newlines
        newline_ratio = text1.count('\n') / len(text1)
        assert newline_ratio < 0.5, f"Output is mostly newlines ({newline_ratio:.2%}), content not extracted"

        # Test case 2: visibility:hidden (another hiding pattern)
        html2 = '<html><body style="visibility:hidden"><h1>Hidden Content</h1><p>Test paragraph.</p></body></html>'
        text2 = html_to_text(html2)

        assert 'Hidden Content' in text2, "Failed to extract content from visibility:hidden body"
        assert 'Test paragraph' in text2, "Failed to extract paragraph from visibility:hidden body"

        # Test case 3: Mixed styles (display:none with other CSS)
        html3 = '<html><body style="color: red; display:none; font-size: 12px"><p>Mixed style content</p></body></html>'
        text3 = html_to_text(html3)

        assert 'Mixed style content' in text3, "Failed to extract content from body with mixed styles"

        # Test case 4: Case insensitivity (DISPLAY:NONE uppercase)
        html4 = '<html><body style="DISPLAY:NONE"><p>Uppercase style</p></body></html>'
        text4 = html_to_text(html4)

        assert 'Uppercase style' in text4, "Failed to handle uppercase DISPLAY:NONE"

        # Test case 5: Space variations (display: none vs display:none)
        html5 = '<html><body style="display: none"><p>With spaces</p></body></html>'
        text5 = html_to_text(html5)

        assert 'With spaces' in text5, "Failed to handle 'display: none' with space"

        # Test case 6: Body with other attributes (class, id)
        html6 = '<html><body class="foo" style="display:none" id="bar"><p>With attributes</p></body></html>'
        text6 = html_to_text(html6)

        assert 'With attributes' in text6, "Failed to extract from body with multiple attributes"

        # Test case 7: Should NOT affect opacity:0 (which doesn't hide from inscriptis)
        html7 = '<html><body style="opacity:0"><p>Transparent content</p></body></html>'
        text7 = html_to_text(html7)

        # Opacity doesn't affect inscriptis text extraction, content should be there
        assert 'Transparent content' in text7, "Incorrectly stripped opacity:0 style"

        print("  ✓ All display:none body tag tests passed")

    def test_style_tag_with_svg_data_uri(self):
        """
        Test that style tags containing SVG data URIs are properly stripped.

        Some WordPress and modern sites embed SVG as data URIs in CSS, which contains
        <svg> and </svg> tags within the style content. The regex must use backreferences
        to ensure <style> matches </style> (not </svg> inside the CSS).

        This was causing errors where the regex would match <style> and stop at the first
        </svg> it encountered inside a CSS data URI, breaking the HTML structure.
        """
        # Real-world example from WordPress wp-block-image styles
        html = '''<!DOCTYPE html>
<html>
<head>
    <style id='wp-block-image-inline-css'>
.wp-block-image>a,.wp-block-image>figure>a{display:inline-block}.wp-block-image img{box-sizing:border-box;height:auto;max-width:100%;vertical-align:bottom}@supports ((-webkit-mask-image:none) or (mask-image:none)) or (-webkit-mask-image:none){.wp-block-image.is-style-circle-mask img{border-radius:0;-webkit-mask-image:url('data:image/svg+xml;utf8,<svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg"><circle cx="50" cy="50" r="50"/></svg>');mask-image:url('data:image/svg+xml;utf8,<svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg"><circle cx="50" cy="50" r="50"/></svg>');mask-mode:alpha}}
    </style>
</head>
<body>
    <h1>Test Heading</h1>
    <p>This is the actual content that should be extracted.</p>
    <div class="wp-block-image">
        <img src="test.jpg" alt="Test image">
    </div>
</body>
</html>'''

        # This should not crash and should extract the body content
        text = html_to_text(html)

        # Verify the actual body content was extracted
        assert text is not None, "html_to_text returned None"
        assert len(text) > 0, "html_to_text returned empty string"
        assert 'Test Heading' in text, "Failed to extract heading"
        assert 'actual content that should be extracted' in text, "Failed to extract paragraph"

