"""Loader for `legacy/Chummer/data/skills.xml`'s active-skill list.

Only `<skills>` (active skills) is parsed — `<knowledgeskills>` is out of MVP scope per the Project
Overview's in-scope list ("active skills (+ specializations, skill groups)"; knowledge skills aren't
mentioned). All 76 `<skill>` entries are already `source == "SR5"` (confirmed in WP2 and re-checked
here), so unlike `metatypes.py`/`qualities.py` this loader needs no MVP-scope source filter.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

# legacy/Chummer/data/skills.xml, resolved relative to this file (not cwd).
DEFAULT_SKILLS_PATH = (
    Path(__file__).resolve().parents[3] / "legacy" / "Chummer" / "data" / "skills.xml"
)


@dataclass(frozen=True)
class Skill:
    id: str
    name: str
    attribute: str  # linked attribute code, e.g. "AGI"
    category: str  # e.g. "Combat Active", "Technical Active"
    skill_group: str | None  # None for skills that don't belong to a skill group
    can_default: bool  # whether the skill can be used untrained, at rating 0
    exotic: bool  # exotic skills (Exotic Melee/Ranged Weapon, Pilot Exotic Vehicle) are bought
    # per-specific-item rather than as a single general rating (WP124: see `specific`).
    specializations: tuple[str, ...]  # suggested specializations; not an exhaustive/enforced list
    source: str
    page: int
    # WP124: the named weapon or vehicle of one exotic-skill *instance* ("Flamethrower"); `None`
    # for a catalog entry. Instances come from `chummer5.engine.skills.exotic_instance`.
    specific: str | None = None


def _parse_specializations(elem: ET.Element) -> tuple[str, ...]:
    specs_elem = elem.find("specs")
    if specs_elem is None:
        return ()
    return tuple(spec.text or "" for spec in specs_elem.findall("spec"))


def _parse_skill(elem: ET.Element) -> Skill:
    return Skill(
        id=elem.findtext("id", ""),
        name=elem.findtext("name", ""),
        attribute=elem.findtext("attribute", ""),
        category=elem.findtext("category", ""),
        skill_group=elem.findtext("skillgroup") or None,
        can_default=elem.findtext("default", "False") == "True",
        exotic=elem.findtext("exotic", "False") == "True",
        specializations=_parse_specializations(elem),
        source=elem.findtext("source", ""),
        page=int(elem.findtext("page", "0")),
    )


def load_skills(xml_path: Path = DEFAULT_SKILLS_PATH) -> tuple[Skill, ...]:
    """Parse every `<skill>` (active skill) in `skills.xml`."""
    root = ET.parse(xml_path).getroot()
    skills_elem = root.find("skills")
    if skills_elem is None:
        return ()
    return tuple(_parse_skill(s) for s in skills_elem.findall("skill"))
