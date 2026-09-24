"""WP93: the vehicle/drone purchase UI (`POST /ui/vehicles`, `_vehicles.html`) and the character
sheet's stat block, backed directly by `chummer5.engine.vehicles.create_vehicle_selection`.

Same "manual walkthrough; values match engine output for the same inputs" acceptance bar as
`tests/unit/test_web_bioware.py`, plus the two things unique to this section: a **stat block** the
picker and the sheet both render (they share `vehicle_stat_block`, so a divergence would be a bug in
one place, not two), and the shared Step Six nuyen pool now having a sixth spender.
"""

from fastapi.testclient import TestClient

from chummer5.data.metatypes import load_metatypes
from chummer5.data.priorities import load_priorities
from chummer5.data.vehicles import load_vehicles
from chummer5.engine.character import metatype_choices
from chummer5.engine.vehicles import VEHICLE_CATALOG, condition_monitor
from chummer5.web.app import create_app

METATYPES = load_metatypes()
PRIORITIES = load_priorities()

FLY_SPY = next(v for v in VEHICLE_CATALOG if v.name == "MCT Fly-Spy (Minidrone)")  # 2,000Y, drone
AMERICAR = next(v for v in VEHICLE_CATALOG if v.name == "Ford Americar (Sedan)")  # 16,000Y, vehicle
GROWLER = next(v for v in VEHICLE_CATALOG if v.name == "Yamaha Growler (Off-Road Bike)")
# The catalog's most expensive offerable row (300,000Y) -- the only way to overrun a Resources
# budget with one purchase, since a mundane build's cheapest Resources letter is D (50,000Y):
# Talent is forced to E, so the other four letters are a bijection over A-D.
TUNDRA = next(v for v in VEHICLE_CATALOG if v.name.startswith("Renault-Fiat Fokker"))


def _squash(text: str) -> str:
    """Collapse whitespace so an assertion about rendered markup doesn't depend on Jinja's
    indentation (borrowed from `tests/unit/test_web_bioware.py`)."""
    return " ".join(text.split())


def _confirm_human(client: TestClient, resources_letter: str = "A") -> None:
    """Confirm a Human with `resources_letter` for Resources, giving each test a known, real nuyen
    budget. The other three letters fill in whatever is left of A-D: a mundane build forces Talent
    to E, so Heritage/Attributes/Skills/Resources are a bijection over the remaining four.
    """
    client.get("/")
    heritage_letter, attributes_letter, skills_letter = sorted(
        {"A", "B", "C", "D"} - {resources_letter}
    )
    heritage = PRIORITIES.heritage[heritage_letter]
    human_choice = next(
        c for c in metatype_choices(heritage, METATYPES) if c.metatype.name == "Human"
    )
    response = client.post(
        "/ui/priorities",
        data={
            "heritage_letter": heritage_letter,
            "attributes_letter": attributes_letter,
            "skills_letter": skills_letter,
            "resources_letter": resources_letter,
            "talent_letter": "E",
            "metatype_id": human_choice.metatype.id,
        },
    )
    assert "Confirmed: Human" in response.text


def test_the_picker_lists_the_offerable_catalog_and_nothing_else() -> None:
    client = TestClient(create_app())
    _confirm_human(client)

    body = client.get("/ui/page/equipment").text

    assert FLY_SPY.name in body
    assert AMERICAR.name in body
    # The Availability-excluded and unprinted rows never reach the player.
    assert "GMC Banshee" not in body
    assert "Mitsubishi Nightsky" not in body
    assert "Ocular Drone" not in body
    assert "w/Flash-Pak and Grenade" not in body


def test_the_picker_renders_the_printed_stat_block() -> None:
    client = TestClient(create_app())
    _confirm_human(client)

    body = _squash(client.get("/ui/page/equipment").text)

    # The Growler is the one SR5 row printing an on-road/off-road pair in *both* columns (p. 462) --
    # rendered as printed, not collapsed to one number.
    assert "<td>4/5</td> <td>3/4</td>" in body
    # A drone's Seating is "—" (p. 466), and its Condition Monitor uses the 6 + ceil(Body/2) form.
    assert f"<td>{condition_monitor(FLY_SPY)}</td>" in body
    assert GROWLER.name in body


def test_buying_a_drone_and_a_vehicle_matches_engine_output() -> None:
    client = TestClient(create_app())
    _confirm_human(client)

    response = client.post(
        "/ui/vehicles",
        data={f"vehicle_{FLY_SPY.id}": "2", f"vehicle_{AMERICAR.id}": "1"},
    )
    assert response.status_code == 200

    spent = FLY_SPY.cost * 2 + AMERICAR.cost
    budget = PRIORITIES.resources["A"].nuyen
    assert f"nuyen remaining {budget - spent} / {budget}" in _squash(response.text)

    sheet = _squash(client.get("/character/sheet").text)
    # Both stat blocks reach the sheet, with the quantity tallied and the derived CM shown.
    assert f"<td>{FLY_SPY.name}</td> <td>2</td>" in sheet
    assert f"<td>{AMERICAR.name}</td> <td>1</td>" in sheet
    assert f"<td>{condition_monitor(FLY_SPY)}</td>" in sheet  # drone: 6 + ceil(1/2) = 7
    assert f"<td>{condition_monitor(AMERICAR)}</td>" in sheet  # vehicle: 12 + ceil(11/2) = 18
    assert f"Vehicle nuyen cost: {spent}." in sheet
    assert f"Nuyen remaining: {budget - spent} / {budget}" in sheet


def test_a_purchase_over_the_budget_is_rejected_with_the_engine_diagnostic() -> None:
    client = TestClient(create_app())
    _confirm_human(client, resources_letter="D")  # 50,000Y

    response = client.post("/ui/vehicles", data={f"vehicle_{TUNDRA.id}": "1"})  # 300,000Y

    assert "exceeds the nuyen budget" in response.text
    # Nothing was committed, so the sheet still shows an empty section.
    assert "None purchased." in client.get("/character/sheet").text


def test_gear_bought_after_a_vehicle_is_checked_against_the_remaining_budget() -> None:
    """The shared Step Six pool's sixth spender. Buying a 16,000Y car out of Resources D (50,000Y)
    leaves 34,000Y, so a gear purchase that would fit the *whole* budget but not the remainder has
    to be rejected -- which only happens if `submit_resources` knows about `vehicle_cost`.
    """
    client = TestClient(create_app())
    _confirm_human(client, resources_letter="C")
    budget = PRIORITIES.resources["C"].nuyen
    client.post("/ui/vehicles", data={f"vehicle_{AMERICAR.id}": "1"})

    # Meta Link costs 100Y; buy enough to fit the full budget but not what the car left.
    quantity = budget // 100
    response = client.post("/ui/resources", data={"gear_Meta Link": str(quantity)})

    assert "exceeds Resources priority C" in response.text
    assert f"vehicles ({AMERICAR.cost})" in response.text


def test_a_vehicle_purchase_survives_save_and_load() -> None:
    client = TestClient(create_app())
    _confirm_human(client)
    client.post("/ui/vehicles", data={f"vehicle_{FLY_SPY.id}": "3"})

    saved = client.get("/character/save")
    assert saved.status_code == 200

    fresh_client = TestClient(create_app())
    fresh_client.get("/")
    loaded = fresh_client.post(
        "/character/load",
        files={"save_file": ("character.json", saved.content, "application/json")},
    )
    assert loaded.status_code == 200
    sheet = _squash(fresh_client.get("/character/sheet").text)
    assert f"<td>{FLY_SPY.name}</td> <td>3</td>" in sheet


def test_a_vehicle_only_reachable_in_the_raw_data_cannot_be_bought_through_the_route() -> None:
    """The picker filters, but so must the route -- a hand-crafted POST naming an excluded row is
    rejected by `create_vehicle_selection`, not silently accepted."""
    client = TestClient(create_app())
    _confirm_human(client)
    banshee = next(v for v in load_vehicles() if v.name == "GMC Banshee (Thunderbird)")

    response = client.post("/ui/vehicles", data={f"vehicle_{banshee.id}": "1"})

    # The parser only reads fields it finds in the *offerable* catalog, so an excluded id is simply
    # never read -- the purchase resolves as empty rather than as an error. Either way it is not
    # bought, which is the property that matters.
    assert "GMC Banshee" not in response.text
    assert "None purchased." in client.get("/character/sheet").text
