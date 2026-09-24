"""WP94: the Matrix stat block on gear this project was already selling.

Commlinks, cyberdecks and rigger command consoles have been purchasable since WP21, with
`<devicerating>`/`<attack>`/`<sleaze>`/`<dataprocessing>`/`<firewall>`/`<programs>`/
`<attributearray>` discarded at load time -- a player could buy a Fairlight Excalibur and see a
line item and a price (Implementation Plan, Phase P, WP90 section 3). These tests pin the two
halves of closing that: the stat block reaches the character sheet, and the Availability<=12
ruling now applies to those three categories.

The catalog-side assertions (which rows the cap removes, every printed stat asserted against the
p. 267/438/439 tables) live in `tests/unit/test_gear.py`; this module covers only what the browser
actually renders.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from chummer5.data.metatypes import load_metatypes
from chummer5.data.priorities import load_priorities
from chummer5.engine.character import metatype_choices
from chummer5.engine.resources import STARTER_GEAR_CATALOG, StarterGearItem
from chummer5.web.app import create_app
from chummer5.web.routes.resources import matrix_stat_block

METATYPES = load_metatypes()
PRIORITIES = load_priorities()


def _confirm_human_with_resources_a(client: TestClient) -> None:
    """Resources A (450,000 nuyen) -- unlike the D used elsewhere, it affords a cyberdeck and an
    RCC and a commlink in one selection, which is the point of this module.
    """
    client.get("/")
    heritage = PRIORITIES.heritage["B"]
    human_choice = next(
        c for c in metatype_choices(heritage, METATYPES) if c.metatype.name == "Human"
    )
    response = client.post(
        "/ui/priorities",
        data={
            "heritage_letter": "B",
            "attributes_letter": "C",
            "skills_letter": "D",
            "resources_letter": "A",
            "talent_letter": "E",
            "metatype_id": human_choice.metatype.id,
        },
    )
    assert response.status_code == 200


def _catalog_item(name: str) -> StarterGearItem:
    return next(item for item in STARTER_GEAR_CATALOG if item.name == name)


def test_character_sheet_renders_each_category_s_printed_stat_block() -> None:
    client = TestClient(create_app())
    _confirm_human_with_resources_a(client)

    response = client.post(
        "/ui/resources",
        data={
            "gear_Meta Link": "1",
            "gear_Erika MCD-1": "1",
            "gear_Scratch-Built Junk": "1",
        },
    )
    assert response.status_code == 200

    sheet = client.get("/character/sheet")
    assert sheet.status_code == 200
    # A commlink has only Data Processing and Firewall (p. 226); both equal its Device Rating.
    assert "Device Rating 1, Data Processing 1, Firewall 1" in sheet.text
    # A cyberdeck prints its assignable array and program count (p. 439), not four labelled
    # attributes -- and no separate DP/Firewall, since those are two of the four in the array.
    assert "Device Rating 1, Attribute Array 4 3 2 1, Programs 1" in sheet.text
    # An RCC prints Device Rating, Data Processing and Firewall (p. 267). Its `<programs>` value
    # is Chummer-supplied (the printed table has no such column), so it is deliberately not shown.
    assert "Device Rating 1, Data Processing 3, Firewall 2" in sheet.text
    assert "Programs 1, " not in sheet.text


def test_ordinary_gear_still_renders_as_a_plain_line() -> None:
    client = TestClient(create_app())
    _confirm_human_with_resources_a(client)

    client.post("/ui/resources", data={"gear_Ares Predator V": "1"})

    sheet = client.get("/character/sheet")
    assert "Ares Predator V" in sheet.text
    assert "Device Rating" not in sheet.text


def test_matrix_stat_block_is_scoped_to_the_three_device_categories() -> None:
    # 21 other flat rows (RFID tags, credsticks, accessories) carry a <devicerating> but print no
    # stat block in any gear table -- WP94 renders nothing for them.
    credstick = _catalog_item("Certified Credstick, Standard")
    assert credstick.device_rating is not None
    assert matrix_stat_block(credstick) is None
    assert matrix_stat_block(_catalog_item("Ares Predator V")) is None
    assert matrix_stat_block(_catalog_item("Meta Link")) is not None


def test_over_cap_matrix_devices_are_not_offered_by_the_picker() -> None:
    client = TestClient(create_app())
    _confirm_human_with_resources_a(client)

    page = client.get("/ui/page/equipment")

    assert "Transys Avalon" in page.text  # avail 12, exactly on the cap
    for name in (
        "Fairlight Caliban",
        "Shiawase Cyber-5",
        "Fairlight Excalibur",
        "Lone Star Remote Commander",
        "MCT Drone Web",
        "Triox UberMensch",
    ):
        assert name not in page.text, name


def test_buying_an_over_cap_matrix_device_is_rejected_by_the_engine() -> None:
    client = TestClient(create_app())
    _confirm_human_with_resources_a(client)

    # The picker no longer renders the field, but the route must not accept it either: an item
    # outside the catalog is simply never parsed into a purchase, so the spend stays 0.
    response = client.post("/ui/resources", data={"gear_Fairlight Excalibur": "1"})

    assert response.status_code == 200
    budget = PRIORITIES.resources["A"].nuyen
    assert f"{budget} / {budget}" in response.text
