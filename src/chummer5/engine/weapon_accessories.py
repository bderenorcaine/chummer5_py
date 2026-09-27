"""Weapon accessories installed on purchased weapons (WP130).

**Where an accessory lives.** A weapon is ordinary Step Six gear -- a name in
`ResourcesSelection.gear`, repeats allowed -- so an accessory is keyed to **one copy** of it:
`(weapon name, copy index)`, the index counting that weapon's purchases in gear order from 0. Two
Ares Predator Vs are copies 0 and 1, and each carries its own silencer or not. Accessories are gear
too, so they are priced into `ResourcesSelection.nuyen_spent` by
`chummer5.engine.resources.create_resources_selection` rather than into a seventh shared-budget
term; this module only validates and prices them.

**Mounts (p. 431).** "Most firearm accessories must be attached to a particular mount -- top,
barrel, underbarrel. Each mount can only hold one accessory at a time." A weapon's mounts are its
`<accessorymounts>`; a weapon with none (every melee weapon, grenades, bows) takes only
mountless accessories, and one marked `<allowaccessory>False</allowaccessory>` takes none at all.
A `Top/Under` accessory (laser sight, external smartgun) goes on whichever of the two the player
picks.

**Built-ins take their mount first.** A weapon ships with what its `<accessories>` list, at no cost
(p. 424ff: "It comes equipped with a built-in top-mounted laser sight"). Each built-in occupies the
first of its own mounts the weapon has free, in data order -- so the Predator V's internal smartgun
takes no mount, the Remington 950's imaging scope takes Top, and a `Top/Under` built-in laser sight
takes Top, which is what every weapon description that says where puts it. When two built-ins want
the same mount (the Ingram Smartgun X's gas-vent 2 *and* integral suppressor are both Barrel rows),
the second sits on the weapon without a mount rather than being refused. Legacy puts every built-in
on no mount at all ("Internal"); the book's "top-mounted" wording is why this differs -- see
`spec/decisions-log.md`'s WP130 entry.

**One of each, except spare clips and speed loaders.** p. 433 sells those per weapon and "each clip
is specific to the weapon you buy it for", so several may go on one copy. Any other accessory is
refused if the copy already has it, built-in or bought. At most one ammunition-feed replacement
(belt, drum, external power) goes on a copy, since each replaces the weapon's magazine.

**Availability <= 12** (Project Overview's 2026-07-21 ruling) for every new pick: the accessory's
own printed value, or for the internal smartgun, the weapon's Availability + 2 (p. 433:
"Retrofitting a firearm with an internal smartgun system doubles the weapon's price and adds 2 to
its Availability"). Built-ins are never checked: they come with a weapon the catalog already offers.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass

from chummer5.data.gear import parse_rating_availability
from chummer5.data.weapon_accessories import (
    REPEATABLE_ACCESSORIES,
    WeaponAccessory,
    WeaponMountInfo,
    load_weapon_accessories,
    load_weapon_mount_info,
)

# Parsed once at import time, like every other catalog constant in this package.
WEAPON_ACCESSORIES: tuple[WeaponAccessory, ...] = load_weapon_accessories()
WEAPON_MOUNT_INFO: dict[str, WeaponMountInfo] = load_weapon_mount_info()
_ACCESSORY_BY_NAME: dict[str, WeaponAccessory] = {a.name: a for a in WEAPON_ACCESSORIES}

# The offered accessories, in data order: SR5 and not `<hide/>`.
OFFERED_WEAPON_ACCESSORIES: tuple[WeaponAccessory, ...] = tuple(
    a for a in WEAPON_ACCESSORIES if a.offerable
)


@dataclass(frozen=True)
class AccessoryPick:
    """One requested accessory: which weapon copy it goes on, and on which mount (None for a
    mountless accessory, or to take the first free one it fits)."""

    weapon: str
    copy: int
    accessory: str
    mount: str | None = None


@dataclass(frozen=True)
class InstalledAccessory:
    """A validated, priced accessory on one weapon copy."""

    weapon: str
    copy: int
    accessory: WeaponAccessory
    mount: str | None
    cost: int

    @property
    def name(self) -> str:
        return self.accessory.name

    @property
    def unmodeled_effect_note(self) -> str | None:
        return self.accessory.unmodeled_effect_note

    def to_pick(self) -> AccessoryPick:
        return AccessoryPick(self.weapon, self.copy, self.accessory.name, self.mount)


@dataclass(frozen=True)
class BuiltinAccessory:
    """An accessory a weapon ships with, and the mount it took (None: no mount)."""

    name: str
    mount: str | None


def builtin_accessories(weapon: str) -> tuple[BuiltinAccessory, ...]:
    """What `weapon` ships with, each on the first of its mounts still free -- see module
    docstring. A name with no accessory row takes no mount."""
    info = WEAPON_MOUNT_INFO.get(weapon)
    if info is None:
        return ()
    free = list(info.mounts)
    result = []
    for name in info.builtin_accessories:
        row = _ACCESSORY_BY_NAME.get(name)
        mount = next((m for m in (row.mounts if row else ()) if m in free), None)
        if mount is not None:
            free.remove(mount)
        result.append(BuiltinAccessory(name, mount))
    return tuple(result)


def free_mounts(weapon: str, installed: Iterable[InstalledAccessory] = ()) -> tuple[str, ...]:
    """`weapon`'s mounts not taken by a built-in or by `installed` (that copy's accessories)."""
    info = WEAPON_MOUNT_INFO.get(weapon)
    if info is None:
        return ()
    free = list(info.mounts)
    for taken in [b.mount for b in builtin_accessories(weapon)] + [i.mount for i in installed]:
        if taken in free:
            free.remove(taken)
    return tuple(free)


def _availability(avail: str) -> int | None:
    parsed = parse_rating_availability(avail)
    if parsed is None or parsed[0] != 0:
        return None
    return parsed[1]


def accessory_availability(accessory: WeaponAccessory, weapon: str) -> int | None:
    """An accessory's Availability as bought for `weapon`, or None if unreadable. The internal
    smartgun's `+2R` adds to the weapon's own (p. 433)."""
    if accessory.availability.startswith("+"):
        info = WEAPON_MOUNT_INFO.get(weapon)
        base = _availability(info.availability) if info is not None else None
        bonus = _availability(accessory.availability[1:])
        return None if base is None or bonus is None else base + bonus
    return _availability(accessory.availability)


def accessory_problem(
    accessory: WeaponAccessory,
    weapon: str,
    on_copy: Sequence[InstalledAccessory],
    max_availability: int,
) -> str | None:
    """Why `accessory` can't be added to a copy of `weapon` already carrying `on_copy`, or None if
    it can (mount choice aside -- `free_mounts` decides that). Every rule in the module docstring
    except the mount one."""
    info = WEAPON_MOUNT_INFO.get(weapon)
    if info is None:
        return f"{weapon} is not a core weapon"
    if not info.allows_accessories:
        return f"{weapon} takes no accessories"
    if not accessory.offerable:
        return f"{accessory.name} is not an offered accessory"
    present = {b.name for b in builtin_accessories(weapon)} | {i.name for i in on_copy}
    if accessory.name in present and accessory.name not in REPEATABLE_ACCESSORIES:
        return f"{weapon} already has {accessory.name}"
    required = accessory.required
    if required is not None and required.has_weapon_part:
        if not required.matches_weapon(info.details):
            return f"{accessory.name} does not fit {weapon}"
    forbidden = accessory.forbidden
    if forbidden is not None:
        if forbidden.has_weapon_part and forbidden.matches_weapon(info.details):
            return f"{accessory.name} cannot go on {weapon}"
        clash = present & set(forbidden.accessory_any)
        if clash:
            return f"{accessory.name} cannot go with {sorted(clash)[0]}"
    if accessory.ammo_replacement and any(i.accessory.ammo_replacement for i in on_copy):
        return f"{weapon} already has an ammunition-feed replacement"
    if accessory.mounts and not set(accessory.mounts) & set(info.mounts):
        return f"{weapon} has no {'/'.join(accessory.mounts)} mount"
    availability = accessory_availability(accessory, weapon)
    if availability is None or availability > max_availability:
        return (
            f"{accessory.name} on {weapon}: Availability {availability} exceeds the "
            f"character-creation cap of {max_availability}"
        )
    return None


def create_weapon_accessories(
    picks: Iterable[AccessoryPick],
    weapon_costs: Mapping[str, int],
    weapon_counts: Mapping[str, int],
    max_availability: int,
) -> tuple[InstalledAccessory, ...]:
    """Validate and price `picks` against the purchased weapons: `weapon_counts` is how many
    copies of each weapon name were bought, `weapon_costs` each one's unit price (for the internal
    smartgun). Picks are applied in order, so a later one sees the mounts an earlier one took.
    Raises `ValueError` naming the first broken rule.
    """
    installed: list[InstalledAccessory] = []
    for pick in picks:
        if not 0 <= pick.copy < weapon_counts.get(pick.weapon, 0):
            raise ValueError(
                f"{pick.accessory}: no purchased {pick.weapon} #{pick.copy + 1} to install it on"
            )
        accessory = _ACCESSORY_BY_NAME.get(pick.accessory)
        if accessory is None:
            raise ValueError(f"not a weapon accessory: {pick.accessory!r}")
        on_copy = [i for i in installed if (i.weapon, i.copy) == (pick.weapon, pick.copy)]
        problem = accessory_problem(accessory, pick.weapon, on_copy, max_availability)
        if problem is not None:
            raise ValueError(problem)
        mount: str | None = None
        if accessory.mounts:
            free = free_mounts(pick.weapon, on_copy)
            wanted = (pick.mount,) if pick.mount is not None else accessory.mounts
            mount = next((m for m in wanted if m in accessory.mounts and m in free), None)
            if mount is None:
                where = pick.mount or "/".join(accessory.mounts)
                raise ValueError(f"{pick.weapon}'s {where} mount is already taken")
        cost = (
            weapon_costs[pick.weapon]
            if accessory.cost_is_weapon_cost
            else (accessory.cost if accessory.cost is not None else 0)
        )
        installed.append(InstalledAccessory(pick.weapon, pick.copy, accessory, mount, cost))
    return tuple(installed)
