"""The open character: storing, autosaving, opening, and guarding it (WP138).

A chargen session edits one **stored** character, `session.character_id`, from the priority
confirmation that first stores it onward. This module holds every move between the in-memory
session and the `characters` table:

- **restore** (`restore_session`): a session missing for a known key is rebuilt from the user's
  last-opened character (`users.last_character_id`);
- **first store** (`store_new`): the first priority confirmation inserts the character
  (quota-checked); a loaded or imported save is stored the same way, as a *new* character;
- **open / new** (`open_character`, `new_character`);
- **autosave** (`autosave`), after every successful chargen POST, guarded by the row's `revision`
  so a second device's stale copy can't overwrite the first's edits.

And `store_middleware`, which runs the **tab guard** before the route (a request whose
`X-Character-Id` names a character other than the session's) and the autosave after it.

**Threads.** `async def` step POSTs run on the event loop, plain `def` routes in the thread pool
(Phase Y, Finding 4). Anything that reads more than one session field reads a `snapshot()`, every
multi-field change goes through `ChargenSession.adopt`, and autosaves of one session are
serialized by its `save_lock`.
"""

from __future__ import annotations

import hashlib
import logging
from collections.abc import Awaitable, Callable
from enum import Enum
from typing import Any

from fastapi import Request, Response
from starlette.concurrency import run_in_threadpool

from chummer5 import accounts
from chummer5.io.save_format import from_json, to_json
from chummer5.store import CharacterRecord, QuotaExceededError, RevisionConflictError
from chummer5.web.auth import (
    CHARACTERS_PATH,
    LOGIN_PATH,
    LOGOUT_PATH,
    PASSWORD_PATH,
    REGISTER_PATH,
    STATIC_PREFIX,
    app_store,
    current_user,
)
from chummer5.web.catalogs import templates
from chummer5.web.i18n import Message, request_locale, translate
from chummer5.web.routes.character import (
    _apply_built_character_to_session,
    _character_save_from_session,
    build_from_save,
)
from chummer5.web.session import ChargenSession, resolve_session, resolved_session

logger = logging.getLogger(__name__)

CHARACTER_ID_HEADER = "X-Character-Id"
NEW_CHARACTER_TOKEN = "new"
# Switching characters (WP138's open/new, WP139's delete, WP140's upload) lives here: these routes
# change the open character on purpose, behind their own confirmation, so the tab guard doesn't
# apply, and they store what they need themselves, so the autosave doesn't either.
CHARACTERS_PREFIX = "/characters/"
# Display preferences: not the character (see `chummer5.web.prefs`).
PREFS_PREFIX = "/ui/prefs/"
_UNGUARDED_PREFIXES = (STATIC_PREFIX, PREFS_PREFIX, CHARACTERS_PREFIX)
# The list (WP139) is a page of its own, outside the chargen shell.
_UNGUARDED_PATHS = frozenset(
    {LOGIN_PATH, REGISTER_PATH, LOGOUT_PATH, PASSWORD_PATH, CHARACTERS_PATH}
)


# --- who and what --------------------------------------------------------------------------------


def owner_id(request: Request) -> int:
    """The user whose characters this request works on: the logged-in one (hosted), or local
    mode's implicit one, looked up once per app."""
    user = current_user(request)
    if user is not None:
        return user.id
    cached: int | None = getattr(request.app.state, "local_user_id", None)
    if cached is None:
        cached = accounts.ensure_local_user(app_store(request)).id
        request.app.state.local_user_id = cached
    return cached


def open_character_token(session: ChargenSession) -> str:
    """What the shell's `hx-headers` carries, and the tab guard compares against."""
    return NEW_CHARACTER_TOKEN if session.character_id is None else str(session.character_id)


def save_json(session: ChargenSession) -> str:
    """The save JSON of a session -- pass a `snapshot()` of a live one."""
    return to_json(_character_save_from_session(session))


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def open_character_context(request: Request, session: ChargenSession) -> dict[str, Any]:
    """The title bar's open-character block and every switch control's confirmation text."""
    snap = session.snapshot()
    name = snap.character.biography.display_name if snap.character is not None else ""
    locale = request_locale(request)
    shown = name or translate(locale, "Web_Characters_Unnamed")
    return {
        "open_character": {
            "token": open_character_token(snap),
            "stored": snap.character_id is not None,
            "name": name,
            # WP138's switch warning: shown only when another tab of the app is open in this
            # browser (static/tabs.js decides); it names the character being left.
            "switch_question": translate(locale, "Web_Characters_SwitchConfirm", name=shown),
        }
    }


# --- loading -------------------------------------------------------------------------------------


class CharacterLoadError(Exception):
    """A stored save that no longer builds (a catalog changed under it, say)."""


def session_from_record(record: CharacterRecord) -> ChargenSession:
    """A fresh session holding a stored character, ready to `adopt`."""
    try:
        save = from_json(record.save_json)
        built = build_from_save(save)
    except (ValueError, KeyError, AttributeError) as exc:
        logger.warning("stored character %d does not load: %s", record.id, exc)
        raise CharacterLoadError(record.id) from exc
    fresh = ChargenSession()
    _apply_built_character_to_session(fresh, save, built)
    fresh.character_id = record.id
    fresh.revision = record.revision
    # The digest of what *this* code would write, not of the stored bytes: a save written by an
    # older version or an import re-serializes differently, and that alone isn't a change.
    fresh.saved_digest = _digest(save_json(fresh))
    return fresh


def _last_character_id(request: Request) -> int | None:
    user = current_user(request) or app_store(request).get_user(owner_id(request))
    return user.last_character_id if user is not None else None


def restore_session(request: Request) -> ChargenSession:
    """`app.state.session_restorer`: the session for a key that has none, rebuilt from the user's
    last-opened character, or a new character if there is none (or it no longer loads)."""
    character_id = _last_character_id(request)
    if character_id is not None:
        record = app_store(request).get_character(owner_id(request), character_id)
        if record is not None:
            try:
                return session_from_record(record)
            except CharacterLoadError:
                pass
    return ChargenSession()


# --- switching -----------------------------------------------------------------------------------


def store_new(
    request: Request, session: ChargenSession, tentative: ChargenSession
) -> Message | None:
    """Store `tentative`'s character as a **new** character and make `session` adopt it. Returns
    the error to show instead (the quota), leaving `session` untouched."""
    store = app_store(request)
    owner = owner_id(request)
    text = save_json(tentative)
    try:
        record = store.create_character(owner, text)
    except QuotaExceededError:
        return Message.of("Web_Characters_QuotaReached", quota=store.quota)
    tentative.character_id = record.id
    tentative.revision = record.revision
    tentative.saved_digest = _digest(text)
    session.adopt(tentative)
    store.set_last_character(owner, record.id)
    return None


def open_character(request: Request, session: ChargenSession, character_id: int) -> bool:
    """Make `session` edit stored character `character_id`. False if this user has no such
    character; `CharacterLoadError` if it has one that no longer loads."""
    owner = owner_id(request)
    store = app_store(request)
    record = store.get_character(owner, character_id)
    if record is None:
        return False
    fresh = session_from_record(record)
    session.adopt(fresh)
    store.set_last_character(owner, character_id)
    return True


def new_character(request: Request, session: ChargenSession) -> None:
    """Start over with an empty session. Nothing is stored until the priority confirmation."""
    session.adopt(ChargenSession())
    app_store(request).set_last_character(owner_id(request), None)


def reload_session(request: Request, session: ChargenSession, character_id: int) -> None:
    """Throw away the session's copy of `character_id` for the stored one (or for a new
    character, if it was deleted meanwhile), staying on the same page."""
    record = app_store(request).get_character(owner_id(request), character_id)
    fresh = ChargenSession()
    if record is not None:
        try:
            fresh = session_from_record(record)
        except CharacterLoadError:
            fresh = ChargenSession()
    with session.lock:
        if session.character_id != character_id:
            return  # something switched it meanwhile; that wins
        fresh.current_page = session.current_page
        fresh.page_tabs = session.page_tabs
        session.adopt(fresh)


# --- autosave ------------------------------------------------------------------------------------


class SaveOutcome(Enum):
    SKIPPED = "skipped"  # nothing stored to update, or nothing changed
    SAVED = "saved"
    CONFLICT = "conflict"  # changed (or deleted) elsewhere; the session was reloaded


def autosave(request: Request, session: ChargenSession) -> SaveOutcome:
    """Write the session's character back, if it changed. The update only lands if the row is
    still at the revision this session last loaded or saved; if not, another device saved in the
    meantime, this change is dropped, and the session reloads the stored version."""
    with session.save_lock:
        snap = session.snapshot()
        if snap.character is None or snap.character_id is None or snap.revision is None:
            return SaveOutcome.SKIPPED
        text = save_json(snap)
        digest = _digest(text)
        if digest == snap.saved_digest:
            return SaveOutcome.SKIPPED
        try:
            revision = app_store(request).update_character(
                owner_id(request), snap.character_id, text, expected_revision=snap.revision
            )
        except RevisionConflictError:
            revision = None
        if revision is None:
            reload_session(request, session, snap.character_id)
            return SaveOutcome.CONFLICT
        with session.lock:
            if session.character_id == snap.character_id:
                session.revision = revision
                session.saved_digest = digest
        return SaveOutcome.SAVED


# --- the middleware ------------------------------------------------------------------------------


def notice_response(request: Request, message_key: str) -> Response:
    """A 409 that replaces the page with `message_key` and a reload link. htmx 2 swaps no 4xx by
    default; base.html's `htmx-config` opts 409 in."""
    response = templates.TemplateResponse(
        request, "_stale_notice.html", {"message_key": message_key}, status_code=409
    )
    response.headers["HX-Retarget"] = "#page"
    response.headers["HX-Reswap"] = "innerHTML"
    return response


def _guarded(path: str) -> bool:
    return not path.startswith(_UNGUARDED_PREFIXES) and path not in _UNGUARDED_PATHS


async def store_middleware(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    path = request.url.path
    if not _guarded(path):
        return await call_next(request)

    # The tab guard. Only htmx requests carry the header (plain navigation renders whatever is
    # open, so it needs no guard).
    claimed = request.headers.get(CHARACTER_ID_HEADER)
    if claimed is not None:
        session, _ = await run_in_threadpool(resolve_session, request)
        if claimed != open_character_token(session):
            if request.method in ("GET", "HEAD"):
                # A stale tab moving to another step: just reload it into the current character.
                return Response(status_code=200, headers={"HX-Refresh": "true"})
            return notice_response(request, "Web_Characters_StaleTab")

    response = await call_next(request)

    if request.method == "POST" and response.status_code < 400:
        used = resolved_session(request)
        if used is not None:
            outcome = await run_in_threadpool(autosave, request, used)
            if outcome is SaveOutcome.CONFLICT:
                return notice_response(request, "Web_Characters_ChangedElsewhere")
    return response
