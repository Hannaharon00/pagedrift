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

