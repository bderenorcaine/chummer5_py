"""Lifestyle chargen step: `POST /ui/lifestyle` (WP20) -- SR5's mandatory Step Six primary-
Lifestyle purchase (core rulebook, p. 369), drawing from the same Resources-priority nuyen budget
`chummer5.web.routes.resources` validates gear against.

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
from chummer5.engine.lifestyle import (
    MAX_LIFESTYLE_MONTHS,
    MIN_LIFESTYLE_MONTHS,
    create_lifestyle_selection,
)
from chummer5.engine.resources import (
    create_resources_selection,
    resources_gear_args,
    starting_nuyen,
)
from chummer5.web.catalogs import (
    DEFAULT_LIFESTYLE_MONTHS,
    DEFAULT_LIFESTYLE_TIER_NAME,
    LIFESTYLES,
    PRIORITIES,
    templates,
)
from chummer5.web.forms import display_karma_to_nuyen
from chummer5.web.session import SESSION_COOKIE_NAME, resolve_session

router = APIRouter()


def _parse_lifestyle_months(form: FormData) -> int:
    """Read `lifestyle_months` off a submitted form, clamping an unparseable value to 0 -- the
    same "let the engine validate what it's already responsible for" choice
    `chummer5.web.routes.resources._parse_gear` makes for a negative gear quantity. `create_
    lifestyle_selection`'s own 1-100 range check is what rejects 0 (or anything else out of range)
    with a specific message, not this parser.
    """
    raw = form.get("lifestyle_months")
    try:
        return int(str(raw)) if raw is not None else 0
    except ValueError:
        return 0


def _lifestyle_context(
    character: Character | None,
    resources_letter: str,
    tier_name: str,
    months: int,
    gear_cost: int,
    cyberware_cost: int,
    bioware_cost: int,
    karma_converted: int = 0,
    foci_cost: int = 0,
    vehicle_cost: int = 0,
    *,
    error: str | None = None,
) -> dict[str, Any]:
    """Context for `_lifestyle.html`: WP20's mandatory primary-Lifestyle purchase (core rulebook,
    p. 369), drawing from the same Resources-priority nuyen budget
    `chummer5.web.routes.resources._resources_context` validates gear against. `gear_cost` is the
    character's *currently committed* gear spend (`resources_selection.nuyen_spent`, or 0 if none
    yet) -- passed in rather than recomputed here, the mirror image of `_resources_context`'s own
    `lifestyle_cost` parameter (see its docstring for why this cross-section number is threaded
    through rather than each section reaching into the other's catalog/state directly). **WP34**
    adds `cyberware_cost` the same way (the character's currently-selected `cyberware_selection
    .nuyen_spent`, or 0 if none yet), extending the shared budget from two sections to three.
    **WP45** adds `bioware_cost` the same way, extending the shared budget to four sections.
    **WP43** adds `karma_converted` the same way (the character's currently-committed
    `resources_selection.karma_converted`, or 0 if none yet), topping up the budget rather than
    spending from it -- see
    `chummer5.engine.resources`'s module docstring. **WP47** adds `foci_cost` the same way,
    extending the shared budget to five sections. **WP93** adds `vehicle_cost` the same way,
    extending it to six.

    Same `error`-gated re-validation pattern as `_resources_context`/
    `chummer5.web.routes.skills._skill_allocation_context`: when `error` is unset (i.e. this isn't
    redisplaying a submission this same request just rejected), re-derives whether the
    currently-selected tier/months still fits the combined budget, surfacing a distinct
    `lifestyle_budget_warning` rather than silently going over on the next render.
    """
    if character is None:
        return {
            "character": None,
            "lifestyle_options": LIFESTYLES,
            "selected_tier_name": tier_name,
            "selected_months": months,
            "min_lifestyle_months": MIN_LIFESTYLE_MONTHS,
            "max_lifestyle_months": MAX_LIFESTYLE_MONTHS,
            "lifestyle_error": error,
        }
    budget = starting_nuyen(resources_letter, PRIORITIES) + display_karma_to_nuyen(karma_converted)
    budget_warning: str | None = None
    if error is None:
        try:
            selection = create_lifestyle_selection(tier_name, months, LIFESTYLES)
        except ValueError as exc:
            budget_warning = str(exc)
        else:
            total_spent = (
                gear_cost
                + selection.total_cost
                + cyberware_cost
                + bioware_cost
                + foci_cost
                + vehicle_cost
            )
            if total_spent > budget:
                parts = [f"gear ({gear_cost})", f"lifestyle ({selection.total_cost})"]
                if cyberware_cost:
                    parts.append(f"cyberware ({cyberware_cost})")
                if bioware_cost:
                    parts.append(f"bioware ({bioware_cost})")
                if foci_cost:
                    parts.append(f"foci ({foci_cost})")
                if vehicle_cost:
                    parts.append(f"vehicles ({vehicle_cost})")
                budget_warning = (
                    f"No longer fits since priorities were last confirmed: {' + '.join(parts)} "
                    f"spend {total_spent} exceeds Resources priority {resources_letter}'s nuyen "
                    f"budget of {budget}. Adjust the lifestyle below to continue."
                )
    return {
        "character": character,
        "lifestyle_options": LIFESTYLES,
        "selected_tier_name": tier_name,
        "selected_months": months,
        "min_lifestyle_months": MIN_LIFESTYLE_MONTHS,
        "max_lifestyle_months": MAX_LIFESTYLE_MONTHS,
        "nuyen_budget": budget,
        "lifestyle_error": error,
        "lifestyle_budget_warning": budget_warning,
    }


@router.post("/ui/lifestyle", response_class=HTMLResponse)
async def submit_lifestyle(request: Request) -> HTMLResponse:
    session, new_cookie = resolve_session(request)
    session.current_page = "equipment"  # WP61/WP97
    if session.character is None:
        context = _lifestyle_context(
            None,
            session.resources_letter,
            DEFAULT_LIFESTYLE_TIER_NAME,
            DEFAULT_LIFESTYLE_MONTHS,
            0,
            0,
            0,
            0,
        )
    else:
        form = await request.form()
        tier_name = str(form.get("lifestyle_tier") or "")
        months = _parse_lifestyle_months(form)
        resources_selection = session.character.resources_selection
        # WP66: preserve each committed Rating-priced item's chosen rating across re-validation.
        gear_names, rating_gear = (
            resources_gear_args(resources_selection)
            if resources_selection is not None
            else ((), ())
        )
        gear_cost = resources_selection.nuyen_spent if resources_selection is not None else 0
        karma_converted = (
            resources_selection.karma_converted if resources_selection is not None else 0
        )
        cyberware_selection = session.character.cyberware_selection
        cyberware_cost = cyberware_selection.nuyen_spent if cyberware_selection is not None else 0
        bioware_selection = session.character.bioware_selection
        bioware_cost = bioware_selection.nuyen_spent if bioware_selection is not None else 0
        # WP93: see chummer5.web.routes.resources' identical note -- `foci_cost` was displayed but
        # never passed to the accepting call; both it and `vehicle_cost` are threaded now.
        foci_selection = session.character.foci_selection
        foci_cost = foci_selection.nuyen_cost if foci_selection is not None else 0
        vehicle_selection = session.character.vehicle_selection
        vehicle_cost = vehicle_selection.nuyen_spent if vehicle_selection is not None else 0
        try:
            lifestyle_selection = create_lifestyle_selection(tier_name, months, LIFESTYLES)
            new_resources_selection = create_resources_selection(
                session.resources_letter,
                PRIORITIES,
                gear_names,
                rating_gear=rating_gear,
                lifestyle_cost=lifestyle_selection.total_cost,
                cyberware_cost=cyberware_cost,
                bioware_cost=bioware_cost,
                karma_converted=karma_converted,
                foci_cost=foci_cost,
                vehicle_cost=vehicle_cost,
            )
        except ValueError as exc:
            context = _lifestyle_context(
                session.character,
                session.resources_letter,
                tier_name,
                months,
                gear_cost,
                cyberware_cost,
                bioware_cost,
                karma_converted,
                foci_cost,
                vehicle_cost,
                error=str(exc),
            )
        else:
            session.character = replace(
                session.character,
                lifestyle_selection=lifestyle_selection,
                resources_selection=new_resources_selection,
            )
            context = _lifestyle_context(
                session.character,
                session.resources_letter,
                tier_name,
                months,
                gear_cost,
                cyberware_cost,
                bioware_cost,
                karma_converted,
                foci_cost,
                vehicle_cost,
            )
    response = templates.TemplateResponse(request, "_lifestyle.html", context)
    if new_cookie is not None:
        response.set_cookie(SESSION_COOKIE_NAME, new_cookie, httponly=True, samesite="lax")
    return response
