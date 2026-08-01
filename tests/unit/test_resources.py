"""Tests for `chummer5.engine.resources` (WP9): contacts, starting nuyen, and starter gear."""

from __future__ import annotations

from dataclasses import replace

import pytest

from chummer5.data.metatypes import load_metatypes
from chummer5.data.priorities import load_priorities
from chummer5.engine.character import (
    STARTING_KARMA,
    Character,
    create_character,
    create_karma_attribute_points,
    metatype_choices,
)
from chummer5.engine.resources import (
    FREE_CONTACT_POINTS_PER_CHARISMA,
    KARMA_PER_EXCESS_CONTACT_POINT,
    KARMA_TO_NUYEN_RATE,
    MAX_KARMA_TO_NUYEN,
    STARTER_GEAR_CATALOG,
    Contact,
    ContactSelection,
    ResourcesSelection,
    StarterGearItem,
    available_nuyen,
    create_contact_selection,
    create_resources_selection,
    karma_to_nuyen,
    resources_gear_args,
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
        StarterGearItem("Meta Link", 100, category="Commlinks"),
        StarterGearItem("Combat Knife", 300, category="Blades"),
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


# --- WP66: Rating-priced gear purchases --------------------------------------------------------


def test_rating_gear_cost_scales_with_chosen_rating() -> None:
    selection = create_resources_selection(
        letter="A",
        priorities=PRIORITIES,
        gear_names=[],
        rating_gear=[("Fake SIN", 4)],
    )
    # Fake SIN unit cost is 2500/rating -> 4 * 2500 = 10000.
    assert selection.nuyen_spent == 10000
    (item,) = selection.gear
    assert item.name == "Fake SIN"
    assert item.rating == 4
    assert item.cost == 10000


def test_rating_gear_repeats_are_quantity() -> None:
    selection = create_resources_selection(
        letter="A",
        priorities=PRIORITIES,
        gear_names=[],
        rating_gear=[("Glasses", 3), ("Glasses", 3)],
    )
    # Glasses unit cost 100/rating * rating 3 = 300, bought twice = 600.
    assert selection.nuyen_spent == 600
    assert len(selection.gear) == 2


def test_rating_gear_rejects_over_max_rating() -> None:
    # Fake SIN's offered max rating is 4 (avail cap), even though its <rating> is 6.
    with pytest.raises(ValueError, match="rating must be between 1 and 4"):
        create_resources_selection(
            letter="A",
            priorities=PRIORITIES,
            gear_names=[],
            rating_gear=[("Fake SIN", 5)],
        )


def test_rating_gear_rejects_zero_rating() -> None:
    with pytest.raises(ValueError, match="rating must be between 1 and"):
        create_resources_selection(
            letter="A",
            priorities=PRIORITIES,
            gear_names=[],
            rating_gear=[("Glasses", 0)],
        )


def test_rating_gear_rejects_flat_item_as_rating_priced() -> None:
    with pytest.raises(ValueError, match="not a Rating-priced starter-gear catalog item"):
        create_resources_selection(
            letter="A",
            priorities=PRIORITIES,
            gear_names=[],
            rating_gear=[("Meta Link", 2)],
        )


def test_rating_gear_counts_against_budget() -> None:
    # Resources E budget is 6000; a rating-6 item at 5000/rating would be 30000 -> overspend.
    with pytest.raises(ValueError, match="exceeds Resources priority"):
        create_resources_selection(
            letter="E",
            priorities=PRIORITIES,
            gear_names=[],
            rating_gear=[("Activesoft", 6)],
        )


def test_resources_gear_args_round_trips_flat_and_rating() -> None:
    selection = create_resources_selection(
        letter="A",
        priorities=PRIORITIES,
        gear_names=["Meta Link"],
        rating_gear=[("Fake SIN", 4), ("Glasses", 2)],
    )
    gear_names, rating_gear = resources_gear_args(selection)
    assert gear_names == ("Meta Link",)
    assert rating_gear == (("Fake SIN", 4), ("Glasses", 2))
    # Feeding the split back in reproduces the same spend.
    rebuilt = create_resources_selection(
        letter="A",
        priorities=PRIORITIES,
        gear_names=gear_names,
        rating_gear=rating_gear,
    )
    assert rebuilt.nuyen_spent == selection.nuyen_spent


# --- Lifestyle (WP20): shared-budget wiring ----------------------------------------------------


def test_create_resources_selection_lifestyle_cost_defaults_to_zero() -> None:
    """Backward-compatibility check: every pre-WP20 call (no `lifestyle_cost` argument) must
    behave identically to before WP20 touched this function.
    """
    selection = create_resources_selection(
        letter="E", priorities=PRIORITIES, gear_names=["Meta Link"]
    )
    assert selection.lifestyle_cost == 0
    assert selection.nuyen_spent == 100
    assert selection.nuyen_remaining == 5900


def test_create_resources_selection_folds_lifestyle_cost_into_remaining() -> None:
    selection = create_resources_selection(
        letter="E", priorities=PRIORITIES, gear_names=["Meta Link"], lifestyle_cost=2000
    )
    assert selection.lifestyle_cost == 2000
    assert selection.nuyen_spent == 100  # gear-only, unchanged meaning
    assert selection.nuyen_remaining == 6000 - 100 - 2000


def test_create_resources_selection_rejects_combined_gear_and_lifestyle_overspend() -> None:
    with pytest.raises(ValueError, match=r"gear \(100\) \+ lifestyle \(6000\)"):
        create_resources_selection(
            letter="E", priorities=PRIORITIES, gear_names=["Meta Link"], lifestyle_cost=6000
        )


def test_create_resources_selection_allows_lifestyle_alone_up_to_budget() -> None:
    selection = create_resources_selection(
        letter="E", priorities=PRIORITIES, gear_names=[], lifestyle_cost=6000
    )
    assert selection.nuyen_remaining == 0


# --- Cyberware (WP34): shared-budget wiring, extending the two-way check to three ---------------


def test_create_resources_selection_cyberware_cost_defaults_to_zero() -> None:
    """Backward-compatibility check: every pre-WP34 call (no `cyberware_cost` argument) must
    behave identically to before WP34 touched this function.
    """
    selection = create_resources_selection(
        letter="E", priorities=PRIORITIES, gear_names=["Meta Link"]
    )
    assert selection.cyberware_cost == 0
    assert selection.nuyen_remaining == 5900


def test_create_resources_selection_folds_cyberware_cost_into_remaining() -> None:
    selection = create_resources_selection(
        letter="E",
        priorities=PRIORITIES,
        gear_names=["Meta Link"],
        lifestyle_cost=2000,
        cyberware_cost=1000,
    )
    assert selection.cyberware_cost == 1000
    assert selection.nuyen_spent == 100  # gear-only, unchanged meaning
    assert selection.nuyen_remaining == 6000 - 100 - 2000 - 1000


def test_create_resources_selection_rejects_combined_gear_lifestyle_and_cyberware_overspend() -> (
    None
):
    with pytest.raises(
        ValueError, match=r"gear \(100\) \+ lifestyle \(2000\) \+ cyberware \(4000\)"
    ):
        create_resources_selection(
            letter="E",
            priorities=PRIORITIES,
            gear_names=["Meta Link"],
            lifestyle_cost=2000,
            cyberware_cost=4000,
        )


def test_create_resources_selection_gear_only_overspend_message_omits_lifestyle_and_cyberware() -> (
    None
):
    """The single-term message (unextended by WP20/WP34/WP45) still reads exactly as it did
    pre-WP20 -- a real regression risk since `lifestyle_cost`/`cyberware_cost`/`bioware_cost` are
    all now folded into one shared `parts` list.
    """
    with pytest.raises(ValueError, match="gear spend .* exceeds Resources priority"):
        create_resources_selection(
            letter="E",
            priorities=PRIORITIES,
            gear_names=[item.name for item in STARTER_GEAR_CATALOG for _ in range(20)],
        )


# --- Bioware (WP45): shared-budget wiring, extending the three-way check to four ----------------


def test_create_resources_selection_bioware_cost_defaults_to_zero() -> None:
    """Backward-compatibility check: every pre-WP45 call (no `bioware_cost` argument) must behave
    identically to before WP45 touched this function.
    """
    selection = create_resources_selection(
        letter="E", priorities=PRIORITIES, gear_names=["Meta Link"]
    )
    assert selection.bioware_cost == 0
    assert selection.nuyen_remaining == 5900


def test_create_resources_selection_folds_bioware_cost_into_remaining() -> None:
    selection = create_resources_selection(
        letter="E",
        priorities=PRIORITIES,
        gear_names=["Meta Link"],
        lifestyle_cost=2000,
        cyberware_cost=1000,
        bioware_cost=500,
    )
    assert selection.bioware_cost == 500
    assert selection.nuyen_spent == 100  # gear-only, unchanged meaning
    assert selection.nuyen_remaining == 6000 - 100 - 2000 - 1000 - 500


def test_create_resources_selection_rejects_combined_four_way_overspend() -> None:
    with pytest.raises(
        ValueError,
        match=r"gear \(100\) \+ lifestyle \(2000\) \+ cyberware \(1000\) \+ bioware \(3000\)",
    ):
        create_resources_selection(
            letter="E",
            priorities=PRIORITIES,
            gear_names=["Meta Link"],
            lifestyle_cost=2000,
            cyberware_cost=1000,
            bioware_cost=3000,
        )


def test_create_resources_selection_bioware_only_overspend_message_omits_others() -> None:
    """`bioware_cost` alone (no lifestyle/cyberware spend) still produces a two-term message, not
    a four-term one with empty middle terms.
    """
    with pytest.raises(ValueError, match=r"gear \(100\) \+ bioware \(6000\)"):
        create_resources_selection(
            letter="E",
            priorities=PRIORITIES,
            gear_names=["Meta Link"],
            bioware_cost=6000,
        )


# --- Karma-to-Nuyen conversion (WP43) ------------------------------------------------------------


def test_karma_to_nuyen_rate() -> None:
    # Core rulebook p. 94: "up to 10 Karma at 2,000 nuyen per Karma point".
    assert karma_to_nuyen(1) == 2000
    assert karma_to_nuyen(10) == 20000
    assert karma_to_nuyen(0) == 0


def test_karma_to_nuyen_rate_constant() -> None:
    assert KARMA_TO_NUYEN_RATE == 2000
    assert MAX_KARMA_TO_NUYEN == 10


def test_karma_to_nuyen_rejects_negative() -> None:
    with pytest.raises(ValueError, match="between 0 and 10"):
        karma_to_nuyen(-1)


def test_karma_to_nuyen_rejects_above_cap() -> None:
    with pytest.raises(ValueError, match="between 0 and 10"):
        karma_to_nuyen(11)


def test_available_nuyen_adds_karma_conversion_to_priority_budget() -> None:
    assert available_nuyen("E", PRIORITIES, karma_converted=0) == 6000
    assert available_nuyen("E", PRIORITIES, karma_converted=10) == 6000 + 20000


def test_create_resources_selection_karma_converted_defaults_to_zero() -> None:
    """Backward-compatibility check: every pre-WP43 call (no `karma_converted` argument) must
    behave identically to before WP43 touched this function.
    """
    selection = create_resources_selection(
        letter="E", priorities=PRIORITIES, gear_names=["Meta Link"]
    )
    assert selection.karma_converted == 0
    assert selection.nuyen_budget == 6000
    assert selection.nuyen_remaining == 5900


def test_create_resources_selection_karma_conversion_tops_up_the_budget_not_the_spend() -> None:
    selection = create_resources_selection(
        letter="E", priorities=PRIORITIES, gear_names=["Meta Link"], karma_converted=5
    )
    assert selection.karma_converted == 5
    # nuyen_budget stays the pure priority-derived number (unchanged meaning, still what legacy
    # import cross-checks against <startingnuyen>) -- only nuyen_remaining reflects the top-up.
    assert selection.nuyen_budget == 6000
    assert selection.nuyen_spent == 100
    assert selection.nuyen_remaining == 6000 + 10000 - 100


def test_create_resources_selection_karma_conversion_enables_an_otherwise_overbudget_buy() -> None:
    # 20000 nuyen alone exceeds Priority E's 6000 budget; 5 Karma converted (10000) still isn't
    # enough, but the full 10 (20000) is.
    with pytest.raises(ValueError, match="exceeds Resources priority"):
        create_resources_selection(
            letter="E",
            priorities=PRIORITIES,
            gear_names=["Meta Link"] * 200,  # 200 * 100 = 20000
            karma_converted=5,
        )
    selection = create_resources_selection(
        letter="E",
        priorities=PRIORITIES,
        gear_names=["Meta Link"] * 200,
        karma_converted=10,
    )
    assert selection.nuyen_remaining == 6000 + 20000 - 20000


def test_create_resources_selection_rejects_karma_conversion_above_the_cap() -> None:
    with pytest.raises(ValueError, match="between 0 and 10"):
        create_resources_selection(
            letter="E", priorities=PRIORITIES, gear_names=[], karma_converted=11
        )


# --- WP89: Karma-to-Nuyen debits the unified Karma ledger ---------------------------------------


def _human_converting(karma_converted: int) -> Character:
    """A bare Human carrying nothing but a Resources selection with `karma_converted` converted."""
    return replace(
        _human_with_cha(0),
        resources_selection=create_resources_selection(
            letter="E", priorities=PRIORITIES, gear_names=[], karma_converted=karma_converted
        ),
    )


def test_karma_conversion_reduces_karma_remaining_by_exactly_the_converted_amount() -> None:
    """Core rulebook p. 94: "players can convert some of their Karma to nuyen ... up to 10 Karma at
    a rate of 2,000 nuyen per Karma point". The Karma is *spent*, so Step Seven ("Spending Your
    Left Over Karma") sees a smaller pool. WP43 deferred this for want of a ledger; WP51 built one.
    """
    assert _human_converting(0).karma_remaining == STARTING_KARMA
    assert _human_converting(4).karma_remaining == STARTING_KARMA - 4
    assert _human_converting(MAX_KARMA_TO_NUYEN).karma_remaining == (
        STARTING_KARMA - MAX_KARMA_TO_NUYEN
    )
    # It's a Karma-point count, not a nuyen figure: the 2,000¥ rate never reaches the ledger.
    assert _human_converting(4).karma_spent == 4


def test_a_step_seven_spend_affordable_before_a_conversion_is_rejected_after_it() -> None:
    """The ordering the ruling turns on: Step Six's conversion happens *before* Step Seven, so it
    takes its Karma off the top. EDG 2 -> 3 costs `new rating x 5` = 15 Karma, which fits the
    unconverted 25-Karma pool and doesn't fit what remains once 20,000¥ worth is converted.
    """
    unconverted = _human_converting(0)
    selection = create_karma_attribute_points(unconverted, {"EDG": 1}, unconverted.karma_remaining)
    assert selection.karma_cost == 15

    converted = _human_converting(MAX_KARMA_TO_NUYEN)
    assert converted.karma_remaining == STARTING_KARMA - MAX_KARMA_TO_NUYEN  # 25 - 10 = 15
    with pytest.raises(ValueError, match="exceeds the Karma budget"):
        create_karma_attribute_points(converted, {"EDG": 2}, converted.karma_remaining)
