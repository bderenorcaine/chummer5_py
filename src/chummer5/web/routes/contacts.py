"""Contacts chargen step: `POST /ui/contacts` (WP16).

**WP62**: split out of the former `chummer5.web.app` -- see `spec/plan/phase-r-architecture-
cleanup.md`'s WP58 audit for the target shape this module is part of.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from starlette.datastructures import FormData

from chummer5.engine.character import Character
from chummer5.engine.resources import (
    FREE_CONTACT_POINTS_PER_CHARISMA,
    KARMA_PER_EXCESS_CONTACT_POINT,
    Contact,
    ContactSelection,
    create_contact_selection,
)
from chummer5.web.catalogs import MAX_CONTACT_ROWS, templates
from chummer5.web.session import SESSION_COOKIE_NAME, resolve_session

router = APIRouter()


def _relink_contact_selection(
    character: Character, contact_selection: ContactSelection | None
) -> Character:
    """Recompute a carried-forward contact selection against a freshly built `Character`.

    Unlike quality selection, a plain re-attach isn't correct here: `ContactSelection.free_points`/
    `karma_cost` are derived from `character.attribute_value("CHA")`, which a metatype change or an
    attribute-point change/reinterpretation (both things `submit_attributes` and
    `submit_priorities` can each trigger) can itself change. Recomputes from `contact_selection`'s
    own raw `contacts` tuple via
    `create_contact_selection` rather than trusting the old snapshot's numbers -- always safe to
    call (see `create_contact_selection`'s docstring: it never rejects a contact list that already
    passed its Connection/Loyalty-minimum check once). Returns `character` unchanged if no contact
    has ever been committed.
    """
    if contact_selection is None:
        return character
    return replace(
        character, contact_selection=create_contact_selection(character, contact_selection.contacts)
    )


def _parse_contacts(form: FormData, max_rows: int) -> tuple[Contact, ...]:
    """Read up to `max_rows` contact rows off a submitted form into `Contact`s.

    Any row whose name field is blank is skipped entirely (the fixed-row table has no client-side
    add/remove, so most rows are typically empty). A malformed Connection/Loyalty value is treated
    as 0 rather than dropping the whole row -- `create_contact_selection`'s own
    Connection/Loyalty-below-1 check is what's responsible for rejecting it, the same "let the
    engine validate what it's already responsible for" choice `chummer5.web.forms.parse_points`
    makes for negative attribute/skill points.
    """
    contacts = []
    for i in range(max_rows):
        name = str(form.get(f"contact_name_{i}") or "").strip()
        if not name:
            continue
        try:
            connection = int(str(form.get(f"contact_connection_{i}", "0")))
        except ValueError:
            connection = 0
        try:
            loyalty = int(str(form.get(f"contact_loyalty_{i}", "0")))
        except ValueError:
            loyalty = 0
        free = form.get(f"contact_free_{i}") is not None
        contacts.append(Contact(name=name, connection=connection, loyalty=loyalty, free=free))
    return tuple(contacts)


def _contacts_context(
    character: Character | None,
    contacts: tuple[Contact, ...],
    *,
    error: str | None = None,
) -> dict[str, Any]:
    """Context for `_contacts.html`. `points_spent`/`karma_cost` are computed directly from
    `Contact.points` (never by calling `create_contact_selection`, which raises on the very
    Connection/Loyalty-below-1 input an error-echo render needs to display) -- `free_points` reads
    `character.natural_attribute_value("CHA")` fresh on every render, so it always reflects the
    character's *current* CHA even if an attribute submission changed it since contacts were last
    saved. WP81: `natural_`, matching `chummer5.engine.resources.create_contact_selection`'s own
    switch (p. 95 -- augmented CHA does not fund contact points); this render must compute the same
    number that function would, so the two move together.
    """
    if character is None:
        return {"character": None, "contact_error": error}
    rows = [
        {
            "index": i,
            "name": contacts[i].name if i < len(contacts) else "",
            "connection": contacts[i].connection if i < len(contacts) else "",
            "loyalty": contacts[i].loyalty if i < len(contacts) else "",
            "free": contacts[i].free if i < len(contacts) else False,
            "points": contacts[i].points if i < len(contacts) else 0,
        }
        for i in range(MAX_CONTACT_ROWS)
    ]
    free_points = character.natural_attribute_value("CHA") * FREE_CONTACT_POINTS_PER_CHARISMA
    points_spent = sum(contact.points for contact in contacts)
    karma_cost = max(0, points_spent - free_points) * KARMA_PER_EXCESS_CONTACT_POINT
    return {
        "character": character,
        "contact_rows": rows,
        "free_points": free_points,
        "points_spent": points_spent,
        "contact_karma_cost": karma_cost,
        "contact_error": error,
    }


@router.post("/ui/contacts", response_class=HTMLResponse)
async def submit_contacts(request: Request) -> HTMLResponse:
    session, new_cookie = resolve_session(request)
    session.current_page = "contacts"  # WP61/WP97
    if session.character is None:
        context = _contacts_context(None, ())
    else:
        form = await request.form()
        contacts = _parse_contacts(form, MAX_CONTACT_ROWS)
        try:
            selection = create_contact_selection(session.character, contacts)
        except ValueError as exc:
            context = _contacts_context(session.character, contacts, error=str(exc))
        else:
            session.character = replace(session.character, contact_selection=selection)
            context = _contacts_context(session.character, contacts)
    response = templates.TemplateResponse(request, "_contacts.html", context)
    if new_cookie is not None:
        response.set_cookie(SESSION_COOKIE_NAME, new_cookie, httponly=True, samesite="lax")
    return response
