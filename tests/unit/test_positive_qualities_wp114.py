"""WP114: the remaining core positive qualities."""

from __future__ import annotations

from dataclasses import replace

import pytest

from chummer5.data.metatypes import load_metatypes
from chummer5.data.priorities import load_priorities
from chummer5.data.qualities import load_qualities
from chummer5.engine.character import Character, create_character, metatype_choices
from chummer5.engine.derived import damage_resistance, memory, overflow, wound_modifier_rule
from chummer5.engine.qualities import (
    HOME_GROUND_CHOICES,
    MATRIX_ACTION_CHOICES,
    SPIRIT_TYPE_CHOICES,
    QualityPickRequest,
    apply_quality_improvements,
    create_quality_selection,
    mvp_quality_catalog,
    offerable_quality_catalog,
    resolve_metatype_qualities,
)

QUALITIES = load_qualities()
BY_NAME = {q.name: q for q in QUALITIES}
METATYPES = load_metatypes()
PRIORITIES = load_priorities()


def _character(metatype: str = "Human") -> Character:
    choice = next(
        c
        for c in metatype_choices(PRIORITIES.heritage["A"], METATYPES)
        if c.metatype.name == metatype
    )
    character = create_character(choice, "A", "A", PRIORITIES, {"BOD": 2, "LOG": 2, "WIL": 1})
    return replace(
        character, metatype_qualities=resolve_metatype_qualities(choice.metatype, QUALITIES)
    )


def _apply(character: Character, *picks: str | QualityPickRequest) -> None:
    selection = create_quality_selection(
        list(picks), QUALITIES, metatype_name=character.metatype.name
    )
    apply_quality_improvements(character, selection.qualities)


def test_toughness_adds_a_damage_resistance_die() -> None:
    character = _character()
    before = damage_resistance(character)
    _apply(character, BY_NAME["Toughness"].id)
    assert damage_resistance(character) == before + 1


def test_high_pain_tolerance_ignores_one_box_per_rating() -> None:
    character = _character()
    _apply(character, QualityPickRequest(BY_NAME["High Pain Tolerance"].id, rating=3))
    assert wound_modifier_rule(character).physical_boxes_ignored == 3


def test_will_to_live_adds_overflow_per_rating() -> None:
    """Rob's Final Calculations: "Overflow 9 (10, modified by Will to Live)"."""
    character = _character()
    before = overflow(character)
    _apply(character, QualityPickRequest(BY_NAME["Will to Live"].id, rating=2))
    assert overflow(character) == before + 2


def test_photographic_memory_adds_two_to_memory() -> None:
    character = _character()
    assert memory(character) == 3 + 2  # LOG 3 + WIL 2
    _apply(character, BY_NAME["Photographic Memory"].id)
    assert memory(character) == 7


def test_the_three_choice_qualities_validate_their_choice() -> None:
    assert "Hack on the Fly" in MATRIX_ACTION_CHOICES
    assert "Spirit of Fire" in SPIRIT_TYPE_CHOICES and len(SPIRIT_TYPE_CHOICES) == 6
    create_quality_selection(
        [QualityPickRequest(BY_NAME["Codeslinger"].id, choice="Hack on the Fly")], QUALITIES
    )
    with pytest.raises(ValueError, match="needs one of"):
        create_quality_selection(
            [QualityPickRequest(BY_NAME["Codeslinger"].id, choice="Fly")], QUALITIES
        )
    with pytest.raises(ValueError, match="needs one of"):
        create_quality_selection([BY_NAME["Spirit Affinity"].id], QUALITIES, magic_type="Magician")


def test_home_ground_repeats_with_a_different_bonus_each_time() -> None:
    home = BY_NAME["Home Ground"].id
    a, b = HOME_GROUND_CHOICES[:2]
    selection = create_quality_selection(
        [QualityPickRequest(home, choice=a), QualityPickRequest(home, choice=b)], QUALITIES
    )
    assert selection.positive_karma == 20
    with pytest.raises(ValueError, match="same quality instance"):
        create_quality_selection(
            [QualityPickRequest(home, choice=a), QualityPickRequest(home, choice=a)], QUALITIES
        )


def test_the_dwarfs_racial_resistance_is_not_for_sale_and_blocks_the_purchasable_rows() -> None:
    offered = {q.name for q in mvp_quality_catalog(QUALITIES)}
    assert "Resistance to Pathogens/Toxins" not in offered
    assert "Resistance to Toxins" in offered
    dwarf_offered = {q.name for q in offerable_quality_catalog(_character("Dwarf"), QUALITIES)}
    assert not dwarf_offered & {
        "Resistance to Pathogens",
        "Resistance to Toxins",
        "Resistance to Pathogens and Toxins",
    }
    human_offered = {q.name for q in offerable_quality_catalog(_character(), QUALITIES)}
    assert "Resistance to Toxins" in human_offered


def test_every_newly_offered_registry_row_has_a_note() -> None:
    computed = {"Toughness", "High Pain Tolerance", "Will to Live", "Photographic Memory"}
    registry = {
        "Ambidextrous",
        "Analytical Mind",
        "Astral Chameleon",
        "Blandness",
        "Codeslinger",
        "First Impression",
        "Focused Concentration",
        "Home Ground",
        "Human-Looking",
        "Magic Resistance",
        "Quick Healer",
        "Resistance to Pathogens",
        "Resistance to Toxins",
        "Resistance to Pathogens and Toxins",
        "Spirit Affinity",
    }
    for name in registry:
        assert BY_NAME[name].unmodeled_effect_note, name
    for name in computed:
        assert BY_NAME[name].unmodeled_effect_note is None, name
