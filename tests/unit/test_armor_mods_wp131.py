"""WP131: armor modifications, Clothing's player-entered price, and the other gear WP21 excluded
by cost shape."""

from __future__ import annotations

import json
import re

import pytest
from fastapi.testclient import TestClient

from chummer5.data.metatypes import load_metatypes
from chummer5.data.priorities import load_priorities
from chummer5.engine.armor_mods import ARMOR_MODS, ArmorModPick, mod_problem
from chummer5.engine.character import metatype_choices
from chummer5.engine.resources import STARTER_GEAR_CATALOG, create_resources_selection
from chummer5.web.app import create_app
from chummer5.web.routes.resources import encode_armor_mod_pick

PRIORITIES = load_priorities()
METATYPES = load_metatypes()
MODS = {mod.name: mod for mod in ARMOR_MODS}
CATALOG = {item.name: item for item in STARTER_GEAR_CATALOG}
JACKET = "Armor Jacket"


def _buy(gear: list[str], *mods: ArmorModPick, variable=()):  # type: ignore[no-untyped-def]
    return create_resources_selection(
        "A", PRIORITIES, gear, armor_mods=mods, variable_gear=variable
    )


def test_the_catalog_is_the_fourteen_printed_mods() -> None:
    assert len(MODS) == 14
    assert not any(name.startswith("Liner") for name in MODS)
    fire = MODS["Fire Resistance"]
    assert (fire.capacity_at(2), fire.cost_at(2), fire.availability) == (2, 500, "6")
    assert MODS["Chemical Seal"].capacity_at(1) == 6
    # The Clothing table prints no Capacity column.
    assert MODS["Feedback Clothing"].capacity_at(1) == 0


def test_an_armor_jacket_with_fire_resistance_2_within_capacity() -> None:
    # The plan's acceptance.
    selection = _buy([JACKET], ArmorModPick(JACKET, 0, "Fire Resistance", 2))
    assert selection.nuyen_spent == 1000 + 500
    assert selection.armor_mods[0].capacity == 2
    # Capacity equals the Armor rating: 12 on a jacket.
    with pytest.raises(ValueError, match="needs Capacity 6; Armor Jacket has 4 left"):
        _buy(
            [JACKET],
            ArmorModPick(JACKET, 0, "Fire Resistance", 6),
            ArmorModPick(JACKET, 0, "Chemical Protection", 2),
            ArmorModPick(JACKET, 0, "Insulation", 6),
        )


def test_clothing_at_500() -> None:
    # The plan's other acceptance: Clothing at a price the player enters, 20-100,000¥.
    assert CATALOG["Clothing"].price_range == (20, 100000)
    selection = _buy([], variable=[("Clothing", 500)])
    assert selection.nuyen_spent == 500
    assert selection.variable_gear == (("Clothing", 500),)
    with pytest.raises(ValueError, match="between 20 and 100000"):
        _buy([], variable=[("Clothing", 10)])
    with pytest.raises(ValueError, match="needs a price"):
        _buy(["Clothing"])


def test_what_goes_where() -> None:
    def problem(mod: str, armor: str, rating: int = 1, on=()):  # type: ignore[no-untyped-def]
        return mod_problem(MODS[mod], armor, rating, on, 12)

    # (Synth)Leather is a Clothing modification.
    assert problem("(Synth)Leather", "Clothing") is None
    assert problem("(Synth)Leather", JACKET) is not None
    # Shields take three mods; a helmet takes none (its Capacity is for gear).
    assert problem("Fire Resistance", "Riot Shield") is None
    assert problem("Insulation", "Riot Shield") == (
        "a shield takes only Chemical Protection, Fire Resistance, Nonconductivity"
    )
    assert problem("Fire Resistance", "Helmet") == "Helmet takes no armor modifications"
    # A sub-row goes only on its armor.
    assert problem("Urban Explorer Jumpsuit: Helmet", JACKET) is not None
    assert problem("Full Body Armor: Helmet", JACKET) == (
        "Full Body Armor: Helmet goes only on Full Body Armor"
    )
    # p. 437: the chemical seal needs full body armor with its helmet.
    assert "needs Full Body Armor with its helmet" in (
        problem("Chemical Seal", "Full Body Armor") or ""
    )
    # Availability: a `+N` adds to the armor's (Full Body Armor is 14R already).
    assert "exceeds" in (
        problem("Full Body Armor: Environment Adaptation", "Full Body Armor") or ""
    )
    assert problem("Electrochromic Clothing", "Clothing") is None  # 0 + 2
    # One of each per copy.
    selection = _buy([JACKET], ArmorModPick(JACKET, 0, "Shock Frills"))
    assert problem("Shock Frills", JACKET, on=selection.armor_mods) == (
        "Armor Jacket already has Shock Frills"
    )


def test_the_chemical_seal_after_the_full_helmet() -> None:
    fba = "Full Body Armor"
    selection = _buy(
        [fba],
        ArmorModPick(fba, 0, "Full Body Armor: Helmet"),
        ArmorModPick(fba, 0, "Chemical Seal"),
    )
    assert [m.name for m in selection.armor_mods] == ["Full Body Armor: Helmet", "Chemical Seal"]
    assert selection.nuyen_spent == 2000 + 500 + 3000


def test_the_agent_and_the_maglock_options() -> None:
    agent = CATALOG["Agent"]
    # p. 246: Rating x 1,000¥ to 3, Rating x 2,000¥ from 4; Availability Rating x 3 caps it at 4.
    assert agent.max_rating == 4
    selection = create_resources_selection("A", PRIORITIES, [], rating_gear=[("Agent", 4)])
    assert selection.nuyen_spent == 8000
    assert "Custom Commlink" not in CATALOG
    assert CATALOG["Card Reader"].cost == 50
    assert CATALOG["Anti-Tamper Circuits"].max_rating == 4
    assert CATALOG["Anti-Tamper Circuits"].cost_at(3) == 750


def _new_character(client: TestClient) -> None:
    client.get("/")
    human = next(
        c
        for c in metatype_choices(PRIORITIES.heritage["B"], METATYPES)
        if c.metatype.name == "Human"
    )
    client.post(
        "/ui/priorities",
        data={
            "heritage_letter": "B",
            "attributes_letter": "C",
            "skills_letter": "D",
            "resources_letter": "A",
            "talent_letter": "E",
            "metatype_id": human.metatype.id,
        },
    )


def test_the_resources_page_the_save_and_the_sheet() -> None:
    client = TestClient(create_app())
    _new_character(client)
    fba = "Full Body Armor"
    helmet = encode_armor_mod_pick(ArmorModPick(fba, 0, "Full Body Armor: Helmet", 1))
    page = client.post("/ui/resources", data={f"gear_{fba}": "1"}).text
    assert f'value="{helmet}"' in page
    client.post("/ui/resources", data={f"gear_{fba}": "1", "add_armor_mod": helmet})
    leather = encode_armor_mod_pick(ArmorModPick("Clothing", 0, "(Synth)Leather", 1))
    page = client.post(
        "/ui/resources",
        data={
            f"gear_{fba}": "1",
            "armor_mod": helmet,
            "gear_Clothing": "1",
            "price_Clothing": "500",
            "add_armor_mod": leather,
        },
    ).text
    assert 'name="price_Clothing" value="500"' in page

    saved = client.get("/character/save").content
    data = json.loads(saved)
    assert data["variable_gear_picks"] == [{"name": "Clothing", "price": 500}]
    assert {m["mod"] for m in data["armor_mods"]} == {"Full Body Armor: Helmet", "(Synth)Leather"}

    fresh = TestClient(create_app())
    fresh.get("/")
    fresh.post("/character/load", files={"save_file": ("c.json", saved, "application/json")})
    sheet = re.sub(r"\s+", " ", fresh.get("/character/sheet").text)
    # Full body armor with its full helmet: 15 + 3 (p. 436).
    assert "18 (Full Body Armor 18)" in sheet
    assert "Full Body Armor #1: Full Body Armor: Helmet" in sheet
    assert "Clothing #1: (Synth)Leather" in sheet
    assert json.loads(fresh.get("/character/save").content)["armor_mods"] == data["armor_mods"]
