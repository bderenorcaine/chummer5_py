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
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any

from jinja2 import pass_context
from jinja2.runtime import Context
from markupsafe import Markup, escape
from starlette.requests import Request

from chummer5.data.lang import DataTerms, load_data_terms, load_locale_strings
from chummer5.web.prefs import DEFAULT_LOCALE
from chummer5.web.session import SESSION_COOKIE_NAME

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Message:
    """A user-facing message built where the locale isn't known -- a step's context builder, which
    takes a `Character`, not a session (WP102). It carries the key and its parameters; the template
    translates it with the `| tr` filter, in the locale of the request being rendered.

    `params` values are plain values or other `Message`s (translated in turn). An engine
    `ValueError`'s text passed as a parameter stays English: engine messages are rules-layer
    output this layer does not own (see `spec/worklogs/WP102.md`).
    """

    key: str
    params: Mapping[str, Any] = field(default_factory=dict)

    @classmethod
    def of(cls, key: str, **params: Any) -> Message:
        return cls(key, MappingProxyType(dict(params)))


# Loaded catalogs by locale tag. Module-level so a test can install a stub catalog for a made-up
# locale with `monkeypatch.setitem(CATALOGS, "xx-test", {...})`.
CATALOGS: dict[str, Mapping[str, str]] = {}


def catalog(locale: str) -> Mapping[str, str]:
    if locale not in CATALOGS:
        CATALOGS[locale] = load_locale_strings(locale)
    return CATALOGS[locale]


# Game-data translations by locale (WP103), loaded lazily like `CATALOGS`, and stub-able alike.
DATA_TERMS: dict[str, DataTerms] = {}


def data_terms(locale: str) -> DataTerms:
    if locale not in DATA_TERMS:
        DATA_TERMS[locale] = load_data_terms(locale)
    return DATA_TERMS[locale]


def data_term(locale: str, value: Any, *files: str) -> str:
    """A game-data term's display name in `locale` (WP103) -- **display only, never identity**.

    `value` is a catalog object or a context row (anything with a `name`, and ideally a legacy
    GUID `id`, as attribute or mapping key) or a plain English string. Lookup order: the GUID
    (checked against the English name, because GUIDs repeat in the legacy files), then the English
    text in each of `files` (the legacy data files it can come from:
    categories, skill groups, and the name-keyed catalogs -- lifestyle tiers, starter gear, talent
    options, priority rows -- have no id). Anything untranslated is returned as its English name,
    silently: the legacy `_data.xml` files cover what the legacy app shipped, not everything this
    project offers, and a missing game-data translation is normal rather than a bug.

    The returned string must never reach a form value, an id, a save, or a lookup key -- those
    stay English/GUIDs, so saves stay locale-independent (`test_web_data_terms.py` pins that).
    """
    if isinstance(value, str):
        guid, english = None, value
    else:
        guid = _field(value, "id")
        english = str(_field(value, "name") or "")
    terms = data_terms(locale)
    if guid:
        # The legacy files reuse a few GUIDs under two English names (see `DataTerms`), so the
        # entry whose English matches is the one; an id with a single entry is taken as is (a
        # translation file one data rename behind still translates).
        by_name = terms.by_id.get(str(guid).lower(), {})
        translated = by_name.get(english) or (
            next(iter(by_name.values())) if len(by_name) == 1 else None
        )
        if translated:
            return translated
    for file in files:
        translated = terms.by_file.get(file, {}).get(english)
        if translated:
            return translated
    return english


def data_text(locale: str, value: Any, field: str) -> str:
    """A game-data item's long-text `field` (a mentor's `advantage`, …) in `locale`, falling back
    silently to the item's own English `field` -- `data_term`'s counterpart for prose, display
    only in the same way."""
    guid = _field(value, "id")
    if guid:
        translated = data_terms(locale).fields.get((str(guid).lower(), field))
        if translated:
            return translated
    return str(_field(value, field) or "")


def _field(value: Any, name: str) -> Any:
    if isinstance(value, Mapping):
        return value.get(name)
    return getattr(value, name, None)


def missing_key_marker(key: str) -> str:
    return f"⟦{key}⟧"


def _lookup(locale: str, key: str) -> str:
    """`key`'s unformatted text: `locale`, then English, then the logged missing-key marker."""
    text = catalog(locale).get(key)
    if text is None and locale != DEFAULT_LOCALE:
        text = catalog(DEFAULT_LOCALE).get(key)
    if text is None:
        logger.warning("i18n: no text for key %r in %r or %r", key, locale, DEFAULT_LOCALE)
        return missing_key_marker(key)
    return text


def translate(locale: str, key: str, /, *args: Any, **kwargs: Any) -> str:
    """`key`'s text in `locale` (falling back as the module docstring says), with `args`/`kwargs`
    substituted by `str.format` -- positional for legacy `{0}` texts, named for project ones."""
    text = _lookup(locale, key)
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


def _markup_format(key: str, text: str, args: tuple[Any, ...], kwargs: dict[str, Any]) -> Markup:
    """`text` as safe markup with `args` substituted: the catalog text itself is escaped (rule 4 of
    src/chummer5/lang/README.md -- a translation is plain text), each plain-string argument is
    escaped, and an argument that is already `Markup` -- a `<strong>` word the template built
    around its own `_()` call -- is kept as markup. That is how a sentence with inline emphasis
    stays one key without the catalog ever holding a tag."""
    template = escape(text)
    if not args and not kwargs:
        return template
    try:
        return template.format(*args, **kwargs)
    except (IndexError, KeyError, ValueError) as exc:
        logger.warning("i18n: cannot format key %r: %r", key, exc)
        return template


@pass_context
def jinja_translate(context: Context, key: str, /, *args: Any, **kwargs: Any) -> Markup:
    """The `_()` template global: `translate` in the locale of the request being rendered,
    returned as `Markup` so `Markup` arguments survive (see `_markup_format`)."""
    locale = request_locale(context.get("request"))
    return _markup_format(key, _lookup(locale, key), args, kwargs)


def translate_plural(locale: str, key: str, count: int, /, **kwargs: Any) -> str:
    """`key`'s singular (`<key>_One`) or plural (`<key>_Other`) form for `count`, which is also
    passed to the text as `{count}` (WP102).

    Two forms is English's rule, and it is also enough for every locale the legacy catalogs ship:
    de-de/pt-br have the same two, and ja-jp/zh-cn have one (a translator gives both keys the same
    text). It is not enough for languages with more forms (Polish, Russian, Arabic), and French puts
    0 in the singular where this puts it in the plural -- the day such a locale is offered, this is
    the one function (`plural_key`) that has to learn CLDR plural rules.
    """
    return translate(locale, plural_key(key, count), count=count, **kwargs)


def plural_key(key: str, count: int) -> str:
    """The catalog key holding `key`'s form for `count` -- the one place the plural rule lives."""
    return f"{key}_{'One' if count == 1 else 'Other'}"


def format_nuyen(locale: str, amount: int) -> str:
    """A nuyen amount for display -- the one place that decides how money looks (WP102).

    The pattern is a catalog key (`Web_Format_Nuyen`, English `{amount}¥`), so a locale can put
    the sign first or add a space. **Digit grouping is identified, not solved:** amounts render
    ungrouped (`50000¥`), exactly as every template did before WP102; grouping per locale belongs
    here, and only here, when someone takes it on.
    """
    return translate(locale, "Web_Format_Nuyen", amount=amount)


@pass_context
def jinja_translate_plural(context: Context, key: str, count: int, /, **kwargs: Any) -> Markup:
    """The `_n()` template global: `translate_plural`'s form choice, rendered like `_()`."""
    locale = request_locale(context.get("request"))
    form_key = plural_key(key, count)
    return _markup_format(form_key, _lookup(locale, form_key), (), {"count": count, **kwargs})


@pass_context
def jinja_nuyen(context: Context, amount: int) -> str:
    """The `| nuyen` template filter: `format_nuyen` in the rendered request's locale."""
    return format_nuyen(request_locale(context.get("request")), amount)


@dataclass(frozen=True)
class MessageJoin:
    """A `Message` parameter that is a list: its items rendered and joined by the text of
    `separator_key` -- so "gear (43500) + lifestyle (10000)" is three keys, not one English
    string assembled in Python (WP102)."""

    items: tuple[Message | str, ...]
    separator_key: str = "Web_List_Separator"


def render_message(locale: str, message: Message | MessageJoin | str) -> Markup:
    """`message` in `locale` as safe markup; a plain `str` (an engine error's text) passes through,
    escaped. Nested `Message`/`MessageJoin` parameters are rendered first."""
    if isinstance(message, str):
        return escape(message)
    if isinstance(message, MessageJoin):
        separator = escape(_lookup(locale, message.separator_key))
        return separator.join(render_message(locale, item) for item in message.items)
    params = {
        name: render_message(locale, value)
        if isinstance(value, Message | MessageJoin | str)
        else value
        for name, value in message.params.items()
    }
    return _markup_format(message.key, _lookup(locale, message.key), (), params)


@pass_context
def jinja_render_message(context: Context, message: Message | MessageJoin | str) -> Markup:
    """The `| tr` template filter: `render_message` in the rendered request's locale. Used on every
    `*_error`/`*_budget_warning`/`sheet_*` value, which may be a `Message` or an engine string."""
    return render_message(request_locale(context.get("request")), message)


@pass_context
def jinja_data_term(context: Context, value: Any, *files: str) -> str:
    """The `| dterm("file.xml", ...)` template filter: `data_term` in the rendered request's
    locale. Display only -- never apply it to a form value, id, or `data-*` identity attribute."""
    return data_term(request_locale(context.get("request")), value, *files)


@pass_context
def jinja_data_text(context: Context, value: Any, field: str) -> str:
    """The `| dtext("advantage")` template filter: `data_text` in the rendered request's locale."""
    return data_text(request_locale(context.get("request")), value, field)
