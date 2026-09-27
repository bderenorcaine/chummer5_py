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


def test_attribute_bonus_targets_the_named_attribute_code() -> None:
    # WP78: the first CyberwareFlatBonus kind with a real target rather than the _GLOBAL_TARGET
    # sentinel -- `ImprovementType.ATTRIBUTE` resolves against the attribute code.
    (improvement,) = _improvements(
        flat_bonuses=(
            CyberwareFlatBonus(
                target_kind="attribute", value=None, target_name="REA", unique_name="precedence0"
            ),
        ),
        rating=3,
    )
    assert improvement.improvement_type is ImprovementType.ATTRIBUTE
    assert improvement.target == "REA"
    assert improvement.value == 3  # `<val>Rating</val>` resolved against the purchase
    assert improvement.rating == 3
    assert improvement.unique_name == "precedence0"
    assert improvement.condition is None


def test_skill_bonus_targets_the_named_skill() -> None:
    (improvement,) = _improvements(
        flat_bonuses=(
            CyberwareFlatBonus(target_kind="skill", value=None, target_name="Impersonation"),
        ),
        rating=4,
    )
    assert improvement.improvement_type is ImprovementType.SKILL
    assert improvement.target == "Impersonation"
    assert improvement.value == 4
    assert improvement.unique_name is None


def test_initiative_dice_bonus_targets_the_character_wide_total() -> None:
    (improvement,) = _improvements(
        flat_bonuses=(
            CyberwareFlatBonus(
                target_kind="initiative_dice", value=None, unique_name="precedence0"
            ),
        ),
        rating=2,
    )
    assert improvement.improvement_type is ImprovementType.INITIATIVE_DICE
    assert improvement.target == ""  # _GLOBAL_TARGET, which is also the default target_name
    assert improvement.value == 2


def test_a_literal_valued_flat_bonus_ignores_the_purchased_rating() -> None:
    # `value=None` means "ask the purchase"; an int means exactly that int, at any rating.
    (improvement,) = _improvements(
        flat_bonuses=(CyberwareFlatBonus(target_kind="physical_cm", value=1),), rating=5
    )
    assert improvement.value == 1


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


def test_every_supported_condition_key_has_player_facing_english_text() -> None:
    # WP42: a third view of the same four keys -- the sheet prints this beside a conditional
    # bonus's value. Pinned to the same whitelist for the same reason as the map above: a fifth
    # condition added to the data layer without its text would render as a KeyError, not as a
    # missing sentence.
    from chummer5.data.cyberware import _SUPPORTED_BONUS_CONDITIONS, CONDITION_DESCRIPTIONS

    assert set(CONDITION_DESCRIPTIONS) == set(_SUPPORTED_BONUS_CONDITIONS)
    assert all(text for text in CONDITION_DESCRIPTIONS.values())


def test_every_target_kind_the_loader_produces_has_an_improvement_type() -> None:
    # The same pin as above, for the other string -> enum map. WP78 is the WP that made this map
    # grow for the first time since WP40, so an unmapped `target_kind` is now a live failure mode
    # rather than a theoretical one: it would raise a KeyError deep inside a purchase.
    from chummer5.data.bioware import load_bioware
    from chummer5.data.cyberware import load_cyberware
    from chummer5.data.cyberware_subsystems import load_cyberware_entries
    from chummer5.engine.cyberware import _TARGET_KIND_TO_IMPROVEMENT_TYPE

    produced = {
        bonus.target_kind
        for catalog in (load_cyberware(), load_cyberware_entries())
        for item in catalog
        for bonus in (*item.flat_bonuses, *item.conditional_bonuses)
    }
    # WP128: rated bioware goes through the same classifier and translator.
    produced |= {bonus.target_kind for item in load_bioware() for bonus in item.rated_bonuses}
    assert produced <= set(_TARGET_KIND_TO_IMPROVEMENT_TYPE)
    # Every kind the maps carry is one real SR5 content actually uses -- no dead entries.
    assert produced == set(_TARGET_KIND_TO_IMPROVEMENT_TYPE)
