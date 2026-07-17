"""Parser for legacy `.chum5` save files — the raw-field extraction layer under the golden-output
regression corpus (`legacy/Chummer.Tests/TestFiles/*.chum5`; curated subset registered in
`tests/fixtures/`).

Extracts exactly the MVP-relevant fields (metatype, priority selections, attributes, skills,
qualities, karma, nuyen) as faithfully-typed raw values — no rules interpretation, no
cross-referencing against `chummer5.data`'s loaders. That interpretation is WP6-WP10's job; this
module's contract is "what does the save file literally say", so it can serve as ground truth for
those later WPs without importing their conclusions. See `spec/worklogs/WP4.md` for the `.chum5`
structure this was reverse-engineered from (there is no `.xsd` for the save format, unlike the data
files).
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType


@dataclass(frozen=True)
class LegacyAttribute:
    name: str
    metatype_min: int
    metatype_max: int
    metatype_aug_max: int
    base: int  # points allocated via priority/karma, before metatype minimum or improvements
    karma: int  # karma-bought points, tracked separately from `base` by the save format
    total_value: int  # the save's own computed final value; not re-derived here


@dataclass(frozen=True)
class LegacySkill:
    # Save files never repeat a skill's name; only `suid`, which cross-references
    # `chummer5.data.skills.Skill.id` (== `legacy/Chummer/data/skills.xml`'s `<id>`). Resolving that
    # join is a downstream WP's job, not this parser's.
    suid: str
    category: str
    base: int
    karma: int
    bought_with_karma: bool
    specializations: tuple[str, ...]


@dataclass(frozen=True)
class LegacySkillGroup:
    id: str  # instance-scoped; skills.xml's <skillgroups> has no ids to cross-reference against
    name: str
    base: int
    karma: int


@dataclass(frozen=True)
class LegacyQuality:
    id: str  # cross-references chummer5.data.qualities.Quality.id (qualities.xml's <id>)
    name: str
    extra: str  # select-a-target text, e.g. which skill a selectable quality targets; often empty
    karma: int  # <bp>; already signed per qualities.xml (negative for Negative-category qualities)
    quality_type: str  # "Positive" or "Negative"
    source: str


@dataclass(frozen=True)
class PrioritySelections:
    """Raw `<priority*>` fields from a saved character, unparsed beyond XML extraction.

    Field names follow WP2's `PriorityTable` categories (Heritage/Talent/Attributes/Skills/
    Resources: `chummer5.data.priorities`), not the save file's own tag names — the save format
    names the Heritage category `prioritymetatype` and the Talent category `priorityspecial`, which
    would be a confusing dataclass surface to expose verbatim. See spec/worklogs/WP4.md for the full
    tag-name mapping this was reverse-engineered from.

    Every raw value observed in the corpus has the shape `"<letter>,<n>"` (e.g. `"D,1"`). Traced
    through the legacy C# (`SelectMetatypePriority.cs`): the UI only ever reads `priority[0]` as the
    priority letter (`SetPrioritySelectionAsync`'s `x.FindString(priority[0].ToString())`) — no
    reachable code path interprets the trailing number for a loaded character. WP4 does not guess at
    its meaning either; use `priority_letter()` for the one thing that's confirmed.
    """

    heritage: str
    attributes: str
    talent: str
    skills: str
    resources: str
    talent_codename: str  # <prioritytalent>: "Mundane", "Technomancer", "Magician", ...
    # <priorityskills><priorityskill>...</priorityskills> — the second, list-shaped element that
    # shares its tag name with the scalar `skills` field above (see spec/worklogs/WP4.md).
    talent_bonus_skills: tuple[str, ...]


def priority_letter(raw: str) -> str:
    """First character of a raw `<priority*>` field — the only part the legacy UI itself reads."""
    return raw[0] if raw else ""


@dataclass(frozen=True)
class LegacyCharacter:
    metatype: str
    metatype_category: str
    metavariant: str | None
    build_method: str  # "Priority" or "SumtoTen"; see Implementation Plan's corpus note
    game_option: str  # <gameplayoption>: Standard/Prime Runner/Street Level priority-table selector
    magic_enabled: bool
    resonance_enabled: bool
    priorities: PrioritySelections
    attributes: MappingProxyType[str, LegacyAttribute]
    skills: tuple[LegacySkill, ...]
    skill_groups: tuple[LegacySkillGroup, ...]
    qualities: tuple[LegacyQuality, ...]
    karma_remaining: int
    build_karma: int
    nuyen_remaining: float
    starting_nuyen: int


def _parse_bool(text: str | None) -> bool:
    return text == "True"


def _parse_attributes(elem: ET.Element | None) -> MappingProxyType[str, LegacyAttribute]:
    if elem is None:
        return MappingProxyType({})
    attrs: dict[str, LegacyAttribute] = {}
    for a in elem.findall("attribute"):
        name = a.findtext("name", "")
        attrs[name] = LegacyAttribute(
            name=name,
            metatype_min=int(a.findtext("metatypemin", "0")),
            metatype_max=int(a.findtext("metatypemax", "0")),
            metatype_aug_max=int(a.findtext("metatypeaugmax", "0")),
            base=int(a.findtext("base", "0")),
            karma=int(a.findtext("karma", "0")),
            total_value=int(a.findtext("totalvalue", "0")),
        )
    return MappingProxyType(attrs)


def _parse_specializations(elem: ET.Element) -> tuple[str, ...]:
    specs_elem = elem.find("specs")
    if specs_elem is None:
        return ()
    return tuple(s.findtext("name", "") for s in specs_elem.findall("spec"))


def _parse_skill(elem: ET.Element) -> LegacySkill:
    return LegacySkill(
        suid=elem.findtext("suid", ""),
        category=elem.findtext("skillcategory", ""),
        base=int(elem.findtext("base", "0")),
        karma=int(elem.findtext("karma", "0")),
        bought_with_karma=_parse_bool(elem.findtext("buywithkarma")),
        specializations=_parse_specializations(elem),
    )


def _parse_skills(newskills_elem: ET.Element | None) -> tuple[LegacySkill, ...]:
    # Deliberately only <newskills><skills>, not <knoskills> (knowledge skills) — out of MVP scope
    # per WP3's precedent (see spec/worklogs/WP3.md).
    if newskills_elem is None:
        return ()
    skills_elem = newskills_elem.find("skills")
    if skills_elem is None:
        return ()
    return tuple(_parse_skill(s) for s in skills_elem.findall("skill"))


def _parse_skill_groups(newskills_elem: ET.Element | None) -> tuple[LegacySkillGroup, ...]:
    if newskills_elem is None:
        return ()
    groups_elem = newskills_elem.find("groups")
    if groups_elem is None:
        return ()
    return tuple(
        LegacySkillGroup(
            id=g.findtext("id", ""),
            name=g.findtext("name", ""),
            base=int(g.findtext("base", "0")),
            karma=int(g.findtext("karma", "0")),
        )
        for g in groups_elem.findall("group")
    )


def _parse_quality(elem: ET.Element) -> LegacyQuality:
    return LegacyQuality(
        id=elem.findtext("id", ""),
        name=elem.findtext("name", ""),
        extra=elem.findtext("extra", ""),
        karma=int(elem.findtext("bp", "0")),
        quality_type=elem.findtext("qualitytype", ""),
        source=elem.findtext("source", ""),
    )


def _parse_qualities(elem: ET.Element | None) -> tuple[LegacyQuality, ...]:
    if elem is None:
        return ()
    return tuple(_parse_quality(q) for q in elem.findall("quality"))


def _parse_priorities(root: ET.Element) -> PrioritySelections:
    # <priorityskills> appears twice at the same level with different shapes: a scalar
    # "<letter>,<n>" value (the Skills category, like its four siblings) and a list wrapper
    # (<priorityskill> children — bonus skill picks from the Talent choice, e.g. a Technomancer's
    # three free Resonance skills). Disambiguate by shape, not document order, since nothing in the
    # legacy schema guarantees the order.
    talent_bonus_skills: tuple[str, ...] = ()
    skills_scalar = ""
    for el in root.findall("priorityskills"):
        children = list(el)
        if children:
            talent_bonus_skills = tuple(c.text or "" for c in children if c.tag == "priorityskill")
        else:
            skills_scalar = el.text or ""

    return PrioritySelections(
        heritage=root.findtext("prioritymetatype", ""),
        attributes=root.findtext("priorityattributes", ""),
        talent=root.findtext("priorityspecial", ""),
        skills=skills_scalar,
        resources=root.findtext("priorityresources", ""),
        talent_codename=root.findtext("prioritytalent", ""),
        talent_bonus_skills=talent_bonus_skills,
    )


def load_chum5(path: Path) -> LegacyCharacter:
    """Parse a legacy `.chum5` save file into a `LegacyCharacter` of MVP-relevant raw fields.

    Deliberately excludes knowledge skills (out of MVP scope per WP3's precedent) and contacts
    (not in WP4's deliverable list; picked up by WP9). Cyberware/vehicles/gear/spells/magic/
    matrix/etc. are similarly untouched — this parser only extracts what WP6-WP10's engine needs
    to validate against.
    """
    root = ET.parse(path).getroot()
    newskills_elem = root.find("newskills")
    return LegacyCharacter(
        metatype=root.findtext("metatype", ""),
        metatype_category=root.findtext("metatypecategory", ""),
        metavariant=root.findtext("metavariant") or None,
        build_method=root.findtext("buildmethod", ""),
        game_option=root.findtext("gameplayoption", ""),
        magic_enabled=_parse_bool(root.findtext("magenabled")),
        resonance_enabled=_parse_bool(root.findtext("resenabled")),
        priorities=_parse_priorities(root),
        attributes=_parse_attributes(root.find("attributes")),
        skills=_parse_skills(newskills_elem),
        skill_groups=_parse_skill_groups(newskills_elem),
        qualities=_parse_qualities(root.find("qualities")),
        karma_remaining=int(root.findtext("karma", "0")),
        build_karma=int(root.findtext("buildkarma", "0")),
        nuyen_remaining=float(root.findtext("nuyen", "0")),
        starting_nuyen=int(root.findtext("startingnuyen", "0")),
    )
