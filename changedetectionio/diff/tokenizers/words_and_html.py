"""
Tokenizer that preserves HTML tags as atomic units while splitting on whitespace.

This tokenizer is specifically designed for HTML content where:
- HTML tags should remain intact (e.g., '<p>', '<a href="...">')
- Whitespace tokens are preserved for accurate diff reconstruction
- Words are split on whitespace boundaries
"""

