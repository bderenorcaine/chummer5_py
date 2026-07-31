"""Tests for `chummer5.engine.cyberware` -- the `<bonus>` -> `Improvement` translation, which is
all that module still holds after WP41 retired WP32's flat `CyberwareSelection`/
`create_cyberware_selection`/`apply_cyberware_improvements` (see that module's own docstring for
why, and `chummer5.engine.cyberware_subsystems` for the purchase tree that replaced them).

This file used to be `test_cyberware_selection.py`, covering all three. Every selection/apply test
it carried has a direct counterpart in `tests/unit/test_cyberware_tree.py` (budget rejection,
Essence floor, duplicate purchases, flat and conditional bonuses reaching a real `Character`), so
nothing was dropped in the rename -- what remains here is the translation step itself, unit-tested
without a `Character` at all, plus the whitelist pin that keeps the data and engine layers from
drifting apart.
"""

from __future__ import annotations

import pytest

from chummer5.data.cyberware import CyberwareConditionalBonus, CyberwareFlatBonus
from chummer5.engine.cyberware import cyberware_bonus_improvements
from chummer5.engine.improvements import (
    ImprovementCondition,
    ImprovementSource,
    ImprovementType,
)


def _improvements(
    *,
    flat_bonuses: tuple[CyberwareFlatBonus, ...] = (),
    conditional_bonuses: tuple[CyberwareConditionalBonus, ...] = (),
    rating: int = 1,
):
    return cyberware_bonus_improvements(
        item_id="item",
        item_name="Test Item",
        flat_bonuses=flat_bonuses,
        conditional_bonuses=conditional_bonuses,
        rating=rating,
    )


def test_no_bonuses_produce_no_improvements() -> None:
    assert _improvements() == ()


def test_flat_bonus_translates_to_an_unconditional_improvement() -> None:
    (improvement,) = _improvements(
        flat_bonuses=(CyberwareFlatBonus(target_kind="physical_cm", value=1),)
    )
    assert improvement.improvement_type is ImprovementType.PHYSICAL_CM
    assert improvement.value == 1
    assert improvement.condition is None
    assert improvement.source_type is ImprovementSource.CYBERWARE
    assert improvement.source_id == "item"


def test_conditional_bonus_carries_the_compiled_condition_not_the_legacy_string() -> None:
    (improvement,) = _improvements(
        conditional_bonuses=(
            CyberwareConditionalBonus(
                target_kind="mental_limit",
                value=2,
                condition="LimitCondition_SkillsActivePerceptionSpatialRecognizer",
            ),
        )
    )
    assert improvement.improvement_type is ImprovementType.MENTAL_LIMIT
    assert improvement.value == 2
    # WP39: an Enum member compiled once, never a string re-read at resolve time.
    assert improvement.condition is ImprovementCondition.PERCEPTION_SOUND_SOURCE_ONLY


def test_a_value_less_conditional_bonus_resolves_to_the_purchased_rating() -> None:
    # `<value>Rating</value>` -- Vision/Audio Enhancement and Hydraulic Jacks' own shape.
    bonus = CyberwareConditionalBonus(
        target_kind="mental_limit",
        value=None,
        condition="LimitCondition_SkillsActivePerceptionVisual",
    )
    (improvement,) = _improvements(conditional_bonuses=(bonus,), rating=3)
    assert improvement.value == 3
    assert improvement.rating == 3
    assert improvement.condition is ImprovementCondition.PERCEPTION_VISUAL_ONLY


def test_physical_limit_conditional_bonus_targets_the_physical_limit() -> None:
    (improvement,) = _improvements(
        conditional_bonuses=(
            CyberwareConditionalBonus(
                target_kind="physical_limit",
                value=None,
                condition="LimitCondition_CyberwareHydraulicJacks",
            ),
        ),
        rating=2,
    )
    assert improvement.improvement_type is ImprovementType.PHYSICAL_LIMIT
    assert improvement.value == 2
    assert improvement.condition is ImprovementCondition.JUMPING_OR_SPRINTING_ONLY


def test_an_unmapped_condition_key_raises_rather_than_silently_dropping_the_bonus() -> None:
    with pytest.raises(ValueError, match="has no ImprovementCondition"):
        _improvements(
            conditional_bonuses=(
                CyberwareConditionalBonus(
                    target_kind="mental_limit", value=1, condition="LimitCondition_Invented"
                ),
            )
        )


def test_every_supported_condition_key_maps_to_an_improvement_condition() -> None:
    # The two whitelists (data-layer <condition> strings, engine-layer compiled predicates) are
    # written in different modules; this pins them together so neither can grow without the other.
    from chummer5.data.cyberware import _SUPPORTED_BONUS_CONDITIONS
    from chummer5.engine.cyberware import _CONDITION_KEY_TO_CONDITION

    assert set(_CONDITION_KEY_TO_CONDITION) == set(_SUPPORTED_BONUS_CONDITIONS)
    assert set(_CONDITION_KEY_TO_CONDITION.values()) == set(ImprovementCondition)
