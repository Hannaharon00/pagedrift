"""
Content Type Detection and Stream Classification

This module provides intelligent content-type detection for changedetection.io.
It addresses the common problem where HTTP Content-Type headers are missing, incorrect,
or too generic, which would otherwise cause the wrong processor to be used.

The guess_stream_type class combines:
1. HTTP Content-Type headers (when available and reliable)
2. Python-magic library for MIME detection (analyzing actual file content)
3. Content-based pattern matching for text formats (HTML tags, XML declarations, etc.)

