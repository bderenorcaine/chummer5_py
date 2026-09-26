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

**Bonus classification (`BonusSupport`, a fresh 3-way enum mirroring `chummer5.data.foci`'s own
precedent rather than reusing `chummer5.data.qualities`'s -- only one flat shape, `<specificskill>`
with just `name`+`bonus` children, ever appears here):**

- `FLAT_BONUS` (17 of 48 classifiable slots: 10 fixed General bonuses, the 6 sub-options across
  Cat/Fire-Bringer/Wise Warrior's General choice-pairs, and Mountain's Magician choice -- the one
  Magician-slot `<specificskill>` with no `<condition>` child) -- an unconditional, flat skill dice
  bonus, the same shape `chummer5.data.qualities`/`chummer5.data.foci` already recognize.
- `NO_EFFECT` (1: Rat's Magician choice, "+2 dice to Alchemy tests when harvesting reagents, and
  you may use reagents of any tradition", p. 323) -- has **no `<bonus>` element at all** in the raw
  XML, confirmed to be the legacy data authors' own deliberate choice (harvesting reagents isn't a
  tracked dice pool), not an extraction gap -- classified via a name-gated allowlist, mirroring
  `chummer5.data.qualities`'s `_VERIFIED_NO_EFFECT_NAMES` discipline ("verified inert", not "any
  missing `<bonus>` qualifies").
- `NOT_YET_SUPPORTED` (everything else: 3 General bonuses whose one node doesn't match a
  recognized flat shape -- Bear's `<damageresistance>`, an in-play resistance-test bonus this
  engine doesn't compute; Dragonslayer's `<selectskill skillcategory=...>`, a pick-any-skill
  mechanism with no fixed target; Eagle's compound `<addqualities>` + `<specificskill>` node,
  failing as a whole since `addqualities` -- which silently grants the Allergy (pollutants, mild)
  quality per the rulebook's own Disadvantages text, p. 322 -- isn't a recognized shape and this
  project's "all children must be recognized" rule doesn't partially apply a compound bonus; every
  other Magician choice, all `<spellcategory>` (a category-wide spellcasting dice pool this engine
  never computes, since it resolves no in-play Tests at all); every Adept choice, all
  `<specificpower>` (granting free Adept Power levels **outside** the normal Power Point budget --
  a new "grant a Power for free" shape this engine has never built, classified uniformly
  unsupported even for the mechanically simplest single-`<specificpower>` cases, mirroring
  `chummer5.data.foci`'s Qi/Power Focus verdict: "no computed equivalent" is the bar, not "the XML
  shape looks simple").

Every archetype is offered regardless of classification -- mirrors `chummer5.data.foci`'s "offer
the full catalog, apply only the classified-supported subset" precedent (WP47), not
`chummer5.data.qualities`'s "exclude entirely" one: the primary player-facing decision here is
picking an archetype for its narrative advantage/disadvantage identity, not shopping a purely
mechanical catalog, and every archetype still contributes at least *some* real, applied bonus
(even Bear/Dragonslayer/Eagle -- whose General bonus is unsupported -- have no fully-unsupported
choice slot: Bear/Eagle's Adept-choice is unsupported too, so those two archetypes currently apply
nothing at all if the player is an Adept, same honest "verified, not silently wrong" posture WP47
already accepted for 30 of 32 foci).

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
    """One unconditional, flat skill dice bonus -- the only shape this file's `<bonus>` nodes ever
    resolve to `FLAT_BONUS` with."""

    target_kind: str  # always "skill" for this catalog
    target_name: str
    value: int


def _is_flat_skill_bonus(elem: ET.Element) -> bool:
    return {child.tag for child in elem} == _FLAT_SKILL_FIELDS


def _classify_bonus(
    context_name: str, bonus_elem: ET.Element | None
) -> tuple[BonusSupport, tuple[FlatBonus, ...]]:
    """Classify one bonus slot's `<bonus>` node. `context_name` is the enclosing `<choice>`'s own
    `<name>` (used only to look up `_VERIFIED_NO_EFFECT_CHOICES` when `bonus_elem` is absent) --
    irrelevant, and unused, when called for a General slot expressed as a fixed top-level `<bonus>`
    (see `MentorSpiritArchetype.general_options`'s own construction below).
    """
    if bonus_elem is None:
        if context_name in _VERIFIED_NO_EFFECT_CHOICES:
            return BonusSupport.NO_EFFECT, ()
        return BonusSupport.NOT_YET_SUPPORTED, ()

    flat_bonuses = []
    for child in bonus_elem:
        if child.tag == "specificskill" and _is_flat_skill_bonus(child):
            flat_bonuses.append(
                FlatBonus(
                    target_kind="skill",
                    target_name=child.findtext("name", ""),
                    value=int(child.findtext("bonus", "0")),
                )
            )
        else:
            return BonusSupport.NOT_YET_SUPPORTED, ()
    return BonusSupport.FLAT_BONUS, tuple(flat_bonuses)


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


def _parse_choice(archetype_id: str, elem: ET.Element) -> MentorChoice:
    name = elem.findtext("name", "")
    support, flat_bonuses = _classify_bonus(name, elem.find("bonus"))
    return MentorChoice(
        id=f"{archetype_id}:{name}",
        name=name,
        bonus_support=support,
        flat_bonuses=flat_bonuses,
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
        general_support, general_flat_bonuses = _classify_bonus("", general_bonus_elem)
        general_options: tuple[MentorChoice, ...] = (
            MentorChoice(
                id=f"{mentor_id}:general",
                name="General",
                bonus_support=general_support,
                flat_bonuses=general_flat_bonuses,
            ),
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
