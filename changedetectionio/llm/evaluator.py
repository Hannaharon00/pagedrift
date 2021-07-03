"""
LLM evaluation orchestration.

Two public entry points:
  - run_setup(watch, datastore)        — one-time: decide if pre-filter needed
  - evaluate_change(watch, datastore, diff, current_snapshot) — per-change evaluation

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


