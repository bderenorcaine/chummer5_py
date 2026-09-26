"""Resources (starter gear) chargen step: `POST /ui/resources` (WP16, widened by WP20/34/43/45/47).

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

from chummer5.engine.character import Character
from chummer5.engine.derived import ARMOR_CATEGORY
from chummer5.engine.resources import (
    KARMA_TO_NUYEN_RATE,
    MAX_KARMA_TO_NUYEN,
    STARTER_GEAR_CATALOG,
    ResourcesSelection,
    StarterGearItem,
    create_resources_selection,
    starting_nuyen,
)
from chummer5.web.catalogs import PRIORITIES, templates
from chummer5.web.forms import display_karma_to_nuyen
from chummer5.web.i18n import Message, MessageJoin
from chummer5.web.session import SESSION_COOKIE_NAME, resolve_session

router = APIRouter()

# WP94: the gear categories whose printed stat block the character sheet renders. Identical to
# `chummer5.engine.resources._AVAILABILITY_CAPPED_GEAR_CATEGORIES` today and for the same reason
# (Phase P's rigger-adjacent slice), but kept as its own name: one is a display decision, the other
# a purchasability rule, and a future backfill will very plausibly widen one without the other.
MATRIX_STAT_BLOCK_CATEGORIES = frozenset({"Commlinks", "Cyberdecks", "Rigger Command Consoles"})


def matrix_stat_block(item: StarterGearItem) -> MessageJoin | None:
    """One Matrix device's printed stat block as a keyed, comma-joined list of `Message`s (WP102;
    a display string before that), or None for gear that has no such block (WP94).

    Renders **only what the book prints for that category**, which is not the same set of numbers
    for all three:

    - Commlinks (p. 438) print Device Rating alone. Data Processing and Firewall are shown
      alongside it because a commlink has exactly those two Matrix attributes (p. 226) and
      `gear.xml` sets both equal to the Device Rating for every SR5 row -- see
      `spec/rulebooks/learnings/phase-p.md`.
    - Cyberdecks (p. 439) print Device Rating, the Attribute Array and Programs. The array is one
      descending set the decker assigns among Attack/Sleaze/Data Processing/Firewall, so it is
      rendered as the book prints it (`4 3 2 1`) rather than as four labelled values.
    - Rigger Command Consoles (p. 267) print Device Rating, Data Processing and Firewall.
      `gear.xml` also carries a `<programs>` count for every RCC (always equal to its Device
      Rating), but **the core rulebook prints no program-slot number for RCCs at all** -- p. 269's
      rigger-cyberprograms sidebar establishes that RCCs run programs without saying how many. It's
      loaded (`StarterGearItem.programs`) and deliberately not displayed, rather than showing a
      Chummer-supplied number as if it were a printed stat.

    Scoped to those three categories on purpose. 21 other flat rows (RFID tags, credsticks,
    Electronics/Commlink accessories) carry a `<devicerating>` too, but none of them prints a stat
    block in the gear tables, and WP94's brief is the rigger-adjacent slice only -- the same line
    the Availability cap is drawn along in `chummer5.engine.resources`.

    Nothing derives anything from these values -- no Matrix rules exist in this project (WP90 §5).
    """
    if item.device_rating is None or item.category not in MATRIX_STAT_BLOCK_CATEGORIES:
        return None
    parts = [Message.of("Web_Gear_DeviceRating", value=item.device_rating)]
    if item.attribute_array is not None:
        array = MessageJoin(tuple(str(value) for value in item.attribute_array), "Web_List_Space")
        parts.append(Message.of("Web_Gear_AttributeArray", values=array))
    if item.data_processing is not None:
        parts.append(Message.of("Web_Gear_DataProcessing", value=item.data_processing))
    if item.firewall is not None:
        parts.append(Message.of("Web_Gear_Firewall", value=item.firewall))
    if item.attribute_array is not None and item.programs is not None:
        parts.append(Message.of("Web_Gear_Programs", value=item.programs))
    return MessageJoin(tuple(parts))


def _submitted_unworn_armor(
    form: FormData, character: Character, selection: ResourcesSelection
) -> frozenset[str]:
    """WP109: which owned armor is marked not worn after this submission.

    Each armor row rendered with a "worn" checkbox also posts a hidden `armor_shown` marker, so an
    unchecked box (absent from the form) can be told apart from a row that wasn't on the page -- an
    item bought in this very submission had no checkbox yet and stays worn by default. Names no
    longer owned drop out of the set.
    """
    shown = {str(v) for v in form.getlist("armor_shown")}
    worn = {str(v) for v in form.getlist("armor_worn")}
    unworn = (set(character.unworn_armor) - shown) | (shown - worn)
    owned = {item.name for item in selection.gear if item.category == ARMOR_CATEGORY}
    return frozenset(unworn & owned)


def _parse_gear(form: FormData, catalog: Iterable[StarterGearItem]) -> tuple[str, ...]:
    """Expand each starter-gear item's submitted quantity into that many repeats of its name --
    `create_resources_selection`'s `gear_names` is a flat, repeats-allowed name list (see
    `chummer5.engine.resources`), not a `{name: quantity}` mapping. An unparseable or negative
    quantity is clamped to 0: unlike attribute/skill points, there's no engine-level "negative
    quantity" concept here for `create_resources_selection` to validate instead (repeating a name
    -3 times isn't a meaningful rejection to surface), so this is a plain web-robustness clamp, not
    a rule this function is offloading onto the engine.
    """
    names: list[str] = []
    for item in catalog:
        if item.cost_per_rating is not None:
            continue  # WP66: rating-priced items go through _parse_rating_gear instead
        raw = form.get(f"gear_{item.name}")
        try:
            quantity = int(str(raw)) if raw is not None else 0
        except ValueError:
            quantity = 0
        names.extend([item.name] * max(quantity, 0))
    return tuple(names)


def _parse_rating_gear(
    form: FormData, catalog: Iterable[StarterGearItem]
) -> tuple[tuple[str, int], ...]:
    """Expand each Rating-priced item's `(quantity, rating)` form fields into `create_resources_
    selection`'s `rating_gear` argument -- a flat `(name, rating)` list, repeats = quantity (WP66).

    Quantity is clamped to >=0 the same web-robustness way `_parse_gear` clamps it. A missing or
    unparseable rating defaults to 1 (a valid rating); an explicitly out-of-range rating is passed
    through unchanged, so `create_resources_selection`'s own 1..max_rating check is what rejects it,
    not this parser -- mirroring `_parse_gear`'s "let the engine validate what it owns" split.
    """
    picks: list[tuple[str, int]] = []
    for item in catalog:
        if item.cost_per_rating is None:
            continue
        raw_qty = form.get(f"gear_{item.name}")
        try:
            quantity = int(str(raw_qty)) if raw_qty is not None else 0
        except ValueError:
            quantity = 0
        if quantity <= 0:
            continue
        raw_rating = form.get(f"rating_{item.name}")
        try:
            rating = int(str(raw_rating)) if raw_rating is not None else 1
        except ValueError:
            rating = 1
        picks.extend([(item.name, rating)] * quantity)
    return tuple(picks)


def _parse_karma_converted(form: FormData) -> int:
    """Read `karma_converted` off a submitted form (WP43), clamping an unparseable or negative
    value to 0 -- the same "let the engine validate what it's already responsible for" choice
    `_parse_gear`/`chummer5.web.routes.lifestyle._parse_lifestyle_months` make. `karma_to_nuyen`'s
    own 0-10 range check is what rejects anything above the cap, not this parser.
    """
    raw = form.get("karma_converted")
    try:
        value = int(str(raw)) if raw is not None else 0
    except ValueError:
        value = 0
    return max(value, 0)


def _resources_context(
    character: Character | None,
    resources_letter: str,
    gear_names: tuple[str, ...],
    lifestyle_cost: int,
    cyberware_cost: int,
    bioware_cost: int,
    karma_converted: int = 0,
    foci_cost: int = 0,
    vehicle_cost: int = 0,
    rating_gear: tuple[tuple[str, int], ...] = (),
    *,
    error: str | None = None,
) -> dict[str, Any]:
    """Context for `_resources.html`. `gear_names` is the flat, repeats-allowed name list
    `create_resources_selection` itself takes -- tallied into per-item quantities here purely for
    display.

    **WP19**: same `error`-gated re-validation as
    `chummer5.web.routes.attributes._attribute_allocation_context` -- when `error` is unset,
    re-runs `create_resources_selection` against `resources_letter`/`gear_names` purely to derive
    `resources_budget_warning`. `submit_priorities` carries a committed gear purchase forward
    unconditionally now (see its own comment), so a Resources-letter reconfirmation that shrinks
    the nuyen budget below what's already been spent needs to surface here rather than silently
    going over. Not explicitly named in the Implementation Plan's WP19 entry (which lists
    `_priority_form_context`/`_attribute_allocation_context`/`_skill_allocation_context` as the
    three to extend) -- included anyway since gear is carried forward exactly like skill points are,
    and a stale gear purchase deserves the same explanation, not silence.

    **WP20**: `lifestyle_cost` (the character's currently-selected `lifestyle_selection.total_cost`,
    or 0 if none yet) is folded into the displayed remaining budget and the re-validation call, so
    gear and the primary Lifestyle correctly share one Resources-priority nuyen budget instead of
    each silently assuming the whole thing for itself. Not a bidirectional live update, though: this
    section's own `hx-target` only swaps `#resources`, so buying gear here doesn't refresh
    `#lifestyle`'s own displayed remaining-budget number (or vice versa) until the next full page
    render -- a deliberate, documented scope boundary (see this WP's worklog), not an oversight;
    both sections' *validation* (whether a submission is actually accepted) is always correct
    regardless, since both call the same joint `create_resources_selection` check.

    **WP34**: `cyberware_cost` (the character's currently-selected `cyberware_selection.nuyen_
    spent`, or 0 if none yet) folds in the same way, extending the shared-budget check from gear+
    Lifestyle to gear+Lifestyle+cyberware.

    **WP45**: `bioware_cost` folds in the same way, extending the shared-budget check to
    gear+Lifestyle+cyberware+bioware.

    **WP43**: `karma_converted` (this same submission's Karma-to-Nuyen amount, or the character's
    currently-committed one when redisplaying a clean render) tops up the budget the re-validation
    call and the displayed remaining-nuyen number both use.

    **WP47**: `foci_cost` folds in the same way, extending the shared-budget check to
    gear+Lifestyle+cyberware+bioware+Foci.

    **WP93**: `vehicle_cost` folds in the same way, extending it to six sections.
    """
    if character is None:
        return {"character": None, "resources_error": error}
    counts: dict[str, int] = {}
    for name in gear_names:
        counts[name] = counts.get(name, 0) + 1
    # WP66: rating-priced picks tally quantity per name and carry the chosen rating (the UI submits
    # one rating per item, so a name's pairs all share a rating -- last wins if they somehow don't).
    rating_counts: dict[str, int] = {}
    rating_by_name: dict[str, int] = {}
    for name, rating in rating_gear:
        rating_counts[name] = rating_counts.get(name, 0) + 1
        rating_by_name[name] = rating

    def _row(item: StarterGearItem) -> dict[str, Any]:
        if item.cost_per_rating is not None:  # WP66 rating-priced row
            quantity = rating_counts.get(item.name, 0)
            rating = rating_by_name.get(item.name, 1)
            unit = item.cost_per_rating
            return {
                "item": item,
                "quantity": quantity,
                "is_rating": True,
                "rating": rating,
                "max_rating": item.max_rating,
                "unit_cost": unit,
                "subtotal": quantity * rating * unit,
            }
        quantity = counts.get(item.name, 0)
        return {
            "item": item,
            "quantity": quantity,
            "is_rating": False,
            "subtotal": item.cost * quantity,
            # WP109: an owned armor row gets a "worn" checkbox (default: worn).
            "is_armor": item.category == ARMOR_CATEGORY and quantity > 0,
            "worn": item.name not in character.unworn_armor,
        }

    # WP21: ~380 items instead of 5 -- grouped by category (the catalog is already sorted by
    # (category, name), so a plain groupby needs no re-sorting) rather than one long flat table, per
    # the Implementation Plan's explicit instruction. `_character_sheet_context`'s own `gear_rows`
    # (a different context key, just the *purchased* items) is unaffected -- that list is always
    # short, no grouping needed there.
    gear_groups: list[dict[str, Any]] = [
        {
            "category": category,
            "rows": [_row(item) for item in items],
        }
        for category, items in itertools.groupby(
            STARTER_GEAR_CATALOG, key=lambda item: item.category or "Other"
        )
    ]
    budget = starting_nuyen(resources_letter, PRIORITIES)
    spent = sum(int(row["subtotal"]) for group in gear_groups for row in group["rows"])
    budget_warning: Message | None = None
    if error is None:
        try:
            create_resources_selection(
                resources_letter,
                PRIORITIES,
                gear_names,
                rating_gear=rating_gear,
                lifestyle_cost=lifestyle_cost,
                cyberware_cost=cyberware_cost,
                bioware_cost=bioware_cost,
                karma_converted=karma_converted,
                foci_cost=foci_cost,
                vehicle_cost=vehicle_cost,
            )
        except ValueError as exc:
            budget_warning = Message.of("Web_Stale_Resources", error=str(exc))
    return {
        "character": character,
        "gear_groups": gear_groups,
        "nuyen_budget": budget,
        "nuyen_spent": spent,
        "nuyen_remaining": (
            budget
            + display_karma_to_nuyen(karma_converted)
            - spent
            - lifestyle_cost
            - cyberware_cost
            - bioware_cost
            - foci_cost
            - vehicle_cost
        ),
        "karma_converted": karma_converted,
        "max_karma_to_nuyen": MAX_KARMA_TO_NUYEN,
        # WP102: the rate the conversion label shows, read from the engine rather than a literal.
        "karma_to_nuyen_rate": KARMA_TO_NUYEN_RATE,
        "karma_to_nuyen_amount": display_karma_to_nuyen(karma_converted),
        "resources_error": error,
        "resources_budget_warning": budget_warning,
    }


@router.post("/ui/resources", response_class=HTMLResponse)
async def submit_resources(request: Request) -> HTMLResponse:
    session, new_cookie = resolve_session(request)
    session.current_page = "equipment"  # WP61/WP97
    if session.character is None:
        context = _resources_context(None, session.resources_letter, (), 0, 0, 0, 0)
    else:
        form = await request.form()
        gear_names = _parse_gear(form, STARTER_GEAR_CATALOG)
        rating_gear = _parse_rating_gear(form, STARTER_GEAR_CATALOG)
        karma_converted = _parse_karma_converted(form)
        lifestyle_selection = session.character.lifestyle_selection
        lifestyle_cost = lifestyle_selection.total_cost if lifestyle_selection is not None else 0
        cyberware_selection = session.character.cyberware_selection
        cyberware_cost = cyberware_selection.nuyen_spent if cyberware_selection is not None else 0
        bioware_selection = session.character.bioware_selection
        bioware_cost = bioware_selection.nuyen_spent if bioware_selection is not None else 0
        # WP93: Foci and vehicles are the other two spenders of the same pool. `foci_cost` was
        # threaded into this section's *display* re-validation by WP47 but never into the accepting
        # call below -- fixed here alongside `vehicle_cost`, since committing gear must be checked
        # against every sibling spend, not just four of the five.
        foci_selection = session.character.foci_selection
        foci_cost = foci_selection.nuyen_cost if foci_selection is not None else 0
        vehicle_selection = session.character.vehicle_selection
        vehicle_cost = vehicle_selection.nuyen_spent if vehicle_selection is not None else 0
        try:
            selection = create_resources_selection(
                session.resources_letter,
                PRIORITIES,
                gear_names,
                rating_gear=rating_gear,
                lifestyle_cost=lifestyle_cost,
                cyberware_cost=cyberware_cost,
                bioware_cost=bioware_cost,
                karma_converted=karma_converted,
                foci_cost=foci_cost,
                vehicle_cost=vehicle_cost,
            )
        except ValueError as exc:
            context = _resources_context(
                session.character,
                session.resources_letter,
                gear_names,
                lifestyle_cost,
                cyberware_cost,
                bioware_cost,
                karma_converted,
                foci_cost,
                vehicle_cost,
                rating_gear=rating_gear,
                error=str(exc),
            )
        else:
            session.character = replace(
                session.character,
                resources_selection=selection,
                unworn_armor=_submitted_unworn_armor(form, session.character, selection),
            )
            context = _resources_context(
                session.character,
                session.resources_letter,
                gear_names,
                lifestyle_cost,
                cyberware_cost,
                bioware_cost,
                karma_converted,
                foci_cost,
                vehicle_cost,
                rating_gear=rating_gear,
            )
    response = templates.TemplateResponse(request, "_resources.html", context)
    if new_cookie is not None:
        response.set_cookie(SESSION_COOKIE_NAME, new_cookie, httponly=True, samesite="lax")
    return response
