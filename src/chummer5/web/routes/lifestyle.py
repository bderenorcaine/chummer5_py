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
    PERMANENT_LIFESTYLE_MONTHS,
    create_lifestyle_selection,
    lifestyle_cost_percent,
)
from chummer5.engine.resources import (
    create_resources_selection,
    resources_addon_args,
    resources_gear_args,
    starting_nuyen,
)
from chummer5.web.catalogs import (
    DEFAULT_LIFESTYLE_MONTHS,
    DEFAULT_LIFESTYLE_TIER_NAME,
    LIFESTYLE_OPTIONS,
    LIFESTYLES,
    PRIORITIES,
    templates,
)
from chummer5.web.forms import display_karma_to_nuyen
from chummer5.web.i18n import Message, MessageJoin
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
    options: tuple[tuple[str, str | None], ...] = (),
    permanent: bool = False,
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

    **WP132**: `options` (`(name, text)` pairs) and `permanent` are echoed and priced the same way.
    """
    option_rows = _option_rows(options)
    if character is None:
        return {
            "character": None,
            "option_rows": option_rows,
            "lifestyle_permanent": permanent,
            "lifestyle_options": LIFESTYLES,
            "selected_tier_name": tier_name,
            "selected_months": months,
            "min_lifestyle_months": MIN_LIFESTYLE_MONTHS,
            "max_lifestyle_months": MAX_LIFESTYLE_MONTHS,
            "lifestyle_error": error,
        }
    budget = starting_nuyen(resources_letter, PRIORITIES) + display_karma_to_nuyen(karma_converted)
    budget_warning: Message | str | None = None
    if error is None:
        try:
            selection = create_lifestyle_selection(
                tier_name,
                months,
                LIFESTYLES,
                cost_percent=lifestyle_cost_percent(character),
                options=options,
                option_catalog=LIFESTYLE_OPTIONS,
                permanent=permanent,
            )
        except ValueError as exc:
            budget_warning = str(exc)  # an engine message: stays as-is (WP102)
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
                # WP102: one keyed fragment per spender, joined by a keyed " + ", so no English is
                # assembled here -- see `chummer5.web.i18n.MessageJoin`.
                parts = [
                    Message.of("Web_Stale_SpendGear", amount=gear_cost),
                    Message.of("Web_Stale_SpendLifestyle", amount=selection.total_cost),
                ]
                for key, cost in (
                    ("Web_Stale_SpendCyberware", cyberware_cost),
                    ("Web_Stale_SpendBioware", bioware_cost),
                    ("Web_Stale_SpendFoci", foci_cost),
                    ("Web_Stale_SpendVehicles", vehicle_cost),
                ):
                    if cost:
                        parts.append(Message.of(key, amount=cost))
                budget_warning = Message.of(
                    "Web_Stale_Lifestyle",
                    breakdown=MessageJoin(tuple(parts), "Web_List_Plus"),
                    total=total_spent,
                    letter=resources_letter,
                    budget=budget,
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
        "option_rows": option_rows,
        "lifestyle_permanent": permanent,
        "permanent_months": PERMANENT_LIFESTYLE_MONTHS,
    }


# WP132: how many Special Work Areas the form offers a text field for.
MAX_WORK_AREAS = 3


def _option_rows(options: tuple[tuple[str, str | None], ...]) -> list[dict[str, Any]]:
    """One form row per Lifestyle Option: a checkbox, or (for a repeatable one) up to
    `MAX_WORK_AREAS` text fields, echoing `options`."""
    rows: list[dict[str, Any]] = []
    for option in LIFESTYLE_OPTIONS:
        texts = [text or "" for name, text in options if name == option.name]
        rows.append(
            {
                "option": option,
                "checked": bool(texts),
                "texts": (texts + [""] * MAX_WORK_AREAS)[:MAX_WORK_AREAS]
                if option.repeatable
                else [],
            }
        )
    return rows


def _parse_options(form: FormData) -> tuple[tuple[str, str | None], ...]:
    """WP132: `lifestyle_option_{i}` checkboxes, and `lifestyle_option_{i}_text_{n}` fields for a
    repeatable option -- each nonblank one is an instance."""
    picks: list[tuple[str, str | None]] = []
    for index, option in enumerate(LIFESTYLE_OPTIONS):
        if option.repeatable:
            for n in range(MAX_WORK_AREAS):
                text = str(form.get(f"lifestyle_option_{index}_text_{n}") or "").strip()
                if text:
                    picks.append((option.name, text))
        elif form.get(f"lifestyle_option_{index}") is not None:
            picks.append((option.name, None))
    return tuple(picks)


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
        options = _parse_options(form)  # WP132
        permanent = form.get("lifestyle_permanent") is not None
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
            lifestyle_selection = create_lifestyle_selection(
                tier_name,
                months,
                LIFESTYLES,
                cost_percent=lifestyle_cost_percent(session.character),
                options=options,
                option_catalog=LIFESTYLE_OPTIONS,
                permanent=permanent,
            )
            new_resources_selection = create_resources_selection(
                session.resources_letter,
                PRIORITIES,
                gear_names,
                rating_gear=rating_gear,
                **resources_addon_args(resources_selection),  # WP130/WP131
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
                options,
                permanent,
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
                options,
                permanent,
            )
    response = templates.TemplateResponse(request, "_lifestyle.html", context)
    if new_cookie is not None:
        response.set_cookie(SESSION_COOKIE_NAME, new_cookie, httponly=True, samesite="lax")
    return response
