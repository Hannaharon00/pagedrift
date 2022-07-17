# Translation overlay

An optional second catalog layer that lets a deployment reword individual strings **without forking
any template or Python source**.

It exists because rewording a string normally means editing the `_()` call at its call site, and that
edit conflicts on every upstream merge, forever. The overlay moves the reworded text out of the
source tree and into a catalog keyed on the upstream `msgid`, so the call site keeps upstream's
string verbatim and carries no diff at all.

Typical uses: white-labelling, or suppressing instructions that don't apply to how you run the app —
e.g. telling users to set `WEBDRIVER_URL` when the operator, not the user, controls that.

## How it works

`BABEL_TRANSLATION_DIRECTORIES` is a `;` separated list. For each locale, Flask-Babel loads one
catalog per directory and merges them in order (`Domain.get_translations` → babel
`Translations.merge` → `dict.update`), so a **later directory overrides an earlier one per message**,
not per file.

```
changedetectionio/translations/          <- base, upstream
changedetectionio/translations_overlay/  <- this layer, merged on top
```

So for German, `translations/de` and `translations_overlay/de` become a single catalog: the msgids
listed in the overlay take the overlay's text, and the other ~580 keep their upstream German. A
language with no overlay catalog is completely unaffected, as is a msgid the overlay doesn't mention.

Overriding **English** works too. The `en_GB` base catalog has every `msgstr` empty, so English
currently renders straight from the msgids; an overlay `en_GB` entry fills that gap.

Wiring is in `changedetectionio/flask_app.py`. The directory is picked up only if it exists, and
`TRANSLATION_OVERLAY_DIR` can point somewhere else (e.g. a path mounted into a container). No
directory, or a directory with no overrides, means no behaviour change.

## The failure mode this needs guarding

