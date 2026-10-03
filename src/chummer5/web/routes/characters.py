"""The player's characters: the list (WP139), and switching the open character (WP138).

`GET /characters` is the landing page after login: the user's stored characters, newest change
first, filtered by name. Its filter box asks the same URL by htmx and gets only the list back.
It is a page of its own, outside the chargen shell (`#app-shell`), so its requests carry no
`X-Character-Id` and nothing on it is tab-guarded.

Open and New answer with a full navigation to `/` (`HX-Redirect` for htmx), since everything on
the page -- and the shell's `hx-headers` -- belongs to the character being left. Both carry the
switch warning on the controls that post to them (`static/tabs.js`). Delete answers with the list
again; deleting the open character also starts a new one.

**WP140**: `GET /characters/{id}/download` (the stored JSON, verbatim) and `POST
/characters/upload` (any number of JSON saves or legacy `.chum5` files, up to
`uploads.MAX_FILES`, each stored as a **new** character, quota-checked per file). An upload from
the list stores and answers with the list plus a line per file; it opens nothing, so it needs no
switch warning. The Export page's upload (`?open=true`) also opens the (last) stored character,
answering with the whole shell as WP138's load did.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Form, HTTPException, Query, Request, Response
from fastapi.responses import HTMLResponse
from starlette.concurrency import run_in_threadpool

from chummer5.store import CharacterSummary, config
from chummer5.web.auth import CHARACTERS_PATH, app_store, current_user, redirect
from chummer5.web.catalogs import templates
from chummer5.web.i18n import Message, MessageJoin, request_locale, translate
from chummer5.web.persistence import (
    CharacterLoadError,
    adopt_stored,
    insert_new,
    new_character,
    open_character,
    open_character_context,
    owner_id,
)
from chummer5.web.routes.character import (
    _apply_built_character_to_session,
    sheet_fragment,
    switched_response,
)
from chummer5.web.routes.pages import is_htmx_fragment_request, prefs_context
from chummer5.web.session import SESSION_COOKIE_NAME, ChargenSession, resolve_session
from chummer5.web.uploads import (
    MAX_FILES,
    UploadedFile,
    UploadRejectedError,
    import_file,
    read_upload,
)

router = APIRouter()

HOME_PATH = "/"
# Longer than any name a Bio field accepts; a longer filter can match nothing anyway.
MAX_FILTER_LENGTH = 200
UPLOAD_PATH = "/characters/upload"
_DISPOSITION = 'attachment; filename="{}"'
# An uploaded file's name, as the results show it.
_MAX_SHOWN_FILENAME = 100


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


def _list_context(
    request: Request,
    session: ChargenSession,
    name_filter: str,
    upload_results: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
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
        "max_files": MAX_FILES,
        "upload_results": upload_results or [],
        **open_character_context(request, session),
    }


def _list_response(
    request: Request,
    session: ChargenSession,
    new_cookie: str | None,
    name_filter: str,
    *,
    fragment: bool,
    upload_results: list[dict[str, Any]] | None = None,
) -> HTMLResponse:
    context = _list_context(request, session, name_filter, upload_results)
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


# --- download and upload (WP140) -----------------------------------------------------------------


def download_filename(name: str) -> str:
    """A download's file name from a character's shown name: runs of anything outside
    `[A-Za-z0-9_-]` become one `_`, falling back to `character`."""
    stem = re.sub(r"[^A-Za-z0-9_-]+", "_", name).strip("_")[:64]
    return f"{stem or 'character'}.json"


@router.get("/characters/{character_id}/download")
def download_character(request: Request, character_id: int) -> Response:
    """The stored save, byte for byte (owner-scoped: someone else's id is a 404)."""
    record = app_store(request).get_character(owner_id(request), character_id)
    if record is None:
        raise HTTPException(status_code=404)
    filename = download_filename(record.street_name or record.display_name)
    return Response(
        content=record.save_json,
        media_type="application/json",
        headers={"Content-Disposition": _DISPOSITION.format(filename)},
    )


@dataclass(frozen=True)
class _Outcome:
    message: Message
    stored: ChargenSession | None  # the stored character, ready to open; None on an error


def _store_uploads(request: Request, files: list[UploadedFile]) -> list[_Outcome]:
    """Import each file and store it as a new character. In the thread pool: an import is CPU
    work, and twenty of them shouldn't hold up the event loop."""
    max_bytes = config.upload_max_bytes()
    outcomes = []
    for uploaded in files:
        result = import_file(uploaded, max_bytes)
        error = result.error
        tentative: ChargenSession | None = None
        if error is None:
            assert result.save is not None and result.built is not None
            tentative = ChargenSession()
            _apply_built_character_to_session(tentative, result.save, result.built)
            tentative.current_page = "export"
            error = insert_new(request, tentative)
        notes = (error,) if error is not None else result.notes
        message = Message.of(
            "Web_Upload_FileResult",
            file=uploaded.filename[:_MAX_SHOWN_FILENAME],
            result=MessageJoin(notes, "Web_List_Space"),
        )
        outcomes.append(_Outcome(message, tentative if error is None else None))
    return outcomes


@router.post(UPLOAD_PATH, response_class=HTMLResponse)
async def upload_characters(request: Request, open: bool = Query(False)) -> HTMLResponse:  # noqa: A002
    session, new_cookie = resolve_session(request)
    outcomes: list[_Outcome] = []
    refusal: Message | None = None
    name_filter = ""
    try:
        parsed = await read_upload(request)
    except UploadRejectedError as exc:
        refusal = exc.message
    else:
        name_filter = parsed.fields.get("q", "")[:MAX_FILTER_LENGTH]
        if not parsed.files:
            refusal = Message.of("Web_Upload_ChooseFile")
        else:
            outcomes = await run_in_threadpool(_store_uploads, request, parsed.files)

    if open:  # the Export page
        session.current_page = "export"
        stored = [o.stored for o in outcomes if o.stored is not None]
        if refusal is not None:
            return sheet_fragment(request, session, new_cookie, error=refusal, info=None)
        joined = MessageJoin(tuple(o.message for o in outcomes), "Web_List_Space")
        if stored:
            adopt_stored(request, session, stored[-1])
            return switched_response(request, session, new_cookie, joined)
        return sheet_fragment(request, session, new_cookie, error=joined, info=None)

    results = [{"ok": o.stored is not None, "message": o.message} for o in outcomes]
    if refusal is not None:
        results = [{"ok": False, "message": refusal}]
    return _list_response(
        request, session, new_cookie, name_filter, fragment=True, upload_results=results
    )


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
