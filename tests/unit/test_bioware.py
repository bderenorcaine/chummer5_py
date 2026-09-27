"""Tests for `chummer5.data.bioware` (WP45's bioware loader). See that module's docstring for the
full flat-cost/flat-Essence/low-Availability filter and `<bonus>`-classification reasoning this
file exercises.
"""

from __future__ import annotations

from decimal import Decimal

from chummer5.data.bioware import (
    Bioware,
    BiowareFlatBonus,
    BiowareSelectSkillBonus,
    count_by_support,
    load_bioware,
)
from chummer5.data.cyberware import BonusSupport

BIOWARE = load_bioware()


def test_loads_exactly_the_confirmed_flat_low_availability_count() -> None:
    # legacy/Chummer/data/bioware.xml has 213 <bioware> entries total; 23 are source == "SR5"; of
    # those, 8 have both a bare-integer <cost> and a bare-decimal <ess>; of those 8, 2 exceed
    # Availability 12 (Pain Editor 18F, Suprathyroid Gland 20R) -- see module docstring.
    # WP128: plus all 15 rated SR5 rows, each within Availability 12 at rating 1.
    assert len([b for b in BIOWARE if not b.is_rated]) == 6
    assert len(BIOWARE) == 21
    assert all(b.source == "SR5" for b in BIOWARE)
    assert all(b.availability <= 12 for b in BIOWARE)


def test_no_duplicate_ids_or_names() -> None:
    ids = [b.id for b in BIOWARE]
    assert len(ids) == len(set(ids))
    names = [b.name for b in BIOWARE]
    assert len(names) == len(set(names))


def test_includes_rating_scaled_items() -> None:
    # WP128: Mnemonic Enhancer/Cerebral Booster/etc. carry a "Rating * N" cost/Essence formula,
    # resolved per purchase. (WP45 excluded them.)
    rated = {b.name: b for b in BIOWARE if b.is_rated}
    assert {"Mnemonic Enhancer", "Cerebral Booster", "Muscle Toner"} <= set(rated)
    assert rated["Cerebral Booster"].cost_at(2) == 63000
    assert rated["Cerebral Booster"].essence_at(3) == Decimal("0.6")


def test_excludes_high_availability_items() -> None:
    # Pain Editor (18F) and Suprathyroid Gland (20R) are otherwise-flat SR5 items excluded solely
    # by the Availability > 12 filter (Project Overview's 2026-07-21 ruling).
    names = {b.name for b in BIOWARE}
    assert "Pain Editor" not in names
    assert "Suprathyroid Gland" not in names


def test_hand_checked_fields_match_the_raw_xml() -> None:
    by_name = {b.name: b for b in BIOWARE}
    cats_eyes = by_name["Cat's Eyes"]
    assert cats_eyes.category == "Basic"
    assert cats_eyes.cost == 4000
    assert cats_eyes.essence_cost == Decimal("0.1")
    assert cats_eyes.availability == 4
    assert cats_eyes.bonus_support == BonusSupport.NO_EFFECT

    sleep_regulator = by_name["Sleep Regulator"]
    assert sleep_regulator.category == "Cultured"
    assert sleep_regulator.cost == 12000
    assert sleep_regulator.essence_cost == Decimal("0.1")
    assert sleep_regulator.availability == 6


def test_no_effect_items_verified_moot_no_hardcoded_engine_hook() -> None:
    # Cat's Eyes, Platelet Factories, Skin Pocket, Sleep Regulator all have an absent <bonus> --
    # verified via a `grep` of the legacy C# turning up no by-name special-casing for any of the 4
    # (see module docstring), mirroring chummer5.data.cyberware's identical "no name-gate needed"
    # reasoning.
    by_name = {b.name: b for b in BIOWARE}
    for name in ("Cat's Eyes", "Platelet Factories", "Skin Pocket", "Sleep Regulator"):
        item = by_name[name]
        assert item.bonus_support == BonusSupport.NO_EFFECT
        assert item.flat_bonuses == ()
        assert item.raw_bonus is None


def test_enhanced_articulation_has_two_distinct_flat_bonus_shapes() -> None:
    # <bonus><physicallimit>1</physicallimit><specificskill><name>Escape Artist</name>
    # <bonus>1</bonus></specificskill></bonus> -- both shapes already recognized by
    # chummer5.data.qualities' identical grammar, reused here (see module docstring).
    item = next(b for b in BIOWARE if b.name == "Enhanced Articulation")
    assert item.bonus_support == BonusSupport.FLAT_BONUS
    assert item.flat_bonuses == (
        BiowareFlatBonus(target_kind="physical_limit", target_name="", value=1),
        BiowareFlatBonus(target_kind="skill", target_name="Escape Artist", value=1),
    )


def test_reflex_recorder_is_a_select_skill_bonus() -> None:
    # <bonus><selectskill limittoattribute="BOD,AGI,REA,STR"><val>1</val></selectskill></bonus> --
    # a player-selected skill bonus, structurally different from <specificskill>'s fixed-name shape.
    # WP80 gave it its own BonusSupport value (it was NOT_YET_SUPPORTED from WP45 until then): the
    # catalog records that a pick is required and what it may be, never the pick itself.
    item = next(b for b in BIOWARE if b.name == "Reflex Recorder")
    assert item.bonus_support == BonusSupport.SELECT_SKILL
    assert item.select_skill_bonus == BiowareSelectSkillBonus(
        value=1, limit_to_attributes=("BOD", "AGI", "REA", "STR")
    )
    assert item.flat_bonuses == ()
    assert item.raw_bonus is not None


def test_reflex_recorder_is_the_only_select_skill_row() -> None:
    # Shape-gated rather than name-gated (see chummer5.data.bioware's docstring), so this pins that
    # the shape is as narrow as claimed -- one row in either augmentation catalog.
    assert [b.name for b in BIOWARE if b.bonus_support == BonusSupport.SELECT_SKILL] == [
        "Reflex Recorder"
    ]


def test_supported_vs_unsupported_counts_are_visible() -> None:
    # FLAT_BONUS: Enhanced Articulation. SELECT_SKILL: Reflex Recorder (WP80; NOT_YET_SUPPORTED
    # before that). NO_EFFECT: the other 4 -- no row is unsupported at all any more. WP128's rated
    # rows: 10 FLAT_BONUS, and 5 NO_EFFECT once their registered children are stripped.
    counts = count_by_support(BIOWARE)
    assert counts[BonusSupport.FLAT_BONUS] == 1 + 10
    assert counts[BonusSupport.SELECT_SKILL] == 1
    assert counts[BonusSupport.NOT_YET_SUPPORTED] == 0
    assert counts[BonusSupport.NO_EFFECT] == 4 + 5
    assert sum(counts.values()) == 21


def test_bioware_fields_hand_checked_against_the_raw_xml() -> None:
    cats_eyes = next(b for b in BIOWARE if b.name == "Cat's Eyes")
    assert cats_eyes == Bioware(
        id="f038260b-f2de-4a9a-9507-5602d0e64a22",
        name="Cat's Eyes",
        category="Basic",
        cost=4000,
        essence_cost=Decimal("0.1"),
        availability=4,
        source="SR5",
        page=459,
        bonus_support=BonusSupport.NO_EFFECT,
        flat_bonuses=(),
        raw_bonus=None,
    )
