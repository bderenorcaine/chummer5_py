"""Loader for `legacy/Chummer/data/mentors.xml`, restricted to SR5 core-rulebook content (Phase M,
WP48).

16 of the file's 81 `<mentor>` entries carry `source == "SR5"` (the rest are later-book content --
SG/SASS/HT/SFCC/SHB2/HS/BOTL/FA/SAG/BTB/SOTG -- out of MVP's core-rulebook scope per the usual
`source` filter). Confirmed via `xml.etree.ElementTree`, not the Implementation Plan's own "20+"
pre-research estimate -- see `spec/rulebooks/learnings.md`'s WP48 entry for the full count and the
rulebook citation (core rulebook pp. 320-324, "Mentor Spirit Archetypes").

**Each archetype offers exactly 3 bonus slots (rulebook, p. 320: "one general bonus, one bonus
that applies only to magicians, and one that applies only to adepts"), not 4.** `mentors.xml`
sometimes expresses the *General* slot as a fixed top-level `<bonus>` (13 of 16 archetypes) and
sometimes as a real 2-option player choice instead (Cat, Fire-Bringer, Wise Warrior -- e.g. Cat's
General is "+2 dice to either Gymnastics or Sneaking Tests (choose one)", p. 321) -- both are the
*same* slot, just two different XML shapes for it. The Magician/Adept slots are always expressed
as a `<choices>/<choice>` pair, gated by a literal `"Magician: "`/`"Adept: "` name prefix --
confirmed via `SelectMentorSpirit.cs`'s `lstMentor_SelectedIndexChanged`, which filters strictly by
that prefix against `Character.MagicianEnabled`/`AdeptEnabled`; the `set="2"` XML attribute some
of these choices carry is UI-dropdown-layout-only (which of two dropdown widgets to populate), not
a gating mechanism, so this loader never reads it. See `MentorSpiritArchetype.general_options`/
`.magician_choice`/`.adept_choice` below for how the 3 slots surface once parsed.

**Bonus classification (`BonusSupport`, a 3-way enum mirroring `chummer5.data.foci`'s precedent).**
WP48 recognized only a flat `<specificskill>` and left 33 of 51 slots unsupported. **WP122**
recognizes every shape a core slot uses (`_parse_slot`), so 50 slots are `FLAT_BONUS`:

- flat skill dice (`<specificskill>`), and Bear's `<damageresistance>` into WP109's pool;
- Dragonslayer's `<selectskill skillcategory="Social Active">` -- "+2 dice pool modifier for one
  social skill of choice" (p. 321), carried as `skill_choice_categories` and a pick-time choice;
- Eagle's `<addqualities>` -- its disadvantage, "You get the Allergy (pollutants, mild) quality"
  (p. 322), granted at 0 Karma (`granted_qualities`);
- every Magician slot's `<spellcategory>` or conditional `<specificskill>` -- dice that count only
  for some tests (`ConditionalPool`), shown on the sheet as the pool such a test rolls;
- every Adept slot's `<specificpower>` -- free power levels outside the Power Point budget
  (`FreePower`), applied as power instances, with a target where the power takes one.

`NO_EFFECT` stays for one slot, Rat's Magician choice ("+2 dice to Alchemy tests when harvesting
reagents", p. 323), which has **no `<bonus>` element at all** in the raw XML. Harvesting isn't a
tracked pool, and it is name-gated (`_VERIFIED_NO_EFFECT_CHOICES`).

Every archetype is offered. Each archetype's disadvantage, which is in play, is its
`unmodeled_effect_note` (WP122); Eagle's is the granted Allergy instead.

`chummer5.engine.qualities` is what actually turns a picked archetype's `FLAT_BONUS` slots into
real `Improvement`s (as part of applying the Mentor Spirit quality) -- this module only loads and
classifies, mirroring every prior `chummer5.data.*` loader's loader/engine split.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from collections.abc import Iterable
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

DEFAULT_MENTORS_PATH = (
    Path(__file__).resolve().parents[3] / "legacy" / "Chummer" / "data" / "mentors.xml"
)

# MVP content scope: only entries carrying this <source> tag are loaded. See "MVP content scope" in
# Implementation Plan.md.
CORE_RULEBOOK_SOURCE = "SR5"

# The one <bonus> child shape this file's SR5 archetypes ever use flat: a bare skill name + an
# unconditional numeric bonus, no other fields (no <condition>, no category/select machinery) --
# the same shape chummer5.data.qualities/foci already recognize.
_FLAT_SKILL_FIELDS = frozenset({"name", "bonus"})

# Rat's Magician choice ("+2 dice to Alchemy tests when harvesting reagents, and you may use
# reagents of any tradition", p. 323) has no <bonus> element at all in the raw XML -- verified via
# the rulebook text (not a tracked dice pool) rather than assumed from the absence alone. See
# module docstring.
_VERIFIED_NO_EFFECT_CHOICES = frozenset(
    {"Magician: +2 to Alchemy for harvesting, and you may use any reagents"}
)


class BonusSupport(Enum):
    """Whether/how a bonus slot's `<bonus>` node was parsed. See module docstring for the 3
    values."""

    FLAT_BONUS = "flat_bonus"
    NO_EFFECT = "no_effect"
    NOT_YET_SUPPORTED = "not_yet_supported"


@dataclass(frozen=True)
class FlatBonus:
    """One unconditional, flat bonus. `target_kind` is "skill" (a skill's dice) or, since WP122,
    "damage_resistance" (Bear). An empty `target_name` on a "skill" bonus means "the skill the
    pick chose" (Dragonslayer's "one social skill of choice")."""

    target_kind: str
    target_name: str
    value: int


@dataclass(frozen=True)
class ConditionalPool:
    """WP122: dice that count only for some tests of some skills -- a Magician slot's "+2 dice for
    Health spells, preparations, and rituals" (Spellcasting, Ritual Spellcasting and Alchemy for
    that category), or "+2 dice summoning spirits of air". `condition` is the printed phrase."""

    skills: tuple[str, ...]
    value: int
    condition: str


@dataclass(frozen=True)
class FreePower:
    """WP122: an Adept slot's free power levels, granted outside the Power Point budget. The
    `target_*` fields narrow what the instance may name (`<bonusoverride>`): Sea's Improved Ability
    must be on an athletic skill, Wolf's Attribute Boost is Agility's."""

    power_name: str
    levels: int
    target_skill_categories: tuple[str, ...] = ()
    target_skill_groups: tuple[str, ...] = ()
    target_attributes: tuple[str, ...] = ()


def _is_flat_skill_bonus(elem: ET.Element) -> bool:
    return {child.tag for child in elem} == _FLAT_SKILL_FIELDS


# WP122: a `<spellcategory>` bonus counts for the category's spells, rituals and preparations
# (p. 321-324: "+2 dice for health spells, preparations, and rituals") -- the three skills that
# cast, perform or brew them.
_SPELL_CATEGORY_SKILLS = ("Spellcasting", "Ritual Spellcasting", "Alchemy")


@dataclass(frozen=True)
class _SlotBonuses:
    """Everything one slot's `<bonus>` grants (WP122)."""

    flat_bonuses: tuple[FlatBonus, ...] = ()
    conditional_pools: tuple[ConditionalPool, ...] = ()
    free_powers: tuple[FreePower, ...] = ()
    skill_choice_categories: tuple[str, ...] = ()
    granted_qualities: tuple[tuple[str, str], ...] = ()  # (quality name, its detail)


def _parse_free_power(elem: ET.Element) -> FreePower:
    override = elem.find("bonusoverride")
    categories: tuple[str, ...] = ()
    groups: tuple[str, ...] = ()
    attributes: tuple[str, ...] = ()
    if override is not None:
        select_skill = override.find("selectskill")
        if select_skill is not None:
            listed = tuple(c.text or "" for c in select_skill.findall("skillcategories/category"))
            single = select_skill.get("skillcategory")
            categories = listed or ((single,) if single else ())
            groups = tuple(g for g in select_skill.get("skillgroup", "").split(",") if g)
        attributes = tuple(a.text or "" for a in override.findall("selectattribute/attribute"))
    return FreePower(
        power_name=elem.findtext("name", ""),
        levels=int(elem.findtext("val", "1")),
        target_skill_categories=categories,
        target_skill_groups=groups,
        target_attributes=attributes,
    )


def _parse_slot(bonus_elem: ET.Element) -> _SlotBonuses | None:
    """WP122: every child shape a core mentor slot uses, or None if one isn't recognized."""
    flat: list[FlatBonus] = []
    pools: list[ConditionalPool] = []
    powers: list[FreePower] = []
    choice_categories: tuple[str, ...] = ()
    granted: list[tuple[str, str]] = []
    for child in bonus_elem:
        tags = {c.tag for c in child}
        if child.tag == "specificskill" and tags == _FLAT_SKILL_FIELDS:
            flat.append(
                FlatBonus("skill", child.findtext("name", ""), int(child.findtext("bonus", "0")))
            )
        elif child.tag == "specificskill" and tags == {*_FLAT_SKILL_FIELDS, "condition"}:
            pools.append(
                ConditionalPool(
                    skills=(child.findtext("name", ""),),
                    value=int(child.findtext("bonus", "0")),
                    condition=f"summoning {child.findtext('condition', '')}",
                )
            )
        elif child.tag == "spellcategory" and tags == {"name", "val"}:
            category = child.findtext("name", "")
            pools.append(
                ConditionalPool(
                    skills=_SPELL_CATEGORY_SKILLS,
                    value=int(child.findtext("val", "0")),
                    condition=f"{category} spells, preparations and rituals",
                )
            )
        elif child.tag == "damageresistance" and len(child) == 0 and child.text:
            flat.append(FlatBonus("damage_resistance", "", int(child.text)))
        elif child.tag == "selectskill" and tags == {"val"} and child.get("skillcategory"):
            flat.append(FlatBonus("skill", "", int(child.findtext("val", "0"))))
            choice_categories = (child.get("skillcategory", ""),)
        elif child.tag == "addqualities":
            granted.extend((q.text or "", q.get("select", "")) for q in child.findall("addquality"))
        elif child.tag == "specificpower":
            powers.append(_parse_free_power(child))
        else:
            return None
    return _SlotBonuses(
        flat_bonuses=tuple(flat),
        conditional_pools=tuple(pools),
        free_powers=tuple(powers),
        skill_choice_categories=choice_categories,
        granted_qualities=tuple(granted),
    )


def _classify_bonus(
    context_name: str, bonus_elem: ET.Element | None
) -> tuple[BonusSupport, _SlotBonuses]:
    """Classify one bonus slot's `<bonus>` node. `context_name` is the enclosing `<choice>`'s own
    `<name>` (used only to look up `_VERIFIED_NO_EFFECT_CHOICES` when `bonus_elem` is absent) --
    irrelevant, and unused, when called for a General slot expressed as a fixed top-level `<bonus>`
    (see `MentorSpiritArchetype.general_options`'s own construction below).

    **WP122**: every core slot's shape is now recognized (`_parse_slot`), so every slot but Rat's
    reagent-harvesting one is `FLAT_BONUS`.
    """
    if bonus_elem is None:
        if context_name in _VERIFIED_NO_EFFECT_CHOICES:
            return BonusSupport.NO_EFFECT, _SlotBonuses()
        return BonusSupport.NOT_YET_SUPPORTED, _SlotBonuses()
    parsed = _parse_slot(bonus_elem)
    if parsed is None:
        return BonusSupport.NOT_YET_SUPPORTED, _SlotBonuses()
    return BonusSupport.FLAT_BONUS, parsed


@dataclass(frozen=True)
class MentorChoice:
    """One option within a bonus slot -- either a General-slot sub-option (Cat/Fire-Bringer/Wise
    Warrior's 2-way "choose one" General bonus) or a magic-type-gated Magician/Adept slot option.

    `id` is a stable, synthetic identifier (`{archetype_id}:{name}`) -- `mentors.xml` gives choices
    no `<id>` of their own, only a `<name>`, and names are unique within one archetype's `<choices>`
    block (confirmed: no archetype repeats a choice name).
    """

    id: str
    name: str
    bonus_support: BonusSupport
    flat_bonuses: tuple[FlatBonus, ...]
    # WP122: the rest of what a slot can grant -- see `_SlotBonuses`.
    conditional_pools: tuple[ConditionalPool, ...] = ()
    free_powers: tuple[FreePower, ...] = ()
    skill_choice_categories: tuple[str, ...] = ()
    granted_qualities: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class MentorSpiritArchetype:
    """One SR5 Mentor Spirit archetype and its 3 rulebook-defined bonus slots (p. 320).

    `general_options` is 1 item for the 13 archetypes whose General slot is a fixed bonus, or 2
    items for the 3 (Cat, Fire-Bringer, Wise Warrior) whose General slot is itself a player choice
    -- `len(general_options) > 1` is exactly the condition under which a player must actually pick
    one; `chummer5.engine.qualities` uses this directly rather than re-deriving it. `magician_
    choice`/`adept_choice` are always present (every SR5 archetype has both), auto-selected by
    `character.magic_type` -- never a player pick.
    """

    id: str
    name: str
    advantage: str
    disadvantage: str
    general_options: tuple[MentorChoice, ...]
    magician_choice: MentorChoice
    adept_choice: MentorChoice
    source: str
    page: int
    # WP122: the disadvantage's in-play part (the Project Overview registry).
    unmodeled_effect_note: str | None = None


# WP122: each core mentor's disadvantage, which is in play for every archetype but Eagle (whose
# Allergy is granted as a quality). Condensed from the printed text (pp. 321-324).
_BERSERK = (
    "may go berserk for up to 3 turns after taking Physical damage in combat, resisted with a "
    "Charisma + Willpower Test"
)
_DISADVANTAGE_NOTES: dict[str, str] = {
    "Bear": f"Disadvantage: {_BERSERK}, or when someone in their care is badly injured (p. 321)",
    "Cat": (
        "Disadvantage: can't make an incapacitating attack without a Charisma + Willpower (3) Test "
        "at the start of combat (p. 321)"
    ),
    "Dog": (
        "Disadvantage: can't leave someone behind or betray a comrade without a Charisma + "
        "Willpower (3) Test (p. 321)"
    ),
    "Dragonslayer": (
        "Disadvantage: -1 dice to all actions after breaking a promise, until it is made good "
        "(p. 321)"
    ),
    "Fire-Bringer": (
        "Disadvantage: can't refuse a sincere request for help without a Charisma + Willpower (3) "
        "Test (p. 322)"
    ),
    "Mountain": ("Disadvantage: abandoning a plan takes a Charisma + Willpower (3) Test (p. 322)"),
    "Rat": (
        "Disadvantage: must flee or seek cover in combat unless a Charisma + Willpower (3) Test "
        "succeeds (p. 323)"
    ),
    "Raven": (
        "Disadvantage: a Charisma + Willpower (3) Test to resist exploiting someone's misfortune "
        "or pulling a prank (p. 323)"
    ),
    "Sea": "Disadvantage: giving anything away takes a Charisma + Willpower (3) Test (p. 323)",
    "Seducer": (
        "Disadvantage: a Charisma + Willpower (3) Test to resist an available vice (p. 323)"
    ),
    "Shark": f"Disadvantage: {_BERSERK} (p. 323)",
    "Snake": (
        "Disadvantage: a Charisma + Willpower (3) Test to resist chasing rare secrets (p. 324)"
    ),
    "Thunderbird": (
        "Disadvantage: a Charisma + Willpower (3) Test to avoid answering an insult in kind (p. "
        "324)"
    ),
    "Wise Warrior": (
        "Disadvantage: -1 dice to all actions after acting dishonorably, until atoned for (p. 324)"
    ),
    "Wolf": "Disadvantage: retreating from a fight takes a Charisma + Willpower (3) Test (p. 324)",
}


def _disadvantage_note(name: str) -> str | None:
    note = _DISADVANTAGE_NOTES.get(name)
    return None if note is None else f"{note} -- no in-play test or consequence tracking exists."


def _parse_choice(archetype_id: str, elem: ET.Element) -> MentorChoice:
    name = elem.findtext("name", "")
    support, bonuses = _classify_bonus(name, elem.find("bonus"))
    return _choice(f"{archetype_id}:{name}", name, support, bonuses)


def _choice(
    choice_id: str, name: str, support: BonusSupport, bonuses: _SlotBonuses
) -> MentorChoice:
    return MentorChoice(
        id=choice_id,
        name=name,
        bonus_support=support,
        flat_bonuses=bonuses.flat_bonuses,
        conditional_pools=bonuses.conditional_pools,
        free_powers=bonuses.free_powers,
        skill_choice_categories=bonuses.skill_choice_categories,
        granted_qualities=bonuses.granted_qualities,
    )


def _parse_mentor(elem: ET.Element) -> MentorSpiritArchetype:
    mentor_id = elem.findtext("id", "")
    name = elem.findtext("name", "")

    general_bonus_elem = elem.find("bonus")
    choices_elem = elem.find("choices")
    choice_elems = choices_elem.findall("choice") if choices_elem is not None else ()

    magician_choice: MentorChoice | None = None
    adept_choice: MentorChoice | None = None
    ungated_choices: list[MentorChoice] = []
    for choice_elem in choice_elems:
        choice = _parse_choice(mentor_id, choice_elem)
        if choice.name.startswith("Magician:"):
            magician_choice = choice
        elif choice.name.startswith("Adept:"):
            adept_choice = choice
        else:
            ungated_choices.append(choice)

    if magician_choice is None or adept_choice is None:
        raise ValueError(f"{name}: expected both a Magician: and an Adept: choice")

    if general_bonus_elem is not None:
        general_support, general_bonuses = _classify_bonus("", general_bonus_elem)
        general_options: tuple[MentorChoice, ...] = (
            _choice(f"{mentor_id}:general", "General", general_support, general_bonuses),
        )
    else:
        general_options = tuple(ungated_choices)

    return MentorSpiritArchetype(
        id=mentor_id,
        name=name,
        advantage=elem.findtext("advantage", ""),
        disadvantage=elem.findtext("disadvantage", ""),
        general_options=general_options,
        magician_choice=magician_choice,
        adept_choice=adept_choice,
        source=elem.findtext("source", ""),
        page=int(elem.findtext("page", "0")),
        unmodeled_effect_note=_disadvantage_note(name),
    )


def load_mentors(xml_path: Path = DEFAULT_MENTORS_PATH) -> tuple[MentorSpiritArchetype, ...]:
    """Parse `mentors.xml`, restricted to `source == "SR5"` entries (16 of 81)."""
    root = ET.parse(xml_path).getroot()
    mentors_elem = root.find("mentors")
    if mentors_elem is None:
        return ()
    return tuple(
        _parse_mentor(m)
        for m in mentors_elem.findall("mentor")
        if m.findtext("source") == CORE_RULEBOOK_SOURCE
    )


def gated_choice(archetype: MentorSpiritArchetype, magic_type: str) -> MentorChoice:
    """The archetype's Magician- or Adept-slot choice for `magic_type` ("Magician" or "Adept").

    Raises `ValueError` for any other `magic_type` -- this engine only ever produces "Magician" or
    "Adept" (Phase I's scope; see `chummer5.engine.magic`), so anything else is a real caller bug,
    not an expected runtime edge case.
    """
    if magic_type in ("Magician", "Aspected Magician"):  # WP121: an Aspected Magician's slot
        return archetype.magician_choice
    if magic_type == "Adept":
        return archetype.adept_choice
    raise ValueError(f"not a magic-active type: {magic_type!r}")


def count_by_support(archetypes: Iterable[MentorSpiritArchetype]) -> dict[BonusSupport, int]:
    """Count every classifiable bonus slot (General option(s) + Magician + Adept, across every
    archetype) per `BonusSupport` value, so the supported/unsupported split is visible."""
    counts = {support: 0 for support in BonusSupport}
    for archetype in archetypes:
        slots = (*archetype.general_options, archetype.magician_choice, archetype.adept_choice)
        for choice in slots:
            counts[choice.bonus_support] += 1
    return counts
