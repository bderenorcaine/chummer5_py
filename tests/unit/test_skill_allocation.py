"""Tests for `chummer5.engine.skills` (WP7) -- not to be confused with `test_skills.py`, which
covers the WP3 data loader (`chummer5.data.skills`) this module builds on.
"""

import pytest

from chummer5.data.metatypes import load_metatypes
from chummer5.data.priorities import load_priorities
from chummer5.data.skills import load_skills
from chummer5.engine.character import Character, create_character, metatype_choices
from chummer5.engine.improvements import Improvement, ImprovementSource, ImprovementType
from chummer5.engine.skills import (
    DEFAULT_MODIFIER,
    MAX_SKILL_RATING_CREATE,
    SPECIALIZATION_BONUS,
    SkillAllocation,
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
