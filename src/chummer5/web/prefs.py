"""Display preferences the title bar offers (Phase W): the theme (WP100) and the locale (WP101).

A separate module rather than part of `chummer5.web.shell` because `chummer5.web.session` needs
the defaults for `ChargenSession`'s own fields, and the shell imports the session -- this module
imports neither.

A preference is presentation only: it never reaches `Character`, the save format, or any rules
code, and changing one is not a chargen change (so its route sits under `/ui/prefs/`, which the
`chargen-changed` middleware in `chummer5.web.app` deliberately skips).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Theme:
    """One shipped theme: `static/themes/<slug>.css`, a stylesheet of custom-property
    declarations only (`tests/unit/test_web_themes.py` enforces that) that `base.html` links ahead
    of the structural `app.css`. `label_key` is its name's i18n key (WP101)."""

    slug: str
    label_key: str


THEMES: tuple[Theme, ...] = (
    Theme("classic", "Web_Theme_Classic"),
    Theme("sketch", "Web_Theme_Sketch"),
)

THEMES_BY_SLUG: dict[str, Theme] = {theme.slug: theme for theme in THEMES}

DEFAULT_THEME = "classic"


@dataclass(frozen=True)
class Locale:
    """One offered UI language (WP101). `tag` names its catalog files (`<tag>.xml`, lower-case as
    the legacy files are); `html_lang` is the BCP 47 form for `<html lang>`. `label` is the
    language's own name for itself, deliberately *not* a catalog key: a player who cannot read the
    current language still has to be able to find theirs in the picker."""

    tag: str
    html_lang: str
    label: str


# Only English ships (Phase W, WP101). The mechanism loads any locale with a catalog file --
# legacy/Chummer/lang/ already has five -- but a locale is only worth offering once its strings
# cover the page; until WP102/WP103 convert the templates, every other one would render almost
# entirely in its English fallback.
LOCALES: tuple[Locale, ...] = (Locale("en-us", "en-US", "English"),)

LOCALES_BY_TAG: dict[str, Locale] = {locale.tag: locale for locale in LOCALES}

DEFAULT_LOCALE = "en-us"
