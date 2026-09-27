"""Loader for `armor.xml`'s `<mods>` block (WP131).

**The catalog.** 32 `<mod>` rows carry `source == "SR5"`. 18 are `Liner - ...` rows in six
`Custom Liners (Rating N)` categories. No core armor opens those categories (an armor opens a
category through `<addmodcategory>`, or by its own category or name, legacy's
`AllowedCategories`), so they can never be installed and are not offered. The other 14 are exactly
what pp. 436-438 print:

- the **Clothing table's modifications** (p. 436): Electrochromic modification, Feedback clothing,
  (Synth)Leather;
- the **Armor Modifications table** (p. 438): Chemical Protection, Chemical Seal, Fire Resistance,
  Insulation, Nonconductivity, Shock Frills, Thermal Damping;
- the **indented sub-rows** under Full body armor (Full helmet, Chemical seal, Environment
  adaptation) and Urban Explorer Jumpsuit (Helmet), p. 436.

**Capacity** (p. 437): "The Capacity of a piece of armor is equal to its Armor Rating. Armor
modifications have variable Capacity costs." `<armorcapacity>` is `[N]`, or
`FixedValues([1],...,[6])` -- the table's `[Rating]`. One printed override: the Clothing table
prints no Capacity column, and Feedback clothing's `[3]` would make it impossible on the 0-Capacity
Clothing it is sold for, so the three Clothing-table rows cost no Capacity
(`_NO_CAPACITY_MODS`).

**Where a mod may go.** A mod's `<category>` must be `General`, the armor's own category or name, or
one the armor opens with `<addmodcategory>` -- legacy's rule. Printed text narrows it twice:
- p. 437: the Chemical seal is "Available only to full body armor that includes a helmet";
- p. 438: "Shields may be upgraded with the chemical protection, fire resistance, and
  nonconductivity armor modifications" -- and nothing else.

A `+N` Availability adds to the armor's own (the Clothing table's Electrochromic `+2`, the full body
armor sub-rows' `+6`/`+3`).
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

from chummer5.data.gear import CORE_RULEBOOK_SOURCE, DEFAULT_ARMOR_PATH

_UNREACHABLE_CATEGORY_PREFIX = "Custom Liners"

# The Clothing table's three modifications: no printed Capacity. See module docstring.
_NO_CAPACITY_MODS = frozenset({"Electrochromic Clothing", "Feedback Clothing", "(Synth)Leather"})

# p. 438: the only mods a shield takes.
SHIELD_MODS = frozenset({"Chemical Protection", "Fire Resistance", "Nonconductivity"})

_CAPACITY_RE = re.compile(r"\[(\d+)\]")
_RATING_COST_RE = re.compile(r"Rating\s*\*\s*(\d+)")

# The hand-kept mirror of the Project Overview's "Unmodeled real effects" rows for armor mods
# (WP131), keyed by mod name. The three that change an Armor value are computed, not listed.
_UNMODELED_EFFECT_NOTES: dict[str, str] = {
    "Electrochromic Clothing": (
        "Changes color or displays images (p. 437) -- a costume change with no test behind it."
    ),
    "Feedback Clothing": "A tactile AR component (p. 437) -- no AR or Matrix rules exist.",
    "Chemical Protection": (
        "Adds its rating to resist contact-vector toxins (p. 437) -- no toxin test exists."
    ),
    "Chemical Seal": (
        "Complete protection from contact and inhalation vectors for an hour (p. 437) -- no toxin "
        "test exists."
    ),
    "Full Body Armor: Chemical Seal": (
        "Complete protection from contact and inhalation vectors for an hour (p. 437) -- no toxin "
        "test exists."
    ),
    "Full Body Armor: Environment Adaptation": (
        "Adapted to hot or cold environments (p. 437) -- no environment rules exist."
    ),
    "Fire Resistance": (
        "Adds its rating to Armor against Fire damage (p. 437) -- no elemental damage test exists."
    ),
    "Insulation": (
        "Adds its rating to Armor against Cold damage (p. 437) -- no elemental damage test exists."
    ),
    "Nonconductivity": (
        "Adds its rating to Armor against Electricity damage (p. 438) -- no elemental damage test "
        "exists."
    ),
    "Shock Frills": (
        "Electricity damage to anyone touching you, 10 charges (p. 438) -- no attack test exists."
    ),
    "Thermal Damping": (
        "Adds its rating to the limit of Sneaking against thermal detection (p. 438) -- no "
        "Sneaking test exists."
    ),
}


@dataclass(frozen=True)
class ArmorMod:
    """One `<mod>` row. `capacity` is per point of rating when `capacity_per_rating` (the
    `FixedValues([1],...,[6])` rows), else flat. `cost` likewise is `cost * rating` when
    `cost_per_rating`. `armor` is what it adds to the armor's rating (the helmets, (Synth)Leather).
    `required_armor` is the parent armor a `<required><parentdetails>` names, if any."""

    id: str
    name: str
    category: str
    armor: int
    capacity: int
    capacity_per_rating: bool
    max_rating: int
    cost: int
    cost_per_rating: bool
    availability: str
    page: int
    required_armor: str | None
    unmodeled_effect_note: str | None = None

    @property
    def rated(self) -> bool:
        return self.max_rating > 1

    def capacity_at(self, rating: int) -> int:
        return self.capacity * rating if self.capacity_per_rating else self.capacity

    def cost_at(self, rating: int) -> int:
        return self.cost * rating if self.cost_per_rating else self.cost


def load_armor_mods(xml_path: Path = DEFAULT_ARMOR_PATH) -> tuple[ArmorMod, ...]:
    """The 14 installable SR5 armor mods -- see module docstring."""
    root = ET.parse(xml_path).getroot()
    block = root.find("mods")
    if block is None:
        return ()
    mods = []
    for elem in block.findall("mod"):
        if elem.findtext("source") != CORE_RULEBOOK_SOURCE:
            continue
        category = elem.findtext("category", "")
        if category.startswith(_UNREACHABLE_CATEGORY_PREFIX):
            continue
        name = elem.findtext("name", "")
        capacity_text = elem.findtext("armorcapacity", "[0]").strip()
        # `FixedValues([1],[2],...,[6])` is the printed `[Rating]`: one per rating point.
        per_rating = capacity_text.startswith("FixedValues")
        capacity_match = _CAPACITY_RE.search(capacity_text)
        if name in _NO_CAPACITY_MODS or capacity_match is None:
            capacity = 0
        else:
            capacity = 1 if per_rating else int(capacity_match.group(1))
        cost_text = elem.findtext("cost", "0").strip()
        cost_match = _RATING_COST_RE.fullmatch(cost_text)
        if cost_match:
            cost, cost_per_rating = int(cost_match.group(1)), True
        elif cost_text.isdigit():
            cost, cost_per_rating = int(cost_text), False
        else:
            continue
        required = elem.find("required/parentdetails/name")
        mods.append(
            ArmorMod(
                id=elem.findtext("id", ""),
                name=name,
                category=category,
                armor=int(elem.findtext("armor", "0").strip() or "0"),
                capacity=capacity,
                capacity_per_rating=per_rating,
                max_rating=int(elem.findtext("maxrating", "1") or "1"),
                cost=cost,
                cost_per_rating=cost_per_rating,
                availability=elem.findtext("avail", "0").strip(),
                page=int(elem.findtext("page", "0") or "0"),
                required_armor=(required.text or "").strip() if required is not None else None,
                unmodeled_effect_note=_UNMODELED_EFFECT_NOTES.get(name),
            )
        )
    return tuple(mods)


@dataclass(frozen=True)
class ArmorModSlots:
    """What a mod needs to know about an armor: its Capacity, Availability, category, and the mod
    categories it opens (`<addmodcategory>`)."""

    name: str
    category: str
    capacity: int
    availability: str
    mod_categories: tuple[str, ...]


def load_armor_mod_slots(xml_path: Path = DEFAULT_ARMOR_PATH) -> dict[str, ArmorModSlots]:
    """SR5 armor by name."""
    root = ET.parse(xml_path).getroot()
    block = root.find("armors")
    if block is None:
        return {}
    result = {}
    for elem in block.findall("armor"):
        if elem.findtext("source") != CORE_RULEBOOK_SOURCE:
            continue
        name = elem.findtext("name", "")
        capacity_text = elem.findtext("armorcapacity", "0").strip()
        result[name] = ArmorModSlots(
            name=name,
            category=elem.findtext("category", ""),
            capacity=int(capacity_text) if capacity_text.isdigit() else 0,
            availability=elem.findtext("avail", "0").strip(),
            mod_categories=tuple((c.text or "").strip() for c in elem.findall("addmodcategory")),
        )
    return result
