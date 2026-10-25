"""The application shell's routes (WP97): `GET /`, `GET /ui/page/{slug}`, `GET /ui/nav`, and
`GET /character/sheet` -- plus, from WP98, a composite page's tabs: `GET /ui/page/{slug}/{tab}`
and `GET /ui/tabs/{slug}`, from WP99 the sidebar's `GET /ui/resource-panel`, and from WP100 the
title bar's `POST /ui/prefs/theme`, and from WP101 its `POST /ui/prefs/locale`.

These are the only routes that render more than one step's own fragment. A nav click is an htmx
`GET /ui/page/{slug}` that swaps just `#page` (plus the nav, out of band, so its current-step
marker follows) and pushes the page URL, so the browser's back button walks the step history. The
same URL requested *without* htmx -- a bookmark, a reload, or htmx's own history-restore request on
a cache miss -- renders the whole shell with that step selected instead of a bare fragment.

`GET /character/sheet` is the Export page under its pre-WP97 URL, kept working rather than
renamed (Phase W changes no step route's URL); it moved here from `chummer5.web.routes.character`
because it is now a shell render like the others. The Export page's context is that module's
`_character_sheet_context`, not `chargen_context` -- the two are the WP58 audit's two cross-cutting
aggregators, and a page only needs the one its fragments read.

**WP98**: a composite page (Skills, Magic, Equipment) is a tab strip over its sections. A tab link
is the nav mechanism one level down -- an htmx `GET /ui/page/{slug}/{tab}` into `#page`, pushed to
history, answered with the whole shell when requested directly -- and the page it returns still
renders *every* section's fragment, all but the current one `hidden`. So a tab switch is always a
fresh render (a Talent confirmation is exactly what un-empties the Spells fragment, and no step
route re-renders a sibling), and every fragment id stays in the DOM as it was when they stacked.
The tab strip re-fetches itself from `GET /ui/tabs/{slug}` on the same `chargen-changed` event
the nav uses, so a tab's availability and ⚠ follow a change made on another tab.

**WP148**: the Skills page's tabs are view tabs (`chummer5.web.shell.PageTab`) and use the same
two URLs. `GET /ui/page/skills/{tab}` renders the page with both fragments showing that tab's
panel. Its strip re-fetches `GET /ui/tabs/skills?tab=...`, the tab it was rendered for. The page
remembers no tab: a nav click opens it on its first tab.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse

from chummer5.web import prefs
from chummer5.web.auth import app_store, current_user
from chummer5.web.catalogs import templates
from chummer5.web.persistence import open_character_context
from chummer5.web.prefs import THEMES, THEMES_BY_SLUG
from chummer5.web.routes.character import _character_sheet_context
from chummer5.web.routes.priorities import _session_priority_form_context
from chummer5.web.session import (
    ChargenSession,
    resolve_session,
    set_session_cookie,
)
from chummer5.web.shell import (
    DEFAULT_PAGE,
    STEP_PAGES_BY_SLUG,
    StepPage,
    chargen_context,
    nav_context,
    resolve_tab,
    resource_panel_context,
    skills_tabs_context,
    tabs_context,
    validation_context,
)

router = APIRouter()

_DEFAULT_LOCALE_ENTRY = prefs.LOCALES_BY_TAG[prefs.DEFAULT_LOCALE]


def _page_or_404(slug: str) -> StepPage:
    page = STEP_PAGES_BY_SLUG.get(slug)
    if page is None or not page.enabled:
        raise HTTPException(status_code=404, detail=f"No such chargen page: {slug!r}.")
    return page


def _section_or_404(page: StepPage, tab: str) -> None:
    if page.tabs and page.view_tab(tab) is not None:
        return
    if not page.tabbed or page.section(tab) is None:
        raise HTTPException(
            status_code=404, detail=f"No such section on the {page.slug!r} page: {tab!r}."
        )


def prefs_context(session: ChargenSession) -> dict[str, Any]:
    """What the title bar's display-preference pickers (`_titlebar_prefs.html`) and the theme
    `<link>` read. WP139: the character list page has them too."""
    return {
        "theme": session.theme,
        "themes": THEMES,
        "theme_fonts": THEMES_BY_SLUG[session.theme].fonts,
        "locale": session.locale,
        "locales": prefs.LOCALES,
        "html_lang": prefs.LOCALES_BY_TAG.get(session.locale, _DEFAULT_LOCALE_ENTRY).html_lang,
    }


def _shell_context(
    session: ChargenSession,
    page: StepPage,
    tab: str | None = None,
    sheet_messages: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Everything `_page.html` and `_step_nav.html` read for `page`: the page's own fragment
    context plus the nav's items, and -- for a composite page -- its tab strip, showing `tab` if
    one was requested. `chargen_context` is always computed, because the nav's stale-step markers
    read it whichever page is showing.
    """
    chargen_ctx = chargen_context(session, _session_priority_form_context(session))
    page_ctx = (
        _character_sheet_context(session, chargen_ctx=chargen_ctx, **(sheet_messages or {}))
        if page.slug == "export"
        else chargen_ctx
    )
    context = {
        **page_ctx,
        **nav_context(session, chargen_ctx),
        **validation_context(session, chargen_ctx),  # WP135
        **resource_panel_context(session, chargen_ctx),
        **prefs_context(session),
        "page": page,
    }
    if page.tabbed:
        context |= tabs_context(session, page, chargen_ctx, resolve_tab(session, page, tab))
    elif page.tabs:
        current = page.view_tab(tab) if tab is not None else None
        context |= skills_tabs_context(session, page, chargen_ctx, current or page.tabs[0].slug)
    return context


def _respond(request: Request, response: HTMLResponse, new_cookie: str | None) -> HTMLResponse:
    # The same URL answers with a fragment or a whole document depending on `HX-Request`, so a
    # cache must not hand one out for the other.
    response.headers["Vary"] = "HX-Request"
    set_session_cookie(request, response, new_cookie)
    return response


def _render(request: Request, slug: str, *, fragment: bool, tab: str | None = None) -> HTMLResponse:
    session, new_cookie = resolve_session(request)
    page = _page_or_404(slug)
    if tab is not None:
        _section_or_404(page, tab)
    session.current_page = page.slug
    context = _shell_context(session, page, tab)
    context["current_user"] = current_user(request)  # WP137: the title bar's account links
    context |= open_character_context(request, session)  # WP138
    if fragment:
        response = templates.TemplateResponse(request, "_page.html", {**context, "oob_nav": True})
    else:
        response = templates.TemplateResponse(request, "base.html", context)
    return _respond(request, response, new_cookie)


def shell_swap_response(
    request: Request,
    session: ChargenSession,
    slug: str,
    new_cookie: str | None = None,
    **sheet_messages: Any,
) -> HTMLResponse:
    """WP138: the whole shell for `slug`, swapped over `#app-shell` in place. For a response that
    changed which character is open (the first store at the priority confirmation, a load or an
    import): only re-rendering the wrapper renews its `hx-headers`, and a full reload would lose
    the response's own messages (an import's dropped qualities, say). `sheet_messages` are the
    Export page's `error`/`info`."""
    page = _page_or_404(slug)
    session.current_page = page.slug
    context = _shell_context(session, page, sheet_messages=sheet_messages)
    context["current_user"] = current_user(request)
    context |= open_character_context(request, session)
    response = templates.TemplateResponse(request, "_app_shell.html", context)
    response.headers["HX-Retarget"] = "#app-shell"
    response.headers["HX-Reswap"] = "outerHTML"
    return _respond(request, response, new_cookie)


def is_htmx_fragment_request(request: Request) -> bool:
    # htmx's history-restore request (back button on a history-cache miss) also sets
    # `HX-Request`, but swaps the response in as the whole page, so it needs the full shell.
    return (
        request.headers.get("HX-Request") == "true"
        and request.headers.get("HX-History-Restore-Request") != "true"
    )


@router.get("/", response_class=HTMLResponse)
def index(request: Request) -> HTMLResponse:
    return _render(request, DEFAULT_PAGE, fragment=False)


@router.get("/ui/page/{slug}", response_class=HTMLResponse)
def page(request: Request, slug: str) -> HTMLResponse:
    return _render(request, slug, fragment=is_htmx_fragment_request(request))


@router.get("/ui/page/{slug}/{tab}", response_class=HTMLResponse)
def page_tab(request: Request, slug: str, tab: str) -> HTMLResponse:
    return _render(request, slug, fragment=is_htmx_fragment_request(request), tab=tab)


@router.get("/ui/tabs/{slug}", response_class=HTMLResponse)
def page_tabs(request: Request, slug: str, tab: str | None = None) -> HTMLResponse:
    """A composite page's tab strip alone, re-fetched by the strip itself on `chargen-changed`
    (like the nav), so a change on one tab updates the others' availability and ⚠ markers.
    Marks the page's remembered tab -- the one on screen -- as current, even if the change just
    made it unavailable: the strip must describe the pane it sits over, not pick another.

    WP148: a view-tab strip (Skills) names its tab in the query instead, and carries the page's
    counters, which is how they follow an autosave."""
    session, new_cookie = resolve_session(request)
    page = _page_or_404(slug)
    if page.tabs and page.tab_strip is not None:
        chargen_ctx = chargen_context(session, _session_priority_form_context(session))
        current = (page.view_tab(tab) if tab is not None else None) or page.tabs[0].slug
        context = {"page": page, **skills_tabs_context(session, page, chargen_ctx, current)}
        response = templates.TemplateResponse(request, page.tab_strip, context)
        return _respond(request, response, new_cookie)
    if not page.tabbed:
        raise HTTPException(status_code=404, detail=f"The {page.slug!r} page has no tabs.")
    chargen_ctx = chargen_context(session, _session_priority_form_context(session))
    remembered = session.page_tabs.get(page.slug, "")
    current = remembered if page.section(remembered) else resolve_tab(session, page)
    context = {"page": page, **tabs_context(session, page, chargen_ctx, current)}
    response = templates.TemplateResponse(request, "_page_tabs.html", context)
    return _respond(request, response, new_cookie)


@router.get("/character/sheet", response_class=HTMLResponse)
def character_sheet(request: Request) -> HTMLResponse:
    return _render(request, "export", fragment=False)


@router.get("/ui/nav", response_class=HTMLResponse)
def step_nav(request: Request) -> HTMLResponse:
    """The nav alone, re-fetched by the nav itself after every successful `POST` (the
    `chargen-changed` trigger) so its stale-step markers and current step stay true."""
    session, new_cookie = resolve_session(request)
    chargen_ctx = chargen_context(session, _session_priority_form_context(session))
    response = templates.TemplateResponse(
        request, "_step_nav.html", nav_context(session, chargen_ctx)
    )
    set_session_cookie(request, response, new_cookie)
    return response


@router.get("/ui/open-character", response_class=HTMLResponse)
def open_character_fragment(request: Request) -> HTMLResponse:
    """The title bar's open-character name alone (WP138), re-fetched on `chargen-changed`."""
    session, new_cookie = resolve_session(request)
    response = templates.TemplateResponse(
        request, "_open_character.html", open_character_context(request, session)
    )
    return _respond(request, response, new_cookie)


@router.get("/ui/validation-status", response_class=HTMLResponse)
def validation_status(request: Request) -> HTMLResponse:
    """The title bar's "✓ Complete" / "N issues" status alone (WP135), re-fetched on
    `chargen-changed` like the nav."""
    session, new_cookie = resolve_session(request)
    chargen_ctx = chargen_context(session, _session_priority_form_context(session))
    response = templates.TemplateResponse(
        request, "_validation_status.html", validation_context(session, chargen_ctx)
    )
    set_session_cookie(request, response, new_cookie)
    return response


@router.get("/ui/resource-panel", response_class=HTMLResponse)
def resource_panel(request: Request) -> HTMLResponse:
    """The remaining-resources panel alone (WP99), re-fetched by the panel itself on
    `chargen-changed` -- the same self-refresh the nav uses, so no step route renders it."""
    session, new_cookie = resolve_session(request)
    chargen_ctx = chargen_context(session, _session_priority_form_context(session))
    response = templates.TemplateResponse(
        request, "_resource_panel.html", resource_panel_context(session, chargen_ctx)
    )
    set_session_cookie(request, response, new_cookie)
    return response


@router.post("/ui/prefs/theme", response_class=HTMLResponse)
def set_theme(request: Request, theme: str = Form(...)) -> HTMLResponse:
    """Switch the session's theme (WP100) and answer with the new theme `<link>` -- and the
    title bar's font hint, which is per theme -- out of band, so the page restyles in place. An
    unknown slug is a 422, not a silent fallback: the picker only offers `THEMES`, so anything
    else is a bad request."""
    if theme not in THEMES_BY_SLUG:
        raise HTTPException(status_code=422, detail=f"No such theme: {theme!r}.")
    session, new_cookie = resolve_session(request)
    session.theme = theme
    if (user := current_user(request)) is not None:  # WP137: hosted mode keeps it on the account
        app_store(request).set_user_prefs(user.id, theme=theme)
    response = templates.TemplateResponse(
        request,
        "_theme_swap.html",
        {"theme": theme, "theme_fonts": THEMES_BY_SLUG[theme].fonts, "oob_theme": True},
    )
    set_session_cookie(request, response, new_cookie)
    return response


@router.post("/ui/prefs/locale", response_class=HTMLResponse)
def set_locale(request: Request, locale: str = Form(...)) -> HTMLResponse:
    """Switch the session's UI language (WP101). Unlike a theme, a language change touches every
    string on the page, so the answer is `HX-Refresh` -- htmx reloads the current URL, which is
    always a full-shell render of the page the player is on. `prefs.LOCALES_BY_TAG` is read at
    call time (not imported by name) so a test can offer a stub locale."""
    if locale not in prefs.LOCALES_BY_TAG:
        raise HTTPException(status_code=422, detail=f"No such language: {locale!r}.")
    session, new_cookie = resolve_session(request)
    session.locale = locale
    if (user := current_user(request)) is not None:
        app_store(request).set_user_prefs(user.id, locale=locale)
    response = HTMLResponse("")
    response.headers["HX-Refresh"] = "true"
    set_session_cookie(request, response, new_cookie)
    return response
