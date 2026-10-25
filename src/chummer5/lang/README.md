# UI string catalogs

The web UI never hard-codes user-facing text. Templates call `_("Key")`, and Python calls
`chummer5.web.i18n.translate(locale, "Key")` or builds a `Message` (rule 9). Both look the key up
in the session locale's catalog (WP101). `tests/unit/test_web_no_bare_text.py` enforces this for
every template and every web-layer Python module (WP102).

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

1. **Reuse a legacy key when its English text is exactly what the page shows, with the same
   meaning.** That is how a translation comes for free. `String_Karma` ("Karma") and
   `String_AttributeBODShort` ("BOD", German "KON") are good reuses. A legacy key whose text is
   merely *close* is not: "Lifestyles" for a heading that says "Lifestyle" is a miss. Never edit a
   legacy text to make it fit. Change the page's wording to match, when that costs nothing (WP102
   adopted legacy's Title Case "Adept Powers" and "Attribute Points" this way), or add a project
   key.
2. **Project keys start with `Web_`**, then an area, then a name, in `CamelCase` segments:
   `Web_Nav_Priorities`, `Web_Skills_ColSkillPoints`. The prefix means a key can never collide
   with a legacy one, and a grep tells which layer owns it.
3. **Interpolated text is one key with named placeholders**, never two keys concatenated:
   `Web_Cyberware_Essence` = `Essence remaining: {remaining} / 6 (spent {spent}).`, called as
   `_("Web_Cyberware_Essence", remaining=…, spent=…)`. A language with a different word order
   can then move the placeholders. Legacy keys keep their positional `{0}`, which `_()` also
   accepts.
4. **Texts are plain text.** The result is HTML-escaped like any other template value. Markup stays
   in the template around the `_()` call, not inside the catalog.
5. **Game-data names (skills, qualities, gear, …) are not keys here.** They are translated at
   display time from the legacy `<locale>_data.xml` files (WP103).
6. **Counts use `_n("Key", count, …)`** and two keys, `Key_One` and `Key_Other`, each with
   `{count}`. Never write `point{{ 's' if n != 1 }}` in a template. (Two forms suit every legacy
   locale; see `chummer5.web.i18n.plural_key` for the languages that need more.)
7. **Money uses `{{ amount | nuyen }}`**, which formats through `Web_Format_Nuyen` (`{amount}¥`).
   Never write a literal `¥`; a test enforces that.
8. **A key built from a value** (`_("Web_MagicType_" ~ character.magic_type)`) is fine for a
   closed set of codenames. Add the family to `test_every_computed_key_family_is_complete`, because
   the literal-key test cannot see it.
9. **Python code that builds a message without knowing the locale** (a step's context builder)
   returns `Message.of("Key", **params)`, or `MessageJoin(items, separator_key)` for a list. The
   template renders it with `{{ value | tr }}`, which passes a plain `str` through: that is how an
   engine exception's text is shown, and it stays English.
