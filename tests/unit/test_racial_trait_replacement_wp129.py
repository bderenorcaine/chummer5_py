"""WP129: implants that replace racial traits (p. 94) -- cybereyes and racial vision, skin armor
and a troll's dermal armor."""

from __future__ import annotations

import re
from dataclasses import replace

from fastapi.testclient import TestClient

from chummer5.data.bioware import load_bioware
from chummer5.data.cyberware_subsystems import load_cyberware_entries
from chummer5.data.metatypes import load_metatypes
from chummer5.data.priorities import load_priorities
from chummer5.data.qualities import load_qualities
from chummer5.engine.bioware import (
    BiowarePurchaseRequest,
    apply_bioware_improvements,
    create_bioware_selection,
)
from chummer5.engine.character import Character, create_character, metatype_choices
from chummer5.engine.cyberware_subsystems import (
    CyberwarePurchaseRequest,
    apply_cyberware_tree_improvements,
    create_cyberware_tree_selection,
)
from chummer5.engine.derived import (
    DERMAL_ARMOR_TRAIT,
    SuppressedRacialTrait,
    armor,
    suppressed_racial_traits,
)
from chummer5.engine.qualities import (
    apply_metatype_bonus_improvements,
    resolve_metatype_qualities,
)
from chummer5.web.app import create_app

CYBERWARE = {e.name: e for e in load_cyberware_entries()}
BIOWARE = {b.name: b for b in load_bioware()}
METATYPES = load_metatypes()
PRIORITIES = load_priorities()
QUALITIES = load_qualities()


def _character(metatype: str) -> Character:
    choice = next(
        c
        for c in metatype_choices(PRIORITIES.heritage["A"], METATYPES)
        if c.metatype.name == metatype
    )
    character = create_character(choice, "A", "A", PRIORITIES, {})
    character = replace(
        character, metatype_qualities=resolve_metatype_qualities(character.metatype, QUALITIES)
    )
    apply_metatype_bonus_improvements(character)
    return character


def _eyes(*plugins: str) -> CyberwarePurchaseRequest:
    return CyberwarePurchaseRequest(
        CYBERWARE["Cybereyes Basic System"].id,
        rating=2,
        plugins=tuple(CyberwarePurchaseRequest(CYBERWARE[name].id) for name in plugins),
    )


def _with_cyberware(character: Character, *requests: CyberwarePurchaseRequest) -> Character:
    selection = create_cyberware_tree_selection(requests, CYBERWARE.values(), 10**7)
    character = replace(character, cyberware_selection=selection)
    apply_cyberware_tree_improvements(character, selection)
    return character


def test_cybereyes_remove_an_elfs_low_light_vision() -> None:
    """The plan's acceptance, engine side."""
    elf = _character("Elf")
    assert suppressed_racial_traits(elf) == ()
    assert suppressed_racial_traits(_with_cyberware(elf, _eyes())) == (
        SuppressedRacialTrait("Low-Light Vision", "Cybereyes Basic System"),
    )
    assert suppressed_racial_traits(_with_cyberware(elf, _eyes("Low-Light Vision"))) == ()


def test_the_matching_plugin_is_needed_not_any_plugin() -> None:
    dwarf = _character("Dwarf")
    with_low_light = _with_cyberware(dwarf, _eyes("Low-Light Vision"))
    assert [s.trait for s in suppressed_racial_traits(with_low_light)] == ["Thermographic Vision"]
    assert suppressed_racial_traits(_with_cyberware(dwarf, _eyes("Thermographic Vision"))) == ()


def test_a_human_has_nothing_to_lose() -> None:
    assert suppressed_racial_traits(_with_cyberware(_character("Human"), _eyes())) == ()


def test_orthoskin_replaces_a_trolls_dermal_armor() -> None:
    """p. 94: "orthoskin replaces the natural dermal deposits of a troll so he would no longer
    receive the +1 dermal armor"."""
    troll = _character("Troll")
    base = armor(troll)
    selection = create_bioware_selection(
        [BiowarePurchaseRequest(BIOWARE["Orthoskin"].id, rating=2)], BIOWARE.values(), 10**7
    )
    skinned = replace(troll, bioware_selection=selection)
    apply_bioware_improvements(skinned, selection)
    assert armor(skinned) == base - 1 + 2  # the racial +1 is gone; Orthoskin 2 is there
    assert suppressed_racial_traits(skinned) == (
        SuppressedRacialTrait(DERMAL_ARMOR_TRAIT, "Orthoskin"),
    )


def test_dermal_plating_replaces_it_too() -> None:
    plated = _with_cyberware(
        _character("Troll"), CyberwarePurchaseRequest(CYBERWARE["Dermal Plating"].id, rating=1)
    )
    assert suppressed_racial_traits(plated) == (
        SuppressedRacialTrait(DERMAL_ARMOR_TRAIT, "Dermal Plating"),
    )


def _confirm_elf(client: TestClient) -> None:
    client.get("/")
    elf = next(
        c for c in metatype_choices(PRIORITIES.heritage["B"], METATYPES) if c.metatype.name == "Elf"
    )
    client.post(
        "/ui/priorities",
        data={
            "heritage_letter": "B",
            "attributes_letter": "C",
            "skills_letter": "D",
            "resources_letter": "A",
            "talent_letter": "E",
            "metatype_id": elf.metatype.id,
        },
    )


def test_the_sheet_strikes_the_trait_through_and_the_plugin_restores_it() -> None:
    """The plan's acceptance: an Elf with Cybereyes and no Low-Light plugin loses Low-Light Vision
    on the sheet; adding the plugin restores it."""
    eyes = CYBERWARE["Cybereyes Basic System"]
    low_light = CYBERWARE["Low-Light Vision"]
    client = TestClient(create_app())
    _confirm_elf(client)
    client.post(
        "/ui/cyberware",
        data={f"cyberware_{eyes.id}": "1", f"cyberware_rating_{eyes.id}_0": "2"},
    )
    sheet = re.sub(r"\s+", " ", client.get("/character/sheet").text)
    assert "<s>Low-Light Vision</s> (replaced by Cybereyes Basic System)" in sheet

    client.post(
        "/ui/cyberware",
        data={
            f"cyberware_{eyes.id}": "1",
            f"cyberware_rating_{eyes.id}_0": "2",
            f"plugin_{eyes.id}_0_{low_light.id}": "1",
        },
    )
    sheet = re.sub(r"\s+", " ", client.get("/character/sheet").text)
    assert "<s>Low-Light Vision</s>" not in sheet
    assert "Low-Light Vision" in sheet
