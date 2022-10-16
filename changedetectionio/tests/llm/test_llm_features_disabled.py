"""
Smoke test for the LLM_FEATURES_DISABLED env var.

The env var is intended to hide every LLM/AI surface (settings tab, edit tab,
base-template AI toggle/modal) for hosted deployments. This test renders the
three primary pages with the env var set and verifies that none of the
LLM-related markers leak through.
"""
from flask import url_for


def _llm_markers_absent(body: bytes, where: str = ''):
    """All of these strings appear in LLM UI surfaces — none should render."""
    for marker in (b'AI / LLM', b'toggle-ai-mode', b'llm-not-configured-modal',
                   b'id="ai-llm"', b'#ai-llm', b'href="#ai"'):
        if marker in body:
            idx = body.find(marker)
            context = body[max(0, idx - 80):idx + len(marker) + 80].decode('utf-8', 'replace')
            raise AssertionError(f"[{where}] {marker!r} found in body, context: ...{context}...")


