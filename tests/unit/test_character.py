from dataclasses import replace
from decimal import Decimal
from types import MappingProxyType

import pytest

from chummer5.data.metatypes import load_metatypes
from chummer5.data.priorities import load_priorities
from chummer5.engine.character import (
    ALLOCATABLE_ATTRIBUTES,
    ATTRIBUTE_KARMA_PER_RATING,
    PRIMARY_ATTRIBUTES,
    SPECIAL_ATTRIBUTES,
    STARTING_KARMA,
    Character,
    KarmaAttributeSelection,
    create_character,
    create_karma_attribute_points,
    karma_advancement_cost,
    metatype_choices,
    sr5_metatypes,
)
from chummer5.engine.foci import FociSelection
from chummer5.engine.improvements import (
    Improvement,
    ImprovementSource,
    ImprovementType,
)
from chummer5.engine.qualities import QualitySelection
from chummer5.engine.resources import ContactSelection
from chummer5.engine.spirits import BoundSpiritSelection

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


def test_magic_character_mag_defaults_to_the_talent_granted_rating_with_zero_points_spent() -> None:
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


def test_magic_character_mag_adds_magic_attribute_points_on_top_of_magic_rating() -> None:
    # Post-WP29 correction: MAG uses the exact same "minimum + points + improvements" shape every
    # other attribute does -- the "minimum" is just Talent-sourced (magic_rating) instead of
    # metatype-sourced. See spec/rulebooks/learnings.md's "Post-WP29 correction" entry.
    human = _human_choice("D")
    character = create_character(
        metatype_choice=human,
        heritage_letter="D",
        attributes_letter="A",
        priorities=PRIORITIES,
        attribute_points={},
    )
    adept = replace(character, magic_type="Adept", magic_rating=4, magic_attribute_points=2)
    assert adept.attribute_value("MAG") == 6
    assert adept.power_points == 6  # Power Points track the *finished* Magic rating, not the raw 4


def test_magic_character_mag_caps_at_the_metatype_maximum_even_with_points_and_improvements() -> (
    None
):
    human = _human_choice("D")
    character = create_character(
        metatype_choice=human,
        heritage_letter="D",
        attributes_letter="A",
        priorities=PRIORITIES,
        attribute_points={},
    )
    adept = replace(character, magic_type="Adept", magic_rating=5, magic_attribute_points=3)
    adept.improvements.add(
        Improvement(
            improvement_type=ImprovementType.ATTRIBUTE,
            target="MAG",
            value=2,
            source_type=ImprovementSource.QUALITY,
            source_id="quality-exceptional-attribute",
        )
    )
    # 5 + 3 + 2 = 10, capped at Human's MAG maximum of 6.
    assert adept.attribute_value("MAG") == 6
    assert adept.power_points == 6


def test_magic_attribute_points_do_not_affect_a_mundane_characters_mag() -> None:
    # A stray magic_attribute_points value (e.g. from a stale save) must never leak into MAG for a
    # Mundane character -- magic_type is None still means "not allocatable at all", not
    # "0 + points".
    human = _human_choice("D")
    character = create_character(
        metatype_choice=human,
        heritage_letter="D",
        attributes_letter="A",
        priorities=PRIORITIES,
        attribute_points={},
    )
    stale = replace(character, magic_attribute_points=3)
    assert stale.magic_type is None
    assert stale.attribute_value("MAG") == 0
    assert stale.power_points == 0


def test_magic_essence_loss_is_zero_with_no_essence_improvements() -> None:
    # Every character buildable before Phase J's cyberware catalog existed had no ESSENCE
    # improvement at all -- zero behavioral drift is the headline acceptance criterion for WP35.
    human = _human_choice("D")
    character = create_character(
        metatype_choice=human,
        heritage_letter="D",
        attributes_letter="A",
        priorities=PRIORITIES,
        attribute_points={},
    )
    adept = replace(character, magic_type="Adept", magic_rating=4)
    assert adept.magic_essence_loss == 0
    assert adept.magic_rating_before_essence_loss == 4
    assert adept.attribute_value("MAG") == 4
    assert adept.power_points == 4


def test_mundane_character_is_unaffected_by_any_amount_of_essence_loss() -> None:
    # Core rulebook p.278's Essence-driven Magic-loss rule only makes sense for a magically active
    # character -- a Mundane character's MAG must stay 0 regardless of how much Essence a stray
    # ESSENCE improvement (e.g. from cyberware) has removed.
    human = _human_choice("D")
    character = create_character(
        metatype_choice=human,
        heritage_letter="D",
        attributes_letter="A",
        priorities=PRIORITIES,
        attribute_points={},
    )
    character.improvements.add(
        Improvement(
            improvement_type=ImprovementType.ESSENCE,
            target="",
            value=0,
            source_type=ImprovementSource.CYBERWARE,
            source_id="cyberware-datajack",
            essence_value=Decimal("-5"),
        )
    )
    assert character.magic_type is None
    assert character.attribute_value("MAG") == 0
    assert character.power_points == 0


def test_essence_loss_reduces_mag_by_the_ceiling_of_essence_lost() -> None:
    # Core rulebook p.278: "For every point (or fraction thereof) of Essence lost, both your
    # current Magic Attribute and your maximum Magic Rating are reduced by one." A fractional loss
    # (1.1 Essence here) still knocks off a full point (2), not a proportional fraction of one.
    human = _human_choice("D")
    character = create_character(
        metatype_choice=human,
        heritage_letter="D",
        attributes_letter="A",
        priorities=PRIORITIES,
        attribute_points={},
    )
    adept = replace(character, magic_type="Adept", magic_rating=6)
    adept.improvements.add(
        Improvement(
            improvement_type=ImprovementType.ESSENCE,
            target="",
            value=0,
            source_type=ImprovementSource.CYBERWARE,
            source_id="cyberware-item",
            essence_value=Decimal("-1.1"),
        )
    )
    assert adept.magic_essence_loss == 2
    assert adept.magic_rating_before_essence_loss == 6
    assert adept.attribute_value("MAG") == 4
    assert adept.power_points == 4  # Power Points track the reduced Magic rating too


def test_essence_loss_floors_mag_at_zero_rather_than_going_negative() -> None:
    human = _human_choice("D")
    character = create_character(
        metatype_choice=human,
        heritage_letter="D",
        attributes_letter="A",
        priorities=PRIORITIES,
        attribute_points={},
    )
    magician = replace(character, magic_type="Magician", magic_rating=2)
    magician.improvements.add(
        Improvement(
            improvement_type=ImprovementType.ESSENCE,
            target="",
            value=0,
            source_type=ImprovementSource.CYBERWARE,
            source_id="cyberware-item",
            essence_value=Decimal("-5.9"),
        )
    )
    assert magician.magic_essence_loss == 6
    assert magician.attribute_value("MAG") == 0


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


# -- karma_spent / karma_remaining (WP51: unified Karma ledger) ---------------------------------


def _base_character() -> Character:
    human = _human_choice("D")
    return create_character(
        metatype_choice=human,
        heritage_letter="D",
        attributes_letter="A",
        priorities=PRIORITIES,
        attribute_points={},
    )


def test_karma_remaining_is_starting_karma_with_nothing_committed() -> None:
    character = _base_character()
    assert character.karma_spent == 0
    assert character.karma_remaining == STARTING_KARMA


def test_karma_remaining_subtracts_quality_and_contact_cost() -> None:
    character = replace(
        _base_character(),
        quality_selection=QualitySelection(
            qualities=(), positive_karma=10, negative_karma=0, karma_cost=10
        ),
        contact_selection=ContactSelection(
            contacts=(), free_points=0, points_spent=3, karma_cost=3
        ),
    )
    assert character.karma_spent == 13
    assert character.karma_remaining == STARTING_KARMA - 13


def test_karma_remaining_sums_all_four_selection_types() -> None:
    # Widens the pre-WP51 provisional_karma_budget's own 4-term sum (WP47) into a single property
    # read directly off the character, rather than every caller re-deriving it by hand.
    character = replace(
        _base_character(),
        quality_selection=QualitySelection(
            qualities=(), positive_karma=5, negative_karma=0, karma_cost=5
        ),
        contact_selection=ContactSelection(
            contacts=(), free_points=0, points_spent=2, karma_cost=2
        ),
        bound_spirit_selection=BoundSpiritSelection(spirits=(), karma_cost=4, karma_budget=0),
        foci_selection=FociSelection(
            picks=(), nuyen_cost=0, karma_cost=6, nuyen_budget=0, karma_budget=0
        ),
    )
    assert character.karma_spent == 5 + 2 + 4 + 6
    assert character.karma_remaining == STARTING_KARMA - 17


def test_karma_remaining_can_exceed_starting_karma_from_net_negative_qualities() -> None:
    # Rulebook's own worked examples (Step Four, character_creation_chapter.md): James ends with 26
    # Karma (19 spent on Positive, 20 gained from Negative -- net -1), Rob with 25 (20 spent, 20
    # gained -- net 0), Kyra with 26 (23 spent, 24 gained -- net -1). QualitySelection.karma_cost is
    # already signed (positive_karma - negative_karma), so karma_remaining reproduces exactly these
    # three totals with no separate "starting Karma" field needed -- see Character's own WP51
    # docstring paragraph.
    james = replace(
        _base_character(),
        quality_selection=QualitySelection(
            qualities=(), positive_karma=19, negative_karma=20, karma_cost=19 - 20
        ),
    )
    rob = replace(
        _base_character(),
        quality_selection=QualitySelection(
            qualities=(), positive_karma=20, negative_karma=20, karma_cost=20 - 20
        ),
    )
    kyra = replace(
        _base_character(),
        quality_selection=QualitySelection(
            qualities=(), positive_karma=23, negative_karma=24, karma_cost=23 - 24
        ),
    )
    assert james.karma_remaining == 26
    assert rob.karma_remaining == 25
    assert kyra.karma_remaining == 26


# -- karma_advancement_cost / create_karma_attribute_points (WP52) ------------------------------


def test_karma_advancement_cost_matches_the_karma_advancement_table_for_attributes() -> None:
    # Hand-checked against the core rulebook's own "KARMA ADVANCEMENT TABLE FOR ATTRIBUTES"
    # (p.106-107, re-confirmed during WP51's own research pass -- spec/rulebooks/learnings.md).
    assert karma_advancement_cost(1, 1, ATTRIBUTE_KARMA_PER_RATING) == 10  # 1 -> 2
    assert karma_advancement_cost(1, 2, ATTRIBUTE_KARMA_PER_RATING) == 25  # 1 -> 3
    assert karma_advancement_cost(4, 1, ATTRIBUTE_KARMA_PER_RATING) == 25  # 4 -> 5
    assert karma_advancement_cost(4, 2, ATTRIBUTE_KARMA_PER_RATING) == 55  # 4 -> 6
    assert karma_advancement_cost(3, 0, ATTRIBUTE_KARMA_PER_RATING) == 0  # no points, no cost


def test_create_karma_attribute_points_raises_edg_at_the_confirmed_karma_cost() -> None:
    # Human, Heritage D: EDG minimum 2, 1 priority point spent (rating 3) -- raising to 4 with
    # Karma costs (3 + 1) x 5 = 20, the exact number Wesson.chum5's own real EDG purchase costs
    # (see tests/integration/test_magic_fixtures.py's WP52 tests for the fixture cross-check).
    character = replace(_base_character(), attribute_points=MappingProxyType({"EDG": 1}))
    assert character.attribute_value("EDG") == 3

    selection = create_karma_attribute_points(character, {"EDG": 1}, karma_budget=25)
    assert selection.points == {"EDG": 1}
    assert selection.karma_cost == 20

    character = replace(character, karma_attribute_selection=selection)
    assert character.attribute_value("EDG") == 4
    assert character.karma_spent == 20
    assert character.karma_remaining == STARTING_KARMA - 20


def test_create_karma_attribute_points_rejects_unallocatable_or_mag() -> None:
    character = _base_character()
    with pytest.raises(ValueError, match="not allocatable in MVP scope"):
        create_karma_attribute_points(character, {"MAG": 1}, karma_budget=25)


def test_create_karma_attribute_points_rejects_negative_spend() -> None:
    character = _base_character()
    with pytest.raises(ValueError, match="must not be negative"):
        create_karma_attribute_points(character, {"EDG": -1}, karma_budget=25)


def test_create_karma_attribute_points_rejects_exceeding_metatype_maximum() -> None:
    # Human EDG range is 2-7; 5 priority points already spent (rating 7, already at max) -- 1 more
    # Karma point would exceed it.
    character = replace(_base_character(), attribute_points=MappingProxyType({"EDG": 5}))
    assert character.attribute_value("EDG") == 7
    with pytest.raises(ValueError, match="exceeds Human's maximum of 7"):
        create_karma_attribute_points(character, {"EDG": 1}, karma_budget=999)


def test_create_karma_attribute_points_rejects_exceeding_the_karma_budget() -> None:
    character = replace(_base_character(), attribute_points=MappingProxyType({"EDG": 1}))
    with pytest.raises(ValueError, match="exceeds the Karma budget of 19"):
        create_karma_attribute_points(character, {"EDG": 1}, karma_budget=19)  # costs 20


def test_create_karma_attribute_points_rejects_a_second_primary_attribute_at_natural_maximum() -> (
    None
):
    # Human BOD/AGI natural maximum is 6; 5 priority points on each (rating 6, already at max) --
    # this mirrors the rulebook's own Step Seven restatement of the Step Two rule ("Only one
    # attribute can be at the natural attribute limit... These rules still apply to when you are
    # spending Karma").
    character = replace(_base_character(), attribute_points=MappingProxyType({"BOD": 5, "STR": 4}))
    assert character.attribute_value("BOD") == 6  # already at Human's natural maximum
    with pytest.raises(ValueError, match="only one Mental or Physical attribute"):
        create_karma_attribute_points(character, {"STR": 1}, karma_budget=999)  # STR 5 -> 6


def test_create_karma_attribute_points_allows_a_lone_attribute_at_natural_maximum() -> None:
    # The complement of the rejection test above: raising exactly one Mental/Physical attribute to
    # its natural maximum, with no other already there, is legal.
    character = replace(_base_character(), attribute_points=MappingProxyType({"STR": 4}))
    selection = create_karma_attribute_points(character, {"STR": 1}, karma_budget=999)
    assert selection.points == {"STR": 1}


def test_create_karma_attribute_points_does_not_retroactively_check_pure_priority_spend() -> None:
    # The scope note this WP's own docstring documents, pinned down as a regression test: a
    # character that already has *two* Mental/Physical attributes at their natural maximum from
    # priority-point spend alone (a state create_character, WP6, has never itself rejected) must
    # not be retroactively blocked by an empty or EDG-only karma_points -- this is exactly what the
    # web layer's submit_attributes calls on every attribute-form submission, including ones that
    # spend no Karma on a Mental/Physical attribute at all, purely to re-validate any already-
    # committed Karma spend.
    character = replace(_base_character(), attribute_points=MappingProxyType({"BOD": 5, "STR": 5}))
    assert character.attribute_value("BOD") == 6
    assert character.attribute_value("STR") == 6

    empty_selection = create_karma_attribute_points(character, {}, karma_budget=25)
    assert empty_selection.points == {}

    edg_only_selection = create_karma_attribute_points(character, {"EDG": 1}, karma_budget=25)
    assert edg_only_selection.points == {"EDG": 1}


def test_karma_attribute_selection_field_defaults_to_none() -> None:
    assert _base_character().karma_attribute_selection is None


def test_karma_attribute_selection_is_a_frozen_dataclass_with_the_expected_fields() -> None:
    selection = KarmaAttributeSelection(points=MappingProxyType({"EDG": 2}), karma_cost=45)
    assert selection.points == {"EDG": 2}
    assert selection.karma_cost == 45
    with pytest.raises(AttributeError):
        selection.karma_cost = 0  # type: ignore[misc]
