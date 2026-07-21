"""Tests for `chummer5.data.bioware` (WP45's bioware loader). See that module's docstring for the
full flat-cost/flat-Essence/low-Availability filter and `<bonus>`-classification reasoning this
file exercises.
"""

from __future__ import annotations

from decimal import Decimal

from chummer5.data.bioware import Bioware, BiowareFlatBonus, count_by_support, load_bioware
from chummer5.data.cyberware import BonusSupport

BIOWARE = load_bioware()


def test_loads_exactly_the_confirmed_flat_low_availability_count() -> None:
    # legacy/Chummer/data/bioware.xml has 213 <bioware> entries total; 23 are source == "SR5"; of
    # those, 8 have both a bare-integer <cost> and a bare-decimal <ess>; of those 8, 2 exceed
    # Availability 12 (Pain Editor 18F, Suprathyroid Gland 20R) -- see module docstring.
    assert len(BIOWARE) == 6
    assert all(b.source == "SR5" for b in BIOWARE)
    assert all(b.availability <= 12 for b in BIOWARE)


def test_no_duplicate_ids_or_names() -> None:
    ids = [b.id for b in BIOWARE]
    assert len(ids) == len(set(ids))
    names = [b.name for b in BIOWARE]
    assert len(names) == len(set(names))


def test_excludes_rating_scaled_items() -> None:
    # Mnemonic Enhancer/Cerebral Booster/etc. all have a "Rating * N" cost/Essence formula.
    names = {b.name for b in BIOWARE}
    assert "Mnemonic Enhancer" not in names
    assert "Cerebral Booster" not in names
    assert "Muscle Toner" not in names


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


def test_reflex_recorder_is_not_yet_supported() -> None:
    # <bonus><selectskill limittoattribute="BOD,AGI,REA,STR"><val>1</val></selectskill></bonus> --
    # a player-selected skill bonus, structurally different from <specificskill>'s fixed-name shape.
    item = next(b for b in BIOWARE if b.name == "Reflex Recorder")
    assert item.bonus_support == BonusSupport.NOT_YET_SUPPORTED
    assert item.flat_bonuses == ()
    assert item.raw_bonus is not None


def test_supported_vs_unsupported_counts_are_visible() -> None:
    # FLAT_BONUS: Enhanced Articulation. NOT_YET_SUPPORTED: Reflex Recorder. NO_EFFECT: the other 4.
    counts = count_by_support(BIOWARE)
    assert counts[BonusSupport.FLAT_BONUS] == 1
    assert counts[BonusSupport.NOT_YET_SUPPORTED] == 1
    assert counts[BonusSupport.NO_EFFECT] == 4
    assert sum(counts.values()) == 6


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
