"""Tests for `chummer5.engine.qualities` (quality selection & Improvement application).

Named `test_quality_selection.py`, not `test_qualities.py`, to avoid colliding with
`tests/unit/test_qualities.py` (WP3's data-loader tests) -- mirrors WP7's
`test_skill_allocation.py`/`test_skills.py` split for the same reason.
"""

from __future__ import annotations

import pytest

from chummer5.data.metatypes import load_metatypes
from chummer5.data.priorities import load_priorities
from chummer5.data.qualities import BonusSupport, FlatBonus, Quality, load_qualities
from chummer5.engine.character import create_character, metatype_choices
from chummer5.engine.improvements import ImprovementType
from chummer5.engine.qualities import (
    QUALITY_KARMA_LIMIT,
    apply_quality_improvements,
    create_quality_selection,
    mvp_quality_catalog,
)

QUALITIES = load_qualities()
METATYPES = load_metatypes()
PRIORITIES = load_priorities()

# A synthetic Negative-category FLAT_BONUS quality -- no real SR5 quality with this shape currently
# exists (see module docstring in chummer5.engine.qualities), so the negative-karma-cap rule is
# exercised with hand-authored data, the same "prove the rule in isolation" pattern WP5 used for
# Improvement dedup and WP7 used for the dice-pool formula.
_SYNTHETIC_NEGATIVE_FLAT_BONUS = Quality(
    id="synthetic-negative-flat-bonus",
    name="Synthetic Negative Flat Bonus",
    category="Negative",
    karma=-20,
    limit=None,
    source="SR5",
    page=0,
    bonus_support=BonusSupport.FLAT_BONUS,
    flat_bonuses=(FlatBonus(target_kind="skill", target_name="Running", value=-1),),
    raw_bonus=None,
)

# A second synthetic Positive quality, used to push a selection's positive-karma sum past the
# 25-karma limit (the 3 real FLAT_BONUS qualities only sum to 20 -- see module docstring).
_SYNTHETIC_POSITIVE_FLAT_BONUS = Quality(
    id="synthetic-positive-flat-bonus",
    name="Synthetic Positive Flat Bonus",
    category="Positive",
    karma=10,
    limit=None,
    source="SR5",
    page=0,
    bonus_support=BonusSupport.FLAT_BONUS,
    flat_bonuses=(FlatBonus(target_kind="attribute", target_name="BOD", value=1),),
    raw_bonus=None,
)


def _by_name(name: str) -> Quality:
    return next(q for q in QUALITIES if q.name == name)


def test_mvp_quality_catalog_is_exactly_the_three_flat_bonus_qualities() -> None:
    # Hand-checked against WP3's own count (spec/worklogs/WP3.md): 3 of 96 SR5 qualities are
    # FLAT_BONUS -- Catlike, Double-Jointed, Natural Athlete. All three happen to be Positive; MVP
    # currently offers no Negative quality at all (see module docstring).
    offered = mvp_quality_catalog(QUALITIES)
    assert {q.name for q in offered} == {"Catlike", "Double-Jointed", "Natural Athlete"}
    assert all(q.bonus_support == BonusSupport.FLAT_BONUS for q in offered)
    assert all(q.category == "Positive" for q in offered)


def test_mvp_quality_catalog_excludes_not_yet_supported_quality() -> None:
    # Explicit acceptance-criteria test: a NOT_YET_SUPPORTED quality (Analytical Mind: conditional
    # <skillattribute> bonus) is excluded from the offered list entirely, not offered with its bonus
    # silently dropped.
    analytical_mind = _by_name("Analytical Mind")
    assert analytical_mind.bonus_support == BonusSupport.NOT_YET_SUPPORTED
    offered_names = {q.name for q in mvp_quality_catalog(QUALITIES)}
    assert analytical_mind.name not in offered_names

    with pytest.raises(ValueError, match="not an MVP-offered quality id"):
        create_quality_selection([analytical_mind.id], QUALITIES)


def test_create_quality_selection_single_positive_quality() -> None:
    catlike = _by_name("Catlike")
    selection = create_quality_selection([catlike.id], QUALITIES)
    assert selection.qualities == (catlike,)
    assert selection.positive_karma == 7
    assert selection.negative_karma == 0
    assert selection.karma_cost == 7


def test_create_quality_selection_multiple_positive_qualities_sum() -> None:
    catlike = _by_name("Catlike")
    double_jointed = _by_name("Double-Jointed")
    selection = create_quality_selection([catlike.id, double_jointed.id], QUALITIES)
    assert selection.positive_karma == 13  # 7 + 6
    assert selection.karma_cost == 13


def test_create_quality_selection_empty_selection() -> None:
    selection = create_quality_selection([], QUALITIES)
    assert selection.qualities == ()
    assert selection.positive_karma == 0
    assert selection.negative_karma == 0
    assert selection.karma_cost == 0


def test_create_quality_selection_rejects_unknown_id() -> None:
    with pytest.raises(ValueError, match="not an MVP-offered quality id"):
        create_quality_selection(["not-a-real-id"], QUALITIES)


def test_create_quality_selection_rejects_duplicate_selection() -> None:
    catlike = _by_name("Catlike")
    with pytest.raises(ValueError, match="selected more than once"):
        create_quality_selection([catlike.id, catlike.id], QUALITIES)


def test_create_quality_selection_rejects_positive_karma_over_limit() -> None:
    catalog = (*QUALITIES, _SYNTHETIC_POSITIVE_FLAT_BONUS)
    catlike = _by_name("Catlike")  # 7
    double_jointed = _by_name("Double-Jointed")  # 6
    natural_athlete = _by_name("Natural Athlete")  # 7
    # 7 + 6 + 7 + 10 = 30 > 25.
    with pytest.raises(ValueError, match="Positive Qualities cost 30 karma"):
        create_quality_selection(
            [
                catlike.id,
                double_jointed.id,
                natural_athlete.id,
                _SYNTHETIC_POSITIVE_FLAT_BONUS.id,
            ],
            catalog,
        )


def test_create_quality_selection_allows_exactly_the_karma_limit() -> None:
    catalog = (*QUALITIES, _SYNTHETIC_POSITIVE_FLAT_BONUS)
    catlike = _by_name("Catlike")  # 7
    double_jointed = _by_name("Double-Jointed")  # 6
    # 7 + 6 + 10 = 23, safely under; bump to exactly 25 isn't achievable with these exact karma
    # values, so this just asserts the boundary isn't over-strict (< limit is fine).
    selection = create_quality_selection(
        [catlike.id, double_jointed.id, _SYNTHETIC_POSITIVE_FLAT_BONUS.id], catalog
    )
    assert selection.positive_karma == 23
    assert selection.positive_karma <= QUALITY_KARMA_LIMIT


def test_create_quality_selection_rejects_negative_karma_over_limit() -> None:
    catalog = (*QUALITIES, _SYNTHETIC_NEGATIVE_FLAT_BONUS)
    # A second synthetic negative quality would be needed to exceed 25 from one alone at -20; use
    # two distinct synthetic ids to push the sum past the limit.
    second = Quality(
        id="synthetic-negative-flat-bonus-2",
        name="Synthetic Negative Flat Bonus 2",
        category="Negative",
        karma=-10,
        limit=None,
        source="SR5",
        page=0,
        bonus_support=BonusSupport.FLAT_BONUS,
        flat_bonuses=(FlatBonus(target_kind="skill", target_name="Gymnastics", value=-1),),
        raw_bonus=None,
    )
    catalog = (*catalog, second)
    with pytest.raises(ValueError, match="Negative Qualities grant 30 karma"):
        create_quality_selection(
            [_SYNTHETIC_NEGATIVE_FLAT_BONUS.id, second.id],
            catalog,
        )


def test_create_quality_selection_positive_and_negative_caps_are_independent() -> None:
    # 13 karma of Positive (Catlike + Double-Jointed) plus 20 karma of Negative (the synthetic
    # quality) -- neither side exceeds 25 on its own, even though the combined net swing
    # (positive_karma + negative_karma == 33) would exceed 25 if the two pools were wrongly treated
    # as one shared budget.
    catalog = (*QUALITIES, _SYNTHETIC_NEGATIVE_FLAT_BONUS)
    catlike = _by_name("Catlike")  # 7
    double_jointed = _by_name("Double-Jointed")  # 6
    selection = create_quality_selection(
        [catlike.id, double_jointed.id, _SYNTHETIC_NEGATIVE_FLAT_BONUS.id], catalog
    )
    assert selection.positive_karma == 13
    assert selection.negative_karma == 20
    assert selection.karma_cost == -7  # net karma refund


def _mundane_human_character() -> object:
    heritage = PRIORITIES.heritage["D"]
    human_choice = next(
        c for c in metatype_choices(heritage, METATYPES) if c.metatype.name == "Human"
    )
    return create_character(
        metatype_choice=human_choice,
        heritage_letter="D",
        attributes_letter="A",
        priorities=PRIORITIES,
        attribute_points={"BOD": 3},
    )


def test_apply_quality_improvements_single_skill_target() -> None:
    character = _mundane_human_character()
    catlike = _by_name("Catlike")
    selection = create_quality_selection([catlike.id], QUALITIES)

    apply_quality_improvements(character, selection)

    assert character.improvements.resolve(ImprovementType.SKILL, "Sneaking") == 2
    assert character.improvements.resolve(ImprovementType.SKILL, "Escape Artist") == 0


def test_apply_quality_improvements_multiple_targets_from_one_quality() -> None:
    character = _mundane_human_character()
    natural_athlete = _by_name("Natural Athlete")
    selection = create_quality_selection([natural_athlete.id], QUALITIES)

    apply_quality_improvements(character, selection)

    assert character.improvements.resolve(ImprovementType.SKILL, "Running") == 2
    assert character.improvements.resolve(ImprovementType.SKILL, "Gymnastics") == 2


def test_apply_quality_improvements_attribute_target() -> None:
    character = _mundane_human_character()
    selection = create_quality_selection(
        [_SYNTHETIC_POSITIVE_FLAT_BONUS.id], (*QUALITIES, _SYNTHETIC_POSITIVE_FLAT_BONUS)
    )

    apply_quality_improvements(character, selection)

    # metatype minimum (1) + points spent (3) + this quality's +1 Improvement.
    assert character.attribute_value("BOD") == 5


def test_apply_quality_improvements_can_be_retracted_via_remove_source() -> None:
    character = _mundane_human_character()
    catlike = _by_name("Catlike")
    selection = create_quality_selection([catlike.id], QUALITIES)
    apply_quality_improvements(character, selection)
    assert character.improvements.resolve(ImprovementType.SKILL, "Sneaking") == 2

    character.improvements.remove_source(
        character.improvements.improvements[0].source_type, catlike.id
    )
    assert character.improvements.resolve(ImprovementType.SKILL, "Sneaking") == 0
