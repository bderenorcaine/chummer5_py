"""Tests for `chummer5.engine.qualities` (quality selection & Improvement application).

Named `test_quality_selection.py`, not `test_qualities.py`, to avoid colliding with
`tests/unit/test_qualities.py` (WP3's data-loader tests) -- mirrors WP7's
`test_skill_allocation.py`/`test_skills.py` split for the same reason.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from chummer5.data.mentors import load_mentors
from chummer5.data.metatypes import load_metatypes
from chummer5.data.priorities import load_priorities
from chummer5.data.qualities import BonusSupport, FlatBonus, Quality, load_qualities
from chummer5.data.skills import load_skills
from chummer5.data.traditions import load_traditions
from chummer5.engine.character import Character, create_character, metatype_choices
from chummer5.engine.derived import mental_limit
from chummer5.engine.improvements import ImprovementSource, ImprovementType
from chummer5.engine.magic import create_magic_selection
from chummer5.engine.qualities import (
    MENTOR_SPIRIT_QUALITY_NAME,
    OUT_OF_SCOPE_QUALITY_NAMES,
    QUALITY_KARMA_LIMIT,
    GateContext,
    MentorSpiritPick,
    QualityPick,
    QualityPickRequest,
    apply_mentor_spirit_improvements,
    apply_quality_improvements,
    create_quality_selection,
    mvp_quality_catalog,
    offerable_quality_catalog,
    requirement_failure,
    resolve_metatype_qualities,
)

QUALITIES = load_qualities()
METATYPES = load_metatypes()
PRIORITIES = load_priorities()
TRADITIONS = load_traditions()
SKILLS = load_skills()
MENTORS = load_mentors()
MENTOR_SPIRIT = next(q for q in QUALITIES if q.name == MENTOR_SPIRIT_QUALITY_NAME)

# A synthetic Negative-category FLAT_BONUS quality -- no real SR5 quality with this shape currently
# exists (see module docstring in chummer5.engine.qualities), so the negative-karma-cap rule is
# exercised with hand-authored data, the same "prove the rule in isolation" pattern WP5 used for
# Improvement dedup and WP7 used for the dice-pool formula.
_SYNTHETIC_NEGATIVE_FLAT_BONUS = Quality(
    id="synthetic-negative-flat-bonus",
    name="Synthetic Negative Flat Bonus",
    category="Negative",
    karma=-20,
    limit=None,
    source="SR5",
    page=0,
    bonus_support=BonusSupport.FLAT_BONUS,
    flat_bonuses=(FlatBonus(target_kind="skill", target_name="Running", value=-1),),
    raw_bonus=None,
)

# A second synthetic Positive quality, used to push a selection's positive-karma sum past the
# 25-karma limit (the 3 real FLAT_BONUS qualities only sum to 20 -- see module docstring).
_SYNTHETIC_POSITIVE_FLAT_BONUS = Quality(
    id="synthetic-positive-flat-bonus",
    name="Synthetic Positive Flat Bonus",
    category="Positive",
    karma=10,
    limit=None,
    source="SR5",
    page=0,
    bonus_support=BonusSupport.FLAT_BONUS,
    flat_bonuses=(FlatBonus(target_kind="attribute", target_name="BOD", value=1),),
    raw_bonus=None,
)


def _by_name(name: str) -> Quality:
    return next(q for q in QUALITIES if q.name == name)


def test_mvp_quality_catalog_is_exactly_the_eighty_six_offerable_qualities() -> None:
    # WP8's 3 FLAT_BONUS qualities (Catlike, Double-Jointed, Natural Athlete) + WP22's 3 new
    # FLAT_BONUS Indomitable qualities + WP22's 8 verified-NO_EFFECT qualities = 14, +1 for WP49's
    # Bilingual (see spec/rulebooks/learnings.md's WP49 entry -- Bilingual was NOT_YET_SUPPORTED
    # before this WP, despite the Implementation Plan's own WP49 entry assuming otherwise) = 15,
    # +9 for WP55's SELECT_TEXT qualities (SINner x4, Code of Honor, Codeblock, Social Stress,
    # Natural Immunity x2) = 24. Two of the NO_EFFECT qualities (Simsense Vertigo, Unsteady Hands)
    # plus the 4 SINner variants, Code of Honor, Codeblock, and Social Stress (7 more) are
    # Negative -- 9 Negative qualities total, the rest (15) Positive. WP112 adds Exceptional
    # Attribute and Lucky (Positive) = 26. WP114 adds the 19 remaining in-scope Positive qualities
    # (Aptitude is WP116's; Mentor Spirit is widened per-character, not here) = 45. WP115 adds 36
    # Negative qualities (Incompetent, Uncouth, Uneducated and Sensitive System are WP117's) = 81.
    # WP116 adds Aptitude = 82. WP117 adds Incompetent, Uncouth, Uneducated and Sensitive
    # System = 86: every purchasable in-scope row but Mentor Spirit, which is widened per character.
    offered = mvp_quality_catalog(QUALITIES)
    assert {q.name for q in offered} == {
        "Aptitude",
        "Incompetent",
        "Uncouth",
        "Uneducated",
        "Sensitive System",
        "Addiction (Mild)",
        "Addiction (Moderate)",
        "Addiction (Severe)",
        "Addiction (Burnout)",
        "Allergy (Uncommon, Mild)",
        "Allergy (Uncommon, Moderate)",
        "Allergy (Uncommon, Severe)",
        "Allergy (Uncommon, Extreme)",
        "Allergy (Common, Mild)",
        "Allergy (Common, Moderate)",
        "Allergy (Common, Severe)",
        "Allergy (Common, Extreme)",
        "Astral Beacon",
        "Bad Luck",
        "Bad Rep",
        "Combat Paralysis",
        "Dependent (Nuisance)",
        "Dependent (Inconvenience)",
        "Dependent (Demanding)",
        "Distinctive Style",
        "Elf Poser",
        "Gremlins",
        "Insomnia (Basic)",
        "Insomnia (Full)",
        "Loss of Confidence",
        "Low Pain Tolerance",
        "Ork Poser",
        "Prejudiced (Common, Biased)",
        "Prejudiced (Common, Outspoken)",
        "Prejudiced (Common, Radical)",
        "Prejudiced (Specific, Biased)",
        "Prejudiced (Specific, Outspoken)",
        "Prejudiced (Specific, Radical)",
        "Scorched",
        "Spirit Bane",
        "Weak Immune System",
        "Ambidextrous",
        "Analytical Mind",
        "Astral Chameleon",
        "Blandness",
        "Codeslinger",
        "First Impression",
        "Focused Concentration",
        "High Pain Tolerance",
        "Home Ground",
        "Human-Looking",
        "Magic Resistance",
        "Photographic Memory",
        "Quick Healer",
        "Resistance to Pathogens",
        "Resistance to Toxins",
        "Resistance to Pathogens and Toxins",
        "Spirit Affinity",
        "Toughness",
        "Will to Live",
        "Exceptional Attribute",
        "Lucky",
        "Catlike",
        "Double-Jointed",
        "Natural Athlete",
        "Indomitable (Mental)",
        "Indomitable (Physical)",
        "Indomitable (Social)",
        "Gearhead",
        "Guts",
        "Juryrigger",
        "Natural Hardening",
        "Low-Light Vision",
        "Thermographic Vision",
        "Simsense Vertigo",
        "Unsteady Hands",
        "Bilingual",
        "SINner (National)",
        "SINner (Corporate Limited)",
        "SINner (Criminal)",
        "SINner (Corporate)",
        "Code of Honor",
        "Codeblock",
        "Social Stress",
        "Natural Immunity (Natural)",
        "Natural Immunity (Synthetic)",
    }
    assert all(
        q.bonus_support
        in (BonusSupport.FLAT_BONUS, BonusSupport.NO_EFFECT, BonusSupport.SELECT_TEXT)
        for q in offered
    )
    negative_names = {q.name for q in offered if q.category == "Negative"}
    assert negative_names == {
        "Simsense Vertigo",
        "Unsteady Hands",
        "SINner (National)",
        "SINner (Corporate Limited)",
        "SINner (Criminal)",
        "SINner (Corporate)",
        "Code of Honor",
        "Codeblock",
        "Social Stress",
        "Addiction (Mild)",
        "Addiction (Moderate)",
        "Addiction (Severe)",
        "Addiction (Burnout)",
        "Allergy (Uncommon, Mild)",
        "Allergy (Uncommon, Moderate)",
        "Allergy (Uncommon, Severe)",
        "Allergy (Uncommon, Extreme)",
        "Allergy (Common, Mild)",
        "Allergy (Common, Moderate)",
        "Allergy (Common, Severe)",
        "Allergy (Common, Extreme)",
        "Astral Beacon",
        "Bad Luck",
        "Bad Rep",
        "Combat Paralysis",
        "Dependent (Nuisance)",
        "Dependent (Inconvenience)",
        "Dependent (Demanding)",
        "Distinctive Style",
        "Elf Poser",
        "Gremlins",
        "Insomnia (Basic)",
        "Insomnia (Full)",
        "Loss of Confidence",
        "Low Pain Tolerance",
        "Ork Poser",
        "Prejudiced (Common, Biased)",
        "Prejudiced (Common, Outspoken)",
        "Prejudiced (Common, Radical)",
        "Prejudiced (Specific, Biased)",
        "Prejudiced (Specific, Outspoken)",
        "Prejudiced (Specific, Radical)",
        "Scorched",
        "Spirit Bane",
        "Weak Immune System",
        "Incompetent",
        "Uncouth",
        "Uneducated",
        "Sensitive System",
    }


def test_mvp_quality_catalog_excludes_qualities_researched_and_rejected_this_wp() -> None:
    # WP22's Implementation Plan entry names these explicitly as researched-and-excluded, not
    # silently missing: Astral Beacon/Astral Chameleon/Focused Concentration (magic-gated or
    # unreachable by mundane characters), Gremlins (Notoriety-gated, a system this project doesn't
    # model). See spec/rulebooks/learnings.md's WP22 entry for the full research pass. WP55 later
    # built the free-text mechanism and offered 9 of the 16 qualities WP22 identified as needing it
    # (see that WP's own entry) -- Home Ground, Spirit Affinity, and the 6 Prejudiced variants stay
    # excluded (each needs its own, still-unbuilt kind of engine support: a branching bonus, a
    # magic-gate, a dice-pool-modifier mechanism, respectively).
    #
    # WP114 and WP115 offered every one of them, and WP116-WP117 the rest. What is still unoffered
    # is only the rows never offered from this catalog on purpose.
    unoffered = {q.name for q in QUALITIES} - {q.name for q in mvp_quality_catalog(QUALITIES)}
    assert unoffered == {
        "Mentor Spirit",  # widened per character (WP48)
        "Resistance to Pathogens/Toxins",  # the Dwarf's racial row (WP114)
        *OUT_OF_SCOPE_QUALITY_NAMES,
    }


def test_mvp_quality_catalog_excludes_not_yet_supported_quality() -> None:
    # Explicit acceptance-criteria test: a NOT_YET_SUPPORTED quality is excluded from the offered
    # list entirely, not offered with its bonus silently dropped. (Analytical Mind was the example
    # until WP114 registered it, then Gremlins until WP115, then Uncouth until WP117. Since then
    # the only NOT_YET_SUPPORTED row with no other reason to be unoffered is Mentor Spirit, whose
    # effect is its archetype -- offered to a magic user, and not to a mundane character.)
    mentor = _by_name("Mentor Spirit")
    assert mentor.bonus_support == BonusSupport.NOT_YET_SUPPORTED
    offered_names = {q.name for q in mvp_quality_catalog(QUALITIES)}
    assert mentor.name not in offered_names

    with pytest.raises(ValueError, match="not an MVP-offered quality id"):
        create_quality_selection([mentor.id], QUALITIES)


def test_create_quality_selection_single_positive_quality() -> None:
    catlike = _by_name("Catlike")
    selection = create_quality_selection([catlike.id], QUALITIES)
    assert selection.qualities == (QualityPick(catlike),)
    assert selection.positive_karma == 7
    assert selection.negative_karma == 0
    assert selection.karma_cost == 7


def test_create_quality_selection_multiple_positive_qualities_sum() -> None:
    catlike = _by_name("Catlike")
    double_jointed = _by_name("Double-Jointed")
    selection = create_quality_selection([catlike.id, double_jointed.id], QUALITIES)
    assert selection.positive_karma == 13  # 7 + 6
    assert selection.karma_cost == 13


def test_create_quality_selection_empty_selection() -> None:
    selection = create_quality_selection([], QUALITIES)
    assert selection.qualities == ()
    assert selection.positive_karma == 0
    assert selection.negative_karma == 0
    assert selection.karma_cost == 0


def test_create_quality_selection_rejects_unknown_id() -> None:
    with pytest.raises(ValueError, match="not an MVP-offered quality id"):
        create_quality_selection(["not-a-real-id"], QUALITIES)


def test_create_quality_selection_rejects_duplicate_selection() -> None:
    catlike = _by_name("Catlike")
    with pytest.raises(ValueError, match="selected more than once"):
        create_quality_selection([catlike.id, catlike.id], QUALITIES)


def test_create_quality_selection_rejects_positive_karma_over_limit() -> None:
    catalog = (*QUALITIES, _SYNTHETIC_POSITIVE_FLAT_BONUS)
    catlike = _by_name("Catlike")  # 7
    double_jointed = _by_name("Double-Jointed")  # 6
    natural_athlete = _by_name("Natural Athlete")  # 7
    # 7 + 6 + 7 + 10 = 30 > 25.
    with pytest.raises(ValueError, match="Positive Qualities cost 30 karma"):
        create_quality_selection(
            [
                catlike.id,
                double_jointed.id,
                natural_athlete.id,
                _SYNTHETIC_POSITIVE_FLAT_BONUS.id,
            ],
            catalog,
        )


def test_create_quality_selection_allows_exactly_the_karma_limit() -> None:
    catalog = (*QUALITIES, _SYNTHETIC_POSITIVE_FLAT_BONUS)
    catlike = _by_name("Catlike")  # 7
    double_jointed = _by_name("Double-Jointed")  # 6
    # 7 + 6 + 10 = 23, safely under; bump to exactly 25 isn't achievable with these exact karma
    # values, so this just asserts the boundary isn't over-strict (< limit is fine).
    selection = create_quality_selection(
        [catlike.id, double_jointed.id, _SYNTHETIC_POSITIVE_FLAT_BONUS.id], catalog
    )
    assert selection.positive_karma == 23
    assert selection.positive_karma <= QUALITY_KARMA_LIMIT


def test_create_quality_selection_rejects_negative_karma_over_limit() -> None:
    catalog = (*QUALITIES, _SYNTHETIC_NEGATIVE_FLAT_BONUS)
    # A second synthetic negative quality would be needed to exceed 25 from one alone at -20; use
    # two distinct synthetic ids to push the sum past the limit.
    second = Quality(
        id="synthetic-negative-flat-bonus-2",
        name="Synthetic Negative Flat Bonus 2",
        category="Negative",
        karma=-10,
        limit=None,
        source="SR5",
        page=0,
        bonus_support=BonusSupport.FLAT_BONUS,
        flat_bonuses=(FlatBonus(target_kind="skill", target_name="Gymnastics", value=-1),),
        raw_bonus=None,
    )
    catalog = (*catalog, second)
    with pytest.raises(ValueError, match="Negative Qualities grant 30 karma"):
        create_quality_selection(
            [_SYNTHETIC_NEGATIVE_FLAT_BONUS.id, second.id],
            catalog,
        )


def test_create_quality_selection_positive_and_negative_caps_are_independent() -> None:
    # 13 karma of Positive (Catlike + Double-Jointed) plus 20 karma of Negative (the synthetic
    # quality) -- neither side exceeds 25 on its own, even though the combined net swing
    # (positive_karma + negative_karma == 33) would exceed 25 if the two pools were wrongly treated
    # as one shared budget.
    catalog = (*QUALITIES, _SYNTHETIC_NEGATIVE_FLAT_BONUS)
    catlike = _by_name("Catlike")  # 7
    double_jointed = _by_name("Double-Jointed")  # 6
    selection = create_quality_selection(
        [catlike.id, double_jointed.id, _SYNTHETIC_NEGATIVE_FLAT_BONUS.id], catalog
    )
    assert selection.positive_karma == 13
    assert selection.negative_karma == 20
    assert selection.karma_cost == -7  # net karma refund


def _mundane_human_character() -> object:
    heritage = PRIORITIES.heritage["D"]
    human_choice = next(
        c for c in metatype_choices(heritage, METATYPES) if c.metatype.name == "Human"
    )
    return create_character(
        metatype_choice=human_choice,
        heritage_letter="D",
        attributes_letter="A",
        priorities=PRIORITIES,
        attribute_points={"BOD": 3},
    )


def test_apply_quality_improvements_single_skill_target() -> None:
    character = _mundane_human_character()
    catlike = _by_name("Catlike")
    selection = create_quality_selection([catlike.id], QUALITIES)

    apply_quality_improvements(character, selection.qualities)

    assert character.improvements.resolve(ImprovementType.SKILL, "Sneaking") == 2
    assert character.improvements.resolve(ImprovementType.SKILL, "Escape Artist") == 0


def test_apply_quality_improvements_multiple_targets_from_one_quality() -> None:
    character = _mundane_human_character()
    natural_athlete = _by_name("Natural Athlete")
    selection = create_quality_selection([natural_athlete.id], QUALITIES)

    apply_quality_improvements(character, selection.qualities)

    assert character.improvements.resolve(ImprovementType.SKILL, "Running") == 2
    assert character.improvements.resolve(ImprovementType.SKILL, "Gymnastics") == 2


def test_apply_quality_improvements_indomitable_raises_mental_limit() -> None:
    # End-to-end WP22 acceptance check: Indomitable (Mental) actually raises mental_limit() via
    # chummer5.engine.derived, not just the raw Improvement index.
    character = _mundane_human_character()
    indomitable_mental = _by_name("Indomitable (Mental)")
    selection = create_quality_selection([indomitable_mental.id], QUALITIES)
    base_limit = mental_limit(character)

    apply_quality_improvements(character, selection.qualities)

    assert character.improvements.resolve(ImprovementType.MENTAL_LIMIT, "") == 1
    assert mental_limit(character) == base_limit + 1


def test_apply_quality_improvements_indomitable_trio_raises_all_three_limits() -> None:
    # All 3 Indomitable qualities selected together: 8*3 = 24 karma, under the 25-karma cap, and
    # each raises its own Limit independently (no shared UniqueName dedup between them).
    character = _mundane_human_character()
    mental = _by_name("Indomitable (Mental)")
    physical = _by_name("Indomitable (Physical)")
    social = _by_name("Indomitable (Social)")
    selection = create_quality_selection([mental.id, physical.id, social.id], QUALITIES)
    assert selection.positive_karma == 24

    apply_quality_improvements(character, selection.qualities)

    assert character.improvements.resolve(ImprovementType.MENTAL_LIMIT, "") == 1
    assert character.improvements.resolve(ImprovementType.PHYSICAL_LIMIT, "") == 1
    assert character.improvements.resolve(ImprovementType.SOCIAL_LIMIT, "") == 1


def test_apply_quality_improvements_no_effect_quality_adds_no_improvements() -> None:
    # A verified-NO_EFFECT quality (Gearhead) is selectable and karma-charged, but applies no
    # Improvement -- flat_bonuses is () by construction, so this is a no-op, not a special case.
    character = _mundane_human_character()
    gearhead = _by_name("Gearhead")
    selection = create_quality_selection([gearhead.id], QUALITIES)
    assert selection.positive_karma == 11

    apply_quality_improvements(character, selection.qualities)

    assert character.improvements.improvements == ()


def test_apply_quality_improvements_attribute_target() -> None:
    character = _mundane_human_character()
    selection = create_quality_selection(
        [_SYNTHETIC_POSITIVE_FLAT_BONUS.id], (*QUALITIES, _SYNTHETIC_POSITIVE_FLAT_BONUS)
    )

    apply_quality_improvements(character, selection.qualities)

    # metatype minimum (1) + points spent (3) + this quality's +1 Improvement.
    assert character.attribute_value("BOD") == 5


def test_apply_quality_improvements_can_be_retracted_via_remove_source() -> None:
    character = _mundane_human_character()
    catlike = _by_name("Catlike")
    selection = create_quality_selection([catlike.id], QUALITIES)
    apply_quality_improvements(character, selection.qualities)
    assert character.improvements.resolve(ImprovementType.SKILL, "Sneaking") == 2

    character.improvements.remove_source(
        character.improvements.improvements[0].source_type, catlike.id
    )
    assert character.improvements.resolve(ImprovementType.SKILL, "Sneaking") == 0


# --- WP23: metatype-granted free qualities ------------------------------------------------------


def _mundane_character(metatype_name: str) -> object:
    heritage = PRIORITIES.heritage["D"]
    choice = next(
        c for c in metatype_choices(heritage, METATYPES) if c.metatype.name == metatype_name
    )
    return create_character(
        metatype_choice=choice,
        heritage_letter="D",
        attributes_letter="A",
        priorities=PRIORITIES,
        attribute_points={},
    )


def test_resolve_metatype_qualities_elf() -> None:
    elf = next(m for m in METATYPES if m.name == "Elf" and m.source == "SR5")
    resolved = resolve_metatype_qualities(elf, QUALITIES)
    assert [q.name for q in resolved] == ["Low-Light Vision"]


def test_resolve_metatype_qualities_dwarf_positive_and_negative_combined() -> None:
    dwarf = next(m for m in METATYPES if m.name == "Dwarf" and m.source == "SR5")
    resolved = resolve_metatype_qualities(dwarf, QUALITIES)
    assert [q.name for q in resolved] == [
        "Thermographic Vision",
        "Resistance to Pathogens/Toxins",
    ]


def test_resolve_metatype_qualities_human_is_empty() -> None:
    human = next(m for m in METATYPES if m.name == "Human" and m.source == "SR5")
    assert resolve_metatype_qualities(human, QUALITIES) == ()


def test_resolve_metatype_qualities_raises_for_unresolvable_name() -> None:
    from chummer5.data.metatypes import Metatype

    bogus = Metatype(
        id="bogus",
        name="Bogus",
        category="Metahuman",
        karma=0,
        attributes=next(m for m in METATYPES if m.name == "Human").attributes,
        source="SR5",
        page=0,
        metavariants=(),
        qualities_positive=("Not A Real Quality",),
    )
    with pytest.raises(ValueError, match="not found in the catalog"):
        resolve_metatype_qualities(bogus, QUALITIES)


def test_resistance_to_pathogens_is_not_yet_supported_but_still_grantable() -> None:
    # Confirms WP23's design decision directly: a NOT_YET_SUPPORTED metatype quality still
    # resolves and applies (as a zero-Improvement no-op), rather than raising or being skipped.
    dwarf = next(m for m in METATYPES if m.name == "Dwarf" and m.source == "SR5")
    resistance = next(q for q in QUALITIES if q.name == "Resistance to Pathogens/Toxins")
    assert resistance.bonus_support == BonusSupport.NOT_YET_SUPPORTED
    assert resistance.flat_bonuses == ()
    resolved = resolve_metatype_qualities(dwarf, QUALITIES)
    assert resistance in resolved


def test_apply_quality_improvements_metatype_source_is_independently_retractable() -> None:
    character = _mundane_character("Elf")
    metatype_qualities = resolve_metatype_qualities(character.metatype, QUALITIES)
    catlike = _by_name("Catlike")
    player_selection = create_quality_selection([catlike.id], QUALITIES)

    apply_quality_improvements(
        character, metatype_qualities, source_type=ImprovementSource.METATYPE
    )
    apply_quality_improvements(character, player_selection.qualities)

    # Both bonuses present (Low-Light Vision is NO_EFFECT so contributes no Improvement itself, but
    # Catlike's does) -- retracting only the METATYPE source leaves the QUALITY one untouched.
    assert character.improvements.resolve(ImprovementType.SKILL, "Sneaking") == 2
    low_light = metatype_qualities[0]
    character.improvements.remove_source(ImprovementSource.METATYPE, low_light.id)
    assert character.improvements.resolve(ImprovementType.SKILL, "Sneaking") == 2  # unaffected
    character.improvements.remove_source(ImprovementSource.QUALITY, catlike.id)
    assert character.improvements.resolve(ImprovementType.SKILL, "Sneaking") == 0


def test_offerable_quality_catalog_excludes_metatype_granted_quality() -> None:
    elf_character = _mundane_character("Elf")
    metatype_qualities = resolve_metatype_qualities(elf_character.metatype, QUALITIES)
    elf_character = replace(elf_character, metatype_qualities=metatype_qualities)
    offered = offerable_quality_catalog(elf_character, QUALITIES)
    assert "Low-Light Vision" not in {q.name for q in offered}
    # Every other MVP-offered quality is still there, except WP108's magic-gated ones (this Elf is
    # mundane) -- this excludes exactly the granted one(s).
    assert {q.name for q in offered} == {q.name for q in mvp_quality_catalog(QUALITIES)} - {
        "Low-Light Vision",
        "Elf Poser",  # WP115: humans only
        *_MAGIC_GATED,
    }


# WP114: offered qualities a mundane character's gate hides (WP108).
_MAGIC_GATED = {
    "Astral Chameleon",
    "Focused Concentration",
    "Spirit Affinity",
    # WP115
    "Astral Beacon",
    "Spirit Bane",
}


def test_offerable_quality_catalog_unaffected_for_human() -> None:
    human_character = _mundane_character("Human")
    offered = offerable_quality_catalog(human_character, QUALITIES)
    assert {q.name for q in offered} == {q.name for q in mvp_quality_catalog(QUALITIES)} - {
        "Human-Looking",
        *_MAGIC_GATED,
    }


def test_create_quality_selection_rejects_already_metatype_granted_quality() -> None:
    elf_character = _mundane_character("Elf")
    metatype_qualities = resolve_metatype_qualities(elf_character.metatype, QUALITIES)
    elf_character = replace(elf_character, metatype_qualities=metatype_qualities)
    offered = offerable_quality_catalog(elf_character, QUALITIES)
    low_light = next(q for q in QUALITIES if q.name == "Low-Light Vision")
    with pytest.raises(ValueError, match="not an MVP-offered quality id"):
        create_quality_selection([low_light.id], offered)


# --- WP48: Mentor Spirit --------------------------------------------------------------------------


_MAGICAL_SKILL_IDS = [s.id for s in SKILLS if s.category == "Magical Active"][:2]


def _magician() -> Character:
    """A Human Magician, Talent letter A (the letter that actually offers "Magician" -- see
    `chummer5.data.priorities`; requires satisfying its 2-skill free-skill grant), Hermetic
    tradition -- mirrors `chummer5.engine.foci`'s own test helper."""
    character = _mundane_human_character()
    tradition = next(t for t in TRADITIONS if t.name == "Hermetic")
    selection = create_magic_selection(
        "A", "Magician", tradition.id, _MAGICAL_SKILL_IDS, PRIORITIES, TRADITIONS, SKILLS
    )
    return replace(
        character,
        magic_type=selection.magic_type,
        magic_rating=selection.magic_rating,
        tradition=selection.tradition,
    )


def _adept() -> Character:
    """A Human Adept, Talent letter D (no free-skill grant)."""
    character = _mundane_human_character()
    selection = create_magic_selection("D", "Adept", None, [], PRIORITIES, TRADITIONS, SKILLS)
    return replace(character, magic_type=selection.magic_type, magic_rating=selection.magic_rating)


# single-option General, both slots unsupported
BEAR = next(m for m in MENTORS if m.name == "Bear")
CAT = next(m for m in MENTORS if m.name == "Cat")  # 2-option General (real player choice)
DOG = next(m for m in MENTORS if m.name == "Dog")  # single-option General, FLAT_BONUS


def test_mentor_spirit_offered_only_for_magic_active_characters() -> None:
    mundane = _mundane_human_character()
    mundane_names = {q.name for q in offerable_quality_catalog(mundane, QUALITIES)}
    assert MENTOR_SPIRIT.name not in mundane_names

    magician = _magician()
    magician_names = {q.name for q in offerable_quality_catalog(magician, QUALITIES)}
    assert MENTOR_SPIRIT.name in magician_names

    adept = _adept()
    adept_names = {q.name for q in offerable_quality_catalog(adept, QUALITIES)}
    assert MENTOR_SPIRIT.name in adept_names


def test_create_quality_selection_rejects_mentor_spirit_for_mundane_via_offered_catalog() -> None:
    # A Mundane character never even sees Mentor Spirit as offerable -- the ordinary "not an
    # MVP-offered quality id" path handles it, no Mentor-Spirit-specific check needed here.
    mundane = _mundane_human_character()
    offered = offerable_quality_catalog(mundane, QUALITIES)
    with pytest.raises(ValueError, match="not an MVP-offered quality id"):
        create_quality_selection([MENTOR_SPIRIT.id], offered, magic_type=None)


def test_create_quality_selection_mentor_spirit_requires_an_archetype() -> None:
    with pytest.raises(ValueError, match="requires an archetype"):
        create_quality_selection(
            [MENTOR_SPIRIT.id], QUALITIES, magic_type="Magician", mentor_catalog=MENTORS
        )


def test_create_quality_selection_rejects_orphaned_archetype_pick() -> None:
    with pytest.raises(ValueError, match="without the Mentor Spirit quality"):
        create_quality_selection(
            [],
            QUALITIES,
            magic_type="Magician",
            mentor_catalog=MENTORS,
            mentor_spirit_archetype_id=DOG.id,
        )


def test_create_quality_selection_rejects_unknown_archetype_id() -> None:
    with pytest.raises(ValueError, match="not a Mentor Spirit archetype id"):
        create_quality_selection(
            [MENTOR_SPIRIT.id],
            QUALITIES,
            magic_type="Magician",
            mentor_catalog=MENTORS,
            mentor_spirit_archetype_id="not-a-real-archetype",
        )


def test_create_quality_selection_single_option_general_auto_resolves() -> None:
    selection = create_quality_selection(
        [MENTOR_SPIRIT.id],
        QUALITIES,
        magic_type="Magician",
        mentor_catalog=MENTORS,
        mentor_spirit_archetype_id=DOG.id,
    )
    assert selection.mentor_spirit == MentorSpiritPick(
        archetype=DOG,
        general_choice=DOG.general_options[0],
        gated_choice=DOG.magician_choice,
    )
    assert selection.karma_cost == MENTOR_SPIRIT.karma


def test_create_quality_selection_accepts_matching_choice_for_single_option_archetype() -> None:
    # Deliberately lenient (not "must be None"): a save/load round trip always persists whatever
    # general_choice.id was actually resolved, even for a single-option archetype -- see this
    # function's own docstring for why rejecting an explicit-but-matching id would break that.
    selection = create_quality_selection(
        [MENTOR_SPIRIT.id],
        QUALITIES,
        magic_type="Magician",
        mentor_catalog=MENTORS,
        mentor_spirit_archetype_id=DOG.id,
        mentor_spirit_general_choice_id=DOG.general_options[0].id,
    )
    assert selection.mentor_spirit is not None
    assert selection.mentor_spirit.general_choice == DOG.general_options[0]


def test_create_quality_selection_rejects_mismatched_choice_for_single_option_archetype() -> None:
    with pytest.raises(ValueError, match="not a General bonus option"):
        create_quality_selection(
            [MENTOR_SPIRIT.id],
            QUALITIES,
            magic_type="Magician",
            mentor_catalog=MENTORS,
            mentor_spirit_archetype_id=DOG.id,
            mentor_spirit_general_choice_id="not-a-real-choice-id",
        )


def test_create_quality_selection_two_option_general_requires_a_pick() -> None:
    with pytest.raises(ValueError, match="a General bonus option must be chosen"):
        create_quality_selection(
            [MENTOR_SPIRIT.id],
            QUALITIES,
            magic_type="Magician",
            mentor_catalog=MENTORS,
            mentor_spirit_archetype_id=CAT.id,
        )


def test_create_quality_selection_two_option_general_resolves_the_chosen_one() -> None:
    sneaking_name = "+2 dice on Sneaking Tests"
    sneaking_option = next(c for c in CAT.general_options if c.name == sneaking_name)
    selection = create_quality_selection(
        [MENTOR_SPIRIT.id],
        QUALITIES,
        magic_type="Magician",
        mentor_catalog=MENTORS,
        mentor_spirit_archetype_id=CAT.id,
        mentor_spirit_general_choice_id=sneaking_option.id,
    )
    assert selection.mentor_spirit is not None
    assert selection.mentor_spirit.general_choice == sneaking_option
    assert selection.mentor_spirit.gated_choice == CAT.magician_choice


def test_create_quality_selection_gated_choice_resolves_from_magic_type() -> None:
    selection = create_quality_selection(
        [MENTOR_SPIRIT.id],
        QUALITIES,
        magic_type="Adept",
        mentor_catalog=MENTORS,
        mentor_spirit_archetype_id=DOG.id,
        mentor_spirit_power_targets=("Low-light vision", "Direction Sense"),  # WP122
    )
    assert selection.mentor_spirit is not None
    assert selection.mentor_spirit.gated_choice == DOG.adept_choice


def test_create_quality_selection_mentor_spirit_karma_shares_the_positive_pool() -> None:
    # Mentor Spirit (5 karma) plus Catlike (7) sum through the ordinary positive_karma path -- no
    # separate budget, unlike Bound Spirits/Foci's provisional leftover-Karma pool.
    catlike = _by_name("Catlike")
    selection = create_quality_selection(
        [MENTOR_SPIRIT.id, catlike.id],
        QUALITIES,
        magic_type="Magician",
        mentor_catalog=MENTORS,
        mentor_spirit_archetype_id=DOG.id,
    )
    assert selection.positive_karma == 12
    assert selection.karma_cost == 12


def test_apply_mentor_spirit_improvements_dog_general_flat_bonus() -> None:
    character = _magician()
    selection = create_quality_selection(
        [MENTOR_SPIRIT.id],
        QUALITIES,
        magic_type="Magician",
        mentor_catalog=MENTORS,
        mentor_spirit_archetype_id=DOG.id,
    )
    assert selection.mentor_spirit is not None

    apply_mentor_spirit_improvements(character, selection.mentor_spirit)

    # Dog's General bonus is +2 Tracking (FLAT_BONUS); Dog's Magician choice (<spellcategory>) is
    # NOT_YET_SUPPORTED, so it contributes nothing.
    assert character.improvements.resolve(ImprovementType.SKILL, "Tracking") == 2
    for imp in character.improvements.improvements:
        assert imp.source_type == ImprovementSource.MENTOR_SPIRIT
        assert imp.source_id == DOG.id


def test_apply_mentor_spirit_improvements_bear_gives_a_magician_damage_resistance() -> None:
    # WP48 found Bear applied nothing at all. WP122 applies its General +2 Damage Resistance; its
    # Magician slot's Health-spell dice are a conditional pool, shown on the sheet, not an
    # Improvement.
    character = _magician()
    selection = create_quality_selection(
        [MENTOR_SPIRIT.id],
        QUALITIES,
        magic_type="Magician",
        mentor_catalog=MENTORS,
        mentor_spirit_archetype_id=BEAR.id,
    )
    assert selection.mentor_spirit is not None

    apply_mentor_spirit_improvements(character, selection.mentor_spirit)

    assert [(i.improvement_type, i.value) for i in character.improvements.improvements] == [
        (ImprovementType.DAMAGE_RESISTANCE, 2)
    ]


def test_apply_mentor_spirit_improvements_can_be_retracted_via_remove_source() -> None:
    character = _magician()
    selection = create_quality_selection(
        [MENTOR_SPIRIT.id],
        QUALITIES,
        magic_type="Magician",
        mentor_catalog=MENTORS,
        mentor_spirit_archetype_id=DOG.id,
    )
    assert selection.mentor_spirit is not None
    apply_mentor_spirit_improvements(character, selection.mentor_spirit)
    assert character.improvements.resolve(ImprovementType.SKILL, "Tracking") == 2

    character.improvements.remove_source(ImprovementSource.MENTOR_SPIRIT, DOG.id)
    assert character.improvements.resolve(ImprovementType.SKILL, "Tracking") == 0


# --- WP55: free-text quality-selection mechanism (SINner, Code of Honor, Codeblock, Social Stress,
# Natural Immunity) ---------------------------------------------------------------------------


def test_create_quality_selection_requires_text_for_select_text_quality() -> None:
    sinner = _by_name("SINner (National)")
    with pytest.raises(ValueError, match="requires a free-text detail"):
        create_quality_selection([sinner.id], QUALITIES)


def test_create_quality_selection_rejects_blank_text_for_select_text_quality() -> None:
    sinner = _by_name("SINner (National)")
    with pytest.raises(ValueError, match="requires a free-text detail"):
        create_quality_selection([QualityPickRequest(sinner.id, text="   ")], QUALITIES)


def test_create_quality_selection_accepts_and_strips_text_for_select_text_quality() -> None:
    sinner = _by_name("SINner (National)")
    selection = create_quality_selection(
        [QualityPickRequest(sinner.id, text="  UCAS  ")], QUALITIES
    )
    assert selection.qualities[0].text == "UCAS"
    assert selection.negative_karma == 5


def test_create_quality_selection_rejects_text_for_a_non_select_text_quality() -> None:
    catlike = _by_name("Catlike")
    with pytest.raises(ValueError, match="doesn't use one"):
        create_quality_selection([QualityPickRequest(catlike.id, text="whatever")], QUALITIES)


def test_create_quality_selection_rejects_sinner_mutual_exclusion() -> None:
    national = _by_name("SINner (National)")
    corporate = _by_name("SINner (Corporate)")
    with pytest.raises(ValueError, match="cannot be taken together with"):
        create_quality_selection(
            [
                QualityPickRequest(national.id, text="UCAS"),
                QualityPickRequest(corporate.id, text="Ares"),
            ],
            QUALITIES,
        )


def test_create_quality_selection_all_four_sinner_variants_are_pairwise_exclusive() -> None:
    names = (
        "SINner (National)",
        "SINner (Corporate Limited)",
        "SINner (Criminal)",
        "SINner (Corporate)",
    )
    for i, name_a in enumerate(names):
        for name_b in names[i + 1 :]:
            a = _by_name(name_a)
            b = _by_name(name_b)
            with pytest.raises(ValueError, match="cannot be taken together with"):
                create_quality_selection(
                    [QualityPickRequest(a.id, text="x"), QualityPickRequest(b.id, text="y")],
                    QUALITIES,
                )


def test_create_quality_selection_natural_immunity_mutual_exclusion_via_synthetic_catalog() -> None:
    # Weak Immune System is NOT_YET_SUPPORTED (never offered by mvp_quality_catalog), so this
    # exclusion can't be reached through the real offered catalog today -- proven instead with a
    # synthetic stand-in quality, the same "prove the rule in isolation" pattern this module already
    # uses for the karma-cap boundary tests above. See spec/worklogs/WP55.md.
    natural_immunity = _by_name("Natural Immunity (Natural)")
    assert natural_immunity.forbidden_names == ("Weak Immune System",)
    synthetic_weak_immune_system = Quality(
        id="synthetic-weak-immune-system",
        name="Weak Immune System",
        category="Negative",
        karma=-10,
        limit=None,
        source="SR5",
        page=0,
        bonus_support=BonusSupport.NO_EFFECT,
        flat_bonuses=(),
        raw_bonus=None,
        forbidden_names=("Natural Immunity (Natural)", "Natural Immunity (Synthetic)"),
    )
    catalog = (*QUALITIES, synthetic_weak_immune_system)
    with pytest.raises(ValueError, match="cannot be taken together with"):
        create_quality_selection(
            [
                QualityPickRequest(natural_immunity.id, text="Ebola"),
                synthetic_weak_immune_system.id,
            ],
            catalog,
        )


def test_create_quality_selection_multiple_select_text_qualities_independent_texts() -> None:
    code_of_honor = _by_name("Code of Honor")
    codeblock = _by_name("Codeblock")
    selection = create_quality_selection(
        [
            QualityPickRequest(code_of_honor.id, text="Never harm children"),
            QualityPickRequest(codeblock.id, text="Matrix Perception"),
        ],
        QUALITIES,
    )
    assert [p.text for p in selection.qualities] == ["Never harm children", "Matrix Perception"]
    assert selection.negative_karma == 25  # 15 + 10


def test_apply_quality_improvements_select_text_quality_adds_no_improvements() -> None:
    # SELECT_TEXT qualities have no <val>-bearing bonus to apply -- flat_bonuses is () by
    # construction, mirroring NO_EFFECT's identical shape.
    character = _mundane_human_character()
    sinner = _by_name("SINner (National)")
    selection = create_quality_selection([QualityPickRequest(sinner.id, text="UCAS")], QUALITIES)
    apply_quality_improvements(character, selection.qualities)
    assert character.improvements.improvements == ()


# --- WP107: quality instances ---------------------------------------------------------------------


def test_limit_parses_into_max_rating_and_repeatable() -> None:
    assert _by_name("Focused Concentration").max_rating == 6
    assert _by_name("Gremlins").max_rating == 4
    assert _by_name("Catlike").max_rating == 1
    assert _by_name("Ambidextrous").max_rating == 1  # "{arm} - 1": two arms on every core metatype
    assert _by_name("Addiction (Mild)").repeatable
    assert not _by_name("Addiction (Mild)").max_rating > 1
    assert not _by_name("Catlike").repeatable
    assert not _by_name("Indomitable (Mental)").repeatable
    assert set(_by_name("Indomitable (Mental)").include_in_limit) == {
        "Indomitable (Physical)",
        "Indomitable (Social)",
    }


def test_a_rated_pick_costs_karma_times_rating_and_applies_its_bonus_times_rating() -> None:
    indomitable = _by_name("Indomitable (Mental)")
    selection = create_quality_selection([QualityPickRequest(indomitable.id, rating=3)], QUALITIES)
    assert selection.positive_karma == 24
    character = _mundane_human_character()
    baseline = mental_limit(character)
    apply_quality_improvements(character, selection.qualities)
    assert mental_limit(character) == baseline + 3


def test_a_rating_outside_the_quality_s_range_is_rejected() -> None:
    indomitable = _by_name("Indomitable (Mental)")
    catlike = _by_name("Catlike")
    with pytest.raises(ValueError, match="rating 4 is outside 1-3"):
        create_quality_selection([QualityPickRequest(indomitable.id, rating=4)], QUALITIES)
    with pytest.raises(ValueError, match="rating 0 is outside 1-3"):
        create_quality_selection([QualityPickRequest(indomitable.id, rating=0)], QUALITIES)
    with pytest.raises(ValueError, match="rating 2 is outside 1-1"):
        create_quality_selection([QualityPickRequest(catlike.id, rating=2)], QUALITIES)


def test_a_rated_quality_is_one_pick_not_several() -> None:
    indomitable = _by_name("Indomitable (Mental)")
    with pytest.raises(ValueError, match="selected more than once"):
        create_quality_selection([indomitable.id, indomitable.id], QUALITIES)


def test_indomitable_s_three_rows_share_one_three_level_cap() -> None:
    """p. 74: "can be split across the three in any combination up to 3 total levels"."""
    mental = _by_name("Indomitable (Mental)")
    physical = _by_name("Indomitable (Physical)")
    create_quality_selection(
        [QualityPickRequest(mental.id, rating=2), QualityPickRequest(physical.id, rating=1)],
        QUALITIES,
    )
    with pytest.raises(ValueError, match="exceeding the shared 3-level maximum"):
        create_quality_selection(
            [QualityPickRequest(mental.id, rating=2), QualityPickRequest(physical.id, rating=2)],
            QUALITIES,
        )


def test_the_karma_caps_sum_karma_times_rating() -> None:
    indomitable = _by_name("Indomitable (Mental)")
    catlike = _by_name("Catlike")
    with pytest.raises(ValueError, match="Positive Qualities cost 31 karma"):
        create_quality_selection(
            [QualityPickRequest(indomitable.id, rating=3), catlike.id], QUALITIES
        )


def test_a_repeatable_quality_takes_several_instances_with_distinct_details() -> None:
    codeblock = _by_name("Codeblock")
    selection = create_quality_selection(
        [
            QualityPickRequest(codeblock.id, text="Matrix Perception"),
            QualityPickRequest(codeblock.id, text="Hack on the Fly"),
        ],
        QUALITIES,
    )
    assert selection.negative_karma == 20
    assert [p.text for p in selection.qualities] == ["Matrix Perception", "Hack on the Fly"]


def test_a_repeatable_quality_rejects_two_identical_instances() -> None:
    codeblock = _by_name("Codeblock")
    with pytest.raises(ValueError, match="same quality instance was selected twice"):
        create_quality_selection(
            [
                QualityPickRequest(codeblock.id, text="Matrix Perception"),
                QualityPickRequest(codeblock.id, text=" Matrix Perception "),
            ],
            QUALITIES,
        )


def test_the_choice_slot_round_trips() -> None:
    exceptional = _by_name("Exceptional Attribute")
    selection = create_quality_selection(
        [QualityPickRequest(exceptional.id, choice="STR")], QUALITIES
    )
    assert selection.qualities[0].choice == "STR"
    assert selection.to_requests() == (QualityPickRequest(exceptional.id, choice="STR"),)


def test_a_choice_on_a_quality_that_takes_none_is_rejected() -> None:
    catlike = _by_name("Catlike")
    with pytest.raises(ValueError, match="takes no choice"):
        create_quality_selection([QualityPickRequest(catlike.id, choice="anything")], QUALITIES)


# --- WP108: prerequisites and catalog hygiene -----------------------------------------------------


def _as_offerable(name: str) -> Quality:
    """A real catalog row forced offerable, so a gate WP114/WP115 will depend on can be exercised
    before those WPs make the row itself offerable."""
    return replace(_by_name(name), bonus_support=BonusSupport.NO_EFFECT)


def _character_of(metatype_name: str, heritage_letter: str = "A") -> Character:
    heritage = PRIORITIES.heritage[heritage_letter]
    choice = next(
        c for c in metatype_choices(heritage, METATYPES) if c.metatype.name == metatype_name
    )
    character = create_character(
        metatype_choice=choice,
        heritage_letter=heritage_letter,
        attributes_letter="B",
        priorities=PRIORITIES,
        attribute_points={},
    )
    return replace(
        character, metatype_qualities=resolve_metatype_qualities(choice.metatype, QUALITIES)
    )


def test_required_and_forbidden_blocks_are_parsed() -> None:
    human_looking = _by_name("Human-Looking")
    assert [r.mode for r in human_looking.required] == ["oneof"]
    assert set(human_looking.required[0].conditions) == {
        ("metatype", "Elf"),
        ("metatype", "Dwarf"),
        ("metatype", "Ork"),
    }
    assert ("quality", "Magician") in _by_name("Magic Resistance").forbidden[0].conditions


def test_an_elf_is_offered_human_looking_and_a_human_is_not() -> None:
    catalog = (*(q for q in QUALITIES if q.name != "Human-Looking"), _as_offerable("Human-Looking"))
    elf_offered = {q.name for q in offerable_quality_catalog(_character_of("Elf"), catalog)}
    human_offered = {q.name for q in offerable_quality_catalog(_character_of("Human"), catalog)}
    assert "Human-Looking" in elf_offered
    assert "Human-Looking" not in human_offered


def test_a_metatype_gated_pick_is_rejected_for_the_wrong_metatype_and_when_it_is_unknown() -> None:
    human_looking = _as_offerable("Human-Looking")
    catalog = (*(q for q in QUALITIES if q.name != "Human-Looking"), human_looking)
    create_quality_selection([human_looking.id], catalog, metatype_name="Ork")
    with pytest.raises(ValueError, match="Human-Looking requires Elf or Dwarf or Ork"):
        create_quality_selection([human_looking.id], catalog, metatype_name="Human")
    # Fails closed: a caller that doesn't say which metatype gets no metatype-gated quality.
    with pytest.raises(ValueError, match="requires"):
        create_quality_selection([human_looking.id], catalog)


def test_magic_resistance_is_unavailable_to_the_awakened() -> None:
    """p. 76 -- expressed in the data as Magic Resistance's `forbidden` naming the talents, which
    WP108 resolves against `magic_type` rather than against picked qualities."""
    magic_resistance = _by_name("Magic Resistance")
    mundane = GateContext(metatype_name="Human", magic_type=None)
    assert requirement_failure(magic_resistance, mundane) is None
    for talent in ("Magician", "Adept"):
        failure = requirement_failure(
            magic_resistance, GateContext(metatype_name="Human", magic_type=talent)
        )
        assert failure == f"Magic Resistance is not available to a {talent} character"


def test_a_magician_is_not_offered_magic_resistance() -> None:
    catalog = (
        *(q for q in QUALITIES if q.name != "Magic Resistance"),
        _as_offerable("Magic Resistance"),
    )
    magician = replace(_character_of("Human"), magic_type="Magician")
    assert "Magic Resistance" not in {q.name for q in offerable_quality_catalog(magician, catalog)}
    mundane = _character_of("Human")
    assert "Magic Resistance" in {q.name for q in offerable_quality_catalog(mundane, catalog)}


def test_spirit_affinity_follows_the_rulebook_s_magic_users_only_not_the_data_s_spellcasters() -> (
    None
):
    """p. 77: "Available only to magic users". The data leaves Adept out; the rulebook wins."""
    spirit_affinity = _by_name("Spirit Affinity")
    for talent in ("Magician", "Adept"):
        context = GateContext(metatype_name="Human", magic_type=talent)
        assert requirement_failure(spirit_affinity, context) is None
    mundane = GateContext(metatype_name="Human", magic_type=None)
    assert requirement_failure(spirit_affinity, mundane) is not None


def test_astral_beacon_s_magenabled_condition_means_any_magic_type() -> None:
    astral_beacon = _by_name("Astral Beacon")
    assert requirement_failure(astral_beacon, GateContext("Human", "Adept")) is None
    assert requirement_failure(astral_beacon, GateContext("Human", None)) == (
        "Astral Beacon requires Adept or Aspected Magician or Magician or a Magic rating"
    )


def test_a_gate_built_only_from_non_core_conditions_can_never_be_met() -> None:
    astral_perception = _by_name("Astral Perception")  # metatype=Pixie
    assert requirement_failure(astral_perception, GateContext("Elf", "Magician")) is not None


def test_out_of_scope_rows_are_excluded_by_name_and_the_catalog_size_is_pinned() -> None:
    """Loud on data drift: 96 SR5 rows, 8 out of scope, 1 metatype-only (the Dwarf's racial
    Resistance row, WP114), 86 offered (WP112 added 2, WP114 19, WP115 36, WP116 1, WP117 4).
    With Mentor Spirit, offered per character, that is all 87 purchasable in-scope rows."""
    names = {q.name for q in QUALITIES}
    assert len(QUALITIES) == 96
    assert OUT_OF_SCOPE_QUALITY_NAMES <= names
    assert len(OUT_OF_SCOPE_QUALITY_NAMES) == 8
    offered = {q.name for q in mvp_quality_catalog(QUALITIES)}
    assert not offered & OUT_OF_SCOPE_QUALITY_NAMES
    assert len(offered) == 86
    forced = tuple(replace(q, bonus_support=BonusSupport.NO_EFFECT) for q in QUALITIES)
    assert len(mvp_quality_catalog(forced)) == 87


def test_mutual_exclusion_still_reports_its_wp55_wording() -> None:
    national = _by_name("SINner (National)")
    criminal = _by_name("SINner (Criminal)")
    with pytest.raises(
        ValueError, match=r"cannot be taken together with: \['SINner \(Criminal\)'\]"
    ):
        create_quality_selection(
            [QualityPickRequest(national.id, text="a"), QualityPickRequest(criminal.id, text="b")],
            QUALITIES,
        )
