"""WP120: the remaining core adept powers, offered as registry rows."""

from __future__ import annotations

from dataclasses import replace

import pytest

from chummer5.data.metatypes import load_metatypes
from chummer5.data.powers import BonusSupport, load_powers
from chummer5.data.priorities import load_priorities
from chummer5.engine.character import create_character, metatype_choices
from chummer5.engine.magic import (
    OUT_OF_SCOPE_POWER_NAMES,
    apply_power_improvements,
    create_power_selection,
    mvp_power_catalog,
)

POWERS = load_powers()
POWER = {p.name: p for p in POWERS}


def test_every_core_power_but_chaos_mentor_is_offered() -> None:
    """The plan's acceptance: all 27 core powers (28 minus Chaos Mentor) are offerable."""
    offered = {p.name for p in mvp_power_catalog(POWERS)}
    assert len(POWERS) == 28
    assert offered == {p.name for p in POWERS} - OUT_OF_SCOPE_POWER_NAMES
    assert OUT_OF_SCOPE_POWER_NAMES == {"Improved Potential (Chaos Mentor)"}


def test_every_power_with_an_in_play_part_has_a_note() -> None:
    """Every NO_EFFECT power carries a note. Of the computed ones, a note is present exactly when
    something printed stays unmodeled."""
    for power in mvp_power_catalog(POWERS):
        if power.bonus_support is BonusSupport.NO_EFFECT:
            assert power.unmodeled_effect_note, power.name
    fully_computed = {
        "Enhanced Perception",
        "Improved Ability (skill)",
        "Improved Physical Attribute",
        "Improved Potential (Social)",
        "Improved Potential (Mental)",
        "Improved Potential (Physical)",
        "Improved Reflexes",
        "Voice Control",
    }
    for name in fully_computed:
        assert POWER[name].unmodeled_effect_note is None, name


def test_attribute_boost_takes_an_attribute_and_raises_nothing() -> None:
    choice = next(
        c
        for c in metatype_choices(load_priorities().heritage["A"], load_metatypes())
        if c.metatype.name == "Human"
    )
    character = replace(
        create_character(choice, "A", "A", load_priorities(), {}), magic_type="Adept"
    )
    before = character.attribute_value("AGI")
    selection = create_power_selection(
        [(POWER["Attribute Boost"].id, 2, "AGI"), (POWER["Attribute Boost"].id, 1, "STR")],
        POWERS,
        6,
    )
    apply_power_improvements(character, selection)
    assert character.attribute_value("AGI") == before
    with pytest.raises(ValueError, match="needs one of"):
        create_power_selection([(POWER["Attribute Boost"].id, 1, "LOG")], POWERS, 6)


def test_improved_sense_takes_a_distinct_free_text_sense_each_time() -> None:
    sense = POWER["Improved Sense"].id
    selection = create_power_selection(
        [(sense, 1, "Low-light vision"), (sense, 1, "Direction Sense")], POWERS, 6
    )
    assert [p.target for p in selection.picks] == ["Low-light vision", "Direction Sense"]
    with pytest.raises(ValueError, match="requires a detail"):
        create_power_selection([(sense, 1, None)], POWERS, 6)
    with pytest.raises(ValueError, match="twice for one target"):
        create_power_selection(
            [(sense, 1, "Perfect Pitch"), (sense, 1, "Perfect Pitch")], POWERS, 6
        )
