# Pydantic Migration

Plan for incrementally moving the app's storage dicts behind Pydantic models. Driven by
security (CWE-915 mass-assignment, see [GHSA-h3x5-5j56-hm2j][advisory]) and schema
enforcement, not just type tidying.

[advisory]: https://github.com/dgtlmoon/changedetection.io/security/advisories/GHSA-h3x5-5j56-hm2j

## The goal

Every form/API endpoint that mutates a stored dict should validate input against a
declared schema before writing. `extra='forbid'` rejects unknown keys — so an attacker
POSTing extra fields like `uuid=…`, `last_checked=…`, `history=[…]` can't smuggle them
into storage. Per-route allowlists work but rot; one declared schema per stored shape
doesn't.

## Prefer a migration over permanent complexity

If you're about to add a compatibility shim, an alias, a backward-compat fallback, or a
"handle both old and new shape" branch — stop and ask whether a one-time `update_N`
migration solves the same problem by *renaming the stored data*. A migration runs once
per install; the shim lives in the code forever and every future contributor has to
understand it.

Concrete example from this PR: the original design used `Field(alias='llm_X')` so
Pydantic could accept both the legacy form-field name (`llm_model`) and the new
storage name (`model`). That alias survived every read/write for the life of the app
and introduced a subtle `model_dump(by_alias=True)` merge bug. The simpler answer was
to rename the form fields to match the storage names (an in-PR rename, no migration
needed since storage was new), drop the aliases entirely, and delete ~25 lines of
plumbing. **Pay once with a migration; don't pay forever with complexity.**

Same principle applies the moment you find yourself writing `dict.get(new_key) or
dict.get(old_key)`. That's a migration in disguise — write the migration instead.

## Architecture choice: validator at the boundary, not domain model

There are two ways to use Pydantic. Pick one per slice — they are not interchangeable.

**Pydantic-as-validator (what we do).** Storage stays a plain dict. A `BaseModel`
validates input at the boundary, dumps back to a dict. No call-site changes; the
existing `watch['x']` dict access keeps working everywhere.

**Pydantic-as-domain-model.** Replace `dict` inheritance with `BaseModel`. ~190 call
sites switch from `watch['x']` to `watch.x`. Much bigger blast radius, defers the
security win. Not what we're doing right now.

The CWE-915 fix only needs the validator pattern. Domain-model replacement is a
separate, later project.

## The template (LLMSettings)

The first migrated slice. Use as the reference for the next one.

**Match the WTForms field names to the storage / Pydantic field names** so the
form-input dict and the storage dict have the same key shape. No aliases, no
`populate_by_name=True`, no `by_alias=True` merge gymnastics. Only reach for
`Field(alias=…)` if you genuinely cannot rename the form field (rare).

`model/LLMSettings.py`:

```python
class LLMSettings(BaseModel):
    model_config = ConfigDict(extra='forbid')

    enabled: bool = True
    model: str = ''
    ...

    # System-managed counters
    tokens_total_cumulative: int = 0
    ...

    # Field groups
    CONNECTION_FIELDS: ClassVar[Tuple[str, ...]] = ('model', 'api_key', ...)
    PROTECTED_FIELDS:  ClassVar[Tuple[str, ...]] = ('tokens_total_cumulative', ...)
```

Boundary pattern at the route handler:

```python
# Read
settings = LLMSettings.model_validate(
    datastore.data['settings']['application'].get('llm') or {}
)

# Merge form input
form_input = dict(form.data.get('llm') or {})
for protected in LLMSettings.PROTECTED_FIELDS:
    form_input.pop(protected, None)  # counters never come from form
merged = LLMSettings.model_validate({**settings.model_dump(), **form_input})

# Write — re-validates the schema on every write
datastore.data['settings']['application']['llm'] = merged.model_dump()
```

## Unresolved architectural decisions

Two decisions need answers before the `WatchInput` slice. They're not blockers for `App.py`.

### OpenAPI spec vs Pydantic model — who's source of truth?

Today: `docs/api-spec.yaml` declares the Watch/Tag shape; `model/schema_utils.py` reads
it to compute readonly fields; the API layer validates against it; the model layer is a
plain dict that doesn't know about either. When `WatchInput` lands, that's a third
shape declaration.

Two ways to live:
- **Pydantic is source.** Generate / sync `api-spec.yaml` from the model
  (e.g. via `model_json_schema()`). One declaration, multiple consumers. Long-term
  right answer; needs tooling.
- **Parallel sources with discipline.** Hand-keep them aligned. Faster to ship but
  drift is inevitable — that's the bug class we're already trying to close.

Recommendation: start parallel (keep `api-spec.yaml` for now), but write Watch's
Pydantic model so it could be the eventual single source. Don't *invent* a new
field shape — match the spec.

### Plugin / processor_config_* extensibility

`processor_config_restock_diff` (and future processor configs) are written by
plugins, not the core. `extra='forbid'` on a Watch input model would reject them.

Options:
- **Per-processor sub-models.** Each plugin owns its `<Processor>Settings` Pydantic
  model; Watch input validates only core fields, processor configs validate
  separately at their own boundary (the per-watch `restock_diff.json`, etc.).
- **Opaque pass-through.** Watch input model treats `processor_config_*` as a
  declared dict-typed field. Loses per-key validation but preserves the
  plugin-extensibility contract.

Recommendation: per-processor sub-models. Matches the file split already done in
`update_30` (separate `restock_diff.json` per watch).

## Migration order

| Target | Difficulty | Value | Status |
|---|---|---|---|
| `LLMSettings` | low | medium | done (this PR) |
| `App.py` → `AppSettings` (nested) | low | medium | next |
| `WatchInput` (form/API validator) | medium | **HIGH — closes [GHSA-h3x5-5j56-hm2j][advisory]** | next-next |
| `TagInput` (form/API validator) | medium | medium | after Watch |
| `watch_base(dict)` → `BaseModel` | very high | high | separate multi-PR project, much later |

`Tags.py` (TagsDict), `persistence.py`, `schema_utils.py` are not data models — leave alone.

### Concrete next steps

