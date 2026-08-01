"""Cyberware+Bioware chargen step: `POST /ui/cyberware` (WP34, widened by WP45 and WP42).

**WP62**: split out of the former `chummer5.web.app` -- see `spec/plan/phase-r-architecture-
cleanup.md`'s WP58 audit for the target shape this module is part of.

**WP41 retyped what this route commits; WP42 widens what it offers.**
`Character.cyberware_selection` has been Phase K's purchase *tree*
(`chummer5.engine.cyberware_subsystems.CyberwareTreeSelection`) since WP41, but the picker stayed
WP34's flat quantity-per-item form over `CYBERWARE` (WP31's 60 flat rows), so every tree the
browser built was a set of zero-plugin, rating-1 leaves. WP42 is the UI half of Phase K:

1. **The offered catalog is `CYBERWARE_STANDALONE`** (76 of WP37's 87 SR5 rows -- see
   `chummer5.web.catalogs` for the two exclusions and the 9 `<requireparent>` rows moved into their
   parents), so rating-scaled items are purchasable at last. `Cybereyes Basic System` and
   `Cyberears` in particular were unreachable before, which meant *no* subsystem parent with a real
   Capacity budget except a cyberlimb.
2. **A rating control per purchased unit**, over exactly the range
   `cyberware_rating_bounds` resolves -- so the form cannot offer a rating the engine then rejects.
3. **A plugin checklist per purchased parent**, with that parent's Capacity spend/remaining shown
   beside it and re-rendered on every change (the section already re-posts itself on `change`, so
   "live" needs no new JS -- the same mechanism WP15's remaining-points display uses).

## The form shape, and why it is indexed per bought unit

`cyberware_{item_id}` keeps its WP34 meaning (a quantity), so a purchase is still "how many of
this row." Everything per-unit hangs off that count by index, mirroring WP80's
`bioware_skill_{id}_{n}` shape exactly:

- `cyberware_rating_{item_id}_{n}` -- the n-th bought unit's rating (absent/blank -> its minimum).
- `plugin_{item_id}_{n}_{plugin_id}` -- a checkbox: install this plugin in that unit.
- `plugin_rating_{item_id}_{n}_{plugin_id}` -- that plugin's own rating.

**A plugin is a checkbox, not a quantity box**, which is the one place this UI is narrower than the
engine: `create_cyberware_tree_selection` would accept two of the same row in one parent outside the
`Cyberlimb Enhancement` category. Deliberate -- SR5's own p. 456 rule forbids the stacking case that
matters, nothing in the core set benefits from a second copy in one limb, and a quantity box would
need a fourth index level (a rating per copy) for no gain. The one consequence, recorded rather than
hidden: a legacy-imported character carrying two identical plugins in one parent renders as one
checked box, so re-submitting the form drops the duplicate. No fixture does this.
"""

from __future__ import annotations

import itertools
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import replace
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from starlette.datastructures import FormData

from chummer5.data.bioware import Bioware
from chummer5.data.cyberware_subsystems import CyberwareEntry
from chummer5.engine.bioware import (
    BiowarePurchaseRequest,
    BiowareSelection,
    apply_bioware_improvements,
    create_bioware_selection,
    select_skill_choices,
)
from chummer5.engine.character import Character
from chummer5.engine.cyberware_subsystems import (
    CyberwarePurchaseRequest,
    CyberwareTreeSelection,
    apply_cyberware_tree_improvements,
    create_cyberware_tree_selection,
    cyberlimb_attribute_maximums,
    cyberware_rating_bounds,
)
from chummer5.engine.derived import BASE_ESSENCE
from chummer5.engine.improvements import ImprovementSource
from chummer5.engine.resources import (
    available_nuyen,
    create_resources_selection,
    resources_gear_args,
    starting_nuyen,
)
from chummer5.web.catalogs import (
    BIOWARE,
    CYBERWARE_ENTRIES,
    CYBERWARE_PLUGIN_CHOICES,
    CYBERWARE_STANDALONE,
    PRIORITIES,
    SKILLS,
    templates,
)
from chummer5.web.forms import display_karma_to_nuyen
from chummer5.web.session import SESSION_COOKIE_NAME, resolve_session

router = APIRouter()

# WP42: `CYBERWARE_STANDALONE` is already sorted by (category, name) for the picker's
# category-grouped `<details>` sections -- see `chummer5.web.catalogs`, and note the sort is
# load-bearing rather than cosmetic: `cyberware.xml`'s document order groups most categories
# consecutively but not perfectly (Cyber Implant Weapon and Cyber Implant Weapon Accessory
# interleave at the end of the file), so `itertools.groupby` over the raw order would produce
# spurious duplicate groups.
#
# The same reasoning, applied to WP45's much smaller bioware catalog (2 categories, Basic/Cultured),
# which still needs its sort done here because `chummer5.web.catalogs` keeps it in document order.
_BIOWARE_BY_CATEGORY = tuple(sorted(BIOWARE, key=lambda item: (item.category, item.name)))
# WP80: the skills each SELECT_SKILL row's purchase-time pick may come from (`Reflex Recorder` is
# the only such row today: the 28 active skills linked to BOD/AGI/REA/STR). Computed once at import
# time like the two sorts above -- it depends only on static catalogs, never on the character.
_BIOWARE_SKILL_CHOICES = {
    item.id: select_skill_choices(item, SKILLS)
    for item in BIOWARE
    if item.select_skill_bonus is not None
}


def _replace_committed_cyberware(
    character: Character, selection: CyberwareTreeSelection
) -> Character:
    """Swap whatever `CYBERWARE`-sourced Improvements `character.improvements` currently holds for
    `selection`'s, and re-attach `selection` as `character.cyberware_selection` -- mirrors
    `chummer5.web.routes.qualities._replace_committed_qualities`'s identical shape, with one
    difference: removes by each *distinct* previously-purchased item id, not once per purchased
    unit. `ImprovementIndex.remove_source` already retracts every Improvement a given source id
    granted at once, and a repeated purchase of the same item shares one `source_id` (the item's
    own catalog id -- see `chummer5.engine.cyberware_subsystems
    .apply_cyberware_tree_improvements`'s own docstring), so removing that id once already clears
    every copy. **WP41**: `walk()`, not the old flat `items` -- a plugin's own Improvements are
    sourced by its own id, so a parent's id alone would leave them behind.
    """
    if character.cyberware_selection is not None:
        for item_id in {node.item.id for node in character.cyberware_selection.walk()}:
            character.improvements.remove_source(ImprovementSource.CYBERWARE, item_id)
    apply_cyberware_tree_improvements(character, selection)
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


def _form_int(form: FormData, key: str) -> int | None:
    """A submitted integer field, or `None` for absent/blank/non-numeric -- the caller decides what
    the absence means (a quantity of 0, or an item's minimum rating).
    """
    raw = form.get(key)
    if raw is None:
        return None
    try:
        return int(str(raw))
    except ValueError:
        return None


def _rating_range(
    item: CyberwareEntry, attribute_maximums: Mapping[str, int]
) -> tuple[int, int] | None:
    """The rating range to offer for `item`, or `None` when it has no rating to pick.

    `None` covers both an unrated row (`cyberware_rating_bounds` gives `(1, 1)`) and the degenerate
    single-value range, so the template renders a control only where there is a choice.
    """
    minimum, maximum = cyberware_rating_bounds(item, attribute_maximums=attribute_maximums)
    return None if minimum >= maximum else (minimum, maximum)


def _parse_cyberware(
    form: FormData, *, attribute_maximums: Mapping[str, int]
) -> tuple[CyberwarePurchaseRequest, ...]:
    """Read the picker form into a purchase *tree* (WP42; WP34 read it into a flat id list).

    Quantity per catalog row as before -- repeats are legal purchases (a matched pair of cyberlimbs,
    see `chummer5.engine.cyberware_subsystems`' module docstring), not an error -- then each bought
    unit's own rating and plugin picks by index. See the module docstring for the three field names
    and for why a plugin is a checkbox rather than a quantity.

    Ratings default to the item's *minimum*, not to 1: `Customized Agility`'s floor is 4
    (`{AGIMinimum}+1`, p. 456), so 1 would be an instant rejection rather than a sane default.
    """
    requests: list[CyberwarePurchaseRequest] = []
    for item in CYBERWARE_STANDALONE:
        quantity = max(_form_int(form, f"cyberware_{item.id}") or 0, 0)
        for index in range(quantity):
            requests.append(
                CyberwarePurchaseRequest(
                    item_id=item.id,
                    rating=_parse_rating(
                        form, f"cyberware_rating_{item.id}_{index}", item, attribute_maximums
                    ),
                    plugins=_parse_plugins(form, item, index, attribute_maximums),
                )
            )
    return tuple(requests)


def _parse_rating(
    form: FormData,
    key: str,
    item: CyberwareEntry,
    attribute_maximums: Mapping[str, int],
) -> int:
    minimum, _ = cyberware_rating_bounds(item, attribute_maximums=attribute_maximums)
    submitted = _form_int(form, key)
    return minimum if submitted is None else submitted


def _parse_plugins(
    form: FormData,
    parent: CyberwareEntry,
    index: int,
    attribute_maximums: Mapping[str, int],
) -> tuple[CyberwarePurchaseRequest, ...]:
    """The plugins checked for the `index`-th bought unit of `parent`.

    A row `CYBERWARE_PLUGIN_CHOICES` doesn't list for this parent is simply not iterated, so a
    hand-crafted request naming an ineligible plugin is ignored here rather than reaching the engine
    -- the same "unknown keys are just not in the catalog to iterate" shape `_parse_gear` has.
    """
    return tuple(
        CyberwarePurchaseRequest(
            item_id=plugin.id,
            rating=_parse_rating(
                form,
                f"plugin_rating_{parent.id}_{index}_{plugin.id}",
                plugin,
                attribute_maximums,
            ),
        )
        for plugin in CYBERWARE_PLUGIN_CHOICES.get(parent.id, ())
        if form.get(f"plugin_{parent.id}_{index}_{plugin.id}") is not None
    )


def _parse_bioware(
    form: FormData, catalog: Iterable[Bioware]
) -> tuple[BiowarePurchaseRequest, ...]:
    """Expand each bioware item's submitted quantity into that many purchase requests -- mirrors
    `_parse_cyberware`'s identical shape, keyed by `bioware_{id}` form fields instead of
    `cyberware_{id}` ones.

    **WP80**: a row that needs a purchase-time skill pick (`Reflex Recorder`) submits one
    `bioware_skill_{id}_{n}` field per bought unit, `n` counting from 0 -- so buying two really is
    two independent picks, which is what SR5 asks for (p. 460). A missing/blank field becomes
    `None` and is rejected by `create_bioware_selection` with the same message a tampered one would
    get, rather than being silently defaulted to some skill the player never chose.
    """
    requests: list[BiowarePurchaseRequest] = []
    for item in catalog:
        raw = form.get(f"bioware_{item.id}")
        try:
            quantity = int(str(raw)) if raw is not None else 0
        except ValueError:
            quantity = 0
        for index in range(max(quantity, 0)):
            chosen = (
                form.get(f"bioware_skill_{item.id}_{index}")
                if item.select_skill_bonus is not None
                else None
            )
            requests.append(
                BiowarePurchaseRequest(
                    item_id=item.id,
                    chosen_skill=str(chosen) if chosen else None,
                )
            )
    return tuple(requests)


def _cyberware_groups(
    requests: Sequence[CyberwarePurchaseRequest], attribute_maximums: Mapping[str, int]
) -> list[dict[str, Any]]:
    """Category-grouped picker rows for the cyberware half (WP42).

    Each row carries its quantity as before, plus one `units` entry per bought copy holding that
    copy's own rating control, resolved prices and -- for a parent with a real Capacity budget --
    its plugin checklist and live Capacity spend. Costs are resolved here rather than read off the
    validated `CyberwareTreeSelection`, for the same reason WP34's own tally was computed
    independently: this has to render the *rejected* state too (an over-budget spend, an
    over-capacity limb), which is exactly when no selection exists to read from.
    """
    units_by_item: dict[str, list[CyberwarePurchaseRequest]] = {}
    for request in requests:
        units_by_item.setdefault(request.item_id, []).append(request)
    return [
        {
            "category": category,
            "rows": [
                _cyberware_row(item, units_by_item.get(item.id, []), attribute_maximums)
                for item in items
            ],
        }
        for category, items in itertools.groupby(
            CYBERWARE_STANDALONE, key=lambda item: item.category
        )
    ]


def _cyberware_row(
    item: CyberwareEntry,
    units: Sequence[CyberwarePurchaseRequest],
    attribute_maximums: Mapping[str, int],
) -> dict[str, Any]:
    unit_rows = [
        _cyberware_unit_row(item, index, request, attribute_maximums)
        for index, request in enumerate(units)
    ]
    return {
        "item": item,
        "quantity": len(unit_rows),
        "units": unit_rows,
        "subtotal": sum(unit["subtotal"] for unit in unit_rows),
        "essence": sum((unit["essence"] for unit in unit_rows), Decimal(0)),
    }


def _cyberware_unit_row(
    item: CyberwareEntry,
    index: int,
    request: CyberwarePurchaseRequest,
    attribute_maximums: Mapping[str, int],
) -> dict[str, Any]:
    """One bought copy of one catalog row: its rating control, its own prices, and its subsystems.

    `capacity_budget` decides whether a subsystem block is offered at all -- a `Cyber Implant
    Weapon` carries `<allowsubsystems>` yet a purely bracketed `<capacity>`, i.e. a budget of zero
    (WP37/WP38's third-nesting-level cut), so offering its 3 accessories could only ever produce
    "exceeds its Capacity budget of 0".
    """
    minimum, _ = cyberware_rating_bounds(item, attribute_maximums=attribute_maximums)
    rating = request.rating
    budget = (
        item.capacity_budget.resolve(rating=rating, min_rating=minimum)
        if item.capacity_budget is not None
        else Decimal(0)
    )
    installed = {plugin.item_id: plugin for plugin in request.plugins}
    plugin_rows = (
        [
            _plugin_row(item, index, plugin, installed.get(plugin.id), attribute_maximums)
            for plugin in CYBERWARE_PLUGIN_CHOICES.get(item.id, ())
        ]
        if budget > 0
        else []
    )
    spent = sum(
        (row["capacity_cost"] for row in plugin_rows if row["selected"]),
        Decimal(0),
    )
    nuyen_cost = int(item.cost.resolve(rating=rating, min_rating=minimum))
    return {
        "index": index,
        "rating": rating,
        "rating_range": _rating_range(item, attribute_maximums),
        "nuyen_cost": nuyen_cost,
        # Dual costing: a standalone purchase is the only thing that charges Essence -- every plugin
        # below contributes exactly zero (module docstring of `engine.cyberware_subsystems`).
        "essence": item.essence_cost.resolve(rating=rating, min_rating=minimum),
        "capacity_budget": budget,
        "capacity_spent": spent,
        "capacity_remaining": budget - spent,
        "plugin_rows": plugin_rows,
        "bundled_names": item.bundled_subsystem_names,
        "subtotal": nuyen_cost + sum(row["nuyen_cost"] for row in plugin_rows if row["selected"]),
    }


def _plugin_row(
    parent: CyberwareEntry,
    index: int,
    plugin: CyberwareEntry,
    request: CyberwarePurchaseRequest | None,
    attribute_maximums: Mapping[str, int],
) -> dict[str, Any]:
    """One installable-plugin checkbox for one bought parent unit.

    Prices are shown whether or not the box is ticked -- an unticked row's numbers are what
    installing it *would* cost, which is the whole point of showing them next to the parent's
    remaining Capacity.
    """
    minimum, _ = cyberware_rating_bounds(plugin, attribute_maximums=attribute_maximums)
    rating = minimum if request is None else request.rating
    return {
        "item": plugin,
        "selected": request is not None,
        "rating": rating,
        "rating_range": _rating_range(plugin, attribute_maximums),
        "field": f"plugin_{parent.id}_{index}_{plugin.id}",
        "rating_field": f"plugin_rating_{parent.id}_{index}_{plugin.id}",
        "nuyen_cost": int(plugin.cost.resolve(rating=rating, min_rating=minimum)),
        "capacity_cost": (
            plugin.capacity_cost.resolve(rating=rating, min_rating=minimum)
            if plugin.capacity_cost is not None
            else Decimal(0)
        ),
    }


def _catalog_groups(
    item_ids: tuple[str, ...],
    catalog_by_category: tuple[Any, ...],
    by_id: dict[str, Any],
) -> list[dict[str, Any]]:
    """Build category-grouped `<details>` rows for a quantity-per-item picker.

    WP45 shared this between the cyberware and bioware halves of `_cyberware_context`; WP42 gave
    cyberware its own tree-shaped builder above, so this now serves the bioware half only -- kept
    under its general name because the shape is still the general one (`chummer5.web.routes
    .resources._resources_context`'s WP21 shape), not a bioware-specific one.
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


def _bioware_groups(
    requests: tuple[BiowarePurchaseRequest, ...], by_id: dict[str, Bioware]
) -> list[dict[str, Any]]:
    """`_catalog_groups`'s bioware counterpart (WP80), which needs two things the cyberware picker
    doesn't: each bought unit's own skill pick, and the list of skills that pick may come from.

    `chosen_skills` is one entry per bought unit, in submission order, so the template can render
    exactly `quantity` dropdowns and re-select what the player already chose across the live
    re-render the form does on every change.
    """
    picks: dict[str, list[str | None]] = {}
    for request in requests:
        picks.setdefault(request.item_id, []).append(request.chosen_skill)
    groups = _catalog_groups(tuple(r.item_id for r in requests), _BIOWARE_BY_CATEGORY, by_id)
    for group in groups:
        for row in group["rows"]:
            item = row["item"]
            row["skill_choices"] = _BIOWARE_SKILL_CHOICES.get(item.id, ())
            row["chosen_skills"] = picks.get(item.id, [])
    return groups


def _cyberware_context(
    character: Character | None,
    resources_letter: str,
    cyberware_requests: tuple[CyberwarePurchaseRequest, ...],
    bioware_requests: tuple[BiowarePurchaseRequest, ...],
    gear_cost: int,
    lifestyle_cost: int,
    karma_converted: int = 0,
    foci_cost: int = 0,
    *,
    error: str | None = None,
) -> dict[str, Any]:
    """Context for `_cyberware.html` (WP34, widened by WP45 and WP42): Phase J's cyberware purchase,
    plus Phase L's bioware purchase folded into the same section.

    **WP42**: `cyberware_requests` is a purchase *tree*, not a flat id list -- the third parameter
    changed shape, and `chummer5.web.routes.priorities` (this function's only other caller) now
    passes `cyberware_selection.to_requests()` rather than a list of top-level ids. That is what
    makes a committed limb's installed plugins survive a full-page re-render instead of being
    silently absent from the form the player then re-submits.

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
    (and the shared Essence floor `create_cyberware_tree_selection`/`create_bioware_selection`
    enforce), surfacing a distinct `cyberware_budget_warning` rather than going over/under on the
    next render.
    """
    if character is None:
        return {"character": None, "cyberware_error": error}
    attribute_maximums = cyberlimb_attribute_maximums(character)
    bioware_by_id = {item.id: item for item in BIOWARE}
    cyberware_groups = _cyberware_groups(cyberware_requests, attribute_maximums)
    bioware_groups = _bioware_groups(bioware_requests, bioware_by_id)
    budget = starting_nuyen(resources_letter, PRIORITIES) + display_karma_to_nuyen(karma_converted)
    nuyen_available = budget - gear_cost - lifestyle_cost - foci_cost
    cyberware_spent = sum(
        int(row["subtotal"]) for group in cyberware_groups for row in group["rows"]
    )
    bioware_spent = sum(int(row["subtotal"]) for group in bioware_groups for row in group["rows"])
    spent = cyberware_spent + bioware_spent
    cyberware_essence_spent = sum(
        (row["essence"] for group in cyberware_groups for row in group["rows"]), Decimal(0)
    )
    bioware_essence_spent = sum(
        (bioware_by_id[request.item_id].essence_cost for request in bioware_requests), Decimal(0)
    )
    essence_spent = cyberware_essence_spent + bioware_essence_spent
    budget_warning: str | None = None
    if error is None:
        try:
            cyberware_selection = create_cyberware_tree_selection(
                cyberware_requests,
                CYBERWARE_ENTRIES,
                nuyen_available,
                attribute_maximums=attribute_maximums,
            )
            create_bioware_selection(
                bioware_requests,
                BIOWARE,
                nuyen_available - cyberware_selection.nuyen_spent,
                other_essence_spent=cyberware_selection.essence_spent,
                skills=SKILLS,
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
        attribute_maximums = cyberlimb_attribute_maximums(session.character)
        cyberware_requests = _parse_cyberware(form, attribute_maximums=attribute_maximums)
        bioware_requests = _parse_bioware(form, BIOWARE)
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
        lifestyle_selection = session.character.lifestyle_selection
        lifestyle_cost = lifestyle_selection.total_cost if lifestyle_selection is not None else 0
        # WP47: Foci's own committed nuyen cost shares this same pool now too.
        foci_selection = session.character.foci_selection
        foci_cost = foci_selection.nuyen_cost if foci_selection is not None else 0
        nuyen_available = available_nuyen(session.resources_letter, PRIORITIES, karma_converted) - (
            gear_cost + lifestyle_cost + foci_cost
        )
        try:
            # Fixed evaluation order (chummer5.engine.bioware's own docstring): cyberware
            # first, unaware of bioware; bioware second, aware of cyberware's own nuyen/Essence
            # spend -- so a combination only invalid once both are counted together is always
            # caught, on the bioware call.
            selection = create_cyberware_tree_selection(
                cyberware_requests,
                CYBERWARE_ENTRIES,
                nuyen_available,
                attribute_maximums=attribute_maximums,
            )
            bioware_selection = create_bioware_selection(
                bioware_requests,
                BIOWARE,
                nuyen_available - selection.nuyen_spent,
                other_essence_spent=selection.essence_spent,
                skills=SKILLS,
            )
            new_resources_selection = create_resources_selection(
                session.resources_letter,
                PRIORITIES,
                gear_names,
                rating_gear=rating_gear,
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
                cyberware_requests,
                bioware_requests,
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
                cyberware_requests,
                bioware_requests,
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
