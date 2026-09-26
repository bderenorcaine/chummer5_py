"""Bound Spirits chargen step: `POST /ui/spirits` (WP46), gated to Magician only.

**WP62**: split out of the former `chummer5.web.app` -- see `spec/plan/phase-r-architecture-
cleanup.md`'s WP58 audit for the target shape this module is part of.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import replace
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from starlette.datastructures import FormData

from chummer5.engine.character import Character
from chummer5.engine.magic import binds_spirits
from chummer5.engine.spirits import create_bound_spirit_selection, offered_spirit_types
from chummer5.web.catalogs import MAX_BOUND_SPIRIT_ROWS, templates
from chummer5.web.i18n import Message
from chummer5.web.session import SESSION_COOKIE_NAME, resolve_session

router = APIRouter()


def _parse_bound_spirits(form: FormData, max_rows: int) -> tuple[tuple[str, int | None, int], ...]:
    """Read up to `max_rows` bound-spirit rows off a submitted form into `(spirit_type, force,
    services)` triples -- mirrors `chummer5.web.routes.contacts._parse_contacts`'s identical
    fixed-row shape. Any row whose spirit-type field is blank is skipped entirely; a malformed
    services value is treated as 0 rather than dropping the row, the same "let the engine validate
    what it's already responsible for" choice `_parse_contacts` makes for Connection/Loyalty
    (`create_bound_spirit_selection`'s own "services must be at least 1" check is what rejects a 0
    here). A blank or malformed Force field becomes `None` -- "default to the character's Magic
    rating", the same meaning `create_bound_spirit_selection` gives a `None` Force (WP70).
    """
    picks: list[tuple[str, int | None, int]] = []
    for i in range(max_rows):
        spirit_type = str(form.get(f"spirit_type_{i}") or "").strip()
        if not spirit_type:
            continue
        try:
            services = int(str(form.get(f"spirit_services_{i}", "0")))
        except ValueError:
            services = 0
        force_raw = str(form.get(f"spirit_force_{i}") or "").strip()
        force: int | None
        try:
            force = int(force_raw) if force_raw else None
        except ValueError:
            force = None
        picks.append((spirit_type, force, services))
    return tuple(picks)


def _spirit_selection_context(
    character: Character | None,
    picks: Iterable[tuple[str, int | None, int]],
    *,
    error: str | None = None,
) -> dict[str, Any]:
    """Context for `_spirit_selection.html` (WP46): `create_bound_spirit_selection` reaching the
    browser, gated to Magician only (mirrors `chummer5.web.routes.spells._spell_selection_context`'s
    identical gating note -- Adepts/Mundane never cast or conjure, see
    `chummer5.engine.spirits`'s module docstring). `picks` is whatever should be shown filled in,
    same echo-the-submission shape as `_spell_selection_context`'s `spell_ids`.

    `karma_budget` is `character.karma_remaining` (WP51's unified ledger) with Bound Spirits' own
    currently-committed cost added back in -- `karma_remaining` already has it subtracted out
    (it's part of the sum), but re-validating a *new* Bound Spirit pick needs the budget as it would
    be with nothing yet committed to this section, the same way every other section's re-validation
    excludes its own prior commitment. Recomputed fresh on every render (not read off a stored
    total), so it always reflects the character's *current* karma spend -- including Foci's, read
    directly off `character.foci_selection` rather than threaded through as a parameter (pre-WP51,
    callers had to pass this by hand; now it's just part of the same `character` already passed in).

    **WP19-style staleness re-validation**: when `error` is unset and a Bound Spirit selection is
    already committed, re-runs `create_bound_spirit_selection` against the *current* character/
    budget purely to derive `spirit_budget_warning` -- an attribute edit (CHA) or a Talent change
    (MAG, tradition) can each shrink what was previously a valid selection, the same way a
    priorities reconfirmation can for every other carried-forward selection (see
    `chummer5.web.routes.talent._talent_selection_context`'s identical pattern).
    """
    if character is None:
        return {"character": None, "spirit_error": error}
    if not binds_spirits(character):  # WP121: a Conjuring aspect binds too
        return {"character": character, "spirit_error": error}
    offered = offered_spirit_types(character.tradition) if character.tradition is not None else ()
    own_committed_cost = (
        character.bound_spirit_selection.karma_cost
        if character.bound_spirit_selection is not None
        else 0
    )
    karma_budget = character.karma_remaining + own_committed_cost
    magic_rating = character.attribute_value("MAG")
    entries = list(picks)
    rows = [
        {
            "index": i,
            "spirit_type": entries[i][0] if i < len(entries) else "",
            # A None Force ("default to Magic") is shown as the Magic rating in the form; the
            # engine resolves the same default, so what's displayed matches what would be bound.
            "force": (entries[i][1] if entries[i][1] is not None else magic_rating)
            if i < len(entries)
            else magic_rating,
            "services": entries[i][2] if i < len(entries) else 0,
        }
        for i in range(MAX_BOUND_SPIRIT_ROWS)
    ]
    karma_spent = sum(services for _, _, services in entries)
    budget_warning: Message | None = None
    if error is None and character.bound_spirit_selection is not None:
        committed_picks: list[tuple[str, int | None, int]] = [
            (spirit.spirit_type, spirit.force, spirit.services)
            for spirit in character.bound_spirit_selection.spirits
        ]
        try:
            create_bound_spirit_selection(committed_picks, character, karma_budget)
        except ValueError as exc:
            budget_warning = Message.of("Web_Stale_Spirits", error=str(exc))
    return {
        "character": character,
        "spirit_rows": rows,
        "offered_spirit_types": offered,
        "max_bound_spirits": character.attribute_value("CHA"),
        "spirit_force": character.attribute_value("MAG"),
        "spirit_karma_budget": karma_budget,
        "spirit_karma_spent": karma_spent,
        "spirit_karma_remaining": karma_budget - karma_spent,
        "spirit_error": error,
        "spirit_budget_warning": budget_warning,
        "spirits_available": True,  # WP121: the template's gate
    }


@router.post("/ui/spirits", response_class=HTMLResponse)
async def submit_spirits(request: Request) -> HTMLResponse:
    session, new_cookie = resolve_session(request)
    session.current_page = "magic"  # WP61/WP97
    if session.character is None or not binds_spirits(session.character):
        context = _spirit_selection_context(session.character, ())
    else:
        form = await request.form()
        picks = _parse_bound_spirits(form, MAX_BOUND_SPIRIT_ROWS)
        character = session.character
        # WP51: budget excludes Bound Spirits' own currently-committed cost (about to be
        # replaced by this submission) -- see _spirit_selection_context's own docstring for why
        # this is `karma_remaining` with that one term added back in.
        own_committed_cost = (
            character.bound_spirit_selection.karma_cost
            if character.bound_spirit_selection is not None
            else 0
        )
        karma_budget = character.karma_remaining + own_committed_cost
        try:
            selection = create_bound_spirit_selection(picks, character, karma_budget)
        except ValueError as exc:
            context = _spirit_selection_context(character, picks, error=str(exc))
        else:
            session.character = replace(character, bound_spirit_selection=selection)
            context = _spirit_selection_context(session.character, picks)
    response = templates.TemplateResponse(request, "_spirit_selection.html", context)
    if new_cookie is not None:
        response.set_cookie(SESSION_COOKIE_NAME, new_cookie, httponly=True, samesite="lax")
    return response
