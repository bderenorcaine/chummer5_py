"""Tests for `chummer5.engine.resources` (WP9): contacts, starting nuyen, and starter gear."""

from __future__ import annotations

import pytest

from chummer5.data.metatypes import load_metatypes
from chummer5.data.priorities import load_priorities
from chummer5.engine.character import Character, create_character, metatype_choices
from chummer5.engine.resources import (
    FREE_CONTACT_POINTS_PER_CHARISMA,
    KARMA_PER_EXCESS_CONTACT_POINT,
    STARTER_GEAR_CATALOG,
    Contact,
    ContactSelection,
    ResourcesSelection,
    StarterGearItem,
    create_contact_selection,
    create_resources_selection,
    starting_nuyen,
)

METATYPES = load_metatypes()
PRIORITIES = load_priorities()


def _human_with_cha(points: int) -> Character:
    heritage = PRIORITIES.heritage["D"]
    human = next(c for c in metatype_choices(heritage, METATYPES) if c.metatype.name == "Human")
    return create_character(
        metatype_choice=human,
        heritage_letter="D",
        attributes_letter="A",
        priorities=PRIORITIES,
        attribute_points={"CHA": points},
    )


# --- Contacts ---------------------------------------------------------------------------------


def test_contact_points_sums_connection_and_loyalty() -> None:
    contact = Contact(name="JoJo", connection=3, loyalty=3)
    assert contact.points == 6


def test_contact_points_floored_at_two() -> None:
    # Both Connection and Loyalty are already >=1 by the core rulebook's own minimum, so the floor
    # of 2 is never actually reached below what 1+1 already gives -- kept for parity with the
    # legacy formula (Contact.cs's ContactPoints), not because MVP can construct a case under it.
    contact = Contact(name="Minimal", connection=1, loyalty=1)
    assert contact.points == 2


def test_free_contact_is_zero_points() -> None:
    contact = Contact(name="Plot Contact", connection=6, loyalty=6, free=True)
    assert contact.points == 0


def test_create_contact_selection_within_free_budget() -> None:
    # Human, CHA points spent = 2 -> metatype minimum (1) + 2 = 3 -> free budget = 3*3 = 9.
    character = _human_with_cha(2)
    assert character.attribute_value("CHA") == 3
    selection = create_contact_selection(character, [Contact(name="JoJo", connection=3, loyalty=3)])
    assert isinstance(selection, ContactSelection)
    assert selection.free_points == 9
    assert selection.points_spent == 6
    assert selection.karma_cost == 0


def test_create_contact_selection_charges_karma_beyond_free_budget() -> None:
    # Yeti-#ffffff2.chum5's own numbers (see spec/worklogs/WP9.md): CHA total 5 -> free budget 15;
    # contacts at (3,3) and (5,4) sum to 6+9=15 -- exactly at budget, no karma owed. Bumped here by
    # one extra contact to actually exercise the excess-karma path.
    character = _human_with_cha(4)  # CHA total_value = 5 -> free budget 15
    assert character.attribute_value("CHA") == 5
    selection = create_contact_selection(
        character,
        [
            Contact(name="JoJo", connection=3, loyalty=3),
            Contact(name="Ralph", connection=5, loyalty=4),
            Contact(name="Extra", connection=2, loyalty=2),
        ],
    )
    assert selection.free_points == 15
    assert selection.points_spent == 19  # 6 + 9 + 4
    assert selection.karma_cost == 4 * KARMA_PER_EXCESS_CONTACT_POINT


def test_create_contact_selection_free_contact_excluded_from_spend() -> None:
    character = _human_with_cha(0)  # CHA total_value = 1 -> free budget 3
    selection = create_contact_selection(
        character, [Contact(name="Plot Hook", connection=6, loyalty=6, free=True)]
    )
    assert selection.points_spent == 0
    assert selection.karma_cost == 0


def test_create_contact_selection_rejects_connection_below_minimum() -> None:
    character = _human_with_cha(0)
    with pytest.raises(ValueError, match="Connection and Loyalty must each be at least"):
        create_contact_selection(character, [Contact(name="Bad", connection=0, loyalty=1)])


def test_create_contact_selection_rejects_loyalty_below_minimum() -> None:
    character = _human_with_cha(0)
    with pytest.raises(ValueError, match="Connection and Loyalty must each be at least"):
        create_contact_selection(character, [Contact(name="Bad", connection=1, loyalty=0)])


def test_create_contact_selection_does_not_reject_over_seven_points_per_contact() -> None:
    # Deliberately not enforced -- Yeti-#ffffff2.chum5 itself has a 9-point contact with no Friends
    # in High Places quality present. See chummer5.engine.resources's module docstring and
    # spec/worklogs/WP9.md.
    character = _human_with_cha(4)
    selection = create_contact_selection(
        character, [Contact(name="Ralph", connection=5, loyalty=4)]
    )
    assert selection.contacts[0].points == 9


def test_create_contact_selection_empty() -> None:
    character = _human_with_cha(0)
    selection = create_contact_selection(character, [])
    assert selection.contacts == ()
    assert selection.points_spent == 0
    assert selection.karma_cost == 0


def test_free_contact_points_per_charisma_constant() -> None:
    # Core rulebook, "Making Connections": free Karma for contacts = Charisma rating x 3.
    assert FREE_CONTACT_POINTS_PER_CHARISMA == 3


# --- Starting nuyen & starter gear -------------------------------------------------------------


def test_starting_nuyen_hand_checked_against_priorities_table() -> None:
    # priorities.xml Standard Resources table: A=450000, B=275000, C=140000, D=50000, E=6000.
    assert starting_nuyen("A", PRIORITIES) == 450000
    assert starting_nuyen("E", PRIORITIES) == 6000


def test_create_resources_selection_within_budget() -> None:
    selection = create_resources_selection(
        letter="E", priorities=PRIORITIES, gear_names=["Meta Link", "Combat Knife"]
    )
    assert isinstance(selection, ResourcesSelection)
    assert selection.nuyen_budget == 6000
    assert selection.nuyen_spent == 400
    assert selection.nuyen_remaining == 5600
    assert selection.gear == (
        StarterGearItem("Meta Link", 100),
        StarterGearItem("Combat Knife", 300),
    )


def test_create_resources_selection_allows_empty_gear() -> None:
    selection = create_resources_selection(letter="E", priorities=PRIORITIES, gear_names=[])
    assert selection.gear == ()
    assert selection.nuyen_spent == 0
    assert selection.nuyen_remaining == 6000


def test_create_resources_selection_allows_repeated_items() -> None:
    selection = create_resources_selection(
        letter="E",
        priorities=PRIORITIES,
        gear_names=["Certified Credstick, Standard", "Certified Credstick, Standard"],
    )
    assert selection.nuyen_spent == 10
    assert len(selection.gear) == 2


def test_create_resources_selection_rejects_unknown_item() -> None:
    with pytest.raises(ValueError, match="not a starter-gear catalog item"):
        create_resources_selection(
            letter="E", priorities=PRIORITIES, gear_names=["Not A Real Item"]
        )


def test_create_resources_selection_rejects_budget_overspend() -> None:
    with pytest.raises(ValueError, match="exceeds Resources priority"):
        create_resources_selection(
            letter="E",
            priorities=PRIORITIES,
            gear_names=[item.name for item in STARTER_GEAR_CATALOG for _ in range(20)],
        )
