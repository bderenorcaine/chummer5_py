from dataclasses import replace
from types import MappingProxyType

import pytest

from chummer5.data.metatypes import load_metatypes
from chummer5.data.priorities import load_priorities
from chummer5.engine.character import (
    ALLOCATABLE_ATTRIBUTES,
    PRIMARY_ATTRIBUTES,
    SPECIAL_ATTRIBUTES,
    Character,
    create_character,
    metatype_choices,
    sr5_metatypes,
)
from chummer5.engine.improvements import (
    Improvement,
    ImprovementSource,
    ImprovementType,
)

METATYPES = load_metatypes()
PRIORITIES = load_priorities()


def test_sr5_metatypes_filters_to_five_core_metahuman_types() -> None:
    core = sr5_metatypes(METATYPES)
    assert {m.name for m in core} == {"Human", "Elf", "Dwarf", "Ork", "Troll"}
    assert all(m.source == "SR5" for m in core)


def test_metatype_choices_drops_non_sr5_metatypes_from_heritage_list() -> None:
    # Heritage A's raw metatype list (priorities.xml) includes A.I., Centaur, Naga, Sasquatch, and
    # every Shapeshifter variant alongside the 5 core types -- none of those are source == "SR5".
    heritage_a = PRIORITIES.heritage["A"]
    assert any(mt.name == "Centaur" for mt in heritage_a.metatypes)  # sanity: raw data has them

    choices = metatype_choices(heritage_a, METATYPES)
    assert {c.metatype.name for c in choices} == {"Human", "Elf", "Dwarf", "Ork", "Troll"}


def test_metatype_choice_special_attribute_points_hand_checked() -> None:
    # Hand-checked against priorities.xml's Heritage letter D: Human's <value> (special-attribute
    # points) is 3 -- also cross-validated against Yeti-#ffffff2.chum5 in
    # tests/integration/test_character_fixtures.py.
    heritage_d = PRIORITIES.heritage["D"]
    choices = {c.metatype.name: c for c in metatype_choices(heritage_d, METATYPES)}
    assert choices["Human"].special_attribute_points == 3
    assert choices["Human"].karma == 0


def _human_choice(heritage_letter: str = "D") -> object:
    heritage = PRIORITIES.heritage[heritage_letter]
    return next(c for c in metatype_choices(heritage, METATYPES) if c.metatype.name == "Human")


def test_create_character_spends_within_both_budgets() -> None:
    human = _human_choice("D")
    character = create_character(
        metatype_choice=human,
        heritage_letter="D",
        attributes_letter="A",
        priorities=PRIORITIES,
        attribute_points={
            "BOD": 3,
            "AGI": 2,
            "REA": 1,
            "STR": 1,
            "CHA": 4,
            "INT": 4,
            "LOG": 5,
            "WIL": 4,
            "EDG": 3,
        },
    )
    assert isinstance(character, Character)
    # Human's metatype minimum for BOD is 1, so 1 + 3 points spent.
    assert character.attribute_value("BOD") == 4
    assert character.attribute_value("EDG") == 5  # metatype minimum 2 + 3 points spent


def test_create_character_allows_partial_spend() -> None:
    # SR5 doesn't require every priority point to be spent -- an engine invariant would be
    # over-strict; that's a UI nudge, not a rule.
    human = _human_choice("D")
    character = create_character(
        metatype_choice=human,
        heritage_letter="D",
        attributes_letter="A",
        priorities=PRIORITIES,
        attribute_points={"BOD": 1},
    )
    assert character.attribute_value("BOD") == 2
    assert character.attribute_value("AGI") == 1  # unspent -> bare metatype minimum


def test_create_character_rejects_primary_overspend() -> None:
    human = _human_choice("D")
    with pytest.raises(ValueError, match="primary attribute spend"):
        create_character(
            metatype_choice=human,
            heritage_letter="D",
            attributes_letter="E",  # Attributes E's budget is 12
            priorities=PRIORITIES,
            attribute_points={"BOD": 13},
        )


def test_create_character_rejects_special_overspend() -> None:
    human = _human_choice("D")  # Human at Heritage D has 3 special-attribute points
    with pytest.raises(ValueError, match="special attribute spend"):
        create_character(
            metatype_choice=human,
            heritage_letter="D",
            attributes_letter="A",
            priorities=PRIORITIES,
            attribute_points={"EDG": 4},
        )


def test_create_character_rejects_exceeding_metatype_maximum() -> None:
    human = _human_choice("A")  # Heritage A's Human has more special-attribute points to spend
    with pytest.raises(ValueError, match="exceeds Human's maximum"):
        create_character(
            metatype_choice=human,
            heritage_letter="A",
            attributes_letter="A",
            priorities=PRIORITIES,
            # Human EDG range is 2-7; even a legally-affordable spend can't push past the max.
            attribute_points={"EDG": 6},
        )


def test_create_character_rejects_negative_spend() -> None:
    human = _human_choice("D")
    with pytest.raises(ValueError, match="must not be negative"):
        create_character(
            metatype_choice=human,
            heritage_letter="D",
            attributes_letter="A",
            priorities=PRIORITIES,
            attribute_points={"BOD": -1},
        )


def test_create_character_rejects_unallocatable_attribute() -> None:
    human = _human_choice("D")
    with pytest.raises(ValueError, match="not allocatable"):
        create_character(
            metatype_choice=human,
            heritage_letter="D",
            attributes_letter="A",
            priorities=PRIORITIES,
            attribute_points={"MAG": 1},
        )


def test_attribute_value_sums_improvements_on_top_of_points_spent() -> None:
    human = _human_choice("D")
    character = create_character(
        metatype_choice=human,
        heritage_letter="D",
        attributes_letter="A",
        priorities=PRIORITIES,
        attribute_points={"BOD": 3},
    )
    character.improvements.add(
        Improvement(
            improvement_type=ImprovementType.ATTRIBUTE,
            target="BOD",
            value=1,
            source_type=ImprovementSource.QUALITY,
            source_id="quality-toughness",
        )
    )
    assert character.attribute_value("BOD") == 5  # 1 (metatype min) + 3 (spent) + 1 (improvement)


def test_attribute_value_caps_at_metatype_maximum_even_with_improvements() -> None:
    human = _human_choice("D")
    character = create_character(
        metatype_choice=human,
        heritage_letter="D",
        attributes_letter="A",
        priorities=PRIORITIES,
        attribute_points={"BOD": 5},  # Human BOD max is 6: 1 (min) + 5 = already at the cap
    )
    character.improvements.add(
        Improvement(
            improvement_type=ImprovementType.ATTRIBUTE,
            target="BOD",
            value=3,
            source_type=ImprovementSource.QUALITY,
            source_id="quality-toughness",
        )
    )
    assert character.attribute_value("BOD") == 6


def test_allocatable_attribute_constants_partition_primary_and_special() -> None:
    assert set(PRIMARY_ATTRIBUTES).isdisjoint(SPECIAL_ATTRIBUTES)
    assert set(ALLOCATABLE_ATTRIBUTES) == set(PRIMARY_ATTRIBUTES) | set(SPECIAL_ATTRIBUTES)


def test_mundane_character_mag_is_zero_not_metatype_minimum() -> None:
    # WP25: metatypes.xml's own MAG range for every MVP metatype has a minimum of 1 (the raw
    # eligibility range) -- but a Mundane character (magic_type is None, the default) must resolve
    # to 0, not that metatype minimum, since "Talent forced to E" means Mundane never actually has
    # Magic. Regression guard for the special case in `attribute_value`.
    human = _human_choice("D")
    character = create_character(
        metatype_choice=human,
        heritage_letter="D",
        attributes_letter="A",
        priorities=PRIORITIES,
        attribute_points={},
    )
    assert character.attribute_range("MAG").minimum == 1  # sanity: the raw range does allow it
    assert character.attribute_value("MAG") == 0
    assert character.power_points == 0


def test_magic_character_mag_is_the_stored_rating_not_a_formula() -> None:
    human = _human_choice("D")
    character = create_character(
        metatype_choice=human,
        heritage_letter="D",
        attributes_letter="A",
        priorities=PRIORITIES,
        attribute_points={},
    )
    magician = replace(character, magic_type="Magician", magic_rating=6)
    assert magician.attribute_value("MAG") == 6
    assert magician.power_points == 0  # only Adepts get Power Points

    adept = replace(character, magic_type="Adept", magic_rating=4)
    assert adept.attribute_value("MAG") == 4
    assert adept.power_points == 4


def test_character_attribute_points_is_read_only_mapping() -> None:
    human = _human_choice("D")
    character = create_character(
        metatype_choice=human,
        heritage_letter="D",
        attributes_letter="A",
        priorities=PRIORITIES,
        attribute_points={"BOD": 1},
    )
    assert isinstance(character.attribute_points, MappingProxyType)
