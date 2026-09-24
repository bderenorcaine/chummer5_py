# UI string catalogs

The web UI never hard-codes user-facing text. Templates call `_("Key")`, and Python calls
`chummer5.web.i18n.translate(locale, "Key")`. Both look the key up in the session locale's
catalog (WP101).

## Where a key's text comes from

A locale's catalog is two layers (`chummer5.data.lang.load_locale_strings`):

1. **`legacy/Chummer/lang/<locale>.xml`**: the legacy app's strings. They include real
   translations for de-de, fr-fr, ja-jp, pt-br, and zh-cn. WinForms mnemonics are stripped on load
   (`&File` → `File`, `&&` → `&`).
2. **This directory's `<locale>.xml`**: keys this project added. Same schema, and it overrides
   layer 1 on a clash (there should never be one; see rule 2).

Lookup falls back from the session locale to `en-us`, and then to a visible `⟦Key⟧` marker plus
a logged warning. A missing translation is never blank.

## Key rules

1. **Reuse a legacy key when its English text is exactly what the page shows, in the same role.**
   That is how a translation comes for free. `String_Karma` ("Karma") is a good reuse. A legacy
   key whose text is merely *close* is not: "Lifestyles" for a heading that says "Lifestyle" is a
   miss. Never edit a legacy text to make it fit. Add a project key instead.
2. **Project keys start with `Web_`**, then an area, then a name, in `CamelCase` segments:
   `Web_Nav_Priorities`, `Web_Skills_PointsRemaining`. The prefix means a key can never collide
   with a legacy one, and a grep tells which layer owns it.
3. **Interpolated text is one key with named placeholders**, never two keys concatenated:
   `Web_Skills_PointsRemaining` = `Skill points remaining: {remaining} / {budget}.`, called as
   `_("Web_Skills_PointsRemaining", remaining=…, budget=…)`. A language with a different word order
   can then move the placeholders. Legacy keys keep their positional `{0}`, which `_()` also
   accepts.
4. **Texts are plain text.** The result is HTML-escaped like any other template value. Markup stays
   in the template around the `_()` call, not inside the catalog.
5. **Game-data names (skills, qualities, gear, …) are not keys here.** They are translated at
   display time from the legacy `<locale>_data.xml` files (WP103).
