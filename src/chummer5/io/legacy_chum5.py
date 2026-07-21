"""Parser for legacy `.chum5` save files — the raw-field extraction layer under the golden-output
regression corpus (`legacy/Chummer.Tests/TestFiles/*.chum5`; curated subset registered in
`tests/fixtures/`).

Extracts exactly the MVP-relevant fields (metatype, priority selections, attributes, skills,
qualities, contacts, karma, nuyen) as faithfully-typed raw values — no rules interpretation, no
cross-referencing against `chummer5.data`'s loaders. That interpretation is WP6-WP10's job; this
module's contract is "what does the save file literally say", so it can serve as ground truth for
those later WPs without importing their conclusions. See `spec/worklogs/WP4.md` for the `.chum5`
structure this was reverse-engineered from (there is no `.xsd` for the save format, unlike the data
files), and `spec/worklogs/WP9.md` for the `<contacts>`/`<contactpoints>` extension WP4 deferred to
this WP.
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
    # <qualitysource>: "Metatype" for a free, auto-granted racial quality (e.g. an Elf's Low-Light
    # Vision), "Selected" for a player pick, among other legacy-internal values MVP doesn't need to
    # distinguish. WP23: without this, legacy_import.py couldn't tell a metatype-granted quality
    # apart from a player-chosen one, and would misreport/mis-import it as a karma-costing pick --
    # see spec/worklogs/WP23.md.
    quality_source: str


@dataclass(frozen=True)
class LegacySpell:
    """One raw `<spells><spell>` entry (WP28). A Magician's chosen spells -- a chargen-time roster
    entry, not a computed value (see `chummer5.engine.magic`'s module docstring), so nothing beyond
    `name`/`source` is needed to cross-reference against `chummer5.data.spells.load_spells()`.
    """

    name: str
    source: str


@dataclass(frozen=True)
class LegacyPower:
    """One raw `<powers><power>` entry (WP28). `extra` is the select-a-target text (e.g. which
    attribute Improved Physical Attribute boosts) -- the same shape as `LegacyQuality.extra`; empty
    for a power with no `select_attribute`-shaped bonus.
    """

    name: str
    rating: int
    levels: bool
    extra: str


@dataclass(frozen=True)
class LegacyCyberware:
    """One raw *top-level* `<cyberwares><cyberware>` entry (WP33). Nested `<children>` (cyberlimb
    enhancements/accessories bought onto a limb) are deliberately not parsed here -- WP31/32 already
    treat that as a different category of purchase entirely, out of Phase J's scope (see
    `tests/integration/test_cyberware_fixtures.py`'s identical "top-level only" precedent), so
    parsing them here would only grow a field this project has no use for.

    `<improvementsource>` ("Cyberware" or "Bioware") is the only reliable way to split the two
    content types this one wrapper element holds -- `<category>` alone doesn't (e.g. "Basic"/
    "Cultured"/"Genemods" categories are Bioware-only in practice, but "Headware"/"Bodyware" span
    both). `cost`/`essence` are kept as raw text, not `int`/`Decimal`: a real purchase's `<cost>`/
    `<ess>` is routinely a rating formula (`"Rating * 0.3"`, `"FixedValues(2,3,5)"`), not a bare
    literal -- this parser's contract is "what the save says", not "what it resolves to" (see module
    docstring). `chummer5.io.legacy_import` decides importability by matching `name`+`grade` against
    WP31's catalog rather than parsing these fields numerically at all.
    """

    name: str
    category: str
    grade: str
    source: str
    improvement_source: str  # "Cyberware" or "Bioware"
    cost: str  # raw <cost> text -- often a rating formula, see class docstring
    essence: str  # raw <ess> text, same caveat


@dataclass(frozen=True)
class LegacyContact:
    name: str
    connection: int
    loyalty: int
    free: bool  # <free>True</free> -- a GM-granted/plot contact; costs no points (WP9)


@dataclass(frozen=True)
class LegacyLifestyle:
    """One raw `<lifestyle>` entry (WP20). `monthly_cost` is `<cost>`'s literal value -- confirmed
    (see `spec/rulebooks/learnings.md`'s WP20 entry) to already be the tier's flat monthly rate, not
    pre-multiplied by `months`; `total_cost = monthly_cost * months` is this project's own
    computation (`chummer5.engine.lifestyle.LifestyleSelection.total_cost`), not a save-format
    field.
    """

    base_lifestyle: str  # <baselifestyle>: the catalog tier name, e.g. "Low"
    months: int
    monthly_cost: int
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
    contacts: tuple[LegacyContact, ...]
    contact_points_budget: int  # <contactpoints>: cached CHA*3 free-contact-point budget (WP9)
    # <lifestyles><lifestyle>...</lifestyle></lifestyles>, every entry in document order (WP20;
    # see LegacyLifestyle's own docstring for why "which one is primary" isn't decided here).
    lifestyles: tuple[LegacyLifestyle, ...]
    # <cyberwares><cyberware>... -- every *top-level* entry (WP12 parsed only a presence boolean;
    # WP33 widens this to real per-item data, see LegacyCyberware's own docstring for why nested
    # <children> stay unparsed). Cyberware *and* Bioware entries both live under this one wrapper
    # element (`<improvementsource>` distinguishes them, not the element name).
    cyberware: tuple[LegacyCyberware, ...]
    # WP28: <tradition><name> -- always present in the save format (even for a mundane character,
    # where it's a meaningless placeholder never consumed downstream) since the legacy engine
    # always instantiates one; "" if somehow absent entirely.
    tradition_name: str
    spells: tuple[LegacySpell, ...]  # <spells><spell>... (WP28) -- a Magician's chosen spells
    powers: tuple[LegacyPower, ...]  # <powers><power>... (WP28) -- an Adept's purchased powers
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
        quality_source=elem.findtext("qualitysource", ""),
    )


def _parse_qualities(elem: ET.Element | None) -> tuple[LegacyQuality, ...]:
    if elem is None:
        return ()
    return tuple(_parse_quality(q) for q in elem.findall("quality"))


def _parse_cyberware_item(elem: ET.Element) -> LegacyCyberware:
    return LegacyCyberware(
        name=elem.findtext("name", ""),
        category=elem.findtext("category", ""),
        grade=elem.findtext("grade", ""),
        source=elem.findtext("source", ""),
        improvement_source=elem.findtext("improvementsource", ""),
        cost=elem.findtext("cost", ""),
        essence=elem.findtext("ess", ""),
    )


def _parse_cyberwares(elem: ET.Element | None) -> tuple[LegacyCyberware, ...]:
    # Top-level <cyberware> children only -- see LegacyCyberware's own docstring for why nested
    # <children> (cyberlimb enhancements/accessories) are deliberately not parsed here.
    if elem is None:
        return ()
    return tuple(_parse_cyberware_item(c) for c in elem.findall("cyberware"))


def _parse_contact(elem: ET.Element) -> LegacyContact:
    return LegacyContact(
        name=elem.findtext("name", ""),
        connection=int(elem.findtext("connection", "0")),
        loyalty=int(elem.findtext("loyalty", "0")),
        free=_parse_bool(elem.findtext("free")),
    )


def _parse_contacts(elem: ET.Element | None) -> tuple[LegacyContact, ...]:
    # Deliberately every <contact> child, not filtered by <type>/<group> -- every mundane fixture's
    # contacts are plain, non-group `type == "Contact"` entries (checked directly across all 11 in
    # WP9), so there is nothing in the curated corpus that would need that filter yet. See
    # spec/worklogs/WP9.md.
    if elem is None:
        return ()
    return tuple(_parse_contact(c) for c in elem.findall("contact"))


def _parse_lifestyle(elem: ET.Element) -> LegacyLifestyle:
    return LegacyLifestyle(
        base_lifestyle=elem.findtext("baselifestyle", ""),
        months=int(elem.findtext("months", "0")),
        monthly_cost=int(elem.findtext("cost", "0")),
        source=elem.findtext("source", ""),
    )


def _parse_lifestyles(elem: ET.Element | None) -> tuple[LegacyLifestyle, ...]:
    # Every child in document order, not just the first -- a character may maintain more than one
    # Lifestyle (core rulebook p. 369: "They may elect to pay other lifestyle costs as well... but
    # must pay full cost on all lifestyles they maintain"). This parser extracts raw fields only;
    # which entry counts as the *primary* Lifestyle (MVP's only modeled one) is an interpretation
    # decision left to `chummer5.io.legacy_import` -- see its own module docstring.
    if elem is None:
        return ()
    return tuple(_parse_lifestyle(lifestyle) for lifestyle in elem.findall("lifestyle"))


def _parse_spell(elem: ET.Element) -> LegacySpell:
    return LegacySpell(name=elem.findtext("name", ""), source=elem.findtext("source", ""))


def _parse_spells(elem: ET.Element | None) -> tuple[LegacySpell, ...]:
    if elem is None:
        return ()
    return tuple(_parse_spell(s) for s in elem.findall("spell"))


def _parse_power(elem: ET.Element) -> LegacyPower:
    return LegacyPower(
        name=elem.findtext("name", ""),
        rating=int(elem.findtext("rating", "1")),
        levels=_parse_bool(elem.findtext("levels")),
        extra=elem.findtext("extra", ""),
    )


def _parse_powers(elem: ET.Element | None) -> tuple[LegacyPower, ...]:
    if elem is None:
        return ()
    return tuple(_parse_power(p) for p in elem.findall("power"))


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

    Deliberately excludes knowledge skills (out of MVP scope per WP3's precedent). Contacts (WP9)
    are now included: every `<contact>` entry plus the character-level `<contactpoints>` cached
    free-budget value (see `spec/worklogs/WP9.md`). Cyberware/bioware presence is now flagged (WP12,
    `has_cyberware`) since it's a real blocking condition for import -- see `spec/worklogs/WP12.md`.
    Lifestyles (WP20) are now included too: every `<lifestyle>` entry, raw (see `LegacyLifestyle`).
    WP28 adds `tradition_name`/`spells`/`powers` -- Phase I's magic-relevant raw fields beyond the
    `magic_enabled` boolean already parsed since WP4 (`MAG`'s own resolved rating needs no new field
    at all: `attributes["MAG"].total_value` already resolves generically, the same way every other
    attribute does). WP33 widens WP12's boolean `has_cyberware` flag into real per-item data
    (`cyberware`, see `LegacyCyberware`) -- every top-level `<cyberwares><cyberware>` entry, needed
    both to decide per-item importability and to cross-check Essence math against WP30's mechanism.
    Vehicles/gear/matrix/etc. remain untouched — this parser only extracts what WP6-WP33's engine
    and import path need to validate against.
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
        contacts=_parse_contacts(root.find("contacts")),
        contact_points_budget=int(root.findtext("contactpoints", "0")),
        lifestyles=_parse_lifestyles(root.find("lifestyles")),
        cyberware=_parse_cyberwares(root.find("cyberwares")),
        tradition_name=root.findtext("tradition/name", ""),
        spells=_parse_spells(root.find("spells")),
        powers=_parse_powers(root.find("powers")),
        karma_remaining=int(root.findtext("karma", "0")),
        build_karma=int(root.findtext("buildkarma", "0")),
        nuyen_remaining=float(root.findtext("nuyen", "0")),
        starting_nuyen=int(root.findtext("startingnuyen", "0")),
    )
