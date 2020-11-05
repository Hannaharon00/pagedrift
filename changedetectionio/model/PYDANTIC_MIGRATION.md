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

