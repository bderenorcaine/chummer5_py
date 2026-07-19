"""Loaders for `legacy/Chummer/data/{gear,armor,weapons}.xml`, restricted to `source == "SR5"` and
to items whose `<cost>` is a plain, non-negative integer literal -- what the Implementation Plan
(WP21) calls "flat-cost": no `Rating`-scaled formula (`Rating * 2500`), no
`FixedValues(...)`/`Variable(...)` formula, and no `+N` cost-modifier shorthand (a handful of
accessories, e.g. Card Reader/Biometric Reader, whose `<cost>` is *added to a parent item's* cost
rather than being a standalone price).

Confirmed counts (re-derived directly from the XML, matching the Implementation Plan's own
research): 391 SR5-sourced `<gear>` entries, of which 266 are flat-cost (125 excluded: 120
`Rating`-formula, 2 `FixedValues`, 1 `Variable`, 2 `+N` modifiers); 12 SR5-sourced `<armor>`
entries, of which 11 are
flat-cost (1 excluded: `Clothing`'s `Variable(20-100000)`); 134 SR5-sourced `<weapon>` entries, all
already flat-cost. Total: 266 + 11 + 134 = 411 -- this module's loaders return exactly that split
(tested directly), matching the acceptance criterion's literal "411 flat items total".

**What this module deliberately does not filter out, and why that's `chummer5.engine.resources`'s
job instead.** Two more subtleties surfaced while building the purchasable catalog on top of these
411 items -- both real, both left in *this* module's output (so the 411 count stays literal and
testable) and handled one layer up:

- **`<hide/>`** marks an entry the legacy engine never offers as a standalone pick -- an
  auto-granted "weapon profile" a piece of gear/armor adds for you (e.g. buying the Armor-category
  `Ballistic Shield` -- cost 1200 -- auto-grants a same-named, 0-cost `Exotic Melee Weapons` weapon
  entry via `<addweapon>`, purely so the shield's melee-attack stats exist somewhere). 29 of the 266
  flat gear entries and 18 of the 134 flat weapon entries carry it.
- **Armor's `<armor>` field is sometimes a stacking bonus, not a standalone rating.** 3 of the 11
  flat armor entries (Helmet `+2`, Ballistic Shield `+6`, Riot Shield `+6`) use a `+N` *additive*
  armor bonus meant to stack on top of worn armor -- genuinely different math from every other flat
  armor item's single rating, and out of scope for this WP (see the Implementation Plan). Exposed
  here as `Armor.armor_stacks`/`Armor.armor_rating` so the engine layer can exclude them from the
  purchasable catalog rather than mis-adding them as if they were a normal armor rating.

Both of these matter because of a real data collision found while building the catalog on top of
this module: a `<hide/>` weapon-profile entry can share its *display name* with the real,
independently-purchasable gear/armor item it's a companion to, at a **different cost** (the
weapon-profile side is always 0) -- e.g. `Ballistic Shield` exists as both a 1200-cost `Armor` and a
0-cost `Exotic Melee Weapons` weapon. A name-keyed catalog (this project's `StarterGearItem` shape
since WP9) can't hold two same-named entries at different prices. `chummer5.engine.resources.build_
starter_gear_catalog` resolves this by dropping every `hidden` entry outright (not just when it
happens to collide) -- kept here rather than in this loader so `load_gear`/`load_armor`/
`load_weapons` each stay a literal, independently-testable translation of one XML file, with no
cross-file knowledge. One further, non-`hidden` collision (`Vision Magnification`: a 250-cost
standalone accessory vs. a 0-cost, `<required>`-gated sensor-housing component) and ~30 harmless
same-cost duplicates (e.g. `Grenade: Flash-Bang` priced identically as both `Ammunition` gear and a
throwable weapon) are resolved there too, by keeping the higher-cost entry.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

_DATA_DIR = Path(__file__).resolve().parents[3] / "legacy" / "Chummer" / "data"
DEFAULT_GEAR_PATH = _DATA_DIR / "gear.xml"
DEFAULT_ARMOR_PATH = _DATA_DIR / "armor.xml"
DEFAULT_WEAPONS_PATH = _DATA_DIR / "weapons.xml"

# MVP content scope: only entries carrying this <source> tag are loaded. See "MVP content scope" in
# Implementation Plan.md.
CORE_RULEBOOK_SOURCE = "SR5"

# A "flat-cost" <cost> is a bare non-negative integer literal -- no Rating/FixedValues/Variable
# formula, and no leading sign (which would mark a cost-modifier added to a parent's price, not a
# standalone item price -- see module docstring).
_FLAT_COST_RE = re.compile(r"\d+")


def _flat_cost(elem: ET.Element) -> int | None:
    text = elem.findtext("cost")
    if text is None:
        return None
    text = text.strip()
    if not _FLAT_COST_RE.fullmatch(text):
        return None
    return int(text)


@dataclass(frozen=True)
class Gear:
    """One flat-cost, SR5-sourced `<gear>` entry."""

    id: str
    name: str
    category: str
    cost: int
    hidden: bool
    source: str
    page: int


@dataclass(frozen=True)
class Armor:
    """One flat-cost, SR5-sourced `<armor>` entry.

    `armor_stacks` is true for the 3 items (Helmet, Ballistic Shield, Riot Shield) whose `<armor>`
    field is a `+N` additive bonus rather than a standalone rating -- see module docstring.
    `armor_rating` is still populated for those (`int("+2") == 2`), so the raw number survives even
    though the engine layer excludes them from the purchasable catalog.
    """

    id: str
    name: str
    category: str
    cost: int
    armor_rating: int
    armor_stacks: bool
    hidden: bool
    source: str
    page: int


@dataclass(frozen=True)
class Weapon:
    """One flat-cost, SR5-sourced `<weapon>` entry."""

    id: str
    name: str
    category: str
    cost: int
    hidden: bool
    source: str
    page: int


def load_gear(xml_path: Path = DEFAULT_GEAR_PATH) -> tuple[Gear, ...]:
    """Parse `gear.xml`, restricted to `source == "SR5"` and flat-cost entries (see module
    docstring)."""
    root = ET.parse(xml_path).getroot()
    gears_elem = root.find("gears")
    if gears_elem is None:
        return ()
    items = []
    for elem in gears_elem.findall("gear"):
        if elem.findtext("source") != CORE_RULEBOOK_SOURCE:
            continue
        cost = _flat_cost(elem)
        if cost is None:
            continue
        items.append(
            Gear(
                id=elem.findtext("id", ""),
                name=elem.findtext("name", ""),
                category=elem.findtext("category", ""),
                cost=cost,
                hidden=elem.find("hide") is not None,
                source=elem.findtext("source", ""),
                page=int(elem.findtext("page", "0")),
            )
        )
    return tuple(items)


def load_armor(xml_path: Path = DEFAULT_ARMOR_PATH) -> tuple[Armor, ...]:
    """Parse `armor.xml`, restricted to `source == "SR5"` and flat-cost entries (see module
    docstring)."""
    root = ET.parse(xml_path).getroot()
    armors_elem = root.find("armors")
    if armors_elem is None:
        return ()
    items = []
    for elem in armors_elem.findall("armor"):
        if elem.findtext("source") != CORE_RULEBOOK_SOURCE:
            continue
        cost = _flat_cost(elem)
        if cost is None:
            continue
        armor_text = elem.findtext("armor", "0").strip()
        items.append(
            Armor(
                id=elem.findtext("id", ""),
                name=elem.findtext("name", ""),
                category=elem.findtext("category", ""),
                cost=cost,
                armor_rating=int(armor_text),
                armor_stacks=armor_text.startswith(("+", "-")),
                hidden=elem.find("hide") is not None,
                source=elem.findtext("source", ""),
                page=int(elem.findtext("page", "0")),
            )
        )
    return tuple(items)


def load_weapons(xml_path: Path = DEFAULT_WEAPONS_PATH) -> tuple[Weapon, ...]:
    """Parse `weapons.xml`, restricted to `source == "SR5"` and flat-cost entries (see module
    docstring -- every SR5 weapon is already flat-cost, so this filter is a no-op for weapons today,
    kept for symmetry and as a guard against a future book's data breaking that assumption)."""
    root = ET.parse(xml_path).getroot()
    weapons_elem = root.find("weapons")
    if weapons_elem is None:
        return ()
    items = []
    for elem in weapons_elem.findall("weapon"):
        if elem.findtext("source") != CORE_RULEBOOK_SOURCE:
            continue
        cost = _flat_cost(elem)
        if cost is None:
            continue
        items.append(
            Weapon(
                id=elem.findtext("id", ""),
                name=elem.findtext("name", ""),
                category=elem.findtext("category", ""),
                cost=cost,
                hidden=elem.find("hide") is not None,
                source=elem.findtext("source", ""),
                page=int(elem.findtext("page", "0")),
            )
        )
    return tuple(items)
