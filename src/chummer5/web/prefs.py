"""Display preferences the title bar offers (Phase W): the theme (WP100).

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
    of the structural `app.css`."""

    slug: str
    label: str


THEMES: tuple[Theme, ...] = (
    Theme("classic", "Classic"),
    Theme("sketch", "Sketch"),
)

THEMES_BY_SLUG: dict[str, Theme] = {theme.slug: theme for theme in THEMES}

DEFAULT_THEME = "classic"
