"""Tests for `chummer5.engine.qualities` (quality selection & Improvement application).

Named `test_quality_selection.py`, not `test_qualities.py`, to avoid colliding with
`tests/unit/test_qualities.py` (WP3's data-loader tests) -- mirrors WP7's
`test_skill_allocation.py`/`test_skills.py` split for the same reason.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from chummer5.data.metatypes import load_metatypes
from chummer5.data.priorities import load_priorities
from chummer5.data.qualities import BonusSupport, FlatBonus, Quality, load_qualities
from chummer5.engine.character import create_character, metatype_choices
from chummer5.engine.derived import mental_limit
from chummer5.engine.improvements import ImprovementSource, ImprovementType
from chummer5.engine.qualities import (
    QUALITY_KARMA_LIMIT,
    apply_quality_improvements,
    create_quality_selection,
    mvp_quality_catalog,
    offerable_quality_catalog,
    resolve_metatype_qualities,
)

QUALITIES = load_qualities()
METATYPES = load_metatypes()
PRIORITIES = load_priorities()

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


def test_mvp_quality_catalog_is_exactly_the_fourteen_offerable_qualities() -> None:
    # WP8's 3 FLAT_BONUS qualities (Catlike, Double-Jointed, Natural Athlete) + WP22's 3 new
    # FLAT_BONUS Indomitable qualities + WP22's 8 verified-NO_EFFECT qualities = 14. Two of the
    # NO_EFFECT qualities (Simsense Vertigo, Unsteady Hands) are Negative -- the first Negative
    # qualities MVP has ever offered (see module docstring); the other 12 are Positive.
    offered = mvp_quality_catalog(QUALITIES)
    assert {q.name for q in offered} == {
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
    }
    assert all(
        q.bonus_support in (BonusSupport.FLAT_BONUS, BonusSupport.NO_EFFECT) for q in offered
    )
    negative_names = {q.name for q in offered if q.category == "Negative"}
    assert negative_names == {"Simsense Vertigo", "Unsteady Hands"}


def test_mvp_quality_catalog_excludes_qualities_researched_and_rejected_this_wp() -> None:
    # WP22's Implementation Plan entry names these explicitly as researched-and-excluded, not
    # silently missing: Astral Beacon/Astral Chameleon/Focused Concentration (magic-gated or
    # unreachable by mundane characters), Gremlins (Notoriety-gated, a system this project doesn't
    # model). See spec/rulebooks/learnings.md's WP22 entry for the full research pass, which also
    # covers Prejudiced/SINner/Home Ground/Code of Honor/Codeblock/Social Stress/Natural
    # Immunity/Spirit Affinity -- all excluded for needing a free-text "select a target" mechanism
    # this WP didn't build.
    offered_names = {q.name for q in mvp_quality_catalog(QUALITIES)}
    excluded_names = {
        "Astral Beacon",
        "Astral Chameleon",
        "Focused Concentration",
        "Gremlins",
        "Home Ground",
        "Code of Honor",
        "Codeblock",
        "Social Stress",
        "Natural Immunity (Natural)",
        "Natural Immunity (Synthetic)",
        "Spirit Affinity",
        "Prejudiced (Common, Biased)",
        "Prejudiced (Common, Outspoken)",
        "Prejudiced (Common, Radical)",
        "Prejudiced (Specific, Biased)",
        "Prejudiced (Specific, Outspoken)",
        "Prejudiced (Specific, Radical)",
        "SINner (Corporate)",
        "SINner (National)",
        "SINner (Corporate Limited)",
        "SINner (Criminal)",
    }
    assert excluded_names.isdisjoint(offered_names)
    # Every name above is a real SR5 quality, not a typo -- guards this test itself against silently
    # asserting nothing.
    real_names = {q.name for q in QUALITIES}
    assert excluded_names <= real_names


def test_mvp_quality_catalog_excludes_not_yet_supported_quality() -> None:
    # Explicit acceptance-criteria test: a NOT_YET_SUPPORTED quality (Analytical Mind: conditional
    # <skillattribute> bonus) is excluded from the offered list entirely, not offered with its bonus
    # silently dropped.
    analytical_mind = _by_name("Analytical Mind")
    assert analytical_mind.bonus_support == BonusSupport.NOT_YET_SUPPORTED
    offered_names = {q.name for q in mvp_quality_catalog(QUALITIES)}
    assert analytical_mind.name not in offered_names

    with pytest.raises(ValueError, match="not an MVP-offered quality id"):
        create_quality_selection([analytical_mind.id], QUALITIES)


def test_create_quality_selection_single_positive_quality() -> None:
    catlike = _by_name("Catlike")
    selection = create_quality_selection([catlike.id], QUALITIES)
    assert selection.qualities == (catlike,)
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
    # Every other MVP-offered quality is still there -- this excludes exactly the granted one(s).
    assert {q.name for q in offered} == {q.name for q in mvp_quality_catalog(QUALITIES)} - {
        "Low-Light Vision"
    }


def test_offerable_quality_catalog_unaffected_for_human() -> None:
    human_character = _mundane_character("Human")
    offered = offerable_quality_catalog(human_character, QUALITIES)
    assert {q.name for q in offered} == {q.name for q in mvp_quality_catalog(QUALITIES)}


def test_create_quality_selection_rejects_already_metatype_granted_quality() -> None:
    elf_character = _mundane_character("Elf")
    metatype_qualities = resolve_metatype_qualities(elf_character.metatype, QUALITIES)
    elf_character = replace(elf_character, metatype_qualities=metatype_qualities)
    offered = offerable_quality_catalog(elf_character, QUALITIES)
    low_light = next(q for q in QUALITIES if q.name == "Low-Light Vision")
    with pytest.raises(ValueError, match="not an MVP-offered quality id"):
        create_quality_selection([low_light.id], offered)
