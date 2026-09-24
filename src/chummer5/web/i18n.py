"""The UI's i18n key layer (WP101): look a string key up in the session locale's catalog.

The mechanism is a plain dict lookup, not gettext -- see `spec/decisions-log.md` (2026-09-24, WP101)
for why. Catalogs are `chummer5.data.lang.load_locale_strings` results, loaded lazily once per
locale and kept for the process lifetime.

**Fallback chain.** The session locale's catalog, then `DEFAULT_LOCALE`'s (a missing translation
shows English, silently -- partial translations are normal), then a visible `⟦Key⟧` marker with
a logged warning (a key missing from English too is a bug, and must never render blank).

**Templates** call `_("Key", name=value)` -- a Jinja global registered in
`chummer5.web.catalogs`, which reads the locale off the request being rendered. **Python** (route
modules building a message) calls `translate(locale, "Key", ...)` with the session's locale.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

from jinja2 import pass_context
from jinja2.runtime import Context
from starlette.requests import Request

from chummer5.data.lang import load_locale_strings
from chummer5.web.prefs import DEFAULT_LOCALE
from chummer5.web.session import SESSION_COOKIE_NAME

logger = logging.getLogger(__name__)

# Loaded catalogs by locale tag. Module-level so a test can install a stub catalog for a made-up
# locale with `monkeypatch.setitem(CATALOGS, "xx-test", {...})`.
CATALOGS: dict[str, Mapping[str, str]] = {}


def catalog(locale: str) -> Mapping[str, str]:
    if locale not in CATALOGS:
        CATALOGS[locale] = load_locale_strings(locale)
    return CATALOGS[locale]


def missing_key_marker(key: str) -> str:
    return f"⟦{key}⟧"


def translate(locale: str, key: str, /, *args: Any, **kwargs: Any) -> str:
    """`key`'s text in `locale` (falling back as the module docstring says), with `args`/`kwargs`
    substituted by `str.format` -- positional for legacy `{0}` texts, named for project ones."""
    text = catalog(locale).get(key)
    if text is None and locale != DEFAULT_LOCALE:
        text = catalog(DEFAULT_LOCALE).get(key)
    if text is None:
        logger.warning("i18n: no text for key %r in %r or %r", key, locale, DEFAULT_LOCALE)
        return missing_key_marker(key)
    if not args and not kwargs:
        return text
    try:
        return text.format(*args, **kwargs)
    except (IndexError, KeyError, ValueError) as exc:
        # A translation whose placeholders don't match the call: show the text unformatted
        # (still readable, and the placeholder names say what was meant) rather than crash.
        logger.warning("i18n: cannot format key %r in %r: %r", key, locale, exc)
        return text


def request_locale(request: Request | None) -> str:
    """The locale of the session behind `request`, or `DEFAULT_LOCALE` if there is none yet.
    Read-only: it never creates a session (rendering a string is no reason to). Cached on
    `request.state`, since a page makes hundreds of `_()` calls."""
    if request is None:
        return DEFAULT_LOCALE
    cached = getattr(request.state, "locale", None)
    if cached is not None:
        return str(cached)
    locale = DEFAULT_LOCALE
    session_id = request.cookies.get(SESSION_COOKIE_NAME)
    sessions = getattr(request.app.state, "sessions", None)
    if session_id is not None and sessions is not None:
        session = sessions.get(session_id)
        if session is not None:
            locale = session.locale
    request.state.locale = locale
    return locale


@pass_context
def jinja_translate(context: Context, key: str, /, *args: Any, **kwargs: Any) -> str:
    """The `_()` template global: `translate` in the locale of the request being rendered."""
    return translate(request_locale(context.get("request")), key, *args, **kwargs)
