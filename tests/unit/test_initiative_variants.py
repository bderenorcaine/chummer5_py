"""WP111: Astral and Matrix initiative (pp. 159, 229-230, 313)."""

from __future__ import annotations

from dataclasses import replace

from chummer5.data.cyberware_subsystems import load_cyberware_entries
from chummer5.data.metatypes import load_metatypes
from chummer5.data.priorities import load_priorities
from chummer5.engine.character import Character, create_character, metatype_choices
from chummer5.engine.cyberware_subsystems import (
    CyberwarePurchaseRequest,
    create_cyberware_tree_selection,
)
from chummer5.engine.derived import (
    astral_initiative,
    initiative_dice,
    initiative_value,
    matrix_vr_initiative,
)
from chummer5.engine.resources import create_resources_selection

METATYPES = load_metatypes()
PRIORITIES = load_priorities()
CYBERWARE = load_cyberware_entries()


def _human(*, magic_type: str | None = None, gear: tuple[str, ...] = ()) -> Character:
    heritage = PRIORITIES.heritage["D"]
    choice = next(c for c in metatype_choices(heritage, METATYPES) if c.metatype.name == "Human")
    character = create_character(
        metatype_choice=choice,
        heritage_letter="D",
        attributes_letter="A",
        priorities=PRIORITIES,
        attribute_points={"INT": 3, "REA": 2},  # INT 4, REA 3
    )
    return replace(
        character,
        magic_type=magic_type,
        resources_selection=create_resources_selection("A", PRIORITIES, gear),
    )


def test_a_magician_with_a_cyberdeck_and_trodes_shows_all_four_rows() -> None:
    character = _human(magic_type="Magician", gear=("Hermes Chariot", "Trodes"))
    assert astral_initiative(character) == 8  # INT 4 x 2
    # Matrix AR is the physical Initiative (p. 229).
    assert (initiative_value(character), initiative_dice(character)) == (7, 1)
    vr = matrix_vr_initiative(character)
    assert vr is not None
    assert vr.device.name == "Hermes Chariot"
    assert vr.from_array and vr.data_processing == 5  # array 5 4 4 2
    assert vr.value == 9
    assert vr.hot_sim


def test_a_mundane_character_with_only_a_commlink_gets_ar_only() -> None:
    character = _human(gear=("Hermes Ikon",))
    assert astral_initiative(character) is None
    assert matrix_vr_initiative(character) is None


def test_a_sim_module_and_trodes_give_cold_sim_from_the_commlink() -> None:
    character = _human(gear=("Hermes Ikon", "Sim Module", "Trodes"))
    vr = matrix_vr_initiative(character)
    assert vr is not None
    assert (vr.device.name, vr.data_processing, vr.from_array) == ("Hermes Ikon", 5, False)
    assert vr.value == 9
    assert not vr.hot_sim


def test_the_hot_sim_module_upgrade_gives_hot_sim() -> None:
    character = _human(gear=("Hermes Ikon", "Sim Module, Hot", "Trodes"))
    vr = matrix_vr_initiative(character)
    assert vr is not None and vr.hot_sim


def test_a_cyberdeck_without_a_neural_interface_cannot_enter_vr() -> None:
    assert matrix_vr_initiative(_human(gear=("Hermes Chariot",))) is None


def test_an_implanted_datajack_is_a_neural_interface() -> None:
    datajack = next(e for e in CYBERWARE if e.name == "Datajack")
    character = _human(gear=("Hermes Chariot",))
    selection = create_cyberware_tree_selection(
        [CyberwarePurchaseRequest(item_id=datajack.id)], CYBERWARE, nuyen_budget=450_000
    )
    character = replace(character, cyberware_selection=selection)
    vr = matrix_vr_initiative(character)
    assert vr is not None and vr.hot_sim


def test_only_a_magician_can_project() -> None:
    """p. 313: "Only characters who are full Magicians can astrally project"."""
    assert astral_initiative(_human(magic_type="Adept")) is None
    assert astral_initiative(_human(magic_type="Aspected Magician")) is None
