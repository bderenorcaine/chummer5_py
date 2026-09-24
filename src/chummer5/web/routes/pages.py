"""The application shell's routes (WP97): `GET /`, `GET /ui/page/{slug}`, `GET /ui/nav`, and
`GET /character/sheet` -- plus, from WP98, a composite page's tabs: `GET /ui/page/{slug}/{tab}`
and `GET /ui/tabs/{slug}`.

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
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse

from chummer5.web.catalogs import templates
from chummer5.web.routes.character import _character_sheet_context
from chummer5.web.routes.priorities import _session_priority_form_context
from chummer5.web.session import SESSION_COOKIE_NAME, ChargenSession, resolve_session
from chummer5.web.shell import (
    DEFAULT_PAGE,
    STEP_PAGES_BY_SLUG,
    StepPage,
    chargen_context,
    nav_context,
    resolve_tab,
    tabs_context,
)

router = APIRouter()


def _page_or_404(slug: str) -> StepPage:
    page = STEP_PAGES_BY_SLUG.get(slug)
    if page is None or not page.enabled:
        raise HTTPException(status_code=404, detail=f"No such chargen page: {slug!r}.")
    return page


def _section_or_404(page: StepPage, tab: str) -> None:
    if not page.tabbed or page.section(tab) is None:
        raise HTTPException(
            status_code=404, detail=f"No such section on the {page.label} page: {tab!r}."
        )


def _shell_context(
    session: ChargenSession, page: StepPage, tab: str | None = None
) -> dict[str, Any]:
    """Everything `_page.html` and `_step_nav.html` read for `page`: the page's own fragment
    context plus the nav's items, and -- for a composite page -- its tab strip, showing `tab` if
    one was requested. `chargen_context` is always computed, because the nav's stale-step markers
    read it whichever page is showing.
    """
    chargen_ctx = chargen_context(session, _session_priority_form_context(session))
    page_ctx = _character_sheet_context(session) if page.slug == "export" else chargen_ctx
    context = {**page_ctx, **nav_context(session, chargen_ctx), "page": page}
    if page.tabbed:
        context |= tabs_context(session, page, chargen_ctx, resolve_tab(session, page, tab))
    return context


def _respond(response: HTMLResponse, new_cookie: str | None) -> HTMLResponse:
    # The same URL answers with a fragment or a whole document depending on `HX-Request`, so a
    # cache must not hand one out for the other.
    response.headers["Vary"] = "HX-Request"
    if new_cookie is not None:
        response.set_cookie(SESSION_COOKIE_NAME, new_cookie, httponly=True, samesite="lax")
    return response


def _render(request: Request, slug: str, *, fragment: bool, tab: str | None = None) -> HTMLResponse:
    session, new_cookie = resolve_session(request)
    page = _page_or_404(slug)
    if tab is not None:
        _section_or_404(page, tab)
    session.current_page = page.slug
    context = _shell_context(session, page, tab)
    if fragment:
        response = templates.TemplateResponse(request, "_page.html", {**context, "oob_nav": True})
    else:
        response = templates.TemplateResponse(request, "base.html", context)
    return _respond(response, new_cookie)


def _is_htmx_fragment_request(request: Request) -> bool:
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
    return _render(request, slug, fragment=_is_htmx_fragment_request(request))


@router.get("/ui/page/{slug}/{tab}", response_class=HTMLResponse)
def page_tab(request: Request, slug: str, tab: str) -> HTMLResponse:
    return _render(request, slug, fragment=_is_htmx_fragment_request(request), tab=tab)


@router.get("/ui/tabs/{slug}", response_class=HTMLResponse)
def page_tabs(request: Request, slug: str) -> HTMLResponse:
    """A composite page's tab strip alone, re-fetched by the strip itself on `chargen-changed`
    (like the nav), so a change on one tab updates the others' availability and ⚠ markers.
    Marks the page's remembered tab -- the one on screen -- as current, even if the change just
    made it unavailable: the strip must describe the pane it sits over, not pick another."""
    session, new_cookie = resolve_session(request)
    page = _page_or_404(slug)
    if not page.tabbed:
        raise HTTPException(status_code=404, detail=f"The {page.label} page has no tabs.")
    chargen_ctx = chargen_context(session, _session_priority_form_context(session))
    remembered = session.page_tabs.get(page.slug, "")
    current = remembered if page.section(remembered) else resolve_tab(session, page)
    context = {"page": page, **tabs_context(session, page, chargen_ctx, current)}
    response = templates.TemplateResponse(request, "_page_tabs.html", context)
    return _respond(response, new_cookie)


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
    if new_cookie is not None:
        response.set_cookie(SESSION_COOKIE_NAME, new_cookie, httponly=True, samesite="lax")
    return response
