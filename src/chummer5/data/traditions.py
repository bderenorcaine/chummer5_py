"""Loader for `legacy/Chummer/data/traditions.xml`, SR5-core, non-Custom traditions only.

`traditions.xml` has 3 `source == "SR5"` entries: Custom, Hermetic, Shamanic. Custom is excluded
here (not just filtered out downstream, mirroring `chummer5.data.qualities`'s "filter at load time"
precedent, since this loader has no other consumer that would want the unfiltered list): unlike
Hermetic/Shamanic, Custom requires the player to hand-define a drain-attribute pair and a
spirit-affinity table rather than picking a fixed catalog entry — a different kind of feature, out
of Phase I's scope entirely (see Implementation Plan's Phase I intro). That leaves exactly 2 offered
traditions, matching the phase intro's own count.

Every SR5 tradition's `<drain>` element is a formula string like `"{WIL} + {LOG}"` — two
brace-wrapped attribute codes joined by `" + "` (confirmed by inspecting every entry in the raw
XML, not assumed). `_parse_drain_attributes` extracts just the two codes; nothing in this phase's
scope needs to evaluate the `" + "` itself as a general formula language, since `chummer5.engine
.derived`'s eventual Drain Resistance (WP28) just needs the two attribute codes to sum.

**WP46** widens `Tradition` with `spirits: SpiritAffinities` -- each SR5 tradition's `<spirits>`
block maps 5 fixed roles (combat/detection/health/illusion/manipulation) onto one of the core
rulebook's 6 spirit types ("Spirit of Air"/"Beasts"/"Earth"/"Fire"/"Man"/"Water", confirmed against
the Magic chapter's own "Spirits" section, p. 303 -- see `spec/rulebooks/learnings.md`'s WP46
entry). Confirmed directly, not assumed: Hermetic and Shamanic each name a *different* 5 of the 6
types (both omit exactly one -- Hermetic never offers Beasts, Shamanic never offers Fire), so which
spirit types a Magician may bind is tradition-dependent, not one universal list.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

# legacy/Chummer/data/traditions.xml, resolved relative to this file (not cwd).
DEFAULT_TRADITIONS_PATH = (
    Path(__file__).resolve().parents[3] / "legacy" / "Chummer" / "data" / "traditions.xml"
)

# MVP/Phase I content scope: only entries carrying this <source> tag are loaded.
CORE_RULEBOOK_SOURCE = "SR5"

# Custom is source == "SR5" too, but excluded — see module docstring.
EXCLUDED_TRADITION_NAMES = frozenset({"Custom"})

_DRAIN_ATTRIBUTE_RE = re.compile(r"\{(\w+)\}")


@dataclass(frozen=True)
class SpiritAffinities:
    """Which spirit type (e.g. "Spirit of Fire") a tradition summons for each of the 5 fixed
    Conjuring roles -- parsed verbatim from `<spirits>`'s 5 children, not modeled as a general
    name->name mapping since every SR5-core tradition carries exactly these 5, no more, no fewer.
    """

    combat: str
    detection: str
    health: str
    illusion: str
    manipulation: str

    @property
    def offered_types(self) -> tuple[str, ...]:
        """The (at most 5, usually distinct) spirit type names this tradition can summon/bind --
        WP46's `offered_spirit_types` reads this rather than the 5 named fields directly, since a
        Bound Spirits picker cares about "which types are legal", not which role each maps to."""
        return (self.combat, self.detection, self.health, self.illusion, self.manipulation)


@dataclass(frozen=True)
class Tradition:
    id: str
    name: str
    drain_attributes: tuple[str, str]  # e.g. ("WIL", "LOG") for Hermetic
    source: str
    page: int
    spirits: SpiritAffinities


def _parse_drain_attributes(raw: str) -> tuple[str, str]:
    codes = _DRAIN_ATTRIBUTE_RE.findall(raw)
    if len(codes) != 2:
        raise ValueError(
            f"expected exactly 2 brace-wrapped drain attributes in {raw!r}, got {codes}"
        )
    return (codes[0], codes[1])


def _parse_spirits(elem: ET.Element | None) -> SpiritAffinities:
    if elem is None:
        raise ValueError("tradition has no <spirits> block")
    return SpiritAffinities(
        combat=elem.findtext("spiritcombat", ""),
        detection=elem.findtext("spiritdetection", ""),
        health=elem.findtext("spirithealth", ""),
        illusion=elem.findtext("spiritillusion", ""),
        manipulation=elem.findtext("spiritmanipulation", ""),
    )


def _parse_tradition(elem: ET.Element) -> Tradition:
    return Tradition(
        id=elem.findtext("id", ""),
        name=elem.findtext("name", ""),
        drain_attributes=_parse_drain_attributes(elem.findtext("drain", "")),
        source=elem.findtext("source", ""),
        page=int(elem.findtext("page", "0")),
        spirits=_parse_spirits(elem.find("spirits")),
    )


def load_traditions(xml_path: Path = DEFAULT_TRADITIONS_PATH) -> tuple[Tradition, ...]:
    """Parse `traditions.xml`, restricted to `source == "SR5"` and excluding Custom (2 of 3)."""
    root = ET.parse(xml_path).getroot()
    traditions_elem = root.find("traditions")
    if traditions_elem is None:
        return ()
    return tuple(
        _parse_tradition(t)
        for t in traditions_elem.findall("tradition")
        if t.findtext("source") == CORE_RULEBOOK_SOURCE
        and t.findtext("name") not in EXCLUDED_TRADITION_NAMES
    )
