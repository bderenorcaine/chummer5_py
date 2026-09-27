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

**The Matrix stat block (WP94).** `load_gear` also reads each flat entry's `<avail>` and its
Matrix-device stats (`<devicerating>`, `<attack>`, `<sleaze>`, `<dataprocessing>`, `<firewall>`,
`<programs>`, `<attributearray>`) into optional `Gear` fields. These were discarded entirely
before, which meant this project sold Commlinks, Cyberdecks and Rigger Command Consoles as a name
and a price with their whole printed stat block thrown away (Implementation Plan, Phase P, WP90
§3). The counts above are unchanged by this -- it adds fields, not rows; the loader stays a
literal pass and every filter still lives one layer up. What *did* change one layer up is that
`chummer5.engine.resources.build_starter_gear_catalog` now applies the Availability<=12 ruling to
those three categories, dropping 6 rows (1 commlink, 2 cyberdecks, 3 RCCs) from the 379-item
purchasable catalog to leave **373**. That cap is still **not** applied to the rest of the
flat-cost catalog -- see that function's docstring and `spec/decisions-log.md`'s 2026-08-01 entry
for the size of the unscheduled general backfill.

**Unmodeled-effect notes (WP95).** `_UNMODELED_EFFECT_NOTES` below is this module's hand-kept
mirror of the Project Overview's "Unmodeled real effects" table, exactly as
`chummer5.data.qualities._UNMODELED_EFFECT_NOTES` (WP56) and `chummer5.data.cyberware
.UNMODELED_EFFECT_NOTES` (WP79) already are for their own catalogs -- runtime code never reads a
`.md` file as data. It is keyed by **category**, not by item name: unlike a quality or a piece of
cyberware, every row in a gear category here has the *same* unmodeled effect (every RCC is a
Matrix device in a project with no Matrix rules; every autosoft is a drone skill in a project with
no drone tests), so 30-odd identical per-name entries would be a mirror with 30 chances to drift.
Both loaders stamp the note onto every row of a covered category.

**It covers the rigger surface only, deliberately.** Four categories (Commlinks, Cyberdecks,
Rigger Command Consoles, Autosofts) of roughly fifty. The other ~50 stay unannotated, the same way
WP79 annotated cyberware without claiming every catalog -- see Phase P's own "explicitly out of
this phase" list.

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
# WP95: the hand-kept mirror of the Project Overview's "Unmodeled real effects" rows for gear,
# keyed by <category> -- see this module's docstring for why by category rather than by name, and
# why only these four. A WP that edits a row here must edit that table in the same commit.
_UNMODELED_EFFECT_NOTES: dict[str, str] = {
    "Commlinks": (
        "Its Device Rating, Data Processing and Firewall (pp. 226, 438) are recorded and shown but "
        "feed nothing -- this project has no Matrix rules at all, so there is no Matrix test, no "
        "PAN, no noise and no hacking defence for them to be a limit or a dice pool in."
    ),
    "Cyberdecks": (
        "Its Device Rating, Attribute Array and program count (p. 439) are recorded and shown but "
        "feed nothing -- this project has no Matrix rules at all. The array's four values are also "
        "assigned among Attack/Sleaze/Data Processing/Firewall in play, a choice nothing here "
        "records, and the deck's built-in hot-sim module has no simsense or VR representation."
    ),
    "Rigger Command Consoles": (
        "Its Device Rating, Data Processing and Firewall (p. 267) are recorded and shown but feed "
        "nothing -- no Matrix rules exist. Everything an RCC is actually for is equally absent: "
        "slaving up to (Device Rating x 3) drones into a WAN, the Noise Reduction/Sharing split "
        "you set at boot, and running shared autosofts for the slaved drones."
    ),
    "Autosofts": (
        "An autosoft is a drone's skill (p. 269) -- Clearsight acts as its Perception, "
        "[Model] Maneuvering as its Pilot skill, and so on. There is no drone test resolution "
        "here for one to roll into, no autosoft slot accounting (a drone runs half its Device "
        "Rating, rounded up), and no way to tie a [Model]/[Weapon] copy to the drone or weapon it "
        "is bought for. Its Rating-scaled nuyen cost is modeled."
    ),
}

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


def _matrix_int(elem: ET.Element, tag: str) -> int | None:
    """One Matrix-device stat as a plain integer, or None if the tag is absent or isn't a bare
    integer (WP94). Fail-closed rather than guessing -- see `Gear`'s docstring for the one SR5 row
    (`Living Persona`, `{RES}`) that takes the None path.
    """
    text = elem.findtext(tag)
    if text is None:
        return None
    text = text.strip()
    return int(text) if text.isdigit() else None


def _attribute_array(elem: ET.Element) -> tuple[int, ...] | None:
    """A cyberdeck's `<attributearray>` (`"4,3,2,1"`) as a tuple, in the printed descending order
    (WP94). None if absent or not a comma-separated integer list.
    """
    text = elem.findtext("attributearray")
    if text is None:
        return None
    parts = [part.strip() for part in text.split(",")]
    if not parts or not all(part.isdigit() for part in parts):
        return None
    return tuple(int(part) for part in parts)


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


_AVAIL_FIXED_VALUES_RE = re.compile(r"FixedValues\(([^)]*)\)")


def availability_at_rating(avail: str, rating: int) -> int | None:
    """An `<avail>`'s magnitude at `rating` (WP126), or None for a form this can't read.

    `parse_rating_availability`'s forms, plus `FixedValues(a,b,c)` -- Wired Reflexes'
    `FixedValues(8R,12R,20R)` -- indexed 1-based by rating and clamped at both ends, the same rule
    `chummer5.data.cyberware_formula` documents for cost and Essence.
    """
    fixed = _AVAIL_FIXED_VALUES_RE.fullmatch(avail.strip())
    if fixed:
        values = [_AVAIL_RESTRICTION_RE.sub("", v.strip()) for v in fixed.group(1).split(",")]
        if not all(v.isdigit() for v in values):
            return None
        return int(values[min(max(rating, 1), len(values)) - 1])
    parsed = parse_rating_availability(avail)
    if parsed is None:
        return None
    slope, intercept = parsed
    return slope * rating + intercept


@dataclass(frozen=True)
class Gear:
    """One flat-cost, SR5-sourced `<gear>` entry.

    **WP94: the Matrix stat block.** `availability` (the raw `<avail>` text, `R`/`F` marker and
    all) plus the six Matrix-device fields were read by nobody before -- a Fairlight Excalibur was
    a name and a price and nothing else. All seven are optional because most gear isn't a Matrix
    device at all: only 49 of the 266 flat SR5 rows carry a `<devicerating>`, and among the three
    categories WP94 actually renders, commlinks/RCCs carry `data_processing`/`firewall` while
    cyberdecks carry `attribute_array`/`programs` instead (p. 226: "Most devices (including
    commlinks) have only two Matrix attributes: Data Processing and Firewall. Decks and hosts have
    all four, including Attack and Sleaze").

    `attribute_array` is the cyberdeck's four assignable Matrix attributes in descending order
    (p. 439), **not** four labelled columns -- it is deliberately a tuple rather than four named
    fields, so nothing downstream can assert an Attack/Sleaze/DP/Firewall assignment the rules
    leave to the decker.

    Every one of the six parses fail-closed to `None` rather than guessing: `Living Persona`'s
    `<devicerating>{RES}</devicerating>` (an attribute reference, not a number) is the one SR5 flat
    row that hits that path, and it is `<hide/>`-marked and dropped from the purchasable catalog
    anyway.

    **WP95: `unmodeled_effect_note`.** Set for every row in a category covered by
    `_UNMODELED_EFFECT_NOTES`, `None` otherwise -- the same field name `chummer5.data.qualities
    .Quality` and `chummer5.data.cyberware.Cyberware` already carry, read by
    `chummer5.engine.derived.unmodeled_effect_notes` through a plain `getattr`.
    """

    id: str
    name: str
    category: str
    cost: int
    hidden: bool
    source: str
    page: int
    availability: str = ""
    device_rating: int | None = None
    attack: int | None = None
    sleaze: int | None = None
    data_processing: int | None = None
    firewall: int | None = None
    programs: int | None = None
    attribute_array: tuple[int, ...] | None = None
    unmodeled_effect_note: str | None = None


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
    unmodeled_effect_note: str | None = None


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
                availability=elem.findtext("avail", "").strip(),
                device_rating=_matrix_int(elem, "devicerating"),
                attack=_matrix_int(elem, "attack"),
                sleaze=_matrix_int(elem, "sleaze"),
                data_processing=_matrix_int(elem, "dataprocessing"),
                firewall=_matrix_int(elem, "firewall"),
                programs=_matrix_int(elem, "programs"),
                attribute_array=_attribute_array(elem),
                unmodeled_effect_note=_UNMODELED_EFFECT_NOTES.get(elem.findtext("category", "")),
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

    WP95: the Autosofts category's `unmodeled_effect_note` is stamped here -- all 6 SR5 autosofts
    are `Rating * 500`-priced, so they are this loader's rows, not `load_gear`'s.
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
                unmodeled_effect_note=_UNMODELED_EFFECT_NOTES.get(elem.findtext("category", "")),
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
