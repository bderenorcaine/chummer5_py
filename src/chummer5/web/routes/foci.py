"""Foci chargen step: `POST /ui/foci` (WP47), gated to any magic-active character.

**WP62**: split out of the former `chummer5.web.app` -- see `spec/plan/phase-r-architecture-
cleanup.md`'s WP58 audit for the target shape this module is part of.
"""

from __future__ import annotations

import itertools
from collections.abc import Iterable
from dataclasses import replace
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from starlette.datastructures import FormData

from chummer5.data.foci import Focus
from chummer5.engine.character import Character
from chummer5.engine.foci import (
    CHARGEN_FORCE_CAP_MULTIPLIER,
    FociSelection,
    apply_foci_improvements,
    create_foci_selection,
)
from chummer5.engine.improvements import ImprovementSource
from chummer5.engine.resources import available_nuyen, create_resources_selection, starting_nuyen
from chummer5.web.catalogs import FOCI, PRIORITIES, templates
from chummer5.web.forms import display_karma_to_nuyen
from chummer5.web.session import SESSION_COOKIE_NAME, resolve_session

router = APIRouter()

# Sorted by (category, name) for the picker's category-grouped `<details>` sections, mirroring
# `STARTER_GEAR_CATALOG`'s own sort. Applied to WP47's Foci catalog (7 rulebook categories, not a
# gear.xml field -- see `chummer5.data.foci`'s own docstring for how `focus_category` is derived).
_FOCI_BY_CATEGORY = tuple(sorted(FOCI, key=lambda item: (item.focus_category, item.name)))


def _replace_committed_foci(character: Character, selection: FociSelection) -> Character:
    """Swap whatever `FOCUS`-sourced Improvements `character.improvements` currently holds for
    `selection`'s, and re-attach `selection` as `character.foci_selection` -- mirrors
    `chummer5.web.routes.cyberware._replace_committed_cyberware`'s identical shape, including
    removing by each *distinct* previously-bonded item id rather than once per bonded unit.
    """
    if character.foci_selection is not None:
        for item_id in {pick.focus.id for pick in character.foci_selection.picks}:
            character.improvements.remove_source(ImprovementSource.FOCUS, item_id)
    apply_foci_improvements(character, selection)
    return replace(character, foci_selection=selection)


def _remove_foci_improvements(character: Character) -> None:
    """Retract every `FOCUS`-sourced Improvement -- mirrors
    `chummer5.web.routes.powers._remove_adept_power_improvements`'s identical shape, used by
    `chummer5.web.routes.talent._replace_committed_talent` (a Talent change invalidates whatever
    Magic-rating-dependent Foci selection was already committed, the same reasoning that WP applies
    to `bound_spirit_selection`/`power_selection`).
    """
    if character.foci_selection is None:
        return
    for item_id in {pick.focus.id for pick in character.foci_selection.picks}:
        character.improvements.remove_source(ImprovementSource.FOCUS, item_id)


def _parse_foci(form: FormData, catalog: Iterable[Focus]) -> tuple[tuple[str, int], ...]:
    """Read a submitted Force per Foci catalog item into `(focus_id, force)` pairs -- unlike
    `chummer5.web.routes.cyberware._parse_cyberware`/`_parse_bioware`'s quantity-per-item shape,
    this UI offers at most one bonded pick per catalog item (Force 0 means "not bonded"), a
    deliberate simplification: no real fixture exercises `create_foci_selection`'s own "bond two of
    the same item" allowance, and a quantity-of-Force-N picker would need a second dimension (how
    many, at what Force each) no other section's UI has needed yet. An unparseable or non-positive
    Force is treated as "not bonded", the same robustness clamp
    `chummer5.web.routes.resources._parse_gear` already applies to a bad quantity.
    """
    picks: list[tuple[str, int]] = []
    for item in catalog:
        raw = form.get(f"focus_force_{item.id}")
        try:
            force = int(str(raw)) if raw is not None else 0
        except ValueError:
            force = 0
        if force > 0:
            picks.append((item.id, force))
    return tuple(picks)


def _foci_selection_context(
    character: Character | None,
    resources_letter: str,
    picks: Iterable[tuple[str, int]],
    gear_cost: int,
    lifestyle_cost: int,
    cyberware_cost: int,
    bioware_cost: int,
    karma_converted: int = 0,
    *,
    error: str | None = None,
) -> dict[str, Any]:
    """Context for `_foci_selection.html` (WP47): `create_foci_selection` reaching the browser,
    gated to any magic-active character (Magician or Adept -- see `chummer5.engine.foci`'s own
    docstring for why this is looser than Bound Spirits' Magician-only gate). `picks` is whatever
    should be shown filled in, the same echo-the-submission shape as
    `chummer5.web.routes.spirits._spirit_selection_context`'s `picks`.

    **Nuyen**: shares the same Step Six pool gear/Lifestyle/cyberware/bioware already draw from --
    `gear_cost`/`lifestyle_cost`/`cyberware_cost`/`bioware_cost` are those sections' currently
    committed spend, the same cross-section wiring
    `chummer5.web.routes.cyberware._cyberware_context` already uses for its own four terms, now
    extended to five.

    **Karma**: `karma_budget` is `character.karma_remaining` (WP51's unified ledger) with Foci's own
    currently-committed cost added back in -- the same "exclude this section's own prior
    commitment" shape `_spirit_selection_context`'s own `karma_budget` uses, mirrored here. Bound
    Spirits' current commitment is read directly off `character.bound_spirit_selection` (part of
    `karma_remaining`'s own sum) rather than threaded through as a parameter, the same
    simplification WP51 made possible on the Bound Spirits side.

    **WP19-style staleness re-validation**: when `error` is unset and a Foci selection is already
    committed, re-runs `create_foci_selection` against the *current* character/budgets purely to
    derive `foci_budget_warning` -- an attribute edit (MAG) or a Talent change can each shrink what
    was previously a valid selection.
    """
    if character is None:
        return {"character": None, "foci_error": error}
    if character.magic_type is None:
        return {"character": character, "foci_error": error}

    entries = list(picks)
    by_id = {item.id: item for item in FOCI}
    force_by_id = dict(entries)
    foci_groups = [
        {
            "category": category,
            "rows": [
                {
                    "item": item,
                    "force": force_by_id.get(item.id, 0),
                    "subtotal": force_by_id.get(item.id, 0) * item.cost_per_force,
                }
                for item in items
            ],
        }
        for category, items in itertools.groupby(
            _FOCI_BY_CATEGORY, key=lambda item: item.focus_category
        )
    ]

    nuyen_available = (
        starting_nuyen(resources_letter, PRIORITIES)
        + display_karma_to_nuyen(karma_converted)
        - gear_cost
        - lifestyle_cost
        - cyberware_cost
        - bioware_cost
    )
    nuyen_spent = sum(int(row["subtotal"]) for group in foci_groups for row in group["rows"])
    own_committed_cost = (
        character.foci_selection.karma_cost if character.foci_selection is not None else 0
    )
    karma_budget = character.karma_remaining + own_committed_cost
    karma_spent = sum(
        force * by_id[focus_id].bonding_karma_per_force for focus_id, force in entries
    )
    budget_warning: str | None = None
    if error is None:
        try:
            create_foci_selection(entries, character, FOCI, nuyen_available, karma_budget)
        except ValueError as exc:
            budget_warning = (
                f"No longer fits since priorities/attributes were last confirmed: {exc}. "
                "Adjust Foci below to continue."
            )
    return {
        "character": character,
        "foci_groups": foci_groups,
        "foci_nuyen_available": nuyen_available,
        "foci_nuyen_spent": nuyen_spent,
        "foci_nuyen_remaining": nuyen_available - nuyen_spent,
        "foci_karma_budget": karma_budget,
        "foci_karma_spent": karma_spent,
        "foci_karma_remaining": karma_budget - karma_spent,
        "foci_max_count": character.attribute_value("MAG"),
        "foci_max_total_force": character.attribute_value("MAG") * CHARGEN_FORCE_CAP_MULTIPLIER,
        "foci_error": error,
        "foci_budget_warning": budget_warning,
    }


@router.post("/ui/foci", response_class=HTMLResponse)
async def submit_foci(request: Request) -> HTMLResponse:
    session, new_cookie = resolve_session(request)
    session.open_section = "foci-selection"  # WP61
    if session.character is None or session.character.magic_type is None:
        context = _foci_selection_context(
            session.character, session.resources_letter, (), 0, 0, 0, 0
        )
    else:
        form = await request.form()
        picks = _parse_foci(form, FOCI)
        character = session.character
        resources_selection = character.resources_selection
        gear_cost = resources_selection.nuyen_spent if resources_selection is not None else 0
        karma_converted = (
            resources_selection.karma_converted if resources_selection is not None else 0
        )
        lifestyle_selection = character.lifestyle_selection
        lifestyle_cost = (
            lifestyle_selection.total_cost if lifestyle_selection is not None else 0
        )
        cyberware_selection = character.cyberware_selection
        cyberware_cost = (
            cyberware_selection.nuyen_spent if cyberware_selection is not None else 0
        )
        bioware_selection = character.bioware_selection
        bioware_cost = bioware_selection.nuyen_spent if bioware_selection is not None else 0
        nuyen_available = available_nuyen(
            session.resources_letter, PRIORITIES, karma_converted
        ) - (gear_cost + lifestyle_cost + cyberware_cost + bioware_cost)
        # WP51: budget excludes Foci's own currently-committed cost (about to be replaced by
        # this submission) -- see _foci_selection_context's own docstring for why this is
        # `karma_remaining` with that one term added back in.
        own_committed_cost = (
            character.foci_selection.karma_cost if character.foci_selection is not None else 0
        )
        karma_budget = character.karma_remaining + own_committed_cost
        try:
            selection = create_foci_selection(
                picks, character, FOCI, nuyen_available, karma_budget
            )
            new_resources_selection = create_resources_selection(
                session.resources_letter,
                PRIORITIES,
                tuple(
                    item.name
                    for item in (
                        resources_selection.gear if resources_selection is not None else ()
                    )
                ),
                lifestyle_cost=lifestyle_cost,
                cyberware_cost=cyberware_cost,
                bioware_cost=bioware_cost,
                karma_converted=karma_converted,
                foci_cost=selection.nuyen_cost,
            )
        except ValueError as exc:
            context = _foci_selection_context(
                character,
                session.resources_letter,
                picks,
                gear_cost,
                lifestyle_cost,
                cyberware_cost,
                bioware_cost,
                karma_converted,
                error=str(exc),
            )
        else:
            session.character = _replace_committed_foci(character, selection)
            session.character = replace(
                session.character, resources_selection=new_resources_selection
            )
            context = _foci_selection_context(
                session.character,
                session.resources_letter,
                picks,
                gear_cost,
                lifestyle_cost,
                cyberware_cost,
                bioware_cost,
                karma_converted,
            )
    context["open_section"] = session.open_section  # WP61
    response = templates.TemplateResponse(request, "_foci_selection.html", context)
    if new_cookie is not None:
        response.set_cookie(SESSION_COOKIE_NAME, new_cookie, httponly=True, samesite="lax")
    return response
