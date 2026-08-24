"""WP95: the unmodeled-effect registry reaches the player for the rigger surface.

Project Overview's "Unmodeled real effects" table is documentation; `unmodeled_effect_note` on a
catalog dataclass is what a player actually sees, collected by
`chummer5.engine.derived.unmodeled_effect_notes` into the character sheet's collapsible section.
Before this WP the rigger surface had neither: `Control Rig` (UI-reachable since WP42, a full point
of Essence at rating 1) carried no note and had no registry row, RCCs/cyberdecks/commlinks/autosofts
had no mechanism at all on the gear side, and `vehicle_selection` was not even walked by the
collector.

The catalog-side correspondence (which cyberware rows must carry a note and which must not) is
pinned in `tests/unit/test_augmentation_unmodeled_registry.py`; this module covers what the browser
renders.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from chummer5.data.metatypes import load_metatypes
from chummer5.data.priorities import load_priorities
from chummer5.engine.character import metatype_choices
from chummer5.engine.vehicles import VEHICLE_CATALOG
from chummer5.web.app import create_app
from chummer5.web.catalogs import CYBERWARE_STANDALONE

METATYPES = load_metatypes()
PRIORITIES = load_priorities()

CONTROL_RIG = next(c for c in CYBERWARE_STANDALONE if c.name == "Control Rig")
FLY_SPY = next(v for v in VEHICLE_CATALOG if v.name == "MCT Fly-Spy (Minidrone)")  # 2,000Y, drone
AMERICAR = next(v for v in VEHICLE_CATALOG if v.name == "Ford Americar (Sedan)")  # 16,000Y, vehicle


def _confirm_human_with_resources_a(client: TestClient) -> None:
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


def test_a_rigger_loadout_renders_three_distinct_unmodeled_notes() -> None:
    """WP95's acceptance criterion: a Control Rig, an RCC and a drone, three notes."""
    client = TestClient(create_app())
    _confirm_human_with_resources_a(client)

    client.post(
        "/ui/cyberware",
        data={f"cyberware_{CONTROL_RIG.id}": "1", f"rating_{CONTROL_RIG.id}": "1"},
    )
    client.post("/ui/resources", data={"gear_Scratch-Built Junk": "1"})
    client.post("/ui/vehicles", data={f"vehicle_{FLY_SPY.id}": "1"})

    sheet = client.get("/character/sheet")
    assert sheet.status_code == 200
    assert "Unmodeled real effects (3)" in sheet.text
    # The control rig's whole payload is an in-play, jumped-in limit bonus on a vehicle (p. 266).
    assert "jumped into a vehicle" in sheet.text
    # The RCC's is the Matrix, plus everything an RCC is actually for.
    assert "Device Rating x 3) drones into a WAN" in sheet.text
    # The drone's is Vehicle Tests plus the rigger-interface half of the p. 265 gap.
    assert "ships with its rigger interface built in" in sheet.text


def test_a_bought_vehicle_says_it_cannot_be_jumped_into() -> None:
    """The display half of WP90 section 1: under the no-modifications ruling a *vehicle* is one no
    rigger can use, because p. 265's Rigger Interface is a modification. Drones differ, so the two
    notes must not be the same string."""
    client = TestClient(create_app())
    _confirm_human_with_resources_a(client)

    client.post("/ui/vehicles", data={f"vehicle_{AMERICAR.id}": "1"})

    sheet = client.get("/character/sheet")
    assert "Unmodeled real effects (1)" in sheet.text
    assert "cannot be jumped into as bought" in sheet.text
    assert "ships with its rigger interface built in" not in sheet.text


def test_a_fleet_of_one_model_contributes_one_note() -> None:
    client = TestClient(create_app())
    _confirm_human_with_resources_a(client)

    client.post("/ui/vehicles", data={f"vehicle_{FLY_SPY.id}": "4", f"vehicle_{AMERICAR.id}": "1"})

    sheet = client.get("/character/sheet")
    # Two distinct models, five vehicles -- `unmodeled_effect_notes` dedupes by name.
    assert "Unmodeled real effects (2)" in sheet.text


def test_gear_outside_the_four_annotated_categories_contributes_nothing() -> None:
    client = TestClient(create_app())
    _confirm_human_with_resources_a(client)

    client.post("/ui/resources", data={"gear_Ares Predator V": "1"})

    sheet = client.get("/character/sheet")
    assert "Unmodeled real effects" not in sheet.text


def test_an_autosoft_carries_the_drone_skill_note() -> None:
    """Autosofts are Rating-priced, so their note rides `load_rating_gear`, not `load_gear` --
    the one place the two loaders had to be changed identically."""
    client = TestClient(create_app())
    _confirm_human_with_resources_a(client)

    client.post(
        "/ui/resources",
        data={"gear_Clearsight Autosoft": "1", "rating_Clearsight Autosoft": "3"},
    )

    sheet = client.get("/character/sheet")
    assert "Unmodeled real effects (1)" in sheet.text
    assert "<strong>Clearsight Autosoft</strong>" in sheet.text
    assert "no autosoft slot accounting" in sheet.text
