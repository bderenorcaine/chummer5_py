"""Vehicles/drones chargen step: `POST /ui/vehicles` (WP93) -- Phase P's stock vehicle purchase,
drawing from the same Resources-priority nuyen budget gear/Lifestyle/cyberware/bioware/foci already
share (p. 94's Step Six Gear Checklist names "Vehicle(s), p. 461 / Drones..., p. 461" alongside the
rest).

**Its own section, not folded into `_resources.html`'s gear picker** -- the same call WP20 made for
Lifestyle and WP34 made for cyberware. A vehicle row has a nine-column stat block and a derived
Condition Monitor that no gear row has, so displaying it inside the gear table would mean one
context builder producing two unrelated row shapes; and the catalog is 35 rows against gear's ~380,
so it would be invisible in there anyway.

**Quantity per row, expanded into repeated ids** -- mirrors `chummer5.web.routes.resources
._parse_gear` exactly, because the underlying rule is the same one: repeats are quantity (a rigger
buys four Fly-Spies), and `create_vehicle_selection` takes a flat, repeats-allowed id list rather
than a `{id: quantity}` mapping.
"""

from __future__ import annotations

import itertools
from collections.abc import Iterable
from dataclasses import replace
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from starlette.datastructures import FormData

from chummer5.data.vehicles import Vehicle
from chummer5.engine.character import Character
from chummer5.engine.resources import (
    create_resources_selection,
    resources_gear_args,
    starting_nuyen,
)
from chummer5.engine.vehicles import VEHICLE_CATALOG, condition_monitor, create_vehicle_selection
from chummer5.web.catalogs import PRIORITIES, templates
from chummer5.web.forms import display_karma_to_nuyen
from chummer5.web.session import SESSION_COOKIE_NAME, resolve_session

router = APIRouter()


def vehicle_stat_block(vehicle: Vehicle) -> dict[str, Any]:
    """One vehicle's printed stat block plus its derived Condition Monitor, in the notation the
    book uses -- `handling`/`speed` render as `4/3` when the row prints an on-road/off-road pair and
    as a single number otherwise (WP91 stores the off-road half as `None` for the latter), and
    `availability` re-joins its `R`/`F` legality marker.

    Shared with `chummer5.web.routes.character`'s character-sheet context so the picker and the
    sheet can never disagree about how a row is displayed.
    """
    handling = str(vehicle.handling)
    if vehicle.handling_offroad is not None:
        handling = f"{vehicle.handling}/{vehicle.handling_offroad}"
    speed = str(vehicle.speed)
    if vehicle.speed_offroad is not None:
        speed = f"{vehicle.speed}/{vehicle.speed_offroad}"
    return {
        "name": vehicle.name,
        "category": vehicle.category,
        "handling": handling,
        "speed": speed,
        "acceleration": vehicle.acceleration,
        "body": vehicle.body,
        "armor": vehicle.armor,
        "pilot": vehicle.pilot,
        "sensor": vehicle.sensor,
        # p. 466 prints "—" for every drone's Seating; None renders as that in the template.
        "seats": vehicle.seats,
        "availability": f"{vehicle.availability}{vehicle.availability_restriction}",
        "cost": vehicle.cost,
        "condition_monitor": condition_monitor(vehicle),
        "is_drone": vehicle.is_drone,
        "page": vehicle.page,
    }


def _parse_vehicles(form: FormData, catalog: Iterable[Vehicle]) -> tuple[str, ...]:
    """Expand each catalog row's submitted quantity into that many repeats of its id.

    An unparseable or negative quantity is clamped to 0 -- a plain web-robustness clamp, not a rule
    offloaded onto the engine, exactly as `chummer5.web.routes.resources._parse_gear` documents for
    the identical case (there is no engine-level "negative quantity" concept for
    `create_vehicle_selection` to reject instead).
    """
    ids: list[str] = []
    for vehicle in catalog:
        raw = form.get(f"vehicle_{vehicle.id}")
        try:
            quantity = int(str(raw)) if raw is not None else 0
        except ValueError:
            quantity = 0
        ids.extend([vehicle.id] * max(quantity, 0))
    return tuple(ids)


def _vehicles_context(
    character: Character | None,
    resources_letter: str,
    vehicle_ids: tuple[str, ...],
    gear_cost: int,
    lifestyle_cost: int,
    cyberware_cost: int,
    bioware_cost: int,
    karma_converted: int = 0,
    foci_cost: int = 0,
    *,
    error: str | None = None,
) -> dict[str, Any]:
    """Context for `_vehicles.html`. `vehicle_ids` is the flat, repeats-allowed id list
    `create_vehicle_selection` itself takes -- tallied into per-row quantities here purely for
    display, the same way `_resources_context` tallies `gear_names`.

    The five cost parameters are the *other* sections' currently-committed spend, threaded through
    the same cross-section wiring every shared-budget section since WP20 uses (see
    `chummer5.web.routes.resources._resources_context`'s docstring for why the numbers are passed in
    rather than each section reaching into the others' state). As there, this isn't a bidirectional
    live update -- buying a vehicle here doesn't refresh `#resources`' displayed remaining budget
    until the next full render -- but *validation* is always correct, because both sections call the
    same joint `create_resources_selection` check.

    Same `error`-gated staleness re-validation as `_resources_context`/`_lifestyle_context`: when
    `error` is unset, re-runs the joint budget check against the current letters/costs purely to
    derive `vehicles_budget_warning`, so a Resources-letter change that shrinks the budget below
    what's already committed says so rather than silently going over.
    """
    if character is None:
        return {"character": None, "vehicles_error": error}
    counts: dict[str, int] = {}
    for vehicle_id in vehicle_ids:
        counts[vehicle_id] = counts.get(vehicle_id, 0) + 1

    # The catalog is already sorted by (category, name) (build_vehicle_catalog's own contract), so a
    # plain groupby needs no re-sorting -- same shape as the gear/cyberware pickers' category
    # `<details>` sections.
    vehicle_groups: list[dict[str, Any]] = [
        {
            "category": category,
            "rows": [
                {
                    "id": vehicle.id,
                    "quantity": counts.get(vehicle.id, 0),
                    "subtotal": vehicle.cost * counts.get(vehicle.id, 0),
                    **vehicle_stat_block(vehicle),
                }
                for vehicle in rows
            ],
        }
        for category, rows in itertools.groupby(VEHICLE_CATALOG, key=lambda v: v.category)
    ]
    budget = starting_nuyen(resources_letter, PRIORITIES) + display_karma_to_nuyen(karma_converted)
    spent = sum(int(row["subtotal"]) for group in vehicle_groups for row in group["rows"])
    budget_warning: str | None = None
    if error is None:
        try:
            create_vehicle_selection(
                vehicle_ids,
                VEHICLE_CATALOG,
                budget - gear_cost - lifestyle_cost - cyberware_cost - bioware_cost - foci_cost,
            )
        except ValueError as exc:
            budget_warning = (
                f"No longer fits since priorities were last confirmed: {exc}. "
                "Adjust the vehicles below to continue."
            )
    return {
        "character": character,
        "vehicle_groups": vehicle_groups,
        "vehicles_nuyen_budget": budget,
        "vehicles_nuyen_spent": spent,
        "vehicles_nuyen_remaining": (
            budget - gear_cost - lifestyle_cost - cyberware_cost - bioware_cost - foci_cost - spent
        ),
        "vehicles_error": error,
        "vehicles_budget_warning": budget_warning,
    }


def _other_section_costs(character: Character) -> tuple[int, int, int, int, int, int]:
    """`(gear, lifestyle, cyberware, bioware, foci, karma_converted)` as currently committed.

    Factored out because this section needs all five sibling spends at once (it is the last of the
    six to join the shared pool), and reading them inline would be a 12-line prelude repeated in
    both branches of the route below.
    """
    resources_selection = character.resources_selection
    lifestyle_selection = character.lifestyle_selection
    cyberware_selection = character.cyberware_selection
    bioware_selection = character.bioware_selection
    foci_selection = character.foci_selection
    return (
        resources_selection.nuyen_spent if resources_selection is not None else 0,
        lifestyle_selection.total_cost if lifestyle_selection is not None else 0,
        cyberware_selection.nuyen_spent if cyberware_selection is not None else 0,
        bioware_selection.nuyen_spent if bioware_selection is not None else 0,
        foci_selection.nuyen_cost if foci_selection is not None else 0,
        resources_selection.karma_converted if resources_selection is not None else 0,
    )


@router.post("/ui/vehicles", response_class=HTMLResponse)
async def submit_vehicles(request: Request) -> HTMLResponse:
    session, new_cookie = resolve_session(request)
    session.open_section = "vehicles"  # WP61
    if session.character is None:
        context = _vehicles_context(None, session.resources_letter, (), 0, 0, 0, 0)
    else:
        form = await request.form()
        vehicle_ids = _parse_vehicles(form, VEHICLE_CATALOG)
        gear, lifestyle, cyberware, bioware, foci, karma_converted = _other_section_costs(
            session.character
        )
        # WP66: preserve each committed Rating-priced item's chosen rating across re-validation.
        resources_selection = session.character.resources_selection
        gear_names, rating_gear = (
            resources_gear_args(resources_selection)
            if resources_selection is not None
            else ((), ())
        )
        budget = starting_nuyen(session.resources_letter, PRIORITIES) + display_karma_to_nuyen(
            karma_converted
        )
        try:
            selection = create_vehicle_selection(
                vehicle_ids,
                VEHICLE_CATALOG,
                budget - gear - lifestyle - cyberware - bioware - foci,
            )
            # Re-derive resources_selection so `nuyen_remaining` (what the character sheet and every
            # other section display) reflects the new vehicle spend -- the same fold
            # `chummer5.io.save_format.build_character` performs after resolving vehicles.
            new_resources_selection = create_resources_selection(
                session.resources_letter,
                PRIORITIES,
                gear_names,
                rating_gear=rating_gear,
                lifestyle_cost=lifestyle,
                cyberware_cost=cyberware,
                bioware_cost=bioware,
                karma_converted=karma_converted,
                foci_cost=foci,
                vehicle_cost=selection.nuyen_spent,
            )
        except ValueError as exc:
            context = _vehicles_context(
                session.character,
                session.resources_letter,
                vehicle_ids,
                gear,
                lifestyle,
                cyberware,
                bioware,
                karma_converted,
                foci,
                error=str(exc),
            )
        else:
            session.character = replace(
                session.character,
                vehicle_selection=selection,
                resources_selection=new_resources_selection,
            )
            context = _vehicles_context(
                session.character,
                session.resources_letter,
                vehicle_ids,
                gear,
                lifestyle,
                cyberware,
                bioware,
                karma_converted,
                foci,
            )
    context["open_section"] = session.open_section  # WP61
    response = templates.TemplateResponse(request, "_vehicles.html", context)
    if new_cookie is not None:
        response.set_cookie(SESSION_COOKIE_NAME, new_cookie, httponly=True, samesite="lax")
    return response
