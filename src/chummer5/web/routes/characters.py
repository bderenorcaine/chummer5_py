"""The player's characters: the list (WP139), and switching the open character (WP138).

`GET /characters` is the landing page after login: the user's stored characters, newest change
first, filtered by name. Its filter box asks the same URL by htmx and gets only the list back.
It is a page of its own, outside the chargen shell (`#app-shell`), so its requests carry no
`X-Character-Id` and nothing on it is tab-guarded.

Open and New answer with a full navigation to `/` (`HX-Redirect` for htmx), since everything on
the page -- and the shell's `hx-headers` -- belongs to the character being left. Both carry the
switch warning on the controls that post to them (`static/tabs.js`). Delete answers with the list
again; deleting the open character also starts a new one.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Form, HTTPException, Query, Request, Response
from fastapi.responses import HTMLResponse

from chummer5.store import CharacterSummary
from chummer5.web.auth import CHARACTERS_PATH, app_store, current_user, redirect
from chummer5.web.catalogs import templates
from chummer5.web.i18n import request_locale, translate
from chummer5.web.persistence import (
    CharacterLoadError,
    new_character,
    open_character,
    open_character_context,
    owner_id,
)
from chummer5.web.routes.pages import is_htmx_fragment_request, prefs_context
from chummer5.web.session import SESSION_COOKIE_NAME, ChargenSession, resolve_session

router = APIRouter()

HOME_PATH = "/"
# Longer than any name a Bio field accepts; a longer filter can match nothing anyway.
MAX_FILTER_LENGTH = 200


def _respond(request: Request, new_cookie: str | None) -> Response:
    response = redirect(request, HOME_PATH)
    if new_cookie is not None:
        response.set_cookie(SESSION_COOKIE_NAME, new_cookie, httponly=True, samesite="lax")
    return response


# --- the list ------------------------------------------------------------------------------------


def _shown_name(summary: CharacterSummary) -> str:
    """Street name first, then name (WP134's `Biography.display_name`, from the columns)."""
    return summary.street_name or summary.display_name


def _updated(stamp: str) -> str:
    """A stored UTC timestamp, to the minute. Players are in one group, rarely across zones;
    the page says it is UTC rather than guessing the browser's zone server-side."""
    return datetime.fromisoformat(stamp).strftime("%Y-%m-%d %H:%M")


def _list_context(request: Request, session: ChargenSession, name_filter: str) -> dict[str, Any]:
    store = app_store(request)
    owner = owner_id(request)
    summaries = store.list_characters(owner, name_filter)
    count = len(summaries) if not name_filter.strip() else store.count_characters(owner)
    open_id = session.character_id
    locale = request_locale(request)
    rows = []
    for summary in summaries:
        name = _shown_name(summary)
        shown = name or translate(locale, "Web_Characters_Unnamed")
        is_open = summary.id == open_id
        rows.append(
            {
                "id": summary.id,
                "name": name,
                "metatype": summary.metatype,
                "updated": _updated(summary.updated),
                "updated_iso": summary.updated,
                "is_open": is_open,
                "delete_question": translate(locale, "Web_Characters_DeleteConfirm", name=shown),
                # Deleting the open character switches this browser to a new one: the other tabs'
                # warning, which static/tabs.js adds only when another tab is open.
                "delete_tabs_warning": (
                    translate(locale, "Web_Characters_DeleteOpenTabs") if is_open else ""
                ),
            }
        )
    return {
        "rows": rows,
        "name_filter": name_filter,
        "count": count,
        "quota": store.quota,
        "at_quota": count >= store.quota,
        **open_character_context(request, session),
    }


def _list_response(
    request: Request,
    session: ChargenSession,
    new_cookie: str | None,
    name_filter: str,
    *,
    fragment: bool,
) -> HTMLResponse:
    context = _list_context(request, session, name_filter)
    if fragment:
        response = templates.TemplateResponse(request, "_character_list.html", context)
    else:
        context |= prefs_context(session)
        context["current_user"] = current_user(request)
        context["max_filter"] = MAX_FILTER_LENGTH
        response = templates.TemplateResponse(request, "characters.html", context)
    response.headers["Vary"] = "HX-Request"
    if new_cookie is not None:
        response.set_cookie(SESSION_COOKIE_NAME, new_cookie, httponly=True, samesite="lax")
    return response


@router.get(CHARACTERS_PATH, response_class=HTMLResponse)
def character_list(request: Request, q: str = Query("")) -> HTMLResponse:
    session, new_cookie = resolve_session(request)
    return _list_response(
        request,
        session,
        new_cookie,
        q[:MAX_FILTER_LENGTH],
        fragment=is_htmx_fragment_request(request),
    )


@router.post("/characters/{character_id}/delete", response_class=HTMLResponse)
def delete_stored_character(request: Request, character_id: int, q: str = Form("")) -> HTMLResponse:
    session, new_cookie = resolve_session(request)
    if not app_store(request).delete_character(owner_id(request), character_id):
        raise HTTPException(status_code=404)  # owner-scoped: someone else's looks missing
    if session.character_id == character_id:
        new_character(request, session)
    return _list_response(request, session, new_cookie, q[:MAX_FILTER_LENGTH], fragment=True)


# --- switching -----------------------------------------------------------------------------------


@router.post("/characters/new")
def start_new_character(request: Request) -> Response:
    session, new_cookie = resolve_session(request)
    new_character(request, session)
    return _respond(request, new_cookie)


@router.post("/characters/{character_id}/open")
def open_stored_character(request: Request, character_id: int) -> Response:
    session, new_cookie = resolve_session(request)
    try:
        found = open_character(request, session, character_id)
    except CharacterLoadError:
        raise HTTPException(status_code=422) from None
    if not found:
        # Someone else's id looks exactly like a missing one (owner-scoped lookup).
        raise HTTPException(status_code=404)
    return _respond(request, new_cookie)
