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

from chummer5.engine.armor_mods import (
    ARMOR_MOD_SLOTS,
    ARMOR_MODS,
    ArmorModPick,
    InstalledArmorMod,
    capacity_used,
    mod_problem,
)
from chummer5.engine.character import Character
from chummer5.engine.derived import ARMOR_CATEGORIES
from chummer5.engine.resources import (
    KARMA_TO_NUYEN_RATE,
    MAX_AVAILABILITY,
    MAX_KARMA_TO_NUYEN,
    STARTER_GEAR_CATALOG,
    ResourcesAddOns,
    ResourcesSelection,
    StarterGearItem,
    create_resources_selection,
    resources_addon_args,
    starting_nuyen,
)
from chummer5.engine.weapon_accessories import (
    OFFERED_WEAPON_ACCESSORIES,
    WEAPON_MOUNT_INFO,
    AccessoryPick,
    InstalledAccessory,
    accessory_problem,
    builtin_accessories,
    free_mounts,
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
    owned = {item.name for item in selection.gear if item.category in ARMOR_CATEGORIES}
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
        if item.cost_per_rating is not None or item.price_range is not None:
            continue  # WP66/WP131: rating-priced and variable-priced items are parsed separately
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


# WP130: an accessory pick travels through the form as one "weapon|copy|accessory|mount" string --
# a checked box for each installed one, and one "add" <select> per weapon copy.
_PICK_SEPARATOR = "|"


def encode_accessory_pick(pick: AccessoryPick) -> str:
    return _PICK_SEPARATOR.join((pick.weapon, str(pick.copy), pick.accessory, pick.mount or ""))


def _decode_accessory_pick(raw: str) -> AccessoryPick | None:
    parts = raw.split(_PICK_SEPARATOR)
    if len(parts) != 4 or not parts[1].isdigit():
        return None
    weapon, copy, accessory, mount = parts
    return AccessoryPick(weapon, int(copy), accessory, mount or None)


def _weapon_copies(gear_names: Iterable[str]) -> list[tuple[str, int]]:
    """Every purchased weapon copy that can take accessories, as `(name, copy index)` in gear
    order -- the key `chummer5.engine.weapon_accessories` installs on."""
    seen: dict[str, int] = {}
    copies = []
    for name in gear_names:
        info = WEAPON_MOUNT_INFO.get(name)
        if info is None or not info.allows_accessories:
            continue
        copies.append((name, seen.get(name, 0)))
        seen[name] = seen.get(name, 0) + 1
    return copies


def _parse_accessories(form: FormData, gear_names: tuple[str, ...]) -> tuple[AccessoryPick, ...]:
    """The kept installed accessories, then any newly added ones (WP130). A pick whose weapon copy
    is no longer bought -- the player lowered that weapon's quantity in this same submission -- is
    dropped with it, rather than blocking the change."""
    owned = set(_weapon_copies(gear_names))
    picks = []
    for raw in [*form.getlist("weapon_accessory"), *form.getlist("add_accessory")]:
        pick = _decode_accessory_pick(str(raw))
        if pick is not None and (pick.weapon, pick.copy) in owned:
            picks.append(pick)
    return tuple(picks)


def _weapon_rows(
    gear_names: tuple[str, ...], picks: tuple[AccessoryPick, ...]
) -> list[dict[str, Any]]:
    """One row per purchased weapon copy: its built-ins, its installed accessories, and what can
    still be added (each accessory once per mount it could take)."""
    by_name = {a.name: a for a in OFFERED_WEAPON_ACCESSORIES}
    costs = {item.name: item.cost for item in STARTER_GEAR_CATALOG}
    rows = []
    for weapon, copy in _weapon_copies(gear_names):
        on_copy = []
        for pick in picks:
            accessory = by_name.get(pick.accessory)
            if (pick.weapon, pick.copy) != (weapon, copy) or accessory is None:
                continue
            cost = costs.get(weapon, 0) if accessory.cost_is_weapon_cost else accessory.cost or 0
            on_copy.append(InstalledAccessory(weapon, copy, accessory, pick.mount, cost))
        free = free_mounts(weapon, on_copy)
        options = []
        for accessory in OFFERED_WEAPON_ACCESSORIES:
            if accessory_problem(accessory, weapon, on_copy, MAX_AVAILABILITY) is not None:
                continue
            mounts: tuple[str | None, ...] = (
                tuple(m for m in accessory.mounts if m in free) if accessory.mounts else (None,)
            )
            price = costs.get(weapon, 0) if accessory.cost_is_weapon_cost else accessory.cost or 0
            for mount in mounts:
                options.append(
                    {
                        "value": encode_accessory_pick(
                            AccessoryPick(weapon, copy, accessory.name, mount)
                        ),
                        "name": accessory.name,
                        "mount": mount,
                        "cost": price,
                    }
                )
        rows.append(
            {
                "weapon": weapon,
                "number": copy + 1,
                "builtins": builtin_accessories(weapon),
                "installed": [
                    {"value": encode_accessory_pick(i.to_pick()), "item": i} for i in on_copy
                ],
                "options": options,
            }
        )
    return rows


def _parse_variable_gear(
    form: FormData, catalog: Iterable[StarterGearItem]
) -> tuple[tuple[str, int], ...]:
    """WP131: each variable-priced item's `(quantity, price)` fields as `(name, price)` repeats.
    A missing or unparseable price defaults to the bottom of the range; an out-of-range one is
    passed through for the engine to reject."""
    picks: list[tuple[str, int]] = []
    for item in catalog:
        if item.price_range is None:
            continue
        try:
            quantity = int(str(form.get(f"gear_{item.name}") or 0))
        except ValueError:
            quantity = 0
        if quantity <= 0:
            continue
        try:
            price = int(str(form.get(f"price_{item.name}")))
        except ValueError:
            price = item.price_range[0]
        picks.extend([(item.name, price)] * quantity)
    return tuple(picks)


def encode_armor_mod_pick(pick: ArmorModPick) -> str:
    return _PICK_SEPARATOR.join((pick.armor, str(pick.copy), pick.mod, str(pick.rating)))


def _decode_armor_mod_pick(raw: str) -> ArmorModPick | None:
    parts = raw.split(_PICK_SEPARATOR)
    if len(parts) != 4 or not parts[1].isdigit() or not parts[3].isdigit():
        return None
    return ArmorModPick(parts[0], int(parts[1]), parts[2], int(parts[3]))


def _armor_copies(armor_names: Iterable[str]) -> list[tuple[str, int]]:
    """Every purchased armor copy, as `(name, copy index)` in purchase order (WP131)."""
    seen: dict[str, int] = {}
    copies = []
    for name in armor_names:
        if name not in ARMOR_MOD_SLOTS:
            continue
        copies.append((name, seen.get(name, 0)))
        seen[name] = seen.get(name, 0) + 1
    return copies


def _parse_armor_mods(form: FormData, armor_names: tuple[str, ...]) -> tuple[ArmorModPick, ...]:
    """Kept mods, then newly added ones; a mod on a copy no longer bought is dropped with it."""
    owned = set(_armor_copies(armor_names))
    picks = []
    for raw in [*form.getlist("armor_mod"), *form.getlist("add_armor_mod")]:
        pick = _decode_armor_mod_pick(str(raw))
        if pick is not None and (pick.armor, pick.copy) in owned:
            picks.append(pick)
    return tuple(picks)


def _armor_mod_rows(
    armor_names: tuple[str, ...], picks: tuple[ArmorModPick, ...]
) -> list[dict[str, Any]]:
    """One row per purchased armor copy: its mods, Capacity, and what still fits (each rated mod
    once per rating that fits)."""
    by_name = {mod.name: mod for mod in ARMOR_MODS}
    rows = []
    for armor, copy in _armor_copies(armor_names):
        on_copy = []
        for pick in picks:
            mod = by_name.get(pick.mod)
            if (pick.armor, pick.copy) != (armor, copy) or mod is None:
                continue
            on_copy.append(
                InstalledArmorMod(
                    armor,
                    copy,
                    mod,
                    pick.rating,
                    mod.cost_at(pick.rating),
                    mod.capacity_at(pick.rating),
                )
            )
        options = [
            {
                "value": encode_armor_mod_pick(ArmorModPick(armor, copy, mod.name, rating)),
                "mod": mod,
                "rating": rating,
                "cost": mod.cost_at(rating),
            }
            for mod in ARMOR_MODS
            for rating in range(1, mod.max_rating + 1)
            if mod_problem(mod, armor, rating, on_copy, MAX_AVAILABILITY) is None
        ]
        slots = ARMOR_MOD_SLOTS[armor]
        if not options and not on_copy:
            continue
        rows.append(
            {
                "armor": armor,
                "number": copy + 1,
                "installed": [
                    {"value": encode_armor_mod_pick(i.to_pick()), "item": i} for i in on_copy
                ],
                "options": options,
                "capacity_used": capacity_used(on_copy),
                "capacity": slots.capacity,
            }
        )
    return rows


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
    addons: ResourcesAddOns | None = None,
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

    **WP130/WP131**: `addons` are the weapon accessories, armor mods and variable-priced items,
    re-validated with the gear. Accessories and mods show per weapon/armor copy (`weapon_rows`,
    `armor_rows`); all of it is gear spend.
    """
    if character is None:
        return {"character": None, "resources_error": error}
    if addons is None:
        addons = resources_addon_args(None)
    variable_counts: dict[str, int] = {}
    variable_price: dict[str, int] = {}
    for name, price in addons["variable_gear"]:
        variable_counts[name] = variable_counts.get(name, 0) + 1
        variable_price[name] = price
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
            max_rating = item.max_rating or 1
            return {
                "item": item,
                "quantity": quantity,
                "is_rating": True,
                "rating": rating,
                "max_rating": max_rating,
                "unit_cost": item.cost_per_rating,
                # WP131: a `FixedValues` item lists its price at each offered rating.
                "price_list": (
                    [item.cost_at(r) for r in range(1, max_rating + 1)]
                    if item.cost_by_rating is not None
                    else None
                ),
                "subtotal": quantity * item.cost_at(rating),
            }
        if item.price_range is not None:  # WP131 variable-priced row
            quantity = variable_counts.get(item.name, 0)
            price = variable_price.get(item.name, item.price_range[0])
            return {
                "item": item,
                "quantity": quantity,
                "is_rating": False,
                "is_variable": True,
                "price": price,
                "subtotal": quantity * price,
                "is_armor": item.category in ARMOR_CATEGORIES and quantity > 0,
                "worn": item.name not in character.unworn_armor,
            }
        quantity = counts.get(item.name, 0)
        return {
            "item": item,
            "quantity": quantity,
            "is_rating": False,
            "subtotal": item.cost * quantity,
            # WP109: an owned armor row gets a "worn" checkbox (default: worn).
            "is_armor": item.category in ARMOR_CATEGORIES and quantity > 0,
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
    weapon_rows = _weapon_rows(gear_names, addons["weapon_accessories"])
    armor_names = (*gear_names, *(name for name, _ in addons["variable_gear"]))
    armor_rows = _armor_mod_rows(armor_names, addons["armor_mods"])
    spent = (
        sum(int(row["subtotal"]) for group in gear_groups for row in group["rows"])
        + sum(int(i["item"].cost) for row in weapon_rows for i in row["installed"])
        + sum(int(i["item"].cost) for row in armor_rows for i in row["installed"])
    )
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
                **addons,
            )
        except ValueError as exc:
            budget_warning = Message.of("Web_Stale_Resources", error=str(exc))
    return {
        "character": character,
        "gear_groups": gear_groups,
        "weapon_rows": weapon_rows,
        "armor_rows": armor_rows,
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
        variable_gear = _parse_variable_gear(form, STARTER_GEAR_CATALOG)  # WP131
        addons = ResourcesAddOns(
            weapon_accessories=_parse_accessories(form, gear_names),  # WP130
            armor_mods=_parse_armor_mods(form, (*gear_names, *(name for name, _ in variable_gear))),
            variable_gear=variable_gear,
        )
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
                **addons,
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
                addons=addons,
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
                addons=addons,
            )
    response = templates.TemplateResponse(request, "_resources.html", context)
    if new_cookie is not None:
        response.set_cookie(SESSION_COOKIE_NAME, new_cookie, httponly=True, samesite="lax")
    return response
