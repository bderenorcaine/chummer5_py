"""WP127: Standard, Alphaware and Used implants at character creation (p. 451)."""

from __future__ import annotations

import json
import re
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from chummer5.data.bioware import load_bioware
from chummer5.data.cyberware_subsystems import load_cyberware_entries
from chummer5.data.grades import implant_grade, implant_grades
from chummer5.data.metatypes import load_metatypes
from chummer5.data.priorities import load_priorities
from chummer5.engine.bioware import (
    BiowarePurchaseRequest,
    bioware_grade_offered,
    create_bioware_selection,
)
from chummer5.engine.character import metatype_choices
from chummer5.engine.cyberware_subsystems import (
    CyberwarePurchaseRequest,
    availability_capped_maximum,
    create_cyberware_tree_selection,
    offered_grades,
)
from chummer5.web.app import create_app

ENTRIES = load_cyberware_entries()
BY_NAME = {e.name: e for e in ENTRIES}
BIOWARE = {b.name: b for b in load_bioware()}
METATYPES = load_metatypes()
PRIORITIES = load_priorities()


def test_the_grade_table_matches_p_451() -> None:
    table = {
        name: (g.essence_multiplier, g.cost_multiplier, g.availability_modifier)
        for name, g in implant_grades().items()
    }
    assert table == {
        "Standard": (Decimal("1"), Decimal("1"), 0),
        "Alphaware": (Decimal("0.8"), Decimal("1.2"), 2),
        "Used": (Decimal("1.25"), Decimal("0.75"), -4),
    }
    with pytest.raises(ValueError, match="not a grade available at character creation"):
        implant_grade("Betaware")


def _buy(*requests: CyberwarePurchaseRequest, **kwargs: object):  # type: ignore[no-untyped-def]
    return create_cyberware_tree_selection(requests, ENTRIES, 10**7, **kwargs)  # type: ignore[arg-type]


def test_the_plan_acceptance_datajack_prices() -> None:
    datajack = BY_NAME["Datajack"].id
    alpha = _buy(CyberwarePurchaseRequest(datajack, grade="Alphaware"))
    assert (alpha.essence_spent, alpha.nuyen_spent) == (Decimal("0.08"), 1200)
    used = _buy(CyberwarePurchaseRequest(datajack, grade="Used"))
    assert (used.essence_spent, used.nuyen_spent) == (Decimal("0.125"), 750)


def test_a_fraction_of_a_nuyen_rounds_half_up() -> None:
    """A Used Damper is 0.75 x 2,250 = 1,687.50 nuyen; legacy keeps the fraction."""
    assert _buy(CyberwarePurchaseRequest(BY_NAME["Damper"].id, grade="Used")).nuyen_spent == 1688


def test_plugins_inherit_their_parents_grade() -> None:
    """p. 451: "all accessories and add-ons must be of the same grade"."""
    eyes = BY_NAME["Cybereyes Basic System"]
    vision = BY_NAME["Vision Enhancement"]
    selection = _buy(
        CyberwarePurchaseRequest(
            eyes.id,
            rating=2,
            grade="Alphaware",
            plugins=(CyberwarePurchaseRequest(vision.id, rating=1, grade="Used"),),
        )
    )
    plugin = next(node for node in selection.walk() if node.item.id == vision.id)
    assert plugin.grade == "Alphaware"
    assert plugin.nuyen_cost == 4000 * 12 // 10  # Vision Enhancement 1 is 4,000 at Standard
    assert selection.to_requests()[0].grade == "Alphaware"


def test_an_over_cap_fixed_item_offers_standard_only() -> None:
    """Bone Lacing (Titanium) is a fixed 16R: offered, by WP126's ruling, but at Standard only."""
    lacing = BY_NAME["Bone Lacing (Titanium)"]
    assert offered_grades(lacing, 1, 1) == ("Standard",)
    request = CyberwarePurchaseRequest(lacing.id, grade="Alphaware")
    with pytest.raises(ValueError, match="Alphaware grade is over Availability 12"):
        _buy(request, availability_exempt=frozenset())
    _buy(request, availability_exempt=frozenset({(lacing.id, 1, "Alphaware")}))


def test_a_grade_moves_a_scaled_items_rating_cap() -> None:
    """Muscle Replacement is (Rating x 5)R: 2 at Standard, 2 at Alphaware (+2), 3 at Used (-4)."""
    muscle = BY_NAME["Muscle Replacement"]
    assert offered_grades(muscle, 1, 4) == ("Standard", "Alphaware", "Used")
    capped = {g: availability_capped_maximum(muscle, 1, 4, g) for g in implant_grades()}
    assert capped == {"Standard": 2, "Alphaware": 2, "Used": 3}
    _buy(
        CyberwarePurchaseRequest(muscle.id, rating=3, grade="Used"), availability_exempt=frozenset()
    )


def test_sensitive_system_doubles_the_graded_essence() -> None:
    datajack = BY_NAME["Datajack"].id
    selection = _buy(
        CyberwarePurchaseRequest(datajack, grade="Alphaware"), essence_multiplier=Decimal(2)
    )
    assert selection.essence_spent == Decimal("0.16")


def test_bioware_grades() -> None:
    cats_eyes = BIOWARE["Cat's Eyes"]
    selection = create_bioware_selection(
        [BiowarePurchaseRequest(cats_eyes.id, grade="Alphaware")], BIOWARE.values(), 10**6
    )
    assert (selection.nuyen_spent, selection.essence_spent) == (4800, Decimal("0.08"))
    # Enhanced Articulation is printed at Availability 12: Alphaware would be 14.
    articulation = BIOWARE["Enhanced Articulation"]
    assert not bioware_grade_offered(articulation, "Alphaware")
    assert bioware_grade_offered(articulation, "Used")
    with pytest.raises(ValueError, match="Alphaware grade is over Availability 12"):
        create_bioware_selection(
            [BiowarePurchaseRequest(articulation.id, grade="Alphaware")],
            BIOWARE.values(),
            10**6,
            availability_exempt=frozenset(),
        )


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


def test_the_picker_buys_graded_implants_and_the_save_keeps_the_grade() -> None:
    datajack = BY_NAME["Datajack"]
    cats_eyes = BIOWARE["Cat's Eyes"]
    client = TestClient(create_app())
    _confirm(client)
    page = client.post(
        "/ui/cyberware",
        data={
            f"cyberware_{datajack.id}": "1",
            f"cyberware_grade_{datajack.id}_0": "Alphaware",
            f"bioware_{cats_eyes.id}": "1",
            f"bioware_grade_{cats_eyes.id}_0": "Used",
        },
    ).text
    assert f'name="cyberware_grade_{datajack.id}_0"' in page
    assert re.search(r'<option value="Alphaware" selected>', page)

    saved = json.loads(client.get("/character/save").content)
    assert saved["cyberware_purchases"][0]["grade"] == "Alphaware"
    assert saved["bioware_purchases"][0]["grade"] == "Used"
    sheet = re.sub(r"\s+", " ", client.get("/character/sheet").text)
    assert "Datajack [Alphaware]" in sheet
    assert "Cat's Eyes [Used]" in sheet or "Cat&#39;s Eyes [Used]" in sheet
