"""Armor modifications installed on purchased armor (WP131).

Keyed exactly like WP130's weapon accessories: an armor is a gear purchase, repeats allowed, and a
mod names **one copy** of it -- `(armor name, copy index)` -- counting that armor's purchases in
`ResourcesSelection.gear` order. Mods are gear, so their cost joins `nuyen_spent`.

**Rules checked for each new mod** (see `chummer5.data.armor_mods` for the citations):
- the mod's category is `General`, the armor's category or name, or one it opens;
- a mod naming a required parent armor goes only on that armor;
- a shield takes only Chemical Protection, Fire Resistance and Nonconductivity, and a helmet
  (whose Capacity 6 is for gear, p. 438) takes none;
- either Chemical seal needs a Full body armor that has its helmet;
- each mod once per copy -- a second Fire Resistance would be a higher rating, not a second mod;
- the rating is 1 to the mod's maximum;
- the copy's mods fit its Capacity, which equals its Armor rating;
- Availability <= 12, a `+N` adding to the armor's own.

**What is computed.** A mod's `<armor>` adds to that copy's Armor rating: Full helmet +3, Urban
Explorer helmet +2, (Synth)Leather 4 on 0-rated Clothing. `chummer5.engine.derived.worn_armor`
applies it, so it feeds WP109's Armor and Damage Resistance. The elemental and toxin ratings are
situational and are registry rows.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from chummer5.data.armor_mods import (
    SHIELD_MODS,
    ArmorMod,
    ArmorModSlots,
    load_armor_mod_slots,
    load_armor_mods,
)
from chummer5.data.gear import parse_rating_availability

ARMOR_MODS: tuple[ArmorMod, ...] = load_armor_mods()
ARMOR_MOD_SLOTS: dict[str, ArmorModSlots] = load_armor_mod_slots()
_MOD_BY_NAME = {mod.name: mod for mod in ARMOR_MODS}

_SHIELDS = frozenset({"Ballistic Shield", "Riot Shield"})
_HELMETS = frozenset({"Helmet"})
_FULL_BODY_ARMOR = "Full Body Armor"
_FULL_BODY_HELMET = "Full Body Armor: Helmet"
_CHEMICAL_SEALS = frozenset({"Chemical Seal", "Full Body Armor: Chemical Seal"})


@dataclass(frozen=True)
class ArmorModPick:
    """One requested mod on one armor copy, at a rating (1 for an unrated mod)."""

    armor: str
    copy: int
    mod: str
    rating: int = 1


@dataclass(frozen=True)
class InstalledArmorMod:
    armor: str
    copy: int
    mod: ArmorMod
    rating: int
    cost: int
    capacity: int

    @property
    def name(self) -> str:
        return self.mod.name

    @property
    def unmodeled_effect_note(self) -> str | None:
        return self.mod.unmodeled_effect_note

    def to_pick(self) -> ArmorModPick:
        return ArmorModPick(self.armor, self.copy, self.mod.name, self.rating)


def _availability(avail: str) -> int | None:
    parsed = parse_rating_availability(avail)
    if parsed is None or parsed[0] != 0:
        return None
    return parsed[1]


def mod_availability(mod: ArmorMod, armor: str, rating: int) -> int | None:
    """A mod's Availability on `armor` at `rating`, or None if unreadable."""
    text = mod.availability
    if text.startswith("+"):
        slots = ARMOR_MOD_SLOTS.get(armor)
        base = _availability(slots.availability) if slots is not None else None
        bonus = _availability(text[1:])
        return None if base is None or bonus is None else base + bonus
    del rating  # every rated core mod has a flat Availability
    return _availability(text)


def capacity_used(installed: Iterable[InstalledArmorMod]) -> int:
    return sum(mod.capacity for mod in installed)


def mod_problem(
    mod: ArmorMod,
    armor: str,
    rating: int,
    on_copy: Iterable[InstalledArmorMod],
    max_availability: int,
) -> str | None:
    """Why `mod` at `rating` can't go on a copy of `armor` already carrying `on_copy`, or None."""
    slots = ARMOR_MOD_SLOTS.get(armor)
    if slots is None:
        return f"{armor} is not a core armor"
    on_copy = list(on_copy)
    if armor in _HELMETS:
        return f"{armor} takes no armor modifications"
    if armor in _SHIELDS and mod.name not in SHIELD_MODS:
        return f"a shield takes only {', '.join(sorted(SHIELD_MODS))}"
    allowed = {"General", slots.category, slots.name, *slots.mod_categories}
    if mod.category not in allowed:
        return f"{mod.name} does not fit {armor}"
    if mod.required_armor is not None and mod.required_armor != armor:
        return f"{mod.name} goes only on {mod.required_armor}"
    if mod.name in _CHEMICAL_SEALS and (
        armor != _FULL_BODY_ARMOR or not any(i.name == _FULL_BODY_HELMET for i in on_copy)
    ):
        return f"{mod.name} needs Full Body Armor with its helmet"
    if any(i.name == mod.name for i in on_copy):
        return f"{armor} already has {mod.name}"
    if not 1 <= rating <= mod.max_rating:
        return f"{mod.name}: rating must be between 1 and {mod.max_rating}, got {rating}"
    free = slots.capacity - capacity_used(on_copy)
    if mod.capacity_at(rating) > free:
        return f"{mod.name} needs Capacity {mod.capacity_at(rating)}; {armor} has {free} left"
    availability = mod_availability(mod, armor, rating)
    if availability is None or availability > max_availability:
        return (
            f"{mod.name} on {armor}: Availability {availability} exceeds the "
            f"character-creation cap of {max_availability}"
        )
    return None


def create_armor_mods(
    picks: Iterable[ArmorModPick],
    armor_counts: Mapping[str, int],
    max_availability: int,
) -> tuple[InstalledArmorMod, ...]:
    """Validate and price `picks` against the purchased armor (`armor_counts`: copies bought per
    name). Picks apply in order, so a Chemical seal must follow its helmet. Raises `ValueError`."""
    installed: list[InstalledArmorMod] = []
    for pick in picks:
        if not 0 <= pick.copy < armor_counts.get(pick.armor, 0):
            raise ValueError(f"{pick.mod}: no purchased {pick.armor} #{pick.copy + 1} to modify")
        mod = _MOD_BY_NAME.get(pick.mod)
        if mod is None:
            raise ValueError(f"not an armor modification: {pick.mod!r}")
        on_copy = [i for i in installed if (i.armor, i.copy) == (pick.armor, pick.copy)]
        problem = mod_problem(mod, pick.armor, pick.rating, on_copy, max_availability)
        if problem is not None:
            raise ValueError(problem)
        installed.append(
            InstalledArmorMod(
                pick.armor,
                pick.copy,
                mod,
                pick.rating,
                mod.cost_at(pick.rating),
                mod.capacity_at(pick.rating),
            )
        )
    return tuple(installed)


def armor_bonus(installed: Iterable[InstalledArmorMod], armor: str, copy: int) -> int:
    """What a copy's mods add to its Armor rating."""
    return sum(i.mod.armor for i in installed if (i.armor, i.copy) == (armor, copy))
