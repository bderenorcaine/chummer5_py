"""Cyberware+Bioware chargen step: `POST /ui/cyberware` (WP34, widened by WP45).

**WP62**: split out of the former `chummer5.web.app` -- see `spec/plan/phase-r-architecture-
cleanup.md`'s WP58 audit for the target shape this module is part of.
"""

from __future__ import annotations

import itertools
from collections.abc import Iterable
from dataclasses import replace
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from starlette.datastructures import FormData

from chummer5.data.bioware import Bioware
from chummer5.data.cyberware import Cyberware
from chummer5.engine.bioware import (
    BiowareSelection,
    apply_bioware_improvements,
    create_bioware_selection,
)
from chummer5.engine.character import Character
from chummer5.engine.cyberware import (
    CyberwareSelection,
    apply_cyberware_improvements,
    create_cyberware_selection,
)
from chummer5.engine.derived import BASE_ESSENCE
from chummer5.engine.improvements import ImprovementSource
from chummer5.engine.resources import available_nuyen, create_resources_selection, starting_nuyen
from chummer5.web.catalogs import BIOWARE, CYBERWARE, PRIORITIES, templates
from chummer5.web.forms import display_karma_to_nuyen
from chummer5.web.session import SESSION_COOKIE_NAME, resolve_session

router = APIRouter()

# Sorted by (category, name) for the picker's category-grouped `<details>` sections, mirroring
# `STARTER_GEAR_CATALOG`'s own sort -- unlike that catalog, `load_cyberware()`'s XML-document order
# already groups most categories consecutively but not perfectly (Cyber Implant Weapon and Cyber
# Implant Weapon Accessory interleave at the end of the file), so a plain `itertools.groupby` over
# `CYBERWARE` directly would produce spurious duplicate groups. Computed once at import time, not
# per-request.
_CYBERWARE_BY_CATEGORY = tuple(sorted(CYBERWARE, key=lambda item: (item.category, item.name)))
# Same reasoning, applied to WP45's much smaller bioware catalog (2 categories, Basic/Cultured).
_BIOWARE_BY_CATEGORY = tuple(sorted(BIOWARE, key=lambda item: (item.category, item.name)))


def _replace_committed_cyberware(character: Character, selection: CyberwareSelection) -> Character:
    """Swap whatever `CYBERWARE`-sourced Improvements `character.improvements` currently holds for
    `selection`'s, and re-attach `selection` as `character.cyberware_selection` -- mirrors
    `chummer5.web.routes.qualities._replace_committed_qualities`'s identical shape, with one
    difference: removes by each *distinct* previously-purchased item id, not once per purchased
    unit. `ImprovementIndex.remove_source` already retracts every Improvement a given source id
    granted at once, and a repeated purchase of the same item shares one `source_id` (the item's
    own catalog id -- see `chummer5.engine.cyberware`'s own "duplicate purchases share one
    source_id" docstring), so removing that id once already clears every copy.
    """
    if character.cyberware_selection is not None:
        for item_id in {item.id for item in character.cyberware_selection.items}:
            character.improvements.remove_source(ImprovementSource.CYBERWARE, item_id)
    apply_cyberware_improvements(character, selection)
    return replace(character, cyberware_selection=selection)


def _replace_committed_bioware(character: Character, selection: BiowareSelection) -> Character:
    """Swap whatever `BIOWARE`-sourced Improvements `character.improvements` currently holds for
    `selection`'s, and re-attach `selection` as `character.bioware_selection` -- mirrors
    `_replace_committed_cyberware`'s identical shape, including removing by each *distinct*
    previously-purchased item id rather than once per purchased unit.
    """
    if character.bioware_selection is not None:
        for item_id in {item.id for item in character.bioware_selection.items}:
            character.improvements.remove_source(ImprovementSource.BIOWARE, item_id)
    apply_bioware_improvements(character, selection)
    return replace(character, bioware_selection=selection)


def _parse_cyberware(form: FormData, catalog: Iterable[Cyberware]) -> tuple[str, ...]:
    """Expand each cyberware item's submitted quantity into that many repeats of its id -- mirrors
    `chummer5.web.routes.resources._parse_gear`'s identical shape, keyed by catalog id (not name):
    `create_cyberware_selection`'s own `item_ids` parameter takes ids, and repeats are legal
    purchases (a matched pair of cyberlimbs -- see `chummer5.engine.cyberware`'s module docstring),
    not an error to reject.
    """
    ids: list[str] = []
    for item in catalog:
        raw = form.get(f"cyberware_{item.id}")
        try:
            quantity = int(str(raw)) if raw is not None else 0
        except ValueError:
            quantity = 0
        ids.extend([item.id] * max(quantity, 0))
    return tuple(ids)


def _parse_bioware(form: FormData, catalog: Iterable[Bioware]) -> tuple[str, ...]:
    """Expand each bioware item's submitted quantity into that many repeats of its id -- mirrors
    `_parse_cyberware`'s identical shape, keyed by `bioware_{id}` form fields instead of
    `cyberware_{id}` ones.
    """
    ids: list[str] = []
    for item in catalog:
        raw = form.get(f"bioware_{item.id}")
        try:
            quantity = int(str(raw)) if raw is not None else 0
        except ValueError:
            quantity = 0
        ids.extend([item.id] * max(quantity, 0))
    return tuple(ids)


def _catalog_groups(
    item_ids: tuple[str, ...],
    catalog_by_category: tuple[Any, ...],
    by_id: dict[str, Any],
) -> list[dict[str, Any]]:
    """Build category-grouped `<details>` rows for a quantity-per-item picker -- shared by the
    cyberware and bioware halves of `_cyberware_context` (WP45), mirroring
    `chummer5.web.routes.resources._resources_context`'s WP21 shape.
    """
    counts: dict[str, int] = {}
    for item_id in item_ids:
        counts[item_id] = counts.get(item_id, 0) + 1
    return [
        {
            "category": category,
            "rows": [
                {
                    "item": item,
                    "quantity": counts.get(item.id, 0),
                    "subtotal": item.cost * counts.get(item.id, 0),
                }
                for item in items
            ],
        }
        for category, items in itertools.groupby(
            catalog_by_category, key=lambda item: item.category
        )
    ]


def _cyberware_context(
    character: Character | None,
    resources_letter: str,
    item_ids: tuple[str, ...],
    bioware_item_ids: tuple[str, ...],
    gear_cost: int,
    lifestyle_cost: int,
    karma_converted: int = 0,
    foci_cost: int = 0,
    *,
    error: str | None = None,
) -> dict[str, Any]:
    """Context for `_cyberware.html` (WP34, widened by WP45): Phase J's cyberware purchase, plus
    Phase L's bioware purchase folded into the same section.

    **A new peer section, not folded into `_resources.html`'s gear picker** -- mirrors WP20's own
    explicit "Lifestyle gets its own section despite sharing a budget" choice (see that WP's
    worklog for the full reasoning). SR5 frames "buy gear" and "install cyberware/bioware" as
    distinct chargen decisions with different validation rules (an Essence floor here, not just a
    nuyen cap), and cramming these catalogs into `_resources_context` would make that one context
    builder responsible for unrelated catalogs. Shares the same Resources-priority nuyen budget as
    gear/Lifestyle though -- `gear_cost`/`lifestyle_cost` are those two sections' currently-
    committed spend, threaded through the same cross-section wiring `_resources_context`/
    `_lifestyle_context` already use for each other (see their docstrings). **WP43** adds
    `karma_converted` the same way, topping up the budget rather than spending from it. **WP47**
    adds `foci_cost` the same way, extending the shared budget to five sections.

    **WP45: bioware folds into this same section rather than getting its own** -- unlike Lifestyle
    (its own distinct rulebook chargen step), the rulebook's own Step Six groups "Cyberware and
    Bioware" as one combined subsection (see `chummer5.engine.cyberware`'s module docstring for the
    citation), both catalogs are tiny/near-identical in shape (nuyen + Essence, no other validation
    rule), and they share one Essence pool that has to be checked jointly regardless -- cramming a
    second, near-duplicate section into the UI would only fragment one shared decision. Evaluation
    order is fixed and documented in `chummer5.engine.bioware`'s module docstring: cyberware is
    resolved first (unaware of bioware), bioware second (aware of cyberware's own nuyen/Essence
    spend) -- so a combination only invalid once both are counted together is always caught, on the
    bioware call.

    Same `error`-gated re-validation pattern as `_resources_context`/`_lifestyle_context`: when
    `error` is unset, re-derives whether the currently-selected items still fit the combined budget
    (and the shared Essence floor `create_cyberware_selection`/`create_bioware_selection` enforce),
    surfacing a distinct `cyberware_budget_warning` rather than silently going over/under on the
    next render.
    """
    if character is None:
        return {"character": None, "cyberware_error": error}
    cyberware_by_id = {item.id: item for item in CYBERWARE}
    bioware_by_id = {item.id: item for item in BIOWARE}
    cyberware_groups = _catalog_groups(item_ids, _CYBERWARE_BY_CATEGORY, cyberware_by_id)
    bioware_groups = _catalog_groups(bioware_item_ids, _BIOWARE_BY_CATEGORY, bioware_by_id)
    budget = starting_nuyen(resources_letter, PRIORITIES) + display_karma_to_nuyen(karma_converted)
    nuyen_available = budget - gear_cost - lifestyle_cost - foci_cost
    cyberware_spent = sum(
        int(row["subtotal"]) for group in cyberware_groups for row in group["rows"]
    )
    bioware_spent = sum(int(row["subtotal"]) for group in bioware_groups for row in group["rows"])
    spent = cyberware_spent + bioware_spent
    cyberware_essence_spent = sum(
        (cyberware_by_id[item_id].essence_cost for item_id in item_ids), Decimal(0)
    )
    bioware_essence_spent = sum(
        (bioware_by_id[item_id].essence_cost for item_id in bioware_item_ids), Decimal(0)
    )
    essence_spent = cyberware_essence_spent + bioware_essence_spent
    budget_warning: str | None = None
    if error is None:
        try:
            cyberware_selection = create_cyberware_selection(item_ids, CYBERWARE, nuyen_available)
            create_bioware_selection(
                bioware_item_ids,
                BIOWARE,
                nuyen_available - cyberware_selection.nuyen_spent,
                other_essence_spent=cyberware_selection.essence_spent,
            )
        except ValueError as exc:
            budget_warning = (
                f"No longer fits since priorities were last confirmed: {exc}. "
                "Adjust cyberware/bioware below to continue."
            )
    return {
        "character": character,
        "cyberware_groups": cyberware_groups,
        "bioware_groups": bioware_groups,
        "nuyen_available": nuyen_available,
        "nuyen_spent": spent,
        "nuyen_remaining": nuyen_available - spent,
        "essence_spent": essence_spent,
        "essence_remaining": BASE_ESSENCE - essence_spent,
        "cyberware_error": error,
        "cyberware_budget_warning": budget_warning,
    }


@router.post("/ui/cyberware", response_class=HTMLResponse)
async def submit_cyberware(request: Request) -> HTMLResponse:
    session, new_cookie = resolve_session(request)
    session.open_section = "cyberware"  # WP61
    if session.character is None:
        context = _cyberware_context(None, session.resources_letter, (), (), 0, 0, 0)
    else:
        form = await request.form()
        item_ids = _parse_cyberware(form, CYBERWARE)
        bioware_item_ids = _parse_bioware(form, BIOWARE)
        resources_selection = session.character.resources_selection
        gear_names = (
            tuple(item.name for item in resources_selection.gear)
            if resources_selection is not None
            else ()
        )
        gear_cost = resources_selection.nuyen_spent if resources_selection is not None else 0
        karma_converted = (
            resources_selection.karma_converted if resources_selection is not None else 0
        )
        lifestyle_selection = session.character.lifestyle_selection
        lifestyle_cost = (
            lifestyle_selection.total_cost if lifestyle_selection is not None else 0
        )
        # WP47: Foci's own committed nuyen cost shares this same pool now too.
        foci_selection = session.character.foci_selection
        foci_cost = foci_selection.nuyen_cost if foci_selection is not None else 0
        nuyen_available = available_nuyen(
            session.resources_letter, PRIORITIES, karma_converted
        ) - (gear_cost + lifestyle_cost + foci_cost)
        try:
            # Fixed evaluation order (chummer5.engine.bioware's own docstring): cyberware
            # first, unaware of bioware; bioware second, aware of cyberware's own nuyen/Essence
            # spend -- so a combination only invalid once both are counted together is always
            # caught, on the bioware call.
            selection = create_cyberware_selection(item_ids, CYBERWARE, nuyen_available)
            bioware_selection = create_bioware_selection(
                bioware_item_ids,
                BIOWARE,
                nuyen_available - selection.nuyen_spent,
                other_essence_spent=selection.essence_spent,
            )
            new_resources_selection = create_resources_selection(
                session.resources_letter,
                PRIORITIES,
                gear_names,
                lifestyle_cost=lifestyle_cost,
                cyberware_cost=selection.nuyen_spent,
                bioware_cost=bioware_selection.nuyen_spent,
                karma_converted=karma_converted,
                foci_cost=foci_cost,
            )
        except ValueError as exc:
            context = _cyberware_context(
                session.character,
                session.resources_letter,
                item_ids,
                bioware_item_ids,
                gear_cost,
                lifestyle_cost,
                karma_converted,
                foci_cost,
                error=str(exc),
            )
        else:
            session.character = _replace_committed_cyberware(session.character, selection)
            session.character = _replace_committed_bioware(session.character, bioware_selection)
            session.character = replace(
                session.character, resources_selection=new_resources_selection
            )
            context = _cyberware_context(
                session.character,
                session.resources_letter,
                item_ids,
                bioware_item_ids,
                gear_cost,
                lifestyle_cost,
                karma_converted,
                foci_cost,
            )
    context["open_section"] = session.open_section  # WP61
    response = templates.TemplateResponse(request, "_cyberware.html", context)
    if new_cookie is not None:
        response.set_cookie(SESSION_COOKIE_NAME, new_cookie, httponly=True, samesite="lax")
    return response
