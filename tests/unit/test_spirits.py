from dataclasses import replace

import pytest

from chummer5.data.metatypes import load_metatypes
from chummer5.data.priorities import load_priorities
from chummer5.data.traditions import load_traditions
from chummer5.engine.character import Character, create_character, metatype_choices
from chummer5.engine.magic import create_magic_selection
from chummer5.engine.spirits import (
    STARTING_KARMA,
    BoundSpirit,
    BoundSpiritSelection,
    create_bound_spirit_selection,
    offered_spirit_types,
)

PRIORITIES = load_priorities()
TRADITIONS = load_traditions()
METATYPES = load_metatypes()

HERMETIC = next(t for t in TRADITIONS if t.name == "Hermetic")
SHAMANIC = next(t for t in TRADITIONS if t.name == "Shamanic")


def _mundane_human(heritage_letter: str = "D", attributes_letter: str = "A") -> Character:
    heritage = PRIORITIES.heritage[heritage_letter]
    human = next(c for c in metatype_choices(heritage, METATYPES) if c.metatype.name == "Human")
    return create_character(
        metatype_choice=human,
        heritage_letter=heritage_letter,
        attributes_letter=attributes_letter,
        priorities=PRIORITIES,
        attribute_points={},
    )


def _magician(*, cha_points: int = 0, tradition_name: str = "Hermetic") -> Character:
    """A Human Magician at Talent letter C (Magic 3, no free-skill grant -- letter A/B both grant
    2 free skills, which would need a real skill catalog and picks just to satisfy `create_magic_
    selection`'s own validation, irrelevant noise for these Bound Spirits tests), Heritage D, with
    `cha_points` spent above the metatype minimum on CHA. Built via `dataclasses.replace` (mirrors
    how the web/save layers attach an already-validated `MagicSelection` onto a `Character`), not
    through any create_* path that doesn't exist for this -- there is no single "create a
    magic-active Character" helper in this engine; every real caller resolves the metatype/attribute
    and magic selections separately and stitches them together the same way this test helper does.
    """
    character = _mundane_human()
    tradition = next(t for t in TRADITIONS if t.name == tradition_name)
    selection = create_magic_selection(
        "C", "Magician", tradition.id, [], PRIORITIES, TRADITIONS, ()
    )
    character = replace(
        character,
        magic_type=selection.magic_type,
        magic_rating=selection.magic_rating,
        tradition=selection.tradition,
        attribute_points={**character.attribute_points, "CHA": cha_points},
    )
    assert character.tradition is not None
    assert character.tradition.name == tradition_name
    return character


# -- offered_spirit_types ---------------------------------------------------------------------


def test_offered_spirit_types_reads_the_traditions_spirit_affinities() -> None:
    assert offered_spirit_types(HERMETIC) == HERMETIC.spirits.offered_types


# -- create_bound_spirit_selection ---------------------------------------------------------------


def test_empty_picks_is_always_fine_even_for_a_non_magician() -> None:
    mundane = _mundane_human()
    selection = create_bound_spirit_selection([], mundane, karma_budget=0)
    assert selection == BoundSpiritSelection(spirits=(), karma_cost=0, karma_budget=0)


def test_rejects_any_pick_without_a_tradition() -> None:
    mundane = _mundane_human()
    with pytest.raises(ValueError, match="require a Magician's tradition"):
        create_bound_spirit_selection(
            [("Spirit of Fire", None, 1)], mundane, karma_budget=STARTING_KARMA
        )


def test_binds_a_single_spirit_within_budget() -> None:
    character = _magician(cha_points=0)
    selection = create_bound_spirit_selection(
        [("Spirit of Fire", None, 3)], character, karma_budget=STARTING_KARMA
    )
    assert selection.karma_cost == 3
    assert selection.karma_budget == STARTING_KARMA
    assert selection.spirits == (
        BoundSpirit(
            spirit_type="Spirit of Fire", force=character.attribute_value("MAG"), services=3
        ),
    )


def test_none_force_defaults_to_the_characters_current_magic_rating() -> None:
    # WP70: a None Force means "default to Magic" -- the UI default and how a pre-WP70 save loads.
    character = _magician()
    assert character.attribute_value("MAG") == 3
    (spirit,) = create_bound_spirit_selection(
        [("Spirit of Air", None, 1)], character, karma_budget=STARTING_KARMA
    ).spirits
    assert spirit.force == 3


def test_binds_at_an_explicit_force_below_magic() -> None:
    # WP70: Force is player-chosen from 1 up to Magic.
    character = _magician()
    assert character.attribute_value("MAG") == 3
    (spirit,) = create_bound_spirit_selection(
        [("Spirit of Air", 1, 2)], character, karma_budget=STARTING_KARMA
    ).spirits
    assert spirit.force == 1


def test_cost_does_not_scale_with_force() -> None:
    # WP70: the chargen cost is a flat 1 Karma per service regardless of Force (rulebook p. 98).
    character = _magician()
    low = create_bound_spirit_selection(
        [("Spirit of Fire", 1, 2)], character, karma_budget=STARTING_KARMA
    )
    high = create_bound_spirit_selection(
        [("Spirit of Fire", 3, 2)], character, karma_budget=STARTING_KARMA
    )
    assert low.karma_cost == high.karma_cost == 2


def test_rejects_force_above_magic_rating() -> None:
    character = _magician()  # Magic 3
    with pytest.raises(ValueError, match="Force must be between 1 and the Magic rating of 3"):
        create_bound_spirit_selection(
            [("Spirit of Fire", 4, 1)], character, karma_budget=STARTING_KARMA
        )


def test_rejects_force_below_one() -> None:
    character = _magician()
    with pytest.raises(ValueError, match="Force must be between 1 and the Magic rating of 3"):
        create_bound_spirit_selection(
            [("Spirit of Fire", 0, 1)], character, karma_budget=STARTING_KARMA
        )


def test_allows_partial_spend() -> None:
    # Mirrors every other create_* function's "doesn't require the full budget to be spent" rule.
    character = _magician()
    selection = create_bound_spirit_selection(
        [("Spirit of Fire", None, 1)], character, karma_budget=STARTING_KARMA
    )
    assert selection.karma_cost == 1


def test_rejects_a_spirit_type_not_offered_by_the_characters_tradition() -> None:
    character = _magician(tradition_name="Hermetic")
    with pytest.raises(ValueError, match="not an offered spirit type"):
        create_bound_spirit_selection(
            [("Spirit of Beasts", None, 1)], character, karma_budget=STARTING_KARMA
        )


def test_shamanic_offers_beasts_not_fire() -> None:
    character = _magician(tradition_name="Shamanic")
    selection = create_bound_spirit_selection(
        [("Spirit of Beasts", None, 1)], character, karma_budget=STARTING_KARMA
    )
    assert selection.spirits[0].spirit_type == "Spirit of Beasts"
    with pytest.raises(ValueError, match="not an offered spirit type"):
        create_bound_spirit_selection(
            [("Spirit of Fire", None, 1)], character, karma_budget=STARTING_KARMA
        )


def test_rejects_services_below_one() -> None:
    character = _magician()
    with pytest.raises(ValueError, match="services must be at least 1"):
        create_bound_spirit_selection(
            [("Spirit of Fire", None, 0)], character, karma_budget=STARTING_KARMA
        )


def test_allows_binding_two_spirits_of_the_same_type() -> None:
    character = _magician(cha_points=2)  # Human CHA min 1 + 2 points = 3, room for 2 spirits
    selection = create_bound_spirit_selection(
        [("Spirit of Fire", None, 1), ("Spirit of Fire", None, 2)],
        character,
        karma_budget=STARTING_KARMA,
    )
    assert len(selection.spirits) == 2
    assert selection.karma_cost == 3


def test_rejects_count_exceeding_charisma() -> None:
    character = _magician(cha_points=0)  # Human CHA min is 1
    with pytest.raises(ValueError, match="exceeding the Charisma limit of 1"):
        create_bound_spirit_selection(
            [("Spirit of Fire", None, 1), ("Spirit of Air", None, 1)],
            character,
            karma_budget=STARTING_KARMA,
        )


def test_rejects_total_karma_exceeding_budget() -> None:
    character = _magician()
    with pytest.raises(ValueError, match="exceeding the available budget of 2"):
        create_bound_spirit_selection([("Spirit of Fire", None, 3)], character, karma_budget=2)


def test_zero_budget_rejects_any_nonzero_pick() -> None:
    character = _magician()
    with pytest.raises(ValueError, match="exceeding the available budget of 0"):
        create_bound_spirit_selection([("Spirit of Fire", None, 1)], character, karma_budget=0)
