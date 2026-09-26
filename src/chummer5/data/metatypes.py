"""Loader for `legacy/Chummer/data/metatypes.xml` into frozen dataclasses.

Parses attribute min/max/augmented-max ranges and metavariants for every metatype in the file.
**WP113** parses the three `<bonus>` children the SR5 base metatypes carry (`lifestylecost`,
`reach`, `armor`) -- see `Metatype.lifestyle_cost_percent`. The rest of this paragraph predates it.

Deliberately does not model `bonus`/`powers`/`addweapon`/`qualityrestriction`/
`halveattributepoints`/`movement` — those describe mechanics (the general Improvement engine,
critter powers, movement rates) that are out of MVP scope. See `spec/worklogs/WP2.md` for the
full reasoning.

**WP23**: the base `<metatype><qualities>` block (which SR5-core qualities a metatype grants for
free — e.g. Elf/Ork → Low-Light Vision) *is* parsed, into `Metatype.qualities_positive`/
`qualities_negative`, mirroring the fields `Metavariant` already had. This was a real, previously
undiscovered gap through WP22 — see `spec/worklogs/WP23.md` and the Project Overview's 2026-07-19
Open Questions entry. `chummer5.engine.qualities.resolve_metatype_qualities` turns these names into
real `Quality` objects and grants them automatically at character creation.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType

# legacy/Chummer/data/metatypes.xml, resolved relative to this file (not cwd).
DEFAULT_METATYPES_PATH = (
    Path(__file__).resolve().parents[3] / "legacy" / "Chummer" / "data" / "metatypes.xml"
)

# Standard SR5 attribute abbreviations, matching
# legacy/Chummer/Backend/Attributes/AttributeSection.cs. XML tag prefix -> attribute code. INI has
# no priority-spent points (Initiative is derived) but the source data carries a range for it, so
# it's kept for fidelity.
_ATTRIBUTE_TAG_PREFIXES = {
    "bod": "BOD",
    "agi": "AGI",
    "rea": "REA",
    "str": "STR",
    "cha": "CHA",
    "int": "INT",
    "log": "LOG",
    "wil": "WIL",
    "ini": "INI",
    "edg": "EDG",
    "mag": "MAG",
    "res": "RES",
    "ess": "ESS",
    "dep": "DEP",
}


@dataclass(frozen=True)
class AttributeRange:
    """A metatype's allowed range for one attribute."""

    minimum: int
    maximum: int
    augmented: int


@dataclass(frozen=True)
class Metavariant:
    id: str
    name: str
    karma: int
    attributes: MappingProxyType[str, AttributeRange]
    qualities_positive: tuple[str, ...]
    qualities_negative: tuple[str, ...]
    source: str
    page: int


@dataclass(frozen=True)
class Metatype:
    id: str
    name: str
    category: str
    karma: int
    attributes: MappingProxyType[str, AttributeRange]
    source: str
    page: int
    metavariants: tuple[Metavariant, ...]
    qualities_positive: tuple[str, ...] = ()
    qualities_negative: tuple[str, ...] = ()
    # WP113: the racial column of the Metatype Attribute Table, from `<bonus>` -- the Lifestyle
    # surcharge in percent (Dwarf 20, Troll 100), extra Reach (Troll 1), and racial dermal armor
    # (Troll 1, in legacy's dedup group `armor_group` -- "group0", shared with Dermal Plating and
    # Orthoskin, so they never stack).
    lifestyle_cost_percent: int = 0
    reach: int = 0
    armor: int = 0
    armor_group: str | None = None
    # WP113: this metatype's own racial effect that this engine can't compute, for the sheet's
    # "Unmodeled real effects" section (the Project Overview registry's matching row).
    unmodeled_effect_note: str | None = None


# WP113: the racial effects no engine number reads, keyed by metatype name. Troll's +1 Reach
# lengthens its melee range (p. 185); there is no melee resolution here.
_UNMODELED_EFFECT_NOTES = {
    "Troll": "+1 Reach (p. 185) -- no melee-combat resolution exists for Reach to matter in.",
}


def _parse_attribute_ranges(elem: ET.Element) -> MappingProxyType[str, AttributeRange]:
    ranges = {}
    for prefix, code in _ATTRIBUTE_TAG_PREFIXES.items():
        ranges[code] = AttributeRange(
            minimum=int(elem.findtext(f"{prefix}min", "0")),
            maximum=int(elem.findtext(f"{prefix}max", "0")),
            augmented=int(elem.findtext(f"{prefix}aug", "0")),
        )
    return MappingProxyType(ranges)


def _parse_quality_names(elem: ET.Element | None, tag: str) -> tuple[str, ...]:
    if elem is None:
        return ()
    group = elem.find(tag)
    if group is None:
        return ()
    return tuple(q.text or "" for q in group.findall("quality"))


def _parse_metavariant(elem: ET.Element) -> Metavariant:
    qualities = elem.find("qualities")
    return Metavariant(
        id=elem.findtext("id", ""),
        name=elem.findtext("name", ""),
        karma=int(elem.findtext("karma", "0")),
        attributes=_parse_attribute_ranges(elem),
        qualities_positive=_parse_quality_names(qualities, "positive"),
        qualities_negative=_parse_quality_names(qualities, "negative"),
        source=elem.findtext("source", ""),
        page=int(elem.findtext("page", "0")),
    )


def _parse_metatype(elem: ET.Element) -> Metatype:
    metavariants_elem = elem.find("metavariants")
    metavariants = (
        tuple(_parse_metavariant(mv) for mv in metavariants_elem.findall("metavariant"))
        if metavariants_elem is not None
        else ()
    )
    qualities = elem.find("qualities")
    bonus = elem.find("bonus")
    armor = bonus.find("armor") if bonus is not None else None
    name = elem.findtext("name", "")
    return Metatype(
        id=elem.findtext("id", ""),
        name=elem.findtext("name", ""),
        category=elem.findtext("category", ""),
        karma=int(elem.findtext("karma", "0")),
        attributes=_parse_attribute_ranges(elem),
        source=elem.findtext("source", ""),
        page=int(elem.findtext("page", "0")),
        metavariants=metavariants,
        qualities_positive=_parse_quality_names(qualities, "positive"),
        qualities_negative=_parse_quality_names(qualities, "negative"),
        lifestyle_cost_percent=int(bonus.findtext("lifestylecost", "0"))
        if bonus is not None
        else 0,
        reach=int(bonus.findtext("reach", "0")) if bonus is not None else 0,
        armor=int(armor.text or "0") if armor is not None else 0,
        armor_group=(
            f"group{armor.get('group')}" if armor is not None and armor.get("group") else None
        ),
        unmodeled_effect_note=_UNMODELED_EFFECT_NOTES.get(name),
    )


def load_metatypes(xml_path: Path = DEFAULT_METATYPES_PATH) -> tuple[Metatype, ...]:
    """Parse every `<metatype>` in `metatypes.xml` into a `Metatype` dataclass."""
    root = ET.parse(xml_path).getroot()
    metatypes_elem = root.find("metatypes")
    if metatypes_elem is None:
        return ()
    return tuple(_parse_metatype(m) for m in metatypes_elem.findall("metatype"))
