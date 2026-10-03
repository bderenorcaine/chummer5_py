"""Switching the open character (WP138): open a stored one, or start a new one.

Both answer with a full navigation to `/` (`HX-Redirect` for htmx), since everything on the page
-- and the shell's `hx-headers` -- belongs to the character being left. Both carry the switch
warning on the controls that post to them (`static/tabs.js`). WP139's character list is where
"open" is offered; the title bar offers "new".
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Response

from chummer5.web.auth import redirect
from chummer5.web.persistence import CharacterLoadError, new_character, open_character
from chummer5.web.session import SESSION_COOKIE_NAME, resolve_session

router = APIRouter()

HOME_PATH = "/"


def _respond(request: Request, new_cookie: str | None) -> Response:
    response = redirect(request, HOME_PATH)
    if new_cookie is not None:
        response.set_cookie(SESSION_COOKIE_NAME, new_cookie, httponly=True, samesite="lax")
    return response


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
