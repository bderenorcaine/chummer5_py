"""WP133: the 5,000¥ and 7-Karma carryover display caps, and the starting-nuyen roll notice."""

from __future__ import annotations

import re

from fastapi.testclient import TestClient

from chummer5.data.lifestyle import load_lifestyles
from chummer5.data.metatypes import load_metatypes
from chummer5.data.priorities import load_priorities
from chummer5.engine.carryover import (
    StartingNuyenRoll,
    karma_carryover,
    nuyen_carryover,
    starting_nuyen_roll,
)
from chummer5.engine.character import metatype_choices
from chummer5.engine.lifestyle import create_lifestyle_selection
from chummer5.web.app import create_app

LIFESTYLES = load_lifestyles()
PRIORITIES = load_priorities()
METATYPES = load_metatypes()


def test_the_starting_nuyen_table_matches_p_95() -> None:
    table = {t.name: (t.starting_dice, t.starting_multiplier) for t in LIFESTYLES}
    assert table == {
        "Street": (1, 20),
        "Squatter": (2, 40),
        "Low": (3, 60),
        "Medium": (4, 100),
        "High": (5, 500),
        "Luxury": (6, 1000),
    }


def test_james_carries_4995_and_rolls_4d6_x_100() -> None:
    # The plan's acceptance: p. 96's James, a Middle Lifestyle and 4,995¥ unspent.
    middle = create_lifestyle_selection("Medium", 12, LIFESTYLES)
    assert nuyen_carryover(4995).carried == 4995
    assert nuyen_carryover(4995).lost == 0
    assert starting_nuyen_roll(middle, 4995) == StartingNuyenRoll(4, 100, 4995)
    # A permanent purchase is the same tier.
    permanent = create_lifestyle_selection("Medium", 1, LIFESTYLES, permanent=True)
    assert starting_nuyen_roll(permanent, 0) == StartingNuyenRoll(4, 100, 0)
    assert starting_nuyen_roll(None, 4995) is None


def test_the_caps() -> None:
    assert (nuyen_carryover(12000).carried, nuyen_carryover(12000).lost) == (5000, 7000)
    # The plan's other acceptance: 12 Karma left shows 7, with 5 lost.
    assert (karma_carryover(12).carried, karma_carryover(12).lost) == (7, 5)
    # Over budget: nothing carries and nothing is "lost" (that's a validation error instead).
    assert (nuyen_carryover(-100).carried, nuyen_carryover(-100).lost) == (0, 0)


def test_the_sheet_shows_the_capped_amounts_and_the_sidebar_the_true_ones() -> None:
    client = TestClient(create_app())
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
            "resources_letter": "E",
            "talent_letter": "A",
            "metatype_id": human.metatype.id,
        },
    )
    client.post("/ui/lifestyle", data={"lifestyle_tier": "Low", "lifestyle_months": "1"})
    sheet = re.sub(r"\s+", " ", client.get("/character/sheet").text)
    # Resources E: 6,000¥ less a 2,000¥ month of Low leaves 4000¥, all of it carried.
    assert "Carried into play: 4000¥." in sheet
    assert "carryover limit will be lost" not in sheet.split("Karma")[0]
    assert "Roll 3D6 × 60¥ for starting nuyen when play begins, plus the 4000¥ carried over." in (
        sheet
    )
    # 25 Karma unspent: 7 carry, 18 would be lost.
    assert "Carried into play: 7 Karma." in sheet
    assert "18 Karma over the 7-Karma carryover limit will be lost." in sheet
