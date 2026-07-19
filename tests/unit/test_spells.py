from collections import Counter

from chummer5.data.spells import Spell, load_spells

SPELLS = load_spells()


def test_load_spells_returns_93_sr5_entries() -> None:
    # Implementation Plan's Phase I intro: 93 of spells.xml's 363 raw entries carry source == "SR5".
    assert len(SPELLS) == 93
    assert all(s.source == "SR5" for s in SPELLS)


def test_category_distribution_hand_checked_against_the_raw_xml() -> None:
    counts = Counter(s.category for s in SPELLS)
    assert counts == {
        "Illusion": 19,
        "Combat": 18,
        "Detection": 18,
        "Manipulation": 18,
        "Health": 11,
        "Rituals": 9,
    }


def test_fireball_fields_hand_checked_against_the_raw_xml() -> None:
    fireball = next(s for s in SPELLS if s.name == "Fireball")
    assert fireball == Spell(
        id="9ce1e699-3c30-4184-858b-d5539935ef96",
        name="Fireball",
        category="Combat",
        damage="P",
        duration="I",
        dv="F-1",
        range="LOS (A)",
        type="P",
        descriptor="Indirect, Elemental, Area",
        source="SR5",
        page=284,
    )


def test_manabolt_and_heal_fields_hand_checked_against_the_raw_xml() -> None:
    manabolt = next(s for s in SPELLS if s.name == "Manabolt")
    assert manabolt.category == "Combat"
    assert manabolt.damage == "P"
    assert manabolt.dv == "F-3"
    assert manabolt.range == "LOS"
    assert manabolt.type == "M"

    heal = next(s for s in SPELLS if s.name == "Heal")
    assert heal.category == "Health"
    assert heal.duration == "P"
    assert heal.dv == "F-4"


def test_no_duplicate_ids() -> None:
    ids = [s.id for s in SPELLS]
    assert len(ids) == len(set(ids))
