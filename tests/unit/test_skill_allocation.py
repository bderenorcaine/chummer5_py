"""Tests for `chummer5.engine.skills` (WP7) -- not to be confused with `test_skills.py`, which
covers the WP3 data loader (`chummer5.data.skills`) this module builds on.
"""

from dataclasses import replace

import pytest

from chummer5.data.metatypes import load_metatypes
from chummer5.data.priorities import load_priorities
from chummer5.data.skills import load_skills
from chummer5.engine.character import Character, create_character, metatype_choices
from chummer5.engine.improvements import Improvement, ImprovementSource, ImprovementType
from chummer5.engine.skills import (
    DEFAULT_MODIFIER,
    KARMA_SPECIALIZATION_COST,
    MAX_SKILL_RATING_CREATE,
    SPECIALIZATION_BONUS,
    SkillAllocation,
    create_karma_skill_selection,
    create_skill_allocation,
    dice_pool,
    skill_point_budget,
    skill_rating,
)

METATYPES = load_metatypes()
PRIORITIES = load_priorities()
SKILLS = load_skills()

SKILLS_BY_NAME = {s.name: s for s in SKILLS}
# Automatics/Longarms/Pistols all belong to the "Firearms" skill group (skills.xml).
AUTOMATICS = SKILLS_BY_NAME["Automatics"]
LONGARMS = SKILLS_BY_NAME["Longarms"]
PISTOLS = SKILLS_BY_NAME["Pistols"]
# No skill group, AGI-linked, can_default = True.
ARCHERY = SKILLS_BY_NAME["Archery"]
# No skill group, MAG-linked, can_default = False -- cannot be used untrained.
SPELLCASTING = SKILLS_BY_NAME["Spellcasting"]


def _human_with_agi(points: int) -> Character:
    heritage = PRIORITIES.heritage["D"]
    human = next(c for c in metatype_choices(heritage, METATYPES) if c.metatype.name == "Human")
    return create_character(
        metatype_choice=human,
        heritage_letter="D",
        attributes_letter="A",
        priorities=PRIORITIES,
        attribute_points={"AGI": points},
    )


def test_skill_point_budget_hand_checked() -> None:
    # priorities.xml Skills letter C: "C - 28 Skills/2 Skill Groups".
    budget = skill_point_budget("C", PRIORITIES)
    assert (budget.skills, budget.skill_groups) == (28, 2)


def test_create_skill_allocation_within_budget() -> None:
    allocation = create_skill_allocation(
        letter="C",
        priorities=PRIORITIES,
        skills=SKILLS,
        skill_points={ARCHERY.id: 4},
        group_points={"Firearms": 2},
    )
    assert isinstance(allocation, SkillAllocation)
    assert allocation.skill_points[ARCHERY.id] == 4
    assert allocation.group_points["Firearms"] == 2


def test_create_skill_allocation_allows_partial_spend() -> None:
    allocation = create_skill_allocation(
        letter="C", priorities=PRIORITIES, skills=SKILLS, skill_points={}, group_points={}
    )
    assert dict(allocation.skill_points) == {}
    assert dict(allocation.group_points) == {}


def test_create_skill_allocation_rejects_skill_budget_overspend() -> None:
    with pytest.raises(ValueError, match="skill point spend"):
        create_skill_allocation(
            letter="E",  # 18 skill points
            priorities=PRIORITIES,
            skills=SKILLS,
            skill_points={
                ARCHERY.id: 6,
                SPELLCASTING.id: 6,
                SKILLS_BY_NAME["Demolitions"].id: 6,
                LONGARMS.id: 1,
            },
            group_points={},
        )


def test_create_skill_allocation_rejects_group_budget_overspend() -> None:
    with pytest.raises(ValueError, match="skill group point spend"):
        create_skill_allocation(
            letter="D",  # 0 skill group points
            priorities=PRIORITIES,
            skills=SKILLS,
            skill_points={},
            group_points={"Firearms": 1},
        )


def test_create_skill_allocation_rejects_rating_above_chargen_max() -> None:
    with pytest.raises(ValueError, match="exceeds the chargen skill rating maximum"):
        create_skill_allocation(
            letter="A",
            priorities=PRIORITIES,
            skills=SKILLS,
            skill_points={ARCHERY.id: MAX_SKILL_RATING_CREATE + 1},
            group_points={},
        )


def test_create_skill_allocation_rejects_negative_spend() -> None:
    with pytest.raises(ValueError, match="must not be negative"):
        create_skill_allocation(
            letter="A",
            priorities=PRIORITIES,
            skills=SKILLS,
            skill_points={ARCHERY.id: -1},
            group_points={},
        )


def test_create_skill_allocation_rejects_unknown_skill_id() -> None:
    with pytest.raises(ValueError, match="not a known skill id"):
        create_skill_allocation(
            letter="A",
            priorities=PRIORITIES,
            skills=SKILLS,
            skill_points={"not-a-real-skill-id": 1},
            group_points={},
        )


def test_create_skill_allocation_rejects_unknown_group() -> None:
    with pytest.raises(ValueError, match="not a known skill group"):
        create_skill_allocation(
            letter="A",
            priorities=PRIORITIES,
            skills=SKILLS,
            skill_points={},
            group_points={"Not A Real Group": 1},
        )


def test_create_skill_allocation_rejects_individual_points_while_group_bought() -> None:
    # Strict skill groups (legacy default): once Firearms has group points, Automatics can't also
    # carry its own base points -- confirmed against Yeti-#ffffff2.chum5 in
    # tests/integration/test_character_fixtures.py.
    with pytest.raises(ValueError, match="strict skill groups"):
        create_skill_allocation(
            letter="A",
            priorities=PRIORITIES,
            skills=SKILLS,
            skill_points={AUTOMATICS.id: 1},
            group_points={"Firearms": 2},
        )


def test_skill_rating_uses_group_rating_when_group_has_points() -> None:
    character = _human_with_agi(0)
    allocation = create_skill_allocation(
        letter="A",
        priorities=PRIORITIES,
        skills=SKILLS,
        skill_points={},
        group_points={"Firearms": 3},
    )
    assert skill_rating(character, allocation, AUTOMATICS) == 3
    assert skill_rating(character, allocation, LONGARMS) == 3


def test_skill_rating_uses_own_points_when_group_unbought() -> None:
    character = _human_with_agi(0)
    allocation = create_skill_allocation(
        letter="A",
        priorities=PRIORITIES,
        skills=SKILLS,
        skill_points={AUTOMATICS.id: 4},
        group_points={},
    )
    assert skill_rating(character, allocation, AUTOMATICS) == 4
    assert skill_rating(character, allocation, LONGARMS) == 0


def test_skill_rating_sums_improvements_and_caps_at_chargen_max() -> None:
    character = _human_with_agi(0)
    allocation = create_skill_allocation(
        letter="A",
        priorities=PRIORITIES,
        skills=SKILLS,
        skill_points={ARCHERY.id: MAX_SKILL_RATING_CREATE},
        group_points={},
    )
    character.improvements.add(
        Improvement(
            improvement_type=ImprovementType.SKILL,
            target=ARCHERY.name,
            value=2,
            source_type=ImprovementSource.QUALITY,
            source_id="quality-test",
        )
    )
    assert skill_rating(character, allocation, ARCHERY) == MAX_SKILL_RATING_CREATE


def test_dice_pool_is_rating_plus_attribute() -> None:
    character = _human_with_agi(3)
    allocation = create_skill_allocation(
        letter="A",
        priorities=PRIORITIES,
        skills=SKILLS,
        skill_points={ARCHERY.id: 4},
        group_points={},
    )
    expected = 4 + character.attribute_value("AGI")
    assert dice_pool(character, allocation, ARCHERY) == expected


def test_dice_pool_specialization_adds_bonus_only_at_positive_rating() -> None:
    character = _human_with_agi(3)
    allocation = create_skill_allocation(
        letter="A",
        priorities=PRIORITIES,
        skills=SKILLS,
        skill_points={ARCHERY.id: 4},
        group_points={},
    )
    unspecialized = dice_pool(character, allocation, ARCHERY, specialized=False)
    specialized = dice_pool(character, allocation, ARCHERY, specialized=True)
    assert specialized == unspecialized + SPECIALIZATION_BONUS


def test_dice_pool_specialization_ignored_for_exotic_skills() -> None:
    character = _human_with_agi(0)
    exotic = SKILLS_BY_NAME["Exotic Melee Weapon"]
    allocation = create_skill_allocation(
        letter="A",
        priorities=PRIORITIES,
        skills=SKILLS,
        skill_points={exotic.id: 3},
        group_points={},
    )
    unspecialized = dice_pool(character, allocation, exotic, specialized=False)
    specialized = dice_pool(character, allocation, exotic, specialized=True)
    assert specialized == unspecialized


def test_dice_pool_applies_default_modifier_at_zero_rating_when_allowed() -> None:
    character = _human_with_agi(2)
    allocation = create_skill_allocation(
        letter="A", priorities=PRIORITIES, skills=SKILLS, skill_points={}, group_points={}
    )
    assert ARCHERY.can_default
    assert dice_pool(character, allocation, ARCHERY) == max(
        0, character.attribute_value("AGI") + DEFAULT_MODIFIER
    )


def test_dice_pool_is_zero_at_zero_rating_when_defaulting_not_allowed() -> None:
    character = _human_with_agi(0)
    allocation = create_skill_allocation(
        letter="A", priorities=PRIORITIES, skills=SKILLS, skill_points={}, group_points={}
    )
    assert not SPELLCASTING.can_default
    assert dice_pool(character, allocation, SPELLCASTING) == 0


# WP50: specializations.


def test_create_skill_allocation_accepts_specialization_on_individually_purchased_skill() -> None:
    allocation = create_skill_allocation(
        letter="A",
        priorities=PRIORITIES,
        skills=SKILLS,
        skill_points={ARCHERY.id: 4},
        group_points={},
        specializations={ARCHERY.id: "Longbow"},
    )
    assert allocation.specializations[ARCHERY.id] == "Longbow"


def test_create_skill_allocation_specialization_costs_a_skill_point() -> None:
    # Letter E: 18 skill points. Archery(6) + Spellcasting(6) + Demolitions(6) = 18, exactly the
    # budget, with no room left for a specialization's extra point.
    demolitions = SKILLS_BY_NAME["Demolitions"]
    assert skill_point_budget("E", PRIORITIES).skills == 18
    with pytest.raises(ValueError, match="skill point spend"):
        create_skill_allocation(
            letter="E",
            priorities=PRIORITIES,
            skills=SKILLS,
            skill_points={ARCHERY.id: 6, SPELLCASTING.id: 6, demolitions.id: 6},
            group_points={},
            specializations={ARCHERY.id: "Longbow"},
        )
    # Dropping Archery's rating by 1 (to 5) frees exactly the 1 point the specialization costs.
    allocation = create_skill_allocation(
        letter="E",
        priorities=PRIORITIES,
        skills=SKILLS,
        skill_points={ARCHERY.id: 5, SPELLCASTING.id: 6, demolitions.id: 6},
        group_points={},
        specializations={ARCHERY.id: "Longbow"},
    )
    assert allocation.specializations[ARCHERY.id] == "Longbow"


def test_create_skill_allocation_rejects_specialization_on_unbought_skill() -> None:
    with pytest.raises(ValueError, match="cannot add a specialization"):
        create_skill_allocation(
            letter="A",
            priorities=PRIORITIES,
            skills=SKILLS,
            skill_points={},
            group_points={},
            specializations={ARCHERY.id: "Longbow"},
        )


def test_create_skill_allocation_rejects_specialization_on_group_purchased_skill() -> None:
    # Automatics' rating comes from the Firearms group, not its own skill_points -- Step Five
    # forbids specializing it (rulebook p.88: breaking a group like this "cannot happen in Step
    # Five... only in Step Seven").
    with pytest.raises(ValueError, match="cannot add a specialization"):
        create_skill_allocation(
            letter="A",
            priorities=PRIORITIES,
            skills=SKILLS,
            skill_points={},
            group_points={"Firearms": 2},
            specializations={AUTOMATICS.id: "Assault Rifles"},
        )


def test_create_skill_allocation_rejects_blank_specialization_name() -> None:
    with pytest.raises(ValueError, match="must not be blank"):
        create_skill_allocation(
            letter="A",
            priorities=PRIORITIES,
            skills=SKILLS,
            skill_points={ARCHERY.id: 4},
            group_points={},
            specializations={ARCHERY.id: "   "},
        )


def test_create_skill_allocation_rejects_specialization_on_unknown_skill_id() -> None:
    with pytest.raises(ValueError, match="not a known skill id"):
        create_skill_allocation(
            letter="A",
            priorities=PRIORITIES,
            skills=SKILLS,
            skill_points={},
            group_points={},
            specializations={"not-a-real-skill-id": "Whatever"},
        )


def test_dice_pool_defaults_specialized_from_the_allocation() -> None:
    character = _human_with_agi(3)
    allocation = create_skill_allocation(
        letter="A",
        priorities=PRIORITIES,
        skills=SKILLS,
        skill_points={ARCHERY.id: 4},
        group_points={},
        specializations={ARCHERY.id: "Longbow"},
    )
    unspecialized = create_skill_allocation(
        letter="A",
        priorities=PRIORITIES,
        skills=SKILLS,
        skill_points={ARCHERY.id: 4},
        group_points={},
    )
    assert (
        dice_pool(character, allocation, ARCHERY)
        == dice_pool(character, unspecialized, ARCHERY) + SPECIALIZATION_BONUS
    )
    # An explicit override still wins over the allocation's own state.
    assert dice_pool(character, allocation, ARCHERY, specialized=False) == dice_pool(
        character, unspecialized, ARCHERY
    )


# WP53: Karma-funded skill/skill-group increases and specializations, including group-breaking.


def _character_with_skill_allocation(allocation: SkillAllocation) -> Character:
    return replace(_human_with_agi(0), skill_allocation=allocation)


def test_karma_skill_points_raises_individual_skill_rating() -> None:
    allocation = create_skill_allocation(
        letter="A",
        priorities=PRIORITIES,
        skills=SKILLS,
        skill_points={ARCHERY.id: 2},
        group_points={},
    )
    character = _character_with_skill_allocation(allocation)
    selection = create_karma_skill_selection(
        character, SKILLS, karma_skill_points={ARCHERY.id: 2}, karma_budget=100
    )
    # KARMA ADVANCEMENT TABLE FOR SKILLS, Active Skill row: 2->3 costs 6, 3->4 costs 8 -- 14 total.
    assert selection.karma_cost == 14
    assert selection.skill_points[ARCHERY.id] == 2
    character = replace(character, karma_skill_selection=selection)
    assert skill_rating(character, allocation, ARCHERY) == 4


def test_karma_skill_points_from_zero_matches_hand_checked_table_cell() -> None:
    character = _character_with_skill_allocation(
        create_skill_allocation(
            letter="A", priorities=PRIORITIES, skills=SKILLS, skill_points={}, group_points={}
        )
    )
    # Buying a brand-new skill up to rating 3 costs 12 (2+4+6), the table's own worked example
    # (core rulebook p.105's Running-skill example) for a from-scratch Active skill purchase.
    selection = create_karma_skill_selection(
        character, SKILLS, karma_skill_points={ARCHERY.id: 3}, karma_budget=100
    )
    assert selection.karma_cost == 12


def test_karma_group_points_raises_group_rating() -> None:
    allocation = create_skill_allocation(
        letter="A",
        priorities=PRIORITIES,
        skills=SKILLS,
        skill_points={},
        group_points={"Firearms": 1},
    )
    character = _character_with_skill_allocation(allocation)
    selection = create_karma_skill_selection(
        character, SKILLS, karma_group_points={"Firearms": 1}, karma_budget=100
    )
    # Active Skill Group row: 1->2 costs new_rating x 5 = 10.
    assert selection.karma_cost == 10
    character = replace(character, karma_skill_selection=selection)
    assert skill_rating(character, allocation, AUTOMATICS) == 2
    assert skill_rating(character, allocation, LONGARMS) == 2


def test_karma_specialization_costs_flat_seven_karma() -> None:
    allocation = create_skill_allocation(
        letter="A",
        priorities=PRIORITIES,
        skills=SKILLS,
        skill_points={ARCHERY.id: 2},
        group_points={},
    )
    character = _character_with_skill_allocation(allocation)
    selection = create_karma_skill_selection(
        character, SKILLS, karma_specializations={ARCHERY.id: "Longbow"}, karma_budget=100
    )
    assert selection.karma_cost == KARMA_SPECIALIZATION_COST == 7


def test_karma_specialization_on_group_member_breaks_the_group() -> None:
    # Before: Firearms bought as a group at rating 3 -- every member shares that rating.
    allocation = create_skill_allocation(
        letter="A",
        priorities=PRIORITIES,
        skills=SKILLS,
        skill_points={},
        group_points={"Firearms": 3},
    )
    character = _character_with_skill_allocation(allocation)
    assert skill_rating(character, allocation, AUTOMATICS) == 3
    assert skill_rating(character, allocation, LONGARMS) == 3
    assert skill_rating(character, allocation, PISTOLS) == 3

    selection = create_karma_skill_selection(
        character,
        SKILLS,
        karma_specializations={AUTOMATICS.id: "Assault Rifles"},
        karma_budget=100,
    )
    assert selection.broken_groups == frozenset({"Firearms"})
    assert selection.karma_cost == KARMA_SPECIALIZATION_COST

    character = replace(character, karma_skill_selection=selection)
    # After: the specialized member is now individually tracked (still rating 3, frozen at the
    # group's own rating), and its siblings are unaffected, still group-rated at 3.
    assert skill_rating(character, allocation, AUTOMATICS) == 3
    assert skill_rating(character, allocation, LONGARMS) == 3
    assert skill_rating(character, allocation, PISTOLS) == 3
    assert dice_pool(character, allocation, AUTOMATICS) == dice_pool(
        character, allocation, LONGARMS
    ) + SPECIALIZATION_BONUS


def test_karma_skill_points_on_group_member_breaks_the_group_without_a_specialization() -> None:
    # The rulebook's group-breaking rule (p.87-88) has two independent triggers -- this is the
    # other one: raising a member's rating directly with Karma, no specialization involved.
    allocation = create_skill_allocation(
        letter="A",
        priorities=PRIORITIES,
        skills=SKILLS,
        skill_points={},
        group_points={"Firearms": 3},
    )
    character = _character_with_skill_allocation(allocation)
    selection = create_karma_skill_selection(
        character, SKILLS, karma_skill_points={AUTOMATICS.id: 1}, karma_budget=100
    )
    assert selection.broken_groups == frozenset({"Firearms"})
    # 3->4 costs new_rating x 2 = 8.
    assert selection.karma_cost == 8

    character = replace(character, karma_skill_selection=selection)
    assert skill_rating(character, allocation, AUTOMATICS) == 4
    assert skill_rating(character, allocation, LONGARMS) == 3  # unaffected by the break


def test_karma_group_points_conflicts_with_breaking_the_same_group() -> None:
    allocation = create_skill_allocation(
        letter="A",
        priorities=PRIORITIES,
        skills=SKILLS,
        skill_points={},
        group_points={"Firearms": 3},
    )
    character = _character_with_skill_allocation(allocation)
    with pytest.raises(ValueError, match="cannot Karma-fund skill group"):
        create_karma_skill_selection(
            character,
            SKILLS,
            karma_group_points={"Firearms": 1},
            karma_specializations={AUTOMATICS.id: "Assault Rifles"},
            karma_budget=100,
        )


def test_karma_group_points_rejects_a_fresh_group_conflicting_with_individual_spend() -> None:
    allocation = create_skill_allocation(
        letter="A",
        priorities=PRIORITIES,
        skills=SKILLS,
        skill_points={AUTOMATICS.id: 2},
        group_points={},
    )
    character = _character_with_skill_allocation(allocation)
    with pytest.raises(ValueError, match="strict skill groups"):
        create_karma_skill_selection(
            character, SKILLS, karma_group_points={"Firearms": 1}, karma_budget=100
        )


def test_karma_skill_points_rejects_unknown_skill_id() -> None:
    character = _human_with_agi(0)
    with pytest.raises(ValueError, match="not a known skill id"):
        create_karma_skill_selection(
            character, SKILLS, karma_skill_points={"not-a-real-skill-id": 1}, karma_budget=100
        )


def test_karma_group_points_rejects_unknown_group() -> None:
    character = _human_with_agi(0)
    with pytest.raises(ValueError, match="not a known skill group"):
        create_karma_skill_selection(
            character, SKILLS, karma_group_points={"Not A Group": 1}, karma_budget=100
        )


def test_karma_specialization_rejects_already_specialized_skill() -> None:
    allocation = create_skill_allocation(
        letter="A",
        priorities=PRIORITIES,
        skills=SKILLS,
        skill_points={ARCHERY.id: 2},
        group_points={},
        specializations={ARCHERY.id: "Longbow"},
    )
    character = _character_with_skill_allocation(allocation)
    with pytest.raises(ValueError, match="already has a specialization"):
        create_karma_skill_selection(
            character, SKILLS, karma_specializations={ARCHERY.id: "Crossbow"}, karma_budget=100
        )


def test_karma_specialization_rejects_unbought_skill() -> None:
    character = _human_with_agi(0)
    with pytest.raises(ValueError, match="at least 1 point"):
        create_karma_skill_selection(
            character, SKILLS, karma_specializations={ARCHERY.id: "Longbow"}, karma_budget=100
        )


def test_karma_specialization_allows_a_skill_karma_funded_in_the_same_submission() -> None:
    character = _human_with_agi(0)
    selection = create_karma_skill_selection(
        character,
        SKILLS,
        karma_skill_points={ARCHERY.id: 1},
        karma_specializations={ARCHERY.id: "Longbow"},
        karma_budget=100,
    )
    # 0->1 costs 2, specialization costs 7 flat.
    assert selection.karma_cost == 2 + KARMA_SPECIALIZATION_COST


def test_karma_skill_points_rejects_negative_spend() -> None:
    character = _human_with_agi(0)
    with pytest.raises(ValueError, match="must not be negative"):
        create_karma_skill_selection(
            character, SKILLS, karma_skill_points={ARCHERY.id: -1}, karma_budget=100
        )


def test_karma_skill_points_rejects_rating_above_chargen_max() -> None:
    allocation = create_skill_allocation(
        letter="A",
        priorities=PRIORITIES,
        skills=SKILLS,
        skill_points={ARCHERY.id: MAX_SKILL_RATING_CREATE},
        group_points={},
    )
    character = _character_with_skill_allocation(allocation)
    with pytest.raises(ValueError, match="exceeds the chargen skill rating maximum"):
        create_karma_skill_selection(
            character, SKILLS, karma_skill_points={ARCHERY.id: 1}, karma_budget=100
        )


def test_karma_skill_selection_rejects_over_budget_spend() -> None:
    character = _human_with_agi(0)
    with pytest.raises(ValueError, match="exceeds the Karma budget"):
        create_karma_skill_selection(
            character, SKILLS, karma_skill_points={ARCHERY.id: 1}, karma_budget=1
        )


def test_dice_pool_specialized_auto_detects_karma_funded_specialization() -> None:
    allocation = create_skill_allocation(
        letter="A",
        priorities=PRIORITIES,
        skills=SKILLS,
        skill_points={ARCHERY.id: 4},
        group_points={},
    )
    character = _character_with_skill_allocation(allocation)
    selection = create_karma_skill_selection(
        character, SKILLS, karma_specializations={ARCHERY.id: "Longbow"}, karma_budget=100
    )
    character = replace(character, karma_skill_selection=selection)
    unspecialized = dice_pool(character, allocation, ARCHERY, specialized=False)
    assert dice_pool(character, allocation, ARCHERY) == unspecialized + SPECIALIZATION_BONUS
