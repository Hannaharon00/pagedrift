"""
Base contract + shared helpers for a processor's history/diff ("difference") page.

Each processor can provide a custom history/diff view by shipping a
``processors/<name>/difference.py`` module that exposes a module-level ``render(...)``
function. The route ``blueprint/ui/diff.py::diff_history_page`` resolves it via
``get_processor_submodule(processor_name, 'difference')`` and calls ``render(...)`` with the
keyword contract below; processors without one fall back to ``text_json_diff``.

This module formalises that previously-implicit contract:
  * ``DifferenceRenderer`` documents the ``render(...)`` signature (for typing/static checks).
  * ``resolve_diff_versions()`` centralises the from/to version selection that was duplicated
    between ``text_json_diff/difference.py`` and the ``/diff/.../llm-summary`` route, so every
    processor resolves "which two snapshots am I comparing" identically.
"""
from dataclasses import dataclass
from typing import Any, List, Protocol, runtime_checkable

from loguru import logger


