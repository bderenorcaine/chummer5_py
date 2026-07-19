"""Loader for `legacy/Chummer/data/spells.xml`, restricted to `source == "SR5"` (93 of 363 entries).

MVP's "core rulebook only" scope narrows the file the same way `chummer5.data.qualities` narrows
`qualities.xml`. Unlike qualities, a spell needs no `<bonus>`-node classification at all: per the
Implementation Plan's Phase I intro (WP26), a spell is a chargen-time roster entry, not a computed
value -- this engine has no casting-test/drain-resolution system to model at chargen (mirrors
mundane MVP's own "no combat system" posture), so every field captured here is descriptive
(category/damage/duration/dv/range/type/descriptor), not consumed by any formula. A handful of SR5
spells (7 of 93 -- the `Detect [...]`/`Increase [Attribute]`/`Decrease [Attribute]` family) carry a
`<bonus>` node prompting an in-play player choice (which attribute, what to detect); confirmed this
is a target/effect *parameter* for the spell's own in-play resolution, not a chargen-time
Improvement grant the way a quality's `<bonus>` is -- so it's deliberately not parsed at all here.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

# legacy/Chummer/data/spells.xml, resolved relative to this file (not cwd).
DEFAULT_SPELLS_PATH = (
    Path(__file__).resolve().parents[3] / "legacy" / "Chummer" / "data" / "spells.xml"
)

# MVP content scope: only entries carrying this <source> tag are loaded. See "MVP content scope" in
# Implementation Plan.md.
CORE_RULEBOOK_SOURCE = "SR5"


@dataclass(frozen=True)
class Spell:
    """One SR5-sourced `<spell>` entry -- a chargen-time roster item, not a computed value.

    `damage`/`duration`/`dv`/`range`/`type` are the raw SR5 shorthand codes (e.g. `damage="P"` for
    Physical, `duration="I"` for Instant, `dv="F-3"` for a Force-relative Drain Value) kept as-is
    for display; this engine has no in-play resolution system to interpret them against.
    """

    id: str
    name: str
    category: str  # Combat/Detection/Health/Illusion/Manipulation/Rituals
    damage: str
    duration: str
    dv: str
    range: str
    type: str
    descriptor: str
    source: str
    page: int


def _parse_spell(elem: ET.Element) -> Spell:
    return Spell(
        id=elem.findtext("id", ""),
        name=elem.findtext("name", ""),
        category=elem.findtext("category", ""),
        damage=elem.findtext("damage", ""),
        duration=elem.findtext("duration", ""),
        dv=elem.findtext("dv", ""),
        range=elem.findtext("range", ""),
        type=elem.findtext("type", ""),
        descriptor=elem.findtext("descriptor", ""),
        source=elem.findtext("source", ""),
        page=int(elem.findtext("page", "0")),
    )


def load_spells(xml_path: Path = DEFAULT_SPELLS_PATH) -> tuple[Spell, ...]:
    """Parse `spells.xml`, restricted to `source == "SR5"` entries (93 of 363)."""
    root = ET.parse(xml_path).getroot()
    spells_elem = root.find("spells")
    if spells_elem is None:
        return ()
    return tuple(
        _parse_spell(s)
        for s in spells_elem.findall("spell")
        if s.findtext("source") == CORE_RULEBOOK_SOURCE
    )
