"""WP126: Availability <= 12 for rating-scaled cyberware, and Device Rating <= 6 for electronics
(Step Six, p. 94). A fixed over-cap Availability stays offered, by ruling."""

from __future__ import annotations

import json
import re

import pytest
from fastapi.testclient import TestClient

from chummer5.data.cyberware_subsystems import load_cyberware_entries
from chummer5.data.gear import availability_at_rating
from chummer5.data.metatypes import load_metatypes
from chummer5.data.priorities import load_priorities
from chummer5.engine.character import metatype_choices
from chummer5.engine.cyberware_subsystems import (
    CyberwarePurchaseRequest,
    create_cyberware_tree_selection,
    cyberware_rating_bounds,
    purchased_ratings,
)
from chummer5.engine.resources import STARTER_GEAR_CATALOG
from chummer5.web.app import create_app

ENTRIES = load_cyberware_entries()
BY_NAME = {e.name: e for e in ENTRIES}
METATYPES = load_metatypes()
PRIORITIES = load_priorities()
GEAR = {g.name: g for g in STARTER_GEAR_CATALOG}


def test_availability_reads_every_rating_scaled_form() -> None:
    assert availability_at_rating("(Rating * 5)R", 3) == 15
    assert availability_at_rating("Rating * 2", 4) == 8
    assert availability_at_rating("Rating", 5) == 5
    assert availability_at_rating("16F", 3) == 16
    assert availability_at_rating("FixedValues(8R,12R,20R)", 1) == 8
    assert availability_at_rating("FixedValues(8R,12R,20R)", 3) == 20
    assert availability_at_rating("+Rating - MinRating + 1", 2) is None


@pytest.mark.parametrize(
    ("name", "bounds"),
    [
        ("Muscle Replacement", (1, 2)),  # (Rating * 5)R -- the plan's acceptance
        ("Wired Reflexes", (1, 2)),  # FixedValues(8R,12R,20R)
        ("Dermal Plating", (1, 3)),  # (Rating * 4)R
        ("Data Lock", (1, 6)),  # Rating * 2, printed to 12
        ("Cybereyes Basic System", (1, 4)),  # (Rating * 3): already within the cap
        ("Retinal Duplication", (1, 6)),  # a fixed 16F: offered as it stood, by ruling
    ],
)
def test_the_offered_range_stops_at_availability_12(name: str, bounds: tuple[int, int]) -> None:
    assert cyberware_rating_bounds(BY_NAME[name], cap_availability=True) == bounds


def test_the_uncapped_bounds_are_unchanged() -> None:
    assert cyberware_rating_bounds(BY_NAME["Muscle Replacement"]) == (1, 4)


def _buy(rating: int, exempt: frozenset[tuple[str, int]] | None):  # type: ignore[no-untyped-def]
    request = CyberwarePurchaseRequest(item_id=BY_NAME["Muscle Replacement"].id, rating=rating)
    return create_cyberware_tree_selection((request,), ENTRIES, 10**7, availability_exempt=exempt)


def test_a_new_over_cap_rating_is_rejected_and_an_owned_one_stands() -> None:
    _buy(2, frozenset())
    with pytest.raises(ValueError, match="over Availability 12"):
        _buy(3, frozenset())
    owned = purchased_ratings(_buy(3, None))  # a save or a legacy file: no check
    assert _buy(3, owned).purchases[0].rating == 3


def test_sensors_top_out_at_device_rating_6() -> None:
    assert GEAR["Single Sensor"].max_rating == 6
    assert GEAR["Sensor Array"].max_rating == 6
    # A rating that isn't a Device Rating keeps its range: Arrow: Standard is Availability = Rating.
    assert GEAR["Arrow: Standard"].max_rating == 12


def _confirm(client: TestClient) -> None:
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


def _options(html: str, field: str) -> list[str]:
    select = re.search(rf'name="{re.escape(field)}"[^>]*>(.*?)</select>', html, re.S)
    assert select is not None
    return re.findall(r'<option value="(\d+)"', select.group(1))


def test_the_picker_offers_2_and_a_loaded_rating_3_survives_an_edit() -> None:
    muscle = BY_NAME["Muscle Replacement"]
    client = TestClient(create_app())
    _confirm(client)
    page = client.post("/ui/cyberware", data={f"cyberware_{muscle.id}": "1"}).text
    assert _options(page, f"cyberware_rating_{muscle.id}_0") == ["1", "2"]
    page = client.post(
        "/ui/cyberware",
        data={f"cyberware_{muscle.id}": "1", f"cyberware_rating_{muscle.id}_0": "3"},
    ).text
    assert "over Availability 12" in page

    # A pre-WP126 save holding Muscle Replacement 3 loads, shows 3, and survives another edit.
    saved = json.loads(client.get("/character/save").content)
    saved["cyberware_purchases"] = [{"item_id": muscle.id, "rating": 3, "plugins": []}]
    fresh = TestClient(create_app())
    fresh.get("/")
    fresh.post(
        "/characters/upload?open=true",
        files={"files": ("c.json", json.dumps(saved).encode(), "application/json")},
    )
    datajack = BY_NAME["Datajack"]
    page = fresh.post(
        "/ui/cyberware",
        data={
            f"cyberware_{muscle.id}": "1",
            f"cyberware_rating_{muscle.id}_0": "3",
            f"cyberware_{datajack.id}": "1",
        },
    ).text
    assert "over Availability 12" not in page
    assert _options(page, f"cyberware_rating_{muscle.id}_0") == ["1", "2", "3"]
