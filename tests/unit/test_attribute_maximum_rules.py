"""WP112: one attribute at its natural maximum; Exceptional Attribute and Lucky."""

from __future__ import annotations

from dataclasses import replace

import pytest

from chummer5.data.lifestyle import load_lifestyles
from chummer5.data.metatypes import load_metatypes
from chummer5.data.priorities import load_priorities
from chummer5.data.qualities import load_qualities
from chummer5.data.skills import load_skills
from chummer5.engine.character import (
    Character,
    create_character,
    create_karma_attribute_points,
    metatype_choices,
)
from chummer5.engine.derived import physical_limit
from chummer5.engine.qualities import (
    QualityPickRequest,
    apply_quality_improvements,
    create_quality_selection,
)
from chummer5.io.save_format import CharacterSave, build_character, create_character_save

METATYPES = load_metatypes()
PRIORITIES = load_priorities()
QUALITIES = load_qualities()
SKILLS = load_skills()
LIFESTYLES = load_lifestyles()
BY_NAME = {q.name: q for q in QUALITIES}
EXCEPTIONAL = BY_NAME["Exceptional Attribute"]
LUCKY = BY_NAME["Lucky"]


def _choice(metatype: str, heritage: str = "A"):  # noqa: ANN202 - a MetatypeChoice
    return next(
        c
        for c in metatype_choices(PRIORITIES.heritage[heritage], METATYPES)
        if c.metatype.name == metatype
    )


def _rob_save() -> CharacterSave:
    """The rulebook's Rob (Step Two): a Heritage B troll, Attributes A, spending up to STR 11."""
    return create_character_save(
        metatype_name="Troll",
        heritage_letter="B",
        attributes_letter="A",
        attribute_points={
            "BOD": 4,
            "AGI": 3,
            "REA": 2,
            "STR": 6,
            "CHA": 2,
            "INT": 2,
            "LOG": 2,
            "WIL": 3,
        },
        skills_letter="C",
        skill_points={},
        group_points={},
        quality_picks=(
            QualityPickRequest(BY_NAME["SINner (National)"].id, text="UCAS"),
            QualityPickRequest(EXCEPTIONAL.id, choice="STR"),
        ),
        contacts=(),
        resources_letter="D",
        gear_names=(),
        lifestyle_tier_name="Low",
        lifestyle_months=1,
    )


def _build(save: CharacterSave) -> Character:
    return build_character(
        save,
        metatypes=METATYPES,
        priorities=PRIORITIES,
        skills=SKILLS,
        qualities=QUALITIES,
        lifestyles=LIFESTYLES,
    )


def test_robs_troll_with_strength_11_builds() -> None:
    rob = _build(_rob_save())
    assert rob.attribute_value("STR") == 11
    assert rob.attribute_maximum("STR") == 11
    assert rob.attribute_augmented_maximum("STR") == 15
    # Rob's Final Calculations: Physical limit 12 = ceil((11 x 2 + 9 + 3) / 3).
    assert physical_limit(rob) == 12
    assert rob.quality_selection is not None
    assert rob.quality_selection.positive_karma == 14


def test_robs_strength_11_is_rejected_without_the_quality() -> None:
    save = replace(
        _rob_save(),
        quality_picks=(QualityPickRequest(BY_NAME["SINner (National)"].id, text="UCAS"),),
    )
    with pytest.raises(ValueError, match="STR: 11 exceeds Troll's maximum of 10"):
        _build(save)


def test_one_priority_submission_may_not_put_two_attributes_at_maximum() -> None:
    with pytest.raises(ValueError, match="only one Mental or Physical attribute"):
        create_character(
            _choice("Human"),
            "A",
            "A",
            PRIORITIES,
            {"BOD": 5, "AGI": 5},
            previous_attribute_points={},
        )


def test_raising_a_second_attribute_to_maximum_later_is_rejected_too() -> None:
    with pytest.raises(ValueError, match="raising AGI would put 2 there"):
        create_character(
            _choice("Human"),
            "A",
            "A",
            PRIORITIES,
            {"BOD": 5, "AGI": 5},
            previous_attribute_points={"BOD": 5, "AGI": 4},
        )


def test_an_existing_breach_does_not_block_an_unrelated_edit() -> None:
    """WP52's scoping: two attributes already at maximum (a legacy import) may still be edited
    elsewhere -- WP135 reports the breach instead."""
    create_character(
        _choice("Human"),
        "A",
        "A",
        PRIORITIES,
        {"BOD": 5, "AGI": 5, "LOG": 2},
        previous_attribute_points={"BOD": 5, "AGI": 5, "LOG": 1},
    )


def test_without_previous_points_the_rule_is_not_checked() -> None:
    """A fresh build (save load, legacy import) is not a player's submission."""
    create_character(_choice("Human"), "A", "A", PRIORITIES, {"BOD": 5, "AGI": 5})


def test_the_rule_reads_the_raised_maximum() -> None:
    """The closing checklist: "or one higher with Exceptional Attribute". STR 6 on a Human with
    Exceptional Attribute (STR) is not at *its* maximum (7), so BOD may sit at 6 alongside it."""
    create_character(
        _choice("Human"),
        "A",
        "A",
        PRIORITIES,
        {"BOD": 5, "STR": 5},
        maximum_bonus={"STR": 1},
        previous_attribute_points={},
    )
    with pytest.raises(ValueError, match="only one"):
        create_character(
            _choice("Human"),
            "A",
            "A",
            PRIORITIES,
            {"BOD": 5, "STR": 6},
            maximum_bonus={"STR": 1},
            previous_attribute_points={},
        )


def test_karma_points_count_towards_the_natural_rating() -> None:
    with pytest.raises(ValueError, match="only one"):
        create_character(
            _choice("Human"),
            "A",
            "A",
            PRIORITIES,
            {"BOD": 5, "AGI": 4},
            previous_attribute_points={"BOD": 5},
            karma_points={"AGI": 1},
        )


def test_lucky_raises_edges_maximum_and_lowers_notoriety() -> None:
    character = create_character(_choice("Human"), "A", "A", PRIORITIES, {})
    selection = create_quality_selection([LUCKY.id], QUALITIES)
    apply_quality_improvements(character, selection.qualities)
    assert character.attribute_maximum("EDG") == character.attribute_range("EDG").maximum + 1


def test_exceptional_attribute_needs_a_valid_choice() -> None:
    with pytest.raises(ValueError, match="needs one of"):
        create_quality_selection([EXCEPTIONAL.id], QUALITIES)
    with pytest.raises(ValueError, match="got 'EDG'"):
        create_quality_selection([QualityPickRequest(EXCEPTIONAL.id, choice="EDG")], QUALITIES)
    with pytest.raises(ValueError, match="got 'MAG'"):
        create_quality_selection([QualityPickRequest(EXCEPTIONAL.id, choice="MAG")], QUALITIES)
    create_quality_selection(
        [QualityPickRequest(EXCEPTIONAL.id, choice="MAG")], QUALITIES, magic_type="Adept"
    )


def test_exceptional_attribute_and_lucky_are_mutually_exclusive() -> None:
    with pytest.raises(ValueError, match="cannot be taken together"):
        create_quality_selection(
            [QualityPickRequest(EXCEPTIONAL.id, choice="STR"), LUCKY.id], QUALITIES
        )


def test_karma_spend_respects_the_raised_maximum() -> None:
    character = create_character(_choice("Human"), "A", "A", PRIORITIES, {"STR": 5})
    selection = create_quality_selection(
        [QualityPickRequest(EXCEPTIONAL.id, choice="STR")], QUALITIES
    )
    apply_quality_improvements(character, selection.qualities)
    karma = create_karma_attribute_points(character, {"STR": 1}, karma_budget=50)
    assert karma.karma_cost == 35  # new rating 7 x 5
    with pytest.raises(ValueError, match="exceeds Human's maximum of 7"):
        create_karma_attribute_points(character, {"STR": 2}, karma_budget=100)
