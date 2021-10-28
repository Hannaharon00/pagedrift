"""
Prompt construction for LLM evaluation calls.
Pure functions — no side effects, fully testable.
"""

import re

from .bm25_trim import trim_to_relevant

_AGO_RE = re.compile(r'^\d+\s+\w+\s+ago$', re.IGNORECASE)

SNAPSHOT_CONTEXT_CHARS = 30_000  # current page state excerpt sent alongside the diff


def _annotate_moved_lines(diff_text: str) -> str:
    """
    Pre-process a unified diff to mark lines that appear on both the + and - sides
    as [MOVED] (~ prefix) rather than genuinely added/removed. This prevents the LLM from
    incorrectly classifying repositioned content as new or deleted.
    Also marks standalone relative timestamps (e.g. '3 hours ago') as ~ trivial.

    Lines are compared after stripping leading +/- and whitespace so that
    indentation changes don't prevent matching.
    """
    lines = diff_text.splitlines()
    added_texts = {
        line[1:].strip().lower() for line in lines if line.startswith('+') and line[1:].strip()
    }
    removed_texts = {
        line[1:].strip().lower() for line in lines if line.startswith('-') and line[1:].strip()
    }
    moved_texts = added_texts & removed_texts

    result = []
    has_changes = False
    for line in lines:
        if line.startswith(('+', '-')):
            bare = line[1:].strip().lower()
            if bare in moved_texts or _AGO_RE.match(line[1:].strip()):
                result.append(f'~{line[1:]}')  # ~ prefix = moved/reordered/trivial, skip
                has_changes = True
                continue
        result.append(line)
    return '\n'.join(result) if has_changes else diff_text


def build_eval_prompt(
    intent: str, diff: str, current_snapshot: str = '', url: str = '', title: str = ''
) -> str:
    """
    Build the user message for a diff evaluation call.
    The system prompt is kept separate (see build_eval_system_prompt).
    """
    parts = []

    if url:
        parts.append(f"URL: {url}")
    if title:
        parts.append(f"Page title: {title}")

    parts.append(f"Intent: {intent}")

    if current_snapshot:
        excerpt = trim_to_relevant(current_snapshot, intent, max_chars=SNAPSHOT_CONTEXT_CHARS)
        if excerpt:
            parts.append(f"\nCurrent page state (relevant excerpt):\n{excerpt}")

    parts.append(f"\nWhat changed (diff):\n{diff}")

    return '\n'.join(parts)


