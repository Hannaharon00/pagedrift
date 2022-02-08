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


def build_change_summary_system_prompt() -> str:
    """
    Universal, format-agnostic instructions: how to READ a diff and accuracy rules.
    All output-format choices (prose vs JSON, sections, bullets, language, length)
    are owned by the user prompt — including the default in
    DEFAULT_CHANGE_SUMMARY_PROMPT — so that a user replacing the user-prompt
    (e.g. asking for raw JSON) is not overridden by hard-coded format rules here.
    """
    return (
        "You analyse a unified-diff document showing how a monitored web page changed, "
        "and produce exactly the output the user asks for.\n\n"
        "Rules for reading the diff:\n"
        "- Lines starting with + are genuinely new content.\n"
        "- Lines starting with - are genuinely removed content.\n"
        "- Lines starting with ~ have been PRE-IDENTIFIED as moved/reordered or trivial — "
        "the same text exists on both sides of the diff, or the line is a standalone timestamp. "
        "Do NOT treat ~ lines as added or removed.\n\n"
        "Accuracy: only report what the +/- lines actually contain. Never invent details, "
        "never speculate, never add information that isn't in the diff.\n\n"
        "Follow the user's instructions exactly — including the requested output format "
        "(plain text, JSON, Markdown, single value, etc.), structure, language, and length. "
        "Do not add preamble, meta-commentary, or self-introduction. Produce only the output "
        "the user asked for — nothing before it, nothing after it."
    )


def build_setup_prompt(intent: str, snapshot_text: str, url: str = '') -> str:
    """
    Build the prompt for the one-time setup call that decides whether
    a CSS pre-filter would improve evaluation precision.
    """
    excerpt = trim_to_relevant(snapshot_text, intent, max_chars=4_000)

    parts = []
    if url:
        parts.append(f"URL: {url}")
    parts.append(f"Intent: {intent}")
    parts.append(f"\nPage content excerpt:\n{excerpt}")

    return '\n'.join(parts)


def build_setup_system_prompt() -> str:
    return (
        "You help configure a website change monitor.\n"
        "Given a monitoring intent and a sample of the page content, decide if a CSS pre-filter "
        "would improve evaluation precision by scoping the content to a specific structural section.\n\n"
        "Respond with ONLY a JSON object:\n"
        '{"needs_prefilter": true/false, "selector": "CSS selector or null", "reason": "one sentence"}\n\n'
        "Rules:\n"
        "- Only recommend a pre-filter when the intent references a specific structural section "
        "(e.g. 'footer', 'sidebar', 'nav', 'header', 'main', 'article') OR the page clearly "
        "has high-noise sections unrelated to the intent\n"
        "- Use ONLY semantic element selectors: footer, nav, header, main, article, aside, "
        "or attribute-based like [id*='price'], [class*='sidebar'] — NEVER positional selectors "
        "like div:nth-child(3) or //*[2]\n"
        "- Default to needs_prefilter=false — most intents don't need one\n"
        "- selector must be null when needs_prefilter=false"
    )
