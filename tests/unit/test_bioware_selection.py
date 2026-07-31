"""Tests for `chummer5.engine.bioware` (WP45's `BiowareSelection` builder + Improvement applier) --
synthetic data first, mirroring `tests/unit/test_cyberware_selection.py`'s identical "prove the
mechanism in isolation" pattern. Real-fixture cross-checks live in
`tests/integration/test_bioware_fixtures.py`.
"""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal

import pytest

from chummer5.data.bioware import Bioware, BiowareFlatBonus, BiowareSelectSkillBonus
from chummer5.data.cyberware import BonusSupport
from chummer5.data.metatypes import load_metatypes
from chummer5.data.priorities import load_priorities
from chummer5.data.skills import Skill
from chummer5.engine.bioware import (
    BiowarePurchase,
    BiowarePurchaseRequest,
    BiowareSelection,
    apply_bioware_improvements,
    create_bioware_selection,
    select_skill_choices,
)
from chummer5.engine.character import create_character, metatype_choices
from chummer5.engine.cyberware_subsystems import (
    CyberwarePurchaseRequest,
    create_cyberware_tree_selection,
)
from chummer5.engine.derived import BASE_ESSENCE, essence, physical_limit
from chummer5.engine.improvements import ImprovementSource, ImprovementType

METATYPES = load_metatypes()
PRIORITIES = load_priorities()


def _no_effect_item(item_id: str, name: str, cost: int, essence_cost: str) -> Bioware:
    return Bioware(
        id=item_id,
        name=name,
        category="Basic",
        cost=cost,
        essence_cost=Decimal(essence_cost),
        availability=4,
        source="SR5",
        page=1,
        bonus_support=BonusSupport.NO_EFFECT,
        flat_bonuses=(),
        raw_bonus=None,
    )


def _limit_bonus_item(item_id: str, name: str, cost: int, essence_cost: str) -> Bioware:
    return Bioware(
        id=item_id,
        name=name,
        category="Basic",
        cost=cost,
        essence_cost=Decimal(essence_cost),
        availability=12,
        source="SR5",
        page=1,
        bonus_support=BonusSupport.FLAT_BONUS,
        flat_bonuses=(BiowareFlatBonus(target_kind="physical_limit", target_name="", value=1),),
        raw_bonus="<bonus><physicallimit>1</physicallimit></bonus>",
    )


def _select_skill_item(item_id: str, name: str, cost: int, essence_cost: str) -> Bioware:
    """WP80: a row whose bonus is a purchase-time player pick (`Reflex Recorder`'s shape)."""
    return Bioware(
        id=item_id,
        name=name,
        category="Cultured",
        cost=cost,
        essence_cost=Decimal(essence_cost),
        availability=10,
        source="SR5",
        page=460,
        bonus_support=BonusSupport.SELECT_SKILL,
        flat_bonuses=(),
        raw_bonus='<bonus><selectskill limittoattribute="BOD,AGI,REA,STR"><val>1</val>'
        "</selectskill></bonus>",
        select_skill_bonus=BiowareSelectSkillBonus(
            value=1, limit_to_attributes=("BOD", "AGI", "REA", "STR")
        ),
    )


def _skill(skill_id: str, name: str, attribute: str) -> Skill:
    return Skill(
        id=skill_id,
        name=name,
        attribute=attribute,
        category="Combat Active",
        skill_group=None,
        can_default=True,
        exotic=False,
        specializations=(),
        source="SR5",
        page=1,
    )


# Two eligible (AGI/STR-linked) skills and one that fails the filter (LOG-linked), mirroring the
# real filter's shape without depending on the real catalog -- that cross-check is in
# tests/integration/test_bioware_fixtures.py.
LONGARMS = _skill("lon", "Longarms", "AGI")
SWIMMING = _skill("swi", "Swimming", "STR")
COMPUTER = _skill("com", "Computer", "LOG")
SKILLS = (LONGARMS, SWIMMING, COMPUTER)

CATS_EYES = _no_effect_item("ce", "Cat's Eyes", 4000, "0.1")
SLEEP_REGULATOR = _no_effect_item("sr", "Sleep Regulator", 12000, "0.1")
ARTICULATION = _limit_bonus_item("ea", "Enhanced Articulation", 24000, "0.3")
RECORDER = _select_skill_item("rr", "Reflex Recorder", 14000, "0.1")
CATALOG = (CATS_EYES, SLEEP_REGULATOR, ARTICULATION, RECORDER)


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


# --- create_bioware_selection --------------------------------------------------------------------


def test_builds_selection_with_correct_nuyen_and_essence_totals() -> None:
    selection = create_bioware_selection(["ce", "sr"], CATALOG, nuyen_budget=20000)
    assert selection.items == (CATS_EYES, SLEEP_REGULATOR)
    assert selection.nuyen_spent == 16000
    assert selection.essence_spent == Decimal("0.2")
    assert selection.nuyen_budget == 20000


def test_rejects_unknown_id() -> None:
    with pytest.raises(ValueError, match="not a bioware catalog id"):
        create_bioware_selection(["nope"], CATALOG, nuyen_budget=100000)


def test_rejects_nuyen_spend_over_budget() -> None:
    with pytest.raises(ValueError, match="exceeds the nuyen budget"):
        create_bioware_selection(["ce", "sr"], CATALOG, nuyen_budget=10000)


def test_does_not_require_full_budget_spent() -> None:
    selection = create_bioware_selection(["ce"], CATALOG, nuyen_budget=1_000_000)
    assert selection.nuyen_spent == 4000


def test_duplicate_purchases_are_allowed_and_sum_costs() -> None:
    selection = create_bioware_selection(["ce", "ce"], CATALOG, nuyen_budget=100000)
    assert selection.items == (CATS_EYES, CATS_EYES)
    assert selection.nuyen_spent == 8000
    assert selection.essence_spent == Decimal("0.2")


def test_rejects_essence_spend_that_would_leave_no_essence_remaining() -> None:
    # 20 Cat's Eyes at Essence 0.1 each == 2.0 -- well under the floor alone; use a bigger multiple
    # to actually hit BASE_ESSENCE (6): 60 copies at 0.1 == 6.
    with pytest.raises(ValueError, match="would leave no Essence remaining"):
        create_bioware_selection(["ce"] * 60, CATALOG, nuyen_budget=1_000_000)


def test_allows_essence_spend_that_leaves_a_fraction_remaining() -> None:
    selection = create_bioware_selection(["ce"] * 59, CATALOG, nuyen_budget=1_000_000)
    assert selection.essence_spent == Decimal("5.9")
    assert selection.essence_spent < BASE_ESSENCE


def test_other_essence_spent_defaults_to_zero() -> None:
    selection = create_bioware_selection(["ce"] * 59, CATALOG, nuyen_budget=1_000_000)
    assert selection.essence_spent == Decimal("5.9")


def test_other_essence_spent_folds_into_the_shared_floor_check() -> None:
    # The fixed cyberware-first/bioware-second evaluation order this module's docstring documents:
    # 59 Cat's Eyes (Essence 5.9) alone fits, but with 0.2 already spent on cyberware elsewhere the
    # combined total (6.1) crosses the strictly-positive floor.
    with pytest.raises(ValueError, match="would leave no Essence remaining"):
        create_bioware_selection(
            ["ce"] * 59, CATALOG, nuyen_budget=1_000_000, other_essence_spent=Decimal("0.2")
        )


def test_other_essence_spent_still_allows_a_fraction_remaining() -> None:
    selection = create_bioware_selection(
        ["ce"] * 50, CATALOG, nuyen_budget=1_000_000, other_essence_spent=Decimal("0.9")
    )
    assert selection.essence_spent == Decimal("5.0")


def test_shared_floor_matches_a_real_combined_cyberware_and_bioware_check() -> None:
    """Confirms the two modules' floors genuinely compose: resolve cyberware first (unaware of
    bioware), then bioware second (aware of cyberware) -- the combined Essence spend must still
    respect the one shared floor regardless of which module's own check is doing the rejecting.
    """
    from chummer5.data.cyberware_subsystems import load_cyberware_entries

    # A real catalog row, priced by the tree engine (WP41): 5 Reaction Enhancers at Rating 1
    # (0.3 Essence each) spends 1.5, leaving the bioware call below to trip the shared floor.
    reaction_enhancers = next(
        entry for entry in load_cyberware_entries() if entry.name == "Reaction Enhancers"
    )
    cyberware_selection = create_cyberware_tree_selection(
        [CyberwarePurchaseRequest(item_id=reaction_enhancers.id)] * 5,
        (reaction_enhancers,),
        nuyen_budget=1_000_000,
    )
    assert cyberware_selection.essence_spent == Decimal("1.5")
    with pytest.raises(ValueError, match="would leave no Essence remaining"):
        create_bioware_selection(
            ["ce"] * 50,
            CATALOG,
            nuyen_budget=1_000_000,
            other_essence_spent=cyberware_selection.essence_spent,
        )


# --- apply_bioware_improvements -------------------------------------------------------------------


def test_apply_adds_essence_improvement_reducing_essence() -> None:
    character = _human_character()
    selection = create_bioware_selection(["ce"], CATALOG, nuyen_budget=100000)
    apply_bioware_improvements(character, selection)

    assert essence(character) == Decimal(BASE_ESSENCE) - Decimal("0.1")

    improvements = character.improvements.improvements
    assert len(improvements) == 1
    imp = improvements[0]
    assert imp.improvement_type == ImprovementType.ESSENCE
    assert imp.source_type == ImprovementSource.BIOWARE
    assert imp.source_id == "ce"
    assert imp.essence_value == Decimal("-0.1")


def test_apply_flat_bonus_raises_physical_limit() -> None:
    character = _human_character()
    base_limit = physical_limit(character)

    selection = create_bioware_selection(["ea"], CATALOG, nuyen_budget=100000)
    apply_bioware_improvements(character, selection)

    assert physical_limit(character) == base_limit + 1
    assert essence(character) == Decimal(BASE_ESSENCE) - Decimal("0.3")


def test_apply_duplicate_purchase_sums_essence_and_flat_bonus_twice() -> None:
    character = _human_character()
    base_limit = physical_limit(character)

    selection = create_bioware_selection(["ea", "ea"], CATALOG, nuyen_budget=100000)
    apply_bioware_improvements(character, selection)

    assert physical_limit(character) == base_limit + 2
    assert essence(character) == Decimal(BASE_ESSENCE) - Decimal("0.6")


def test_bioware_selection_is_a_frozen_dataclass_field_default_none() -> None:
    character = _human_character()
    assert character.bioware_selection is None
    selection = BiowareSelection(
        purchases=(BiowarePurchase(item=CATS_EYES),),
        nuyen_budget=1000,
        nuyen_spent=4000,
        essence_spent=Decimal("0.1"),
    )
    character = replace(character, bioware_selection=selection)
    assert character.bioware_selection is selection


# --- WP80: `Reflex Recorder`'s purchase-time skill choice -----------------------------------------


def _recorder(chosen_skill: str | None) -> BiowarePurchaseRequest:
    return BiowarePurchaseRequest(item_id="rr", chosen_skill=chosen_skill)


def test_select_skill_choices_are_exactly_the_skills_passing_the_filter() -> None:
    assert select_skill_choices(RECORDER, SKILLS) == (LONGARMS, SWIMMING)
    # A row with no pick to make offers none, rather than "every skill".
    assert select_skill_choices(CATS_EYES, SKILLS) == ()


def test_purchase_with_a_chosen_skill_raises_exactly_that_skill() -> None:
    character = _human_character()
    selection = create_bioware_selection(
        [_recorder("Longarms")], CATALOG, nuyen_budget=100000, skills=SKILLS
    )
    assert selection.purchases[0].chosen_skill == "Longarms"
    apply_bioware_improvements(character, selection)

    # p. 460: "adds 1 to the Rating of a specific skill" -- a rating bonus, hence SKILL.
    assert character.improvements.resolve(ImprovementType.SKILL, "Longarms") == 1
    assert character.improvements.resolve(ImprovementType.SKILL, "Swimming") == 0
    assert essence(character) == Decimal(BASE_ESSENCE) - Decimal("0.1")


def test_rejects_a_skill_outside_the_limittoattribute_filter() -> None:
    with pytest.raises(ValueError, match="Computer is linked to LOG"):
        create_bioware_selection(
            [_recorder("Computer")], CATALOG, nuyen_budget=100000, skills=SKILLS
        )


def test_rejects_an_unknown_skill_name() -> None:
    with pytest.raises(ValueError, match="not an active skill"):
        create_bioware_selection([_recorder("Nope")], CATALOG, nuyen_budget=100000, skills=SKILLS)


def test_rejects_a_missing_or_blank_pick() -> None:
    for chosen in (None, "   "):
        with pytest.raises(ValueError, match="requires a chosen skill"):
            create_bioware_selection(
                [_recorder(chosen)], CATALOG, nuyen_budget=100000, skills=SKILLS
            )


def test_a_bare_id_for_a_row_that_needs_a_pick_is_rejected_too() -> None:
    # The bare-id shorthand means "no player choice", which is not a legal state for this row --
    # see chummer5.engine.bioware's module docstring.
    with pytest.raises(ValueError, match="requires a chosen skill"):
        create_bioware_selection(["rr"], CATALOG, nuyen_budget=100000, skills=SKILLS)


def test_rejects_a_pick_supplied_for_a_row_that_has_nothing_to_choose() -> None:
    # The same "don't silently ignore a stale/tampered field" rule create_quality_selection applies
    # to a SELECT_TEXT quality's own free text.
    with pytest.raises(ValueError, match="has no skill to choose"):
        create_bioware_selection(
            [BiowarePurchaseRequest(item_id="ce", chosen_skill="Longarms")],
            CATALOG,
            nuyen_budget=100000,
            skills=SKILLS,
        )


def test_two_recorders_for_different_skills_each_raise_their_own() -> None:
    # p. 460: "Multiple recorders may be taken for multiple skills".
    character = _human_character()
    selection = create_bioware_selection(
        [_recorder("Longarms"), _recorder("Swimming")],
        CATALOG,
        nuyen_budget=100000,
        skills=SKILLS,
    )
    apply_bioware_improvements(character, selection)

    assert character.improvements.resolve(ImprovementType.SKILL, "Longarms") == 1
    assert character.improvements.resolve(ImprovementType.SKILL, "Swimming") == 1
    assert essence(character) == Decimal(BASE_ESSENCE) - Decimal("0.2")


def test_two_recorders_for_the_same_skill_are_rejected() -> None:
    # p. 460: "... but you can't implant two reflex recorders for the same skill."
    with pytest.raises(ValueError, match="only one per skill"):
        create_bioware_selection(
            [_recorder("Longarms"), _recorder("Longarms")],
            CATALOG,
            nuyen_budget=100000,
            skills=SKILLS,
        )


def test_to_requests_round_trips_the_pick() -> None:
    selection = create_bioware_selection(
        [_recorder("Longarms"), "ce"], CATALOG, nuyen_budget=100000, skills=SKILLS
    )
    assert selection.to_requests() == (
        BiowarePurchaseRequest(item_id="rr", chosen_skill="Longarms"),
        BiowarePurchaseRequest(item_id="ce", chosen_skill=None),
    )
    assert selection.items == (RECORDER, CATS_EYES)


def test_removing_the_source_retracts_both_recorders_at_once() -> None:
    # Duplicate purchases share one source_id (the catalog id), which the web layer's own
    # "swap this source's Improvements" step relies on.
    character = _human_character()
    selection = create_bioware_selection(
        [_recorder("Longarms"), _recorder("Swimming")],
        CATALOG,
        nuyen_budget=100000,
        skills=SKILLS,
    )
    apply_bioware_improvements(character, selection)
    character.improvements.remove_source(ImprovementSource.BIOWARE, "rr")

    assert character.improvements.resolve(ImprovementType.SKILL, "Longarms") == 0
    assert character.improvements.resolve(ImprovementType.SKILL, "Swimming") == 0
    assert essence(character) == Decimal(BASE_ESSENCE)
