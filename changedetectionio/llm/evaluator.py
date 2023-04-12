"""
LLM evaluation orchestration.

Two public entry points:
  - run_setup(watch, datastore)        — one-time: decide if pre-filter needed
  - evaluate_change(watch, datastore, diff, current_snapshot) — per-change evaluation

Intent resolution: watch.llm_intent → first tag with llm_intent whose AI switch is "on"
                   (see tag_llm_applies_to_watches) → None (no evaluation)
Cache: each (intent, diff) pair is evaluated exactly once, result stored in watch.

Environment variable overrides (take priority over datastore settings):
  LLM_MODEL    — model string (e.g. "gpt-4o-mini", "ollama/llama3.2")
  LLM_API_KEY  — API key for cloud providers
  LLM_API_BASE — base URL for local/custom endpoints (e.g. http://localhost:11434)
  LLM_TIMEOUT       — per-request timeout in seconds (default 300). When set, it
                      applies to every endpoint (a single hard ceiling).
  LLM_LOCAL_TIMEOUT — timeout in seconds for local/self-hosted endpoints (api_base
                      on a private/LAN address); default 1800. Applied automatically
                      unless LLM_TIMEOUT is set. See resolve_llm_timeout().
"""

import hashlib
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from loguru import logger

from changedetectionio.strtobool import strtobool

from . import client as llm_client
from .prompt_builder import (
    build_change_summary_prompt, build_change_summary_system_prompt,
    build_eval_prompt, build_eval_system_prompt,
    build_preview_prompt, build_preview_system_prompt,
    build_setup_prompt, build_setup_system_prompt,
)
from .response_parser import parse_eval_response, parse_preview_response, parse_setup_response

from changedetectionio.model.LLMSettings import (
    LLMSettings,
    LLM_DEFAULT_MAX_INPUT_CHARS as _DEFAULT_MAX_INPUT_CHARS,
    LLM_DEFAULT_MAX_SUMMARY_TOKENS,
    LLM_DEFAULT_THINKING_BUDGET,
)


def is_llm_features_disabled() -> bool:
    """True when the LLM_FEATURES_DISABLED env var is set to a truthy value."""
    return bool(strtobool(os.getenv('LLM_FEATURES_DISABLED', '')))


def get_llm_settings(datastore) -> LLMSettings:
    """Hydrate the LLM config dict at settings.application.llm into a validated model.

    Returns a default-constructed LLMSettings when the dict is missing or empty —
    callers never have to None-check the result. The storage layer remains a plain
    dict; this is only the validation/typing layer for reads.
    """
    cfg = datastore.data.get('settings', {}).get('application', {}).get('llm') or {}
    return LLMSettings.model_validate(cfg)


def _get_max_input_chars(datastore) -> int:
    """Max input characters to send to the LLM. Resolution: env var → datastore → 100,000.
    Always returns at least 1 — unlimited is not permitted.
    """
    env_val = os.getenv('LLM_MAX_INPUT_CHARS', '').strip()
    if env_val.isdigit() and int(env_val) > 0:
        return int(env_val)
    stored = get_llm_settings(datastore).max_input_chars
    if stored and stored > 0:
        return stored
    return _DEFAULT_MAX_INPUT_CHARS


class LLMInputTooLargeError(Exception):
    pass


def _check_input_size(text: str, max_chars: int) -> None:
    """Raise LLMInputTooLargeError if text exceeds max_chars."""
    if len(text) > max_chars:
        raise LLMInputTooLargeError(
            f"Change too large for AI summary ({len(text):,} chars, limit {max_chars:,})"
        )


def _thinking_extra_body(model: str, budget: int) -> dict | None:
    """Return litellm extra_body to control thinking for models that support it.

    The `thinkingConfig.thinkingBudget` payload is Gemini-specific (Anthropic and
    OpenAI reasoning models use different parameters), so we gate on the gemini/
    provider prefix first, then defer to litellm's model registry for the actual
    "does this model think?" decision. That picks up new Gemini variants and
    rolling aliases (`gemini-flash-latest`, etc.) as litellm's registry tracks
    them, without us hardcoding model names here.
    """
    if not model.startswith('gemini/'):
        return None
    if 'flash-lite' in model.lower():
        return None
    try:
        import litellm
        if not litellm.get_model_info(model).get('supports_reasoning'):
            return None
    except Exception:
        # Unknown model or registry lookup failed — skip the thinking config
        # rather than guess. Worst case: thinking stays at the provider default.
        return None
    return {'generationConfig': {'thinkingConfig': {'thinkingBudget': budget}}}


def _cached_system(text: str, model: str = '') -> dict:
    """Wrap a system prompt, adding Anthropic prompt-caching headers only for Anthropic models.
    Gemini and other providers have their own caching APIs that break when they receive
    cache_control, so we only apply it where it's supported.
    """
    is_anthropic = model.startswith('claude') or model.startswith('anthropic/')
    if is_anthropic:
        return {'role': 'system', 'content': [{'type': 'text', 'text': text, 'cache_control': {'type': 'ephemeral'}}]}
    return {'role': 'system', 'content': text}


# Output-token cap for the JSON-returning calls (intent eval, preview, setup/prefilter).
# Mirrors client.py's _MAX_COMPLETION_TOKENS so the multiplier helper has a base value
# to scale; cloud-LLM users hit this default unmodified, preserving prior cost defaults.
JSON_RESPONSE_MAX_TOKENS = 400

# Default prompt used when the user hasn't configured llm_change_summary.
# This owns the OUTPUT FORMAT (structure, sections, style, language). The system prompt
# in prompt_builder.build_change_summary_system_prompt() only covers how to READ the diff.
# Users can replace this entirely (e.g. "Just tell me the new timestamp.") without
# fighting hard-coded structure rules from the system prompt.
DEFAULT_CHANGE_SUMMARY_PROMPT = (
    "Describe what changed in plain English using these sections, in this fixed order — "
    "omit a section entirely if there is nothing to report for it:\n"
    "  Added: ...\n"
    "  Changed: ...\n"
    "  Removed: ...\n"
    "The Removed section MUST always be last. Never place removals before additions or changes.\n\n"
    "List items as bullet points with key details for each one. Be considerate of the style "
    "of content you are summarising and adjust your report accordingly.\n"
    "Do not list standalone timestamps like '3 hours ago', 'Yesterday', '2 minutes ago' as added "
    "or removed items — they are not meaningful content changes.\n"
    "For content-heavy pages (news, listings, feeds): quote or paraphrase the specific new "
    "headlines, items, or entries that were added — do not collapse them into vague phrases "
    "like 'new articles were added' or 'section was expanded'.\n"
    "For large blocks of new text (full articles, documents, long paragraphs): briefly summarise "
    "the substance in 1-2 sentences capturing the key point — do not just repeat the title.\n\n"
    "Do not quote non-English text verbatim; translate and summarise all content into English. "
    "Do not give partial listings such as 'Examples include:', always be thorough."
)

# How a watch's or tag's llm_change_summary combines with the prompt it inherits.
# 'replace' is the default and the historical behaviour; 'append' lets a watch add a line
# or two to the inherited prompt instead of holding a full private copy of it, so later
# edits to the global prompt still reach that watch. Re #4251.
LLM_PROMPT_MODE_REPLACE = 'replace'
LLM_PROMPT_MODE_APPEND = 'append'


def _summary_max_tokens(diff: str, max_cap: int = LLM_DEFAULT_MAX_SUMMARY_TOKENS) -> int:
    """Scale completion tokens to diff size: floor 400, ~1 token per 4 chars, ceiling max_cap."""
    return max(400, min(len(diff) // 4, max_cap))


def apply_local_token_multiplier(base_max_tokens: int, llm_cfg: dict) -> int:
    """
    Scale max_tokens for endpoints that commonly serve reasoning models
    (Ollama — self-hosted or ollama.com cloud — and OpenAI-compatible servers like
    vLLM, LM Studio, llama.cpp).

    Reasoning models (Qwen3, DeepSeek-R1, Gemma 3, etc.) emit chain-of-thought into
    `message.reasoning_content` BEFORE the final answer lands in `message.content`.
    Without enough headroom the request truncates mid-thought (`finish_reason='length'`
    or `'stop'` with empty content) and the answer never lands — callers see an empty
    string and silently fall through to safe defaults, hiding the problem.

    Cloud providers with stable, non-reasoning defaults (OpenAI, Anthropic, Gemini,
    OpenRouter) keep their original tight caps so existing users see no behavior or
    cost change. Ollama / OpenAI-compatible users can dial the multiplier down to 1x
    in Settings → AI → Provider if they want to keep costs tight on a paid endpoint.

    Activated when `llm_cfg['provider_kind']` is `'ollama'` or `'openai_compatible'`.
    Multiplier defaults to 5x and is user-configurable in Settings → AI → Provider.
    """
    if (llm_cfg or {}).get('provider_kind') not in ('ollama', 'openai_compatible'):
        return base_max_tokens
    try:
        multiplier = int(llm_cfg.get('local_token_multiplier') or 5)
    except (TypeError, ValueError):
        multiplier = 5
    # Clamp to the same 1-20 range the form enforces. Defense-in-depth against
    # corrupted datastore values that bypassed form validation (manual JSON edits,
    # future migrations, plugins): a runaway multiplier could otherwise produce
    # absurdly large max_tokens caps and exhaust local-endpoint memory.
    multiplier = max(1, min(multiplier, 20))
    return base_max_tokens * multiplier


def _is_local_llm_endpoint(llm_cfg: dict) -> bool:
    """
    True when the configured `api_base` points at an IANA-restricted host
    (private / loopback / link-local / reserved) — i.e. a local or LAN
    self-hosted LLM (Ollama, vLLM, LM Studio, llama.cpp, ...).

    Detection is purely by the api_base host, reusing the same IANA check the
    SSRF guard uses (is_private_hostname). Because it resolves DNS, docker
    service names (`http://ollama:11434`), `host.docker.internal`, and bare LAN
    IPs are all recognised. No api_base (cloud providers) → False.
    """
    api_base = ((llm_cfg or {}).get('api_base') or '').strip()
    if not api_base:
        return False
    try:
        from urllib.parse import urlparse
        from changedetectionio.validate_url import is_private_hostname
        host = urlparse(api_base).hostname
        return bool(host) and is_private_hostname(host)
    except Exception:
        # Never let timeout resolution break an LLM call — fall back to "not local".
        return False


def resolve_llm_timeout(llm_cfg: dict) -> int:
    """
    Per-request timeout (seconds) for an LLM call.

    Cloud providers get client.DEFAULT_TIMEOUT (300s, tunable via LLM_TIMEOUT).
    Local / self-hosted endpoints run on modest hardware and can spend many minutes
    on prompt prefill before the first token, so a 300s cap trips prematurely
    (issue #4225). When the api_base host is IANA-restricted (see
    _is_local_llm_endpoint) we grant client.DEFAULT_LOCAL_TIMEOUT (1800s, tunable
    via LLM_LOCAL_TIMEOUT) — mirroring how Hermes relaxes its timeouts for local
    endpoints. An explicit LLM_TIMEOUT always wins, even for local endpoints, for
    operators who want a single hard ceiling regardless.
    """
    if os.getenv('LLM_TIMEOUT', '').strip():
        return llm_client.DEFAULT_TIMEOUT
    if _is_local_llm_endpoint(llm_cfg):
        return llm_client.DEFAULT_LOCAL_TIMEOUT
    return llm_client.DEFAULT_TIMEOUT


# ---------------------------------------------------------------------------
# Intent resolution
# ---------------------------------------------------------------------------

# A group/tag has exactly one AI control (`llm_backend_profile`), and it is ternary:
#
#   True  — AI on for every watch in the group, using the group's AI settings
#           (llm_intent / llm_change_summary cascade down to the watches)
#   False — AI off for every watch in the group; its prompts are stored but never used
#   None  — the group has no opinion: each watch's own AI switch and prompts apply
#
# On a *watch* the same key is a plain bool (on/off, default on). One control per level, so
# there is nothing to reconcile between an "override?" flag and an "enabled?" flag.
def tag_llm_decision(tag):
    """This group's AI decision: True (on, use its settings), False (off), or None (no opinion)."""
    if not tag:
        return None
    value = tag.get('llm_backend_profile')
    return None if value is None else bool(value)


def tag_llm_applies_to_watches(tag) -> bool:
    """True when this group hands its AI settings down to its watches.

    Only the "on" state does that: a group set to "off" suppresses AI for its watches rather
    than lending them prompts, and a group with no opinion leaves them alone entirely. This is
    the single gate behind both the evaluator cascade and the watch edit page's
    "From group ..." placeholder.
    """
    return tag_llm_decision(tag) is True


def _watch_tags(watch, datastore):
    """Yield this watch's tag dicts, in the watch's own tag order, skipping unknown UUIDs."""
    for tag_uuid in watch.get('tags', []):
        tag = datastore.data['settings']['application'].get('tags', {}).get(tag_uuid)
        if tag:
            yield tag


def _tags_applying_llm(watch, datastore):
    """Yield this watch's groups, in order, that hand their AI settings to their watches."""
    for tag in _watch_tags(watch, datastore):
        if tag_llm_applies_to_watches(tag):
            yield tag


def llm_enabled_for_watch(watch, datastore) -> tuple[bool, str]:
    """Is automatic AI evaluation switched on for this watch? Returns (enabled, source).

    See #4204 — users with hundreds of watches want AI on only a select few.

    A group with an opinion decides for all of its watches ("the group setting overrides any
    watch on/off"), so the first such group wins over the watch's own switch; groups set to
    "leave it to each watch" are skipped. With no group deciding, the watch decides — and a
    missing key means on, so watches predating this switch keep working.

    Only gates *automatic* spend (the worker's intent/summary passes and the restock AI
    plugin). Explicit user actions — the diff page "Summary" button, the intent preview —
    stay available, since those cost tokens only when someone deliberately clicks.
    """
    for tag in _watch_tags(watch, datastore):
        decision = tag_llm_decision(tag)
        if decision is not None:
            return decision, tag.get('title', 'tag')
    return bool(watch.get('llm_backend_profile', True)), 'watch'


def resolve_llm_field(watch, datastore, field: str) -> tuple[str, str]:
    """
    Generic cascade resolver for any LLM per-watch field.
    Returns (value, source) where source is 'watch' or tag title.
    Returns ('', '') if not set anywhere.
    """
    value = (watch.get(field) or '').strip()
    if value:
        return value, 'watch'

    for tag in _tags_applying_llm(watch, datastore):
        tag_value = (tag.get(field) or '').strip()
        if tag_value:
            return tag_value, tag.get('title', 'tag')

    return '', ''


def resolve_intent(watch, datastore) -> tuple[str, str]:
    """
    Return (intent, source) where source is 'watch' or tag title.
    Returns ('', '') if no intent is configured anywhere.
    """
    intent = (watch.get('llm_intent') or '').strip()
    if intent:
        return intent, 'watch'

    for tag in _tags_applying_llm(watch, datastore):
        tag_intent = (tag.get('llm_intent') or '').strip()
        if tag_intent:
            return tag_intent, tag.get('title', 'tag')

    return '', ''


# ---------------------------------------------------------------------------
# LLM config helper
# ---------------------------------------------------------------------------

def get_llm_config(datastore) -> dict | None:
    """
    Return LLM config dict or None if not configured.

    Resolution order (first non-empty model wins):
      1. Environment variables: LLM_MODEL, LLM_API_KEY, LLM_API_BASE
      2. Datastore settings (set via UI)
    """
    if is_llm_features_disabled():
        return None
    # 1. Environment variable override
    env_model = os.getenv('LLM_MODEL', '').strip()
    if env_model:
        return {
            'model': env_model,
            'api_key': os.getenv('LLM_API_KEY', '').strip(),
            'api_base': os.getenv('LLM_API_BASE', '').strip(),
        }

    # 2. Datastore settings
    cfg = datastore.data['settings']['application'].get('llm') or {}
    if not cfg.get('model'):
        return None
    return cfg


def llm_configured_via_env() -> bool:
    """True when LLM config comes from environment variables, not the UI."""
    if is_llm_features_disabled():
        return False
    return bool(os.getenv('LLM_MODEL', '').strip())


