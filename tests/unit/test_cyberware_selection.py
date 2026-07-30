"""Tests for `chummer5.engine.cyberware` (WP32's `CyberwareSelection` builder + Improvement
applier) -- synthetic data first, mirroring WP5/WP30's "prove the mechanism in isolation" pattern
before any real fixture touches it. Fixture cross-checks live in
`tests/integration/test_cyberware_fixtures.py`.
"""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal

import pytest

from chummer5.data.cyberware import (
    BonusSupport,
    Cyberware,
    CyberwareConditionalBonus,
    CyberwareFlatBonus,
)
from chummer5.data.metatypes import load_metatypes
from chummer5.data.priorities import load_priorities
from chummer5.engine.character import create_character, metatype_choices
from chummer5.engine.cyberware import (
    CyberwareSelection,
    apply_cyberware_improvements,
    create_cyberware_selection,
)
from chummer5.engine.derived import (
    BASE_ESSENCE,
    essence,
    mental_limit,
    physical_condition_monitor,
)
from chummer5.engine.improvements import (
    ImprovementCondition,
    ImprovementSource,
    ImprovementType,
    ResolutionContext,
)

METATYPES = load_metatypes()
PRIORITIES = load_priorities()


def _no_effect_item(item_id: str, name: str, cost: int, essence_cost: str) -> Cyberware:
    return Cyberware(
        id=item_id,
        name=name,
        category="Headware",
        cost=cost,
        essence_cost=Decimal(essence_cost),
        source="SR5",
        page=1,
        bonus_support=BonusSupport.NO_EFFECT,
        flat_bonuses=(),
        conditional_bonuses=(),
        raw_bonus=None,
    )


def _cyberlimb_item(item_id: str, name: str, cost: int, essence_cost: str) -> Cyberware:
    return Cyberware(
        id=item_id,
        name=name,
        category="Cyberlimb",
        cost=cost,
        essence_cost=Decimal(essence_cost),
        source="SR5",
        page=1,
        bonus_support=BonusSupport.FLAT_BONUS,
        flat_bonuses=(CyberwareFlatBonus(target_kind="physical_cm", value=1),),
        conditional_bonuses=(),
        raw_bonus="<bonus><conditionmonitor><physical>1</physical></conditionmonitor></bonus>",
    )


DATAJACK = _no_effect_item("dj", "Datajack", 1000, "0.1")
COMMLINK = _no_effect_item("cl", "Commlink", 2000, "0.2")
ARM = _cyberlimb_item("arm", "Synthetic Full Arm", 20000, "1")
CATALOG = (DATAJACK, COMMLINK, ARM)


def _human_character():
    heritage = PRIORITIES.heritage["A"]
    human_choice = next(
        c for c in metatype_choices(heritage, METATYPES) if c.metatype.name == "Human"
    )
    return create_character(
        metatype_choice=human_choice,
        heritage_letter="A",
        attributes_letter="B",
        priorities=PRIORITIES,
        attribute_points={},
    )


# --- create_cyberware_selection ------------------------------------------------------------------


def test_builds_selection_with_correct_nuyen_and_essence_totals() -> None:
    selection = create_cyberware_selection(["dj", "cl"], CATALOG, nuyen_budget=5000)
    assert selection.items == (DATAJACK, COMMLINK)
    assert selection.nuyen_spent == 3000
    assert selection.essence_spent == Decimal("0.3")
    assert selection.nuyen_budget == 5000


def test_rejects_unknown_id() -> None:
    with pytest.raises(ValueError, match="not a cyberware catalog id"):
        create_cyberware_selection(["nope"], CATALOG, nuyen_budget=100000)


def test_rejects_nuyen_spend_over_budget() -> None:
    with pytest.raises(ValueError, match="exceeds the nuyen budget"):
        create_cyberware_selection(["dj", "cl"], CATALOG, nuyen_budget=2000)


def test_does_not_require_full_budget_spent() -> None:
    selection = create_cyberware_selection(["dj"], CATALOG, nuyen_budget=1_000_000)
    assert selection.nuyen_spent == 1000


def test_duplicate_purchases_are_allowed_and_sum_costs() -> None:
    # Confirmed against real fixture data (Barrett.chum5/Bastion.chum5 both buy two of the same
    # bilateral Cyberlimb) -- see module docstring.
    selection = create_cyberware_selection(["arm", "arm"], CATALOG, nuyen_budget=100000)
    assert selection.items == (ARM, ARM)
    assert selection.nuyen_spent == 40000
    assert selection.essence_spent == Decimal("2")


def test_rejects_essence_spend_that_would_leave_no_essence_remaining() -> None:
    # 6 items at Essence 1 each == 6, leaving exactly 0 -- rejected (must stay strictly positive).
    with pytest.raises(ValueError, match="would leave no Essence remaining"):
        create_cyberware_selection(["arm"] * 6, CATALOG, nuyen_budget=1_000_000)


def test_allows_essence_spend_that_leaves_a_fraction_remaining() -> None:
    selection = create_cyberware_selection(["arm"] * 5, CATALOG, nuyen_budget=1_000_000)
    assert selection.essence_spent == Decimal("5")
    assert selection.essence_spent < BASE_ESSENCE


def test_other_essence_spent_defaults_to_zero() -> None:
    # WP45: pre-WP45 call sites never pass other_essence_spent -- confirms the default keeps this
    # WP32-era 5-arm case (Essence 5, under the floor alone) accepted unchanged.
    selection = create_cyberware_selection(["arm"] * 5, CATALOG, nuyen_budget=1_000_000)
    assert selection.essence_spent == Decimal("5")


def test_other_essence_spent_folds_into_the_floor_check() -> None:
    # WP45: a combination only invalid once another selection's (e.g. bioware's) Essence spend is
    # counted alongside this one's -- 5 arms (Essence 5) alone fits, but with 1 more Essence already
    # spent elsewhere the combined total (6) hits the strictly-positive floor.
    with pytest.raises(ValueError, match="would leave no Essence remaining"):
        create_cyberware_selection(
            ["arm"] * 5, CATALOG, nuyen_budget=1_000_000, other_essence_spent=Decimal("1")
        )


def test_other_essence_spent_still_allows_a_fraction_remaining() -> None:
    selection = create_cyberware_selection(
        ["arm"] * 4, CATALOG, nuyen_budget=1_000_000, other_essence_spent=Decimal("1")
    )
    assert selection.essence_spent == Decimal("4")


# --- apply_cyberware_improvements -----------------------------------------------------------------


def test_apply_adds_essence_improvement_reducing_essence() -> None:
    character = _human_character()
    selection = create_cyberware_selection(["dj"], CATALOG, nuyen_budget=100000)
    apply_cyberware_improvements(character, selection)

    assert essence(character) == Decimal(BASE_ESSENCE) - Decimal("0.1")

    improvements = character.improvements.improvements
    assert len(improvements) == 1
    imp = improvements[0]
    assert imp.improvement_type == ImprovementType.ESSENCE
    assert imp.source_type == ImprovementSource.CYBERWARE
    assert imp.source_id == "dj"
    assert imp.essence_value == Decimal("-0.1")


def test_apply_cyberlimb_raises_physical_condition_monitor_via_flat_bonus() -> None:
    character = _human_character()
    base_cm = physical_condition_monitor(character)

    selection = create_cyberware_selection(["arm"], CATALOG, nuyen_budget=100000)
    apply_cyberware_improvements(character, selection)

    assert physical_condition_monitor(character) == base_cm + 1
    assert essence(character) == Decimal(BASE_ESSENCE) - Decimal("1")


def test_apply_duplicate_purchase_sums_essence_and_condition_monitor_twice() -> None:
    character = _human_character()
    base_cm = physical_condition_monitor(character)

    selection = create_cyberware_selection(["arm", "arm"], CATALOG, nuyen_budget=100000)
    apply_cyberware_improvements(character, selection)

    assert physical_condition_monitor(character) == base_cm + 2
    assert essence(character) == Decimal(BASE_ESSENCE) - Decimal("2")


def test_cyberware_selection_is_a_frozen_dataclass_field_default_none() -> None:
    character = _human_character()
    assert character.cyberware_selection is None
    selection = CyberwareSelection(
        items=(DATAJACK,), nuyen_budget=1000, nuyen_spent=1000, essence_spent=Decimal("0.1")
    )
    character = replace(character, cyberware_selection=selection)
    assert character.cyberware_selection is selection


# --- WP40: conditional bonuses ------------------------------------------------------------------


def _conditional_item(
    item_id: str, name: str, *, value: int | None, condition: str, target_kind: str = "mental_limit"
) -> Cyberware:
    return Cyberware(
        id=item_id,
        name=name,
        category="Earware",
        cost=4000,
        essence_cost=Decimal("0.1"),
        source="SR5",
        page=1,
        bonus_support=BonusSupport.CONDITIONAL_BONUS,
        flat_bonuses=(),
        conditional_bonuses=(
            CyberwareConditionalBonus(target_kind=target_kind, value=value, condition=condition),
        ),
        raw_bonus="<bonus><limitmodifier /></bonus>",
    )


SPATIAL = _conditional_item(
    "sr",
    "Spatial Recognizer",
    value=2,
    condition="LimitCondition_SkillsActivePerceptionSpatialRecognizer",
)


def test_conditional_bonus_applies_only_under_its_own_resolution_context() -> None:
    character = _human_character()
    base = mental_limit(character)

    selection = create_cyberware_selection(["sr"], (*CATALOG, SPATIAL), nuyen_budget=100000)
    apply_cyberware_improvements(character, selection)

    # p. 444: "+2 bonus on your limit in Perception Tests to find the source of a specific sound."
    assert mental_limit(character, context=ResolutionContext.PERCEPTION_SOUND_SOURCE) == base + 2
    # The headline figure, and any Mental-limited test with no conditional bonus of its own (a
    # Memory test, say), are untouched.
    assert mental_limit(character) == base
    # No subsumption between conditions (WP39): a plain hearing Perception test is not "finding the
    # source of a sound", so this bonus does not apply to it.
    assert mental_limit(character, context=ResolutionContext.PERCEPTION_HEARING) == base


def test_conditional_improvement_carries_the_compiled_condition_not_a_string() -> None:
    character = _human_character()
    selection = create_cyberware_selection(["sr"], (*CATALOG, SPATIAL), nuyen_budget=100000)
    apply_cyberware_improvements(character, selection)

    bonus = next(
        imp
        for imp in character.improvements.improvements
        if imp.improvement_type is ImprovementType.MENTAL_LIMIT
    )
    assert bonus.condition is ImprovementCondition.PERCEPTION_SOUND_SOURCE_ONLY
    assert bonus.value == 2
    assert bonus.source_type is ImprovementSource.CYBERWARE
    assert bonus.source_id == "sr"


def test_flat_catalog_refuses_a_rating_scaled_conditional_bonus() -> None:
    # WP31's catalog has no rating dimension at all (no row carries a <rating> tag), so a
    # <value>Rating</value> bonus arriving here is data drift. Applying it as +1 would be a
    # plausible-but-wrong number, which is exactly what this engine refuses to produce.
    rating_scaled = _conditional_item(
        "ve",
        "Vision Enhancement",
        value=None,
        condition="LimitCondition_SkillsActivePerceptionVisual",
    )
    character = _human_character()
    selection = create_cyberware_selection(["ve"], (*CATALOG, rating_scaled), nuyen_budget=100000)
    with pytest.raises(ValueError, match="rating-scaled conditional bonus"):
        apply_cyberware_improvements(character, selection)


def test_every_supported_condition_key_maps_to_an_improvement_condition() -> None:
    # The two whitelists (data-layer <condition> strings, engine-layer compiled predicates) are
    # written in different modules; this pins them together so neither can grow without the other.
    from chummer5.data.cyberware import _SUPPORTED_BONUS_CONDITIONS
    from chummer5.engine.cyberware import _CONDITION_KEY_TO_CONDITION

    assert set(_CONDITION_KEY_TO_CONDITION) == set(_SUPPORTED_BONUS_CONDITIONS)
    assert set(_CONDITION_KEY_TO_CONDITION.values()) == set(ImprovementCondition)
