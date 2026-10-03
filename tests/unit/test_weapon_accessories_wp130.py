"""WP130: weapon accessories on purchased weapons -- mounts, built-ins, requirements, pricing, and
the save/sheet round trip."""

from __future__ import annotations

import json
import re

import pytest
from fastapi.testclient import TestClient

from chummer5.data.metatypes import load_metatypes
from chummer5.data.priorities import load_priorities
from chummer5.engine.character import metatype_choices
from chummer5.engine.resources import create_resources_selection
from chummer5.engine.weapon_accessories import (
    OFFERED_WEAPON_ACCESSORIES,
    AccessoryPick,
    accessory_problem,
    builtin_accessories,
    free_mounts,
)
from chummer5.web.app import create_app
from chummer5.web.routes.resources import encode_accessory_pick

PRIORITIES = load_priorities()
METATYPES = load_metatypes()
PREDATOR = "Ares Predator V"
BY_NAME = {a.name: a for a in OFFERED_WEAPON_ACCESSORIES}


def _buy(gear: list[str], *picks: AccessoryPick):  # type: ignore[no-untyped-def]
    return create_resources_selection("A", PRIORITIES, gear, weapon_accessories=picks)


def test_the_offered_catalog_is_p_432_plus_the_weapon_specific_rows() -> None:
    names = {a.name for a in OFFERED_WEAPON_ACCESSORIES}
    assert len(names) == 26
    # The four hidden rows are built-ins only.
    assert not names & {"Sound Suppressor", "External Clip Port", "Survival Knife Bonuses"}
    # p. 432 prints 2,500 where the data says 2,000.
    assert BY_NAME["Smart Firing Platform"].cost == 2500
    assert BY_NAME["Laser Sight"].mounts == ("Top", "Under")
    assert BY_NAME["Spare Clip"].mounts == ()


def test_a_predator_with_silencer_and_smartgun_and_no_second_barrel() -> None:
    # The plan's acceptance: the Predator V ships with its internal smartgun (free, no mount).
    assert builtin_accessories(PREDATOR)[0].name == "Smartgun System, Internal"
    assert builtin_accessories(PREDATOR)[0].mount is None
    selection = _buy([PREDATOR], AccessoryPick(PREDATOR, 0, "Silencer/Suppressor"))
    assert selection.nuyen_spent == 725 + 500
    assert selection.weapon_accessories[0].mount == "Barrel"
    assert selection.accessory_picks == (
        AccessoryPick(PREDATOR, 0, "Silencer/Suppressor", "Barrel"),
    )
    with pytest.raises(ValueError, match="Barrel mount is already taken"):
        _buy(
            [PREDATOR],
            AccessoryPick(PREDATOR, 0, "Silencer/Suppressor"),
            AccessoryPick(PREDATOR, 0, "Gas-Vent 2 System"),
        )


def test_built_ins_take_their_mount_first() -> None:
    assert builtin_accessories("Remington 950")[0].mount == "Top"
    assert "Top" not in free_mounts("Remington 950")
    # A Top/Under built-in laser sight takes Top, per "built-in top-mounted laser sight".
    assert builtin_accessories("Browning Ultra-Power")[0].mount == "Top"
    # The Ingram Smartgun X's suppressor and gas-vent both want Barrel: the second takes none.
    ingram = {b.name: b.mount for b in builtin_accessories("Ingram Smartgun X")}
    assert ingram == {
        "Smartgun System, Internal": None,
        "Sound Suppressor": "Barrel",
        "Gas-Vent 2 System": None,
    }


def test_each_copy_has_its_own_mounts_and_a_missing_copy_is_refused() -> None:
    selection = _buy(
        [PREDATOR, PREDATOR],
        AccessoryPick(PREDATOR, 0, "Silencer/Suppressor"),
        AccessoryPick(PREDATOR, 1, "Silencer/Suppressor"),
    )
    assert [i.copy for i in selection.weapon_accessories] == [0, 1]
    with pytest.raises(ValueError, match="no purchased Ares Predator V #2"):
        _buy([PREDATOR], AccessoryPick(PREDATOR, 1, "Silencer/Suppressor"))


def test_top_or_under_goes_where_the_player_says() -> None:
    selection = _buy(["Ares Alpha"], AccessoryPick("Ares Alpha", 0, "Laser Sight", "Under"))
    assert selection.weapon_accessories[0].mount == "Under"
    with pytest.raises(ValueError, match="mount is already taken"):
        _buy(["Ares Predator V"], AccessoryPick(PREDATOR, 0, "Laser Sight", "Under"))


def test_requirements_and_prohibitions() -> None:
    def problem(accessory: str, weapon: str) -> str | None:
        return accessory_problem(BY_NAME[accessory], weapon, [], 12)

    # A duplicate of a built-in is refused.
    assert problem("Smartgun System, Internal", PREDATOR) == f"{PREDATOR} already has " + (
        "Smartgun System, Internal"
    )
    # p. 432: no silencer on a revolver; speed loaders only fit revolvers.
    assert problem("Silencer/Suppressor", "Ruger Super Warhawk") is not None
    assert problem("Speed Loader", "Ruger Super Warhawk") is None
    assert problem("Speed Loader", PREDATOR) is not None
    # p. 431: only pistols and tasers fit a concealable holster -- not a combat knife.
    assert problem("Concealable Holster", PREDATOR) is None
    assert problem("Concealable Holster", "Combat Knife") is not None
    # The airburst link is for grenade and missile launchers.
    assert problem("Airburst Link", "ArmTech MGL-12") is None
    assert problem("Airburst Link", PREDATOR) is not None
    # A mount accessory on a weapon with no such mount.
    assert problem("Bipod", PREDATOR) == f"{PREDATOR} has no Under mount"


def test_the_internal_smartgun_costs_the_weapon_again_within_availability_12() -> None:
    # Ruger Super Warhawk: 400¥, Availability 4R -> the retrofit is 400¥ at Availability 6.
    selection = _buy(
        ["Ruger Super Warhawk"],
        AccessoryPick("Ruger Super Warhawk", 0, "Smartgun System, Internal"),
    )
    assert selection.weapon_accessories[0].cost == selection.gear[0].cost
    # The Ingram Valiant is Availability 12F: +2 would be 14.
    assert "exceeds" in (
        accessory_problem(BY_NAME["Smartgun System, Internal"], "Ingram Valiant", [], 12) or ""
    )


def test_spare_clips_repeat_other_accessories_do_not() -> None:
    selection = _buy(
        [PREDATOR],
        AccessoryPick(PREDATOR, 0, "Spare Clip"),
        AccessoryPick(PREDATOR, 0, "Spare Clip"),
    )
    assert selection.nuyen_spent == 725 + 10
    with pytest.raises(ValueError, match="already has Quick-Draw Holster"):
        _buy(
            [PREDATOR],
            AccessoryPick(PREDATOR, 0, "Quick-Draw Holster"),
            AccessoryPick(PREDATOR, 0, "Quick-Draw Holster"),
        )


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
    page = client.post("/ui/resources", data={f"gear_{PREDATOR}": "1"}).text
    silencer = encode_accessory_pick(AccessoryPick(PREDATOR, 0, "Silencer/Suppressor", "Barrel"))
    assert f'value="{silencer}"' in page
    page = client.post(
        "/ui/resources", data={f"gear_{PREDATOR}": "1", "add_accessory": silencer}
    ).text
    # Installed: a checked box, and no Barrel option left to add.
    assert re.search(rf'name="weapon_accessory" value="{re.escape(silencer)}"\s+checked', page)
    assert "Gas-Vent 2 System (Barrel mount)" not in page

    saved = client.get("/character/save").content
    data = json.loads(saved)
    assert data["weapon_accessories"] == [
        {"weapon": PREDATOR, "copy": 0, "accessory": "Silencer/Suppressor", "mount": "Barrel"}
    ]
    fresh = TestClient(create_app())
    fresh.get("/")
    fresh.post(
        "/characters/upload?open=true",
        files={"files": ("c.json", saved, "application/json")},
    )
    sheet = re.sub(r"\s+", " ", fresh.get("/character/sheet").text)
    assert "Ares Predator V #1: Smartgun System, Internal (built in)," in sheet
    assert "Silencer/Suppressor (Barrel mount)" in sheet
    assert "-4 to Perception Tests to notice the shot" in sheet  # the registry note
    assert (
        json.loads(fresh.get("/character/save").content)["weapon_accessories"]
        == (data["weapon_accessories"])
    )

    # Selling the weapon drops its accessories with it instead of blocking the change.
    client.post("/ui/resources", data={f"gear_{PREDATOR}": "0", "weapon_accessory": silencer})
    data = json.loads(client.get("/character/save").content)
    assert data["weapon_accessories"] == []
    assert data["gear_names"] == []
