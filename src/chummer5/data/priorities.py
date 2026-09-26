"""Loader for `legacy/Chummer/data/priorities.xml`, Standard prioritytable only.

Heritage/Attributes/Skills/Resources categories are parsed in full (that's what priority-based
mundane chargen needs). The Talent category is parsed too, but only at the flat-scalar level of
each `<talent>` option (name, magic/resonance/depth/spells/skill grant counts) — its nested
`required`/`forbidden`/`qualities`/`skillgroupchoices`/`skillchoices` sub-elements encode
cross-references into the general Improvement/quality-selection machinery that's out of MVP
scope. MVP consumes only letter "E"'s "Mundane" option. See `spec/worklogs/WP2.md`.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType

# legacy/Chummer/data/priorities.xml, resolved relative to this file (not cwd).
DEFAULT_PRIORITIES_PATH = (
    Path(__file__).resolve().parents[3] / "legacy" / "Chummer" / "data" / "priorities.xml"
)

STANDARD_TABLE = "Standard"


def _optional_int(elem: ET.Element, tag: str) -> int | None:
    text = elem.findtext(tag)
    return int(text) if text is not None else None


@dataclass(frozen=True)
class HeritageMetavariantOption:
    name: str
    special_attribute_points: int
    karma: int


@dataclass(frozen=True)
class HeritageMetatypeOption:
    name: str
    special_attribute_points: int
    karma: int
    metavariants: tuple[HeritageMetavariantOption, ...]


@dataclass(frozen=True)
class HeritagePriority:
    letter: str
    name: str
    metatypes: tuple[HeritageMetatypeOption, ...]


@dataclass(frozen=True)
class AttributesPriority:
    letter: str
    name: str
    points: int


@dataclass(frozen=True)
class SkillsPriority:
    letter: str
    name: str
    skills: int
    skill_groups: int


@dataclass(frozen=True)
class ResourcesPriority:
    letter: str
    name: str
    nuyen: int


@dataclass(frozen=True)
class TalentOption:
    """One selectable talent (Magician/Mystic Adept/Technomancer/A.I./Mundane) within a letter."""

    name: str
    codename: str
    magic: int | None
    resonance: int | None
    depth: int | None
    spells: int | None
    cfp: int | None
    skill_qty: int | None
    skill_val: int | None
    skill_type: str | None
    special_attribute_points: int | None
    # WP121: the Aspected Magician's grant -- one skill *group*, picked from `skill_group_choices`
    # (its aspect), at `skill_group_val` (4 at B, 2 at C, 0 at D).
    skill_group_choices: tuple[str, ...] = ()
    skill_group_qty: int | None = None
    skill_group_val: int | None = None


@dataclass(frozen=True)
class TalentPriority:
    letter: str
    name: str
    options: tuple[TalentOption, ...]


@dataclass(frozen=True)
class PriorityTable:
    heritage: MappingProxyType[str, HeritagePriority]
    talent: MappingProxyType[str, TalentPriority]
    attributes: MappingProxyType[str, AttributesPriority]
    skills: MappingProxyType[str, SkillsPriority]
    resources: MappingProxyType[str, ResourcesPriority]

    def mundane_talent(self) -> TalentOption:
        """MVP's only consumed Talent entry: letter E's "Mundane" option."""
        for option in self.talent["E"].options:
            if option.codename == "Mundane":
                return option
        raise LookupError("Talent priority E has no 'Mundane' option")


def _parse_heritage_metavariant(elem: ET.Element) -> HeritageMetavariantOption:
    return HeritageMetavariantOption(
        name=elem.findtext("name", ""),
        special_attribute_points=int(elem.findtext("value", "0")),
        karma=int(elem.findtext("karma", "0")),
    )


def _parse_heritage_metatype(elem: ET.Element) -> HeritageMetatypeOption:
    metavariants_elem = elem.find("metavariants")
    metavariants = (
        tuple(_parse_heritage_metavariant(mv) for mv in metavariants_elem.findall("metavariant"))
        if metavariants_elem is not None
        else ()
    )
    return HeritageMetatypeOption(
        name=elem.findtext("name", ""),
        special_attribute_points=int(elem.findtext("value", "0")),
        karma=int(elem.findtext("karma", "0")),
        metavariants=metavariants,
    )


def _parse_heritage_priority(elem: ET.Element) -> HeritagePriority:
    metatypes_elem = elem.find("metatypes")
    metatypes = (
        tuple(_parse_heritage_metatype(mt) for mt in metatypes_elem.findall("metatype"))
        if metatypes_elem is not None
        else ()
    )
    return HeritagePriority(
        letter=elem.findtext("value", ""),
        name=elem.findtext("name", ""),
        metatypes=metatypes,
    )


def _parse_attributes_priority(elem: ET.Element) -> AttributesPriority:
    return AttributesPriority(
        letter=elem.findtext("value", ""),
        name=elem.findtext("name", ""),
        points=int(elem.findtext("attributes", "0")),
    )


def _parse_skills_priority(elem: ET.Element) -> SkillsPriority:
    return SkillsPriority(
        letter=elem.findtext("value", ""),
        name=elem.findtext("name", ""),
        skills=int(elem.findtext("skills", "0")),
        skill_groups=int(elem.findtext("skillgroups", "0")),
    )


def _parse_resources_priority(elem: ET.Element) -> ResourcesPriority:
    return ResourcesPriority(
        letter=elem.findtext("value", ""),
        name=elem.findtext("name", ""),
        nuyen=int(elem.findtext("resources", "0")),
    )


def _parse_talent_option(elem: ET.Element) -> TalentOption:
    return TalentOption(
        name=elem.findtext("name", ""),
        codename=elem.findtext("value", ""),
        magic=_optional_int(elem, "magic"),
        resonance=_optional_int(elem, "resonance"),
        depth=_optional_int(elem, "depth"),
        spells=_optional_int(elem, "spells"),
        cfp=_optional_int(elem, "cfp"),
        skill_qty=_optional_int(elem, "skillqty"),
        skill_val=_optional_int(elem, "skillval"),
        skill_type=elem.findtext("skilltype"),
        special_attribute_points=_optional_int(elem, "specialattribpoints"),
        skill_group_choices=tuple(
            g.text for g in elem.findall("skillgroupchoices/skillgroup") if g.text
        ),
        skill_group_qty=_optional_int(elem, "skillgroupqty"),
        skill_group_val=_optional_int(elem, "skillgroupval"),
    )


def _parse_talent_priority(elem: ET.Element) -> TalentPriority:
    talents_elem = elem.find("talents")
    options = (
        tuple(_parse_talent_option(t) for t in talents_elem.findall("talent"))
        if talents_elem is not None
        else ()
    )
    return TalentPriority(
        letter=elem.findtext("value", ""),
        name=elem.findtext("name", ""),
        options=options,
    )


def load_priorities(xml_path: Path = DEFAULT_PRIORITIES_PATH) -> PriorityTable:
    """Parse `priorities.xml`'s Heritage/Talent/Attributes/Skills/Resources categories.

    Resources is filtered to the `Standard` prioritytable (`prioritytable` absent or `Standard`);
    the other four categories apply uniformly across all prioritytables in the source data.
    """
    root = ET.parse(xml_path).getroot()
    priorities_elem = root.find("priorities")
    if priorities_elem is None:
        raise ValueError(f"{xml_path}: missing <priorities> element")

    heritage: dict[str, HeritagePriority] = {}
    talent: dict[str, TalentPriority] = {}
    attributes: dict[str, AttributesPriority] = {}
    skills: dict[str, SkillsPriority] = {}
    resources: dict[str, ResourcesPriority] = {}

    for priority_elem in priorities_elem.findall("priority"):
        category = priority_elem.findtext("category")
        if category == "Heritage":
            parsed_h = _parse_heritage_priority(priority_elem)
            heritage[parsed_h.letter] = parsed_h
        elif category == "Talent":
            parsed_t = _parse_talent_priority(priority_elem)
            talent[parsed_t.letter] = parsed_t
        elif category == "Attributes":
            parsed_a = _parse_attributes_priority(priority_elem)
            attributes[parsed_a.letter] = parsed_a
        elif category == "Skills":
            parsed_s = _parse_skills_priority(priority_elem)
            skills[parsed_s.letter] = parsed_s
        elif category == "Resources":
            table = priority_elem.findtext("prioritytable")
            if table is not None and table != STANDARD_TABLE:
                continue
            parsed_r = _parse_resources_priority(priority_elem)
            resources[parsed_r.letter] = parsed_r

    return PriorityTable(
        heritage=MappingProxyType(heritage),
        talent=MappingProxyType(talent),
        attributes=MappingProxyType(attributes),
        skills=MappingProxyType(skills),
        resources=MappingProxyType(resources),
    )
