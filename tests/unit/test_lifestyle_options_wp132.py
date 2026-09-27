"""WP132: Lifestyle Options and a permanent purchase (p. 370)."""

from __future__ import annotations

import json
import re

import pytest
from fastapi.testclient import TestClient

from chummer5.data.lifestyle import load_lifestyle_options, load_lifestyles
from chummer5.data.metatypes import load_metatypes
from chummer5.data.priorities import load_priorities
from chummer5.engine.character import metatype_choices
from chummer5.engine.lifestyle import create_lifestyle_selection, reprice_lifestyle
from chummer5.web.app import create_app

TIERS = load_lifestyles()
OPTIONS = load_lifestyle_options()
METATYPES = load_metatypes()
PRIORITIES = load_priorities()


def _select(tier: str, *options: tuple[str, str | None], **kwargs: object):  # type: ignore[no-untyped-def]
    return create_lifestyle_selection(
        tier,
        1,
        TIERS,
        options=options,
        option_catalog=OPTIONS,
        **kwargs,  # type: ignore[arg-type]
    )


def test_the_five_core_options_match_p_370() -> None:
    table = {o.name: (o.cost_percent, o.flat_cost, o.repeatable) for o in OPTIONS}
    assert table == {
        "Special Work Area": (0, 1000, True),
        "Extra Secure": (20, 0, False),
        "Obscure/Difficult to Find": (10, 0, False),
        "Cramped": (-10, 0, False),
        "Dangerous Area": (-20, 0, False),
    }
    assert all(o.unmodeled_effect_note for o in OPTIONS)


def test_cramped_takes_ten_percent_off_a_middle_lifestyle() -> None:
    """The plan's acceptance (the data calls the Middle tier "Medium", 5,000 a month)."""
    assert _select("Medium", ("Cramped", None)).monthly_cost == 4500


def test_a_permanent_troll_low_lifestyle_costs_400000() -> None:
    """The plan's acceptance: 100 months (p. 370) x 2,000 x the troll tax (+100%)."""
    selection = create_lifestyle_selection("Low", 3, TIERS, cost_percent=100, permanent=True)
    assert (selection.total_cost, selection.months) == (400000, 100)


def test_options_combine_and_the_surcharge_applies_last() -> None:
    selection = _select(
        "Low",
        ("Special Work Area", "garage"),
        ("Special Work Area", "lab"),
        ("Extra Secure", None),
        ("Cramped", None),
        cost_percent=100,
    )
    # 2,000 x (1 + 20% - 10%) + 2 x 1,000 = 4,200, then the troll tax doubles it.
    assert selection.monthly_cost == 8400
    assert reprice_lifestyle(selection, 0).monthly_cost == 4200


def test_what_the_options_reject() -> None:
    with pytest.raises(ValueError, match="can't be taken with this lifestyle"):
        _select("Street", ("Cramped", None))
    with pytest.raises(ValueError, match="already on this Lifestyle"):
        _select("Low", ("Cramped", None), ("Cramped", None))
    with pytest.raises(ValueError, match="already on this Lifestyle"):
        _select("Low", ("Special Work Area", "garage"), ("Special Work Area", "garage"))
    with pytest.raises(ValueError, match="say what the work area is"):
        _select("Low", ("Special Work Area", " "))
    with pytest.raises(ValueError, match="not a Lifestyle Option"):
        _select("Low", ("DocWagon Contract, Gold", None))


def test_the_lifestyle_page_and_the_save() -> None:
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
            "resources_letter": "A",
            "talent_letter": "E",
            "metatype_id": human.metatype.id,
        },
    )
    cramped = next(i for i, o in enumerate(OPTIONS) if o.name == "Cramped")
    work_area = next(i for i, o in enumerate(OPTIONS) if o.name == "Special Work Area")
    client.post(
        "/ui/lifestyle",
        data={
            "lifestyle_tier": "Low",
            "lifestyle_months": "1",
            f"lifestyle_option_{cramped}": "on",
            f"lifestyle_option_{work_area}_text_0": "garage",
            "lifestyle_permanent": "on",
        },
    )
    saved = json.loads(client.get("/character/save").content)
    assert saved["lifestyle_permanent"] is True
    assert saved["lifestyle_months"] == 100
    assert {o["name"] for o in saved["lifestyle_options"]} == {"Cramped", "Special Work Area"}
    sheet = re.sub(r"\s+", " ", client.get("/character/sheet").text)
    # (2,000 - 10% + 1,000) x 100 months
    assert "bought permanently, 280000¥" in sheet
    assert "Special Work Area (garage)" in sheet

    fresh = TestClient(create_app())
    fresh.get("/")
    fresh.post(
        "/character/load",
        files={"save_file": ("c.json", json.dumps(saved).encode(), "application/json")},
    )
    assert "bought permanently, 280000¥" in re.sub(r"\s+", " ", fresh.get("/character/sheet").text)
