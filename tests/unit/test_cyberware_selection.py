"""Tests for `chummer5.engine.cyberware` (WP32's `CyberwareSelection` builder + Improvement
applier) -- synthetic data first, mirroring WP5/WP30's "prove the mechanism in isolation" pattern
before any real fixture touches it. Fixture cross-checks live in
`tests/integration/test_cyberware_fixtures.py`.
"""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal

import pytest

from chummer5.data.cyberware import BonusSupport, Cyberware, CyberwareFlatBonus
from chummer5.data.metatypes import load_metatypes
from chummer5.data.priorities import load_priorities
from chummer5.engine.character import create_character, metatype_choices
from chummer5.engine.cyberware import (
    CyberwareSelection,
    apply_cyberware_improvements,
    create_cyberware_selection,
)
from chummer5.engine.derived import BASE_ESSENCE, essence, physical_condition_monitor
from chummer5.engine.improvements import ImprovementSource, ImprovementType

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
