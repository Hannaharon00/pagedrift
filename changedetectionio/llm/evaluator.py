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


