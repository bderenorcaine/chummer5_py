"""Loader for `weapons.xml`'s `<accessories>` block, plus the weapon-side facts an accessory is
checked against (WP130).

**The catalog.** 30 `<accessory>` rows carry `source == "SR5"`. Four are `<hide/>`: `Sound
Suppressor` and `Survival Knife Bonuses`/`Survival Knife Wireless Bonuses` exist only as built-ins
of particular weapons, and `External Clip Port` is a legacy-internal row. They load (a built-in has
to resolve its mount) but are never offered. The rest match p. 432's Firearm Accessories table,
with three differences in shape, none in substance:

- the table's one `Gas-vent system (Rating 1-3)` row is three rows here (`Gas-Vent 1/2/3 System`),
  each a fixed price -- so no accessory needs a Rating picked;
- two weapon-specific silencers (the Ares Light Fire 70's, p. 425, and the Light Fire 75's
  built-in) and four zero-cost ammunition-feed rows (belt, drums, external power source) come from
  the weapon descriptions rather than the table;
- `Smart Firing Platform` is 2,000¥ in the data and **2,500¥ on p. 432**. The printed price wins
  (`_PRINTED_COST_CORRECTIONS`), the WP92 Tundra-9 precedent.

The three holsters' data requirement is looser than their printed text (it admits a combat knife);
`_PRINTED_CATEGORY_REQUIREMENTS` replaces it with the printed weapon categories.

**`<required>`/`<forbidden>`.** Each is a small condition over the weapon (`<weapondetails>`)
and, for `<forbidden>`, over the accessories already on it (`<oneof><accessory>`). The grammar the
SR5 rows use is small: sibling leaves are ANDed, an `<OR>` block ORs its leaves, and a leaf is a
weapon field (`name`, `category`, `type`, `conceal`, `ammo`, `ammocategory`, `spec`, `spec2`)
compared by `operation` -- equality by default, `contains`, or `lessthanequals`. `Condition` below
parses exactly that and fails closed on anything else: an unknown tag or operation makes the
condition never hold, so an unreadable requirement blocks the accessory rather than letting it
through.

**Built-ins.** A weapon's own `<accessories>` list what it ships with (p. 424ff: the Predator V's
smartgun system, the Ingram Smartgun X's gas-vent and suppressor). Several name non-core rows
(`Stock`, `Folding Stock`, `Electronic Firing`, `Flashlight, Standard`); they still resolve here
because this loader reads every row for mount lookups and only offers the SR5 ones.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from chummer5.data.gear import CORE_RULEBOOK_SOURCE, DEFAULT_WEAPONS_PATH

# p. 432's firearm accessory mounts. A weapon's `<accessorymounts>` also lists `Stock` and `Side`,
# which no core accessory uses; they are kept as data but can never fill.
MOUNTS = ("Top", "Barrel", "Under", "Stock", "Side")

# accessory name -> printed price (p. 432). See module docstring.
_PRINTED_COST_CORRECTIONS: dict[str, int] = {"Smart Firing Platform": 2500}

# accessory name -> the weapon categories the printed text allows, replacing the data's looser
# `<required>` (which admits anything with Concealability <= 0 -- a combat knife included). p. 431:
# "Only pistols and tasers fit in a Concealable Holster." p. 432: the arm slide "can fit a
# hold-out, light pistol, or taser"; the quick-draw holster holds "any weapon of Machine Pistol or
# smaller size".
_PISTOLS = ("Tasers", "Holdouts", "Light Pistols", "Heavy Pistols", "Machine Pistols")
_PRINTED_CATEGORY_REQUIREMENTS: dict[str, tuple[str, ...]] = {
    "Concealable Holster": _PISTOLS,
    "Quick-Draw Holster": _PISTOLS,
    "Hidden Gun Arm Slide": ("Tasers", "Holdouts", "Light Pistols"),
}

# Accessories p. 433 describes as one-per-weapon-copy-bought ("each clip is specific to the weapon
# you buy it for"): a player may buy several for the same gun.
REPEATABLE_ACCESSORIES = frozenset({"Spare Clip", "Speed Loader"})

# The hand-kept mirror of the Project Overview's "Unmodeled real effects" rows for weapon
# accessories (WP130), keyed by accessory name. There are no attack tests, Recoil or
# Concealability numbers anywhere in this engine, so every offered accessory is price-only.
_UNMODELED_EFFECT_NOTES: dict[str, str] = {
    "Airburst Link": (
        "Scatter shrinks by 2 m per net hit instead of 1 when fired by wireless link trigger "
        "(p. 431) -- no attack or scatter resolution exists."
    ),
    "Bipod": "2 Recoil Compensation when deployed (p. 431) -- no recoil or attack test exists.",
    "Concealable Holster": (
        "-1 Concealability, -1 more wireless (p. 431) -- no Concealability or Perception test "
        "exists."
    ),
    "Gas-Vent 1 System": "1 Recoil Compensation (p. 432) -- no recoil or attack test exists.",
    "Gas-Vent 2 System": "2 Recoil Compensation (p. 432) -- no recoil or attack test exists.",
    "Gas-Vent 3 System": "3 Recoil Compensation (p. 432) -- no recoil or attack test exists.",
    "Gyro Mount": (
        "Neutralizes up to 6 points of recoil and movement modifiers (p. 432) -- no attack test "
        "exists."
    ),
    "Hidden Gun Arm Slide": (
        "-1 Concealability; quick-draw threshold 2 (p. 432) -- no Concealability or quick-draw "
        "test exists."
    ),
    "Imaging Scope": (
        "Micro camera and vision magnification, Capacity 3 for vision enhancements (p. 432) -- no "
        "Perception or attack test exists, and nothing can be installed into the scope."
    ),
    "Laser Sight": (
        "+1 Accuracy, or +1 die wireless, neither cumulative with a smartlink (p. 432) -- no "
        "weapon Accuracy or attack test exists."
    ),
    "Periscope": (
        "Shooting around corners at -2 instead of -3, -1 wireless (p. 432) -- no attack test "
        "exists."
    ),
    "Quick-Draw Holster": ("-1 to the quick-draw threshold (p. 432) -- no quick-draw test exists."),
    "Shock Pad": "1 Recoil Compensation (p. 432) -- no recoil or attack test exists.",
    "Silencer/Suppressor": (
        "-4 to Perception Tests to notice the shot (p. 432) -- no Perception test exists."
    ),
    "Silencer (Ares Light Fire 70)": (
        "-4 to Perception Tests to notice the shot (pp. 425, 432) -- no Perception test exists."
    ),
    "Silencer (Ares Light Fire 75)": (
        "-4 to Perception Tests to notice the shot (pp. 425, 432) -- no Perception test exists."
    ),
    "Smart Firing Platform": (
        "A Pilot 3 robotic tripod with Targeting 3 and 5 Recoil Compensation (p. 433) -- no drone "
        "or attack test exists."
    ),
    "Smartgun System, Internal": (
        "+2 Accuracy with a smartlink, +1/+2 dice wireless (p. 433) -- no weapon Accuracy or "
        "attack test exists. Its price (the weapon's cost again) and +2 Availability are modeled."
    ),
    "Smartgun System, External": (
        "+2 Accuracy with a smartlink, +1/+2 dice wireless (p. 433) -- no weapon Accuracy or "
        "attack test exists."
    ),
    "Spare Clip": "A spare magazine (p. 433) -- no ammunition tracking exists.",
    "Speed Loader": (
        "Reloads a revolver as one Complex Action (p. 433) -- no reloading rules exist."
    ),
    "Tripod": "6 Recoil Compensation when deployed (p. 433) -- no recoil or attack test exists.",
    "Belt-Feed, 100-round": "The weapon's 100-round belt option -- no ammunition tracking exists.",
    "Drum Magazine, 24-round": "A 24-round drum -- no ammunition tracking exists.",
    "Drum Magazine, 32-round": "A 32-round drum -- no ammunition tracking exists.",
    "External Power Source": "An external power feed -- no ammunition tracking exists.",
}

_LEAF_FIELDS = frozenset(
    {"name", "category", "type", "conceal", "ammo", "ammocategory", "spec", "spec2"}
)


@dataclass(frozen=True)
class Leaf:
    """One `<field operation="...">value</field>` test."""

    field: str
    operation: str
    value: str

    def holds(self, details: Mapping[str, str]) -> bool:
        actual = details.get(self.field, "")
        if self.operation == "equals":
            return actual == self.value
        if self.operation == "contains":
            return self.value in actual
        if self.operation == "lessthanequals":
            try:
                return int(actual) <= int(self.value)
            except ValueError:
                return False
        return False


@dataclass(frozen=True)
class Condition:
    """A parsed `<required>`/`<forbidden>` block. `all_of` leaves must all hold, and at least one
    of each `any_of` group; `accessory_any` holds if any named accessory is on the weapon.
    `unreadable` is set when the block used something this parser doesn't know -- see module
    docstring. An empty condition holds vacuously (the caller decides what "no block" means).
    """

    all_of: tuple[Leaf, ...] = ()
    any_of: tuple[tuple[Leaf, ...], ...] = ()
    accessory_any: tuple[str, ...] = ()
    unreadable: bool = False

    def matches_weapon(self, details: Mapping[str, str]) -> bool:
        """The `<weapondetails>` half: every AND leaf and one leaf of every OR group."""
        if self.unreadable:
            return False
        return all(leaf.holds(details) for leaf in self.all_of) and all(
            any(leaf.holds(details) for leaf in group) for group in self.any_of
        )

    @property
    def has_weapon_part(self) -> bool:
        return bool(self.all_of or self.any_of or self.unreadable)


def _parse_leaf(elem: ET.Element) -> Leaf | None:
    if elem.tag not in _LEAF_FIELDS:
        return None
    operation = elem.get("operation", "equals")
    if operation not in {"equals", "contains", "lessthanequals"}:
        return None
    return Leaf(elem.tag, operation, (elem.text or "").strip())


def _parse_condition(elem: ET.Element | None) -> Condition | None:
    if elem is None:
        return None
    all_of: list[Leaf] = []
    any_of: list[tuple[Leaf, ...]] = []
    accessories: list[str] = []
    unreadable = False
    for child in elem:
        if child.tag == "oneof":
            for item in child:
                if item.tag == "accessory":
                    accessories.append((item.text or "").strip())
                else:
                    unreadable = True
        elif child.tag == "weapondetails":
            for node in child:
                if node.tag == "OR":
                    group = [_parse_leaf(leaf) for leaf in node]
                    if any(leaf is None for leaf in group):
                        unreadable = True
                    any_of.append(tuple(leaf for leaf in group if leaf is not None))
                else:
                    leaf = _parse_leaf(node)
                    if leaf is None:
                        unreadable = True
                    else:
                        all_of.append(leaf)
        else:
            unreadable = True
    return Condition(tuple(all_of), tuple(any_of), tuple(accessories), unreadable)


@dataclass(frozen=True)
class WeaponAccessory:
    """One `<accessory>` row.

    `mounts` is the set of mounts it may take -- `("Top", "Under")` for a `Top/Under` row, `()`
    for one that uses no mount (a holster, a spare clip, the internal smartgun). `cost` is `None`
    only for `Smartgun System, Internal`, whose price is the weapon's own (`cost_is_weapon_cost`);
    its `availability` is then a `+N` modifier on the weapon's.
    """

    id: str
    name: str
    mounts: tuple[str, ...]
    cost: int | None
    cost_is_weapon_cost: bool
    availability: str
    source: str
    page: int
    hidden: bool
    ammo_replacement: bool
    required: Condition | None
    forbidden: Condition | None
    unmodeled_effect_note: str | None = None

    @property
    def offerable(self) -> bool:
        return self.source == CORE_RULEBOOK_SOURCE and not self.hidden


@dataclass(frozen=True)
class WeaponMountInfo:
    """What an accessory needs to know about a weapon: its mounts, the accessories it ships with
    (by name, in data order), its printed Availability, and the `<weapondetails>` fields."""

    name: str
    mounts: tuple[str, ...]
    builtin_accessories: tuple[str, ...]
    availability: str
    allows_accessories: bool
    details: Mapping[str, str]


def load_weapon_accessories(
    xml_path: Path = DEFAULT_WEAPONS_PATH,
) -> tuple[WeaponAccessory, ...]:
    """Every `<accessory>` row (all sources -- built-ins name non-core rows; `offerable` is the
    SR5, non-hidden filter)."""
    root = ET.parse(xml_path).getroot()
    block = root.find("accessories")
    if block is None:
        return ()
    items = []
    for elem in block.findall("accessory"):
        name = elem.findtext("name", "")
        cost_text = elem.findtext("cost", "0").strip()
        is_weapon_cost = cost_text == "Weapon Cost"
        cost: int | None
        if is_weapon_cost:
            cost = None
        elif cost_text.isdigit():
            cost = _PRINTED_COST_CORRECTIONS.get(name, int(cost_text))
        else:
            continue  # a formula cost no core row uses
        mount_text = (elem.findtext("mount") or "").strip()
        required = _parse_condition(elem.find("required"))
        printed = _PRINTED_CATEGORY_REQUIREMENTS.get(name)
        if printed is not None:
            required = Condition(any_of=(tuple(Leaf("category", "equals", c) for c in printed),))
        items.append(
            WeaponAccessory(
                id=elem.findtext("id", ""),
                name=name,
                mounts=tuple(m for m in mount_text.split("/") if m),
                cost=cost,
                cost_is_weapon_cost=is_weapon_cost,
                availability=elem.findtext("avail", "0").strip(),
                source=elem.findtext("source", ""),
                page=int(elem.findtext("page", "0") or "0"),
                hidden=elem.find("hide") is not None,
                ammo_replacement=elem.find("ammoreplace") is not None,
                required=required,
                forbidden=_parse_condition(elem.find("forbidden")),
                unmodeled_effect_note=_UNMODELED_EFFECT_NOTES.get(name),
            )
        )
    return tuple(items)


def load_weapon_mount_info(
    xml_path: Path = DEFAULT_WEAPONS_PATH,
) -> dict[str, WeaponMountInfo]:
    """SR5 weapons by name, with the fields `WeaponMountInfo` carries."""
    root = ET.parse(xml_path).getroot()
    block = root.find("weapons")
    if block is None:
        return {}
    result: dict[str, WeaponMountInfo] = {}
    for elem in block.findall("weapon"):
        if elem.findtext("source") != CORE_RULEBOOK_SOURCE:
            continue
        name = elem.findtext("name", "")
        mounts_elem = elem.find("accessorymounts")
        mounts = (
            tuple((m.text or "").strip() for m in mounts_elem) if mounts_elem is not None else ()
        )
        builtins_elem = elem.find("accessories")
        builtins = (
            tuple(a.findtext("name", "") for a in builtins_elem)
            if builtins_elem is not None
            else ()
        )
        details = {field: (elem.findtext(field) or "").strip() for field in _LEAF_FIELDS}
        result[name] = WeaponMountInfo(
            name=name,
            mounts=mounts,
            builtin_accessories=builtins,
            availability=elem.findtext("avail", "0").strip(),
            allows_accessories=elem.findtext("allowaccessory", "True") != "False",
            details=details,
        )
    return result
