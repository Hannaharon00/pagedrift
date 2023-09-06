# Translators Guide

This document is for contributors who write templates (HTML) and for translators who maintain `.po` files.
It exists because fragmented `msgid`s — splitting a single sentence across multiple `_()` calls — cause
systematic translation breakage across many languages. Follow the patterns here to prevent that.

---

## Terminology

- **Always use "monitor" or "watcher"** for the concept of watching a URL — never the bare word "watch",
  which translates to "clock" (e.g. `hodinky` in Czech, `시계` in Korean, `時計` in Japanese).
- Use the **shortest suitable wording** for each language. If a language naturally uses the English
  derivative, prefer that.

---

## Template rules: do not fragment `msgid`s

### Why fragments break translation

The GNU gettext manual is explicit on this:

> **[Entire sentences](https://www.gnu.org/software/gettext/manual/html_node/Entire-sentences.html)**:
> Translatable strings should be entire sentences. Because gender/number declension depends on other
> parts of the sentence, half-sentence *"dumb string concatenation"* breaks in many languages other than English.

> **[No string concatenation](https://www.gnu.org/software/gettext/manual/html_node/No-string-concatenation.html)**:
> Placing adjacent `_()` calls is semantically equivalent to runtime `strcat` concatenation, so the same
> guideline applies. The manual also notes that "in some languages the translator might want to swap the
> order" of components.

Move conditional branches outside `_()` so each branch is a complete sentence, not a fragment.

```jinja
{# BAD: three fragments; SOV languages can't reorder %(title)s relative to "URL or Title" #}
{{ _('URL or Title') }}{% if active_tag_uuid %} {{ _('in') }} '{{ active_tag.title }}'{% endif %}

{# GOOD: branch between two complete msgids; each language can freely reorder %(title)s #}
{% if active_tag_uuid %}
  {{ _("URL or Title in '%(title)s'", title=active_tag.title) }}
{% else %}
  {{ _('URL or Title') }}
{% endif %}
```

---

## CJK italic policy

CJK fonts typically have no true italic cut — `<i>` falls back to a mechanical slant that reduces
legibility. Now that `<i>` is inside `msgid`s, CJK translators can handle it per-locale. Apply this policy
for `ja` / `zh` / `zh_Hant_TW`:

| Context | Action |
|---|---|
| `<i>` used for general emphasis | Replace with `<strong>`, or drop if the emphasis is self-evident |
| `<strong><i>...</i></strong>` | Collapse to `<strong>...</strong>` |
| `<i>` wrapping a UI term (e.g. "check unique lines") | Wrap in locale-conventional quotation marks: 「」 for `ja`/`zh_Hant_TW`, `""` for `zh` |

---

## Translation workflow

**Always use these commands** — they read consistent settings from `setup.cfg` and produce minimal diffs:

```bash
python setup.py extract_messages   # Extract translatable strings from source
python setup.py update_catalog     # Propagate new msgids to all .po files
python setup.py compile_catalog    # Compile .po files to binary .mo files
```

Running `pybabel` directly without the project options causes reordering, rewrapping, and line-number
churn that makes diffs hard to review.

### Configuration

All translation settings are in `setup.cfg` (single source of truth):

```ini
[extract_messages]
mapping_file = babel.cfg
output_file = changedetectionio/translations/messages.pot
input_paths = changedetectionio
keywords = _ _l gettext
sort_by_file = true       # Keeps entries ordered by file path
width = 120               # Consistent line width (prevents rewrapping)
add_location = file       # Show file path only (not line numbers)

[update_catalog]
input_file = changedetectionio/translations/messages.pot
output_dir = changedetectionio/translations
domain = messages
width = 120
no_fuzzy_matching = true  # Avoids incorrect automatic matches

[compile_catalog]
directory = changedetectionio/translations
domain = messages
```

---

## Multi-language fix process

When you find a translation error in **any** language, you must check all others for the same `msgid`:

