"""Loaders for `legacy/Chummer/data/{gear,armor,weapons}.xml`, restricted to `source == "SR5"` and
to items whose `<cost>` is a plain, non-negative integer literal -- what the Implementation Plan
(WP21) calls "flat-cost": no `Rating`-scaled formula (`Rating * 2500`), no
`FixedValues(...)`/`Variable(...)` formula, and no `+N` cost-modifier shorthand (a handful of
accessories, e.g. Card Reader/Biometric Reader, whose `<cost>` is *added to a parent item's* cost
rather than being a standalone price).

**Rating-priced gear (WP66).** `load_rating_gear` is the deliberate complement to `load_gear`'s
flat-cost filter over the *same* `gear.xml`: the 120 SR5-sourced entries whose `<cost>` is a
`Rating * N` formula (Fake SINs, AR glasses/goggles/contacts, earbuds/headphones, medkits, and the
rest), previously excluded entirely by WP21. Their price scales with a Rating picked at purchase
(`cost = chosen_rating * cost_per_rating`), and their `<avail>` often scales with Rating too --
`parse_rating_availability` turns that into a `slope*rating + intercept` linear form so the engine's
Availability<=12 cap (Project Overview's 2026-07-21 ruling) can clamp the offered rating range.
This loader stays a literal XML->dataclass pass; the cap, the Foci/Formulae exclusion (those two
categories are owned by the dedicated `chummer5.data.foci`/`chummer5.engine.foci` bonding system,
not offered as plain gear), and the flat/rating name-collision resolution all live one layer up in
`chummer5.engine.resources.build_starter_gear_catalog`.

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

# A "rating-priced" <cost> is `Rating * N` (optionally without surrounding spaces, e.g.
# `Rating*250`) -- the item's price scales with the Rating the player picks at purchase (WP66). N is
# captured as the per-rating unit cost. See module docstring's Rating-priced section.
_RATING_COST_RE = re.compile(r"Rating\s*\*\s*(\d+)")

# An <avail> that scales with Rating is a linear `slope * Rating + intercept`. The trailing R/F
# (Restricted/Forbidden) legality marker is stripped before parsing -- only the numeric magnitude
# matters for WP66's Availability<=12 cap. A leading `+` marks a modifier added to a *parent* item's
# availability (an accessory, not a standalone pick) -- excluded, mirroring load_gear's `+`-cost
# accessory exclusion.
_AVAIL_RESTRICTION_RE = re.compile(r"[RF]$")
_AVAIL_TIMES_RE = re.compile(r"Rating\s*\*\s*(\d+)")
_AVAIL_PLUS_RE = re.compile(r"Rating\s*\+\s*(\d+)")


def _flat_cost(elem: ET.Element) -> int | None:
    text = elem.findtext("cost")
    if text is None:
        return None
    text = text.strip()
    if not _FLAT_COST_RE.fullmatch(text):
        return None
    return int(text)


def _rating_cost(elem: ET.Element) -> int | None:
    """The per-rating unit cost N of a `Rating * N` <cost>, or None if it isn't rating-priced."""
    text = elem.findtext("cost")
    if text is None:
        return None
    match = _RATING_COST_RE.fullmatch(text.strip())
    return int(match.group(1)) if match else None


def parse_rating_availability(avail: str) -> tuple[int, int] | None:
    """Parse a Rating-scaled `<avail>` into `(slope, intercept)` so availability at a given rating
    is `slope * rating + intercept`.

    Returns None for a `+`-prefixed modifier (an accessory added to a parent item's availability,
    not a standalone value -- excluded from the purchasable catalog, mirroring load_gear's `+`-cost
    accessory exclusion) or for any form this parser doesn't recognize (excluded, fail-closed). The
    trailing R/F legality marker is ignored -- only the magnitude matters for WP66's <=12 cap.

    Handles every shape seen in SR5-sourced Rating-priced `gear.xml` entries: bare integers (`0`,
    `8R`, `12F`), `Rating`/`(Rating)`/`(Rating)R`, `Rating * N`/`(Rating * N)F`, `(Rating + N)R`.
    """
    text = avail.strip()
    if text.startswith("+"):
        return None
    text = _AVAIL_RESTRICTION_RE.sub("", text).strip()
    if text.startswith("(") and text.endswith(")"):
        text = text[1:-1].strip()
    if text.isdigit():
        return (0, int(text))
    times = _AVAIL_TIMES_RE.fullmatch(text)
    if times:
        return (int(times.group(1)), 0)
    plus = _AVAIL_PLUS_RE.fullmatch(text)
    if plus:
        return (1, int(plus.group(1)))
    if text == "Rating":
        return (1, 0)
    return None


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
class RatingGear:
    """One SR5-sourced `<gear>` entry whose `<cost>` is a `Rating * N` formula (WP66).

    Unlike flat `Gear`, price isn't fixed: `cost_per_rating` is N, `max_rating` is the item's
    `<rating>` cap, and the actual cost is `chosen_rating * cost_per_rating`. `availability` is the
    raw `<avail>` string, parsed one layer up (`parse_rating_availability`) so the engine's
    Availability<=12 cap can clamp the offered rating range.
    """

    id: str
    name: str
    category: str
    cost_per_rating: int
    max_rating: int
    availability: str
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


def load_rating_gear(xml_path: Path = DEFAULT_GEAR_PATH) -> tuple[RatingGear, ...]:
    """Parse `gear.xml`, restricted to `source == "SR5"` and `Rating * N`-cost entries (WP66).

    The complement of `load_gear`'s flat-cost filter over the same file: 120 SR5-sourced entries
    across gear/audio/vision/etc. that `load_gear` drops because their price scales with Rating.
    A literal per-entry translation like the other loaders -- the Availability<=12 cap, the
    Foci/Formulae exclusion, and the flat/rating name-collision resolution all live one layer up in
    `chummer5.engine.resources.build_starter_gear_catalog`, so this stays a plain XML->dataclass
    pass with no cross-file knowledge.
    """
    root = ET.parse(xml_path).getroot()
    gears_elem = root.find("gears")
    if gears_elem is None:
        return ()
    items = []
    for elem in gears_elem.findall("gear"):
        if elem.findtext("source") != CORE_RULEBOOK_SOURCE:
            continue
        cost_per_rating = _rating_cost(elem)
        if cost_per_rating is None:
            continue
        items.append(
            RatingGear(
                id=elem.findtext("id", ""),
                name=elem.findtext("name", ""),
                category=elem.findtext("category", ""),
                cost_per_rating=cost_per_rating,
                max_rating=int(elem.findtext("rating", "0") or "0"),
                availability=elem.findtext("avail", "0").strip(),
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
