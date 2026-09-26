"""WP20: the primary-Lifestyle selection UI (`POST /ui/lifestyle`), backed directly by
`chummer5.engine.lifestyle.create_lifestyle_selection` and sharing a nuyen budget with
`chummer5.engine.resources.create_resources_selection`'s starter-gear spend (see
`chummer5.web.app._lifestyle_context`'s docstring for the cross-section wiring).

Same "manual walkthrough; values match engine output for the same inputs" acceptance bar as
WP14-WP16's own test modules, plus the WP19-style still-valid/now-invalid reconfirmation checks
`test_web_attribute_skill_allocation.py`/`test_web_quality_contacts_resources.py` already
established for the other carried-forward selections.
"""

from fastapi.testclient import TestClient

from chummer5.data.metatypes import load_metatypes
from chummer5.data.priorities import load_priorities
from chummer5.engine.character import metatype_choices
from chummer5.engine.lifestyle import MAX_LIFESTYLE_MONTHS, create_lifestyle_selection
from chummer5.engine.resources import STARTER_GEAR_CATALOG
from chummer5.web.app import LIFESTYLES, create_app

METATYPES = load_metatypes()
PRIORITIES = load_priorities()


def _confirm_human(client: TestClient) -> None:
    """Same Heritage A / Attributes B / Skills C / Resources D combination every other WP14+ test
    module uses, giving each test here a known, real nuyen budget to check against.
    """
    client.get("/")
    heritage = PRIORITIES.heritage["A"]
    human_choice = next(
        c for c in metatype_choices(heritage, METATYPES) if c.metatype.name == "Human"
    )
    response = client.post(
        "/ui/priorities",
        data={
            "heritage_letter": "A",
            "attributes_letter": "B",
            "skills_letter": "C",
            "resources_letter": "D",
            "talent_letter": "E",
            "metatype_id": human_choice.metatype.id,
        },
    )
    assert "Confirmed: Human" in response.text


def test_index_before_confirmation_shows_a_placeholder() -> None:
    client = TestClient(create_app())

    response = client.get("/ui/page/equipment")

    assert (
        "Confirm a metatype and priorities on the Priorities page before selecting a Lifestyle."
        in response.text
    )


def test_index_after_confirmation_lists_every_tier_and_defaults_to_street() -> None:
    client = TestClient(create_app())
    _confirm_human(client)

    response = client.get("/ui/page/equipment")

    for tier in LIFESTYLES:
        assert tier.name in response.text
    assert 'value="Street" selected' in response.text
    budget = PRIORITIES.resources["D"].nuyen
    assert f"{budget} total" in response.text


def test_selecting_a_paid_tier_matches_engine_output() -> None:
    client = TestClient(create_app())
    _confirm_human(client)

    response = client.post("/ui/lifestyle", data={"lifestyle_tier": "Low", "lifestyle_months": "1"})

    assert response.status_code == 200
    selection = create_lifestyle_selection("Low", 1, LIFESTYLES)
    assert selection.total_cost == 2000
    # The resources section (rendered separately) reflects the combined remaining budget.
    resources_response = client.get("/ui/page/equipment")
    budget = PRIORITIES.resources["D"].nuyen
    assert f"{budget - selection.total_cost} / {budget}" in resources_response.text


def test_selecting_multiple_months_multiplies_the_monthly_rate() -> None:
    client = TestClient(create_app())
    _confirm_human(client)

    client.post("/ui/lifestyle", data={"lifestyle_tier": "Squatter", "lifestyle_months": "3"})

    sheet = client.get("/character/sheet")
    assert "Squatter (3 months, 1500¥)" in sheet.text


def test_unknown_tier_is_rejected() -> None:
    client = TestClient(create_app())
    _confirm_human(client)

    response = client.post(
        "/ui/lifestyle", data={"lifestyle_tier": "Penthouse", "lifestyle_months": "1"}
    )

    assert response.status_code == 200
    assert "not a lifestyle-catalog tier" in response.text


def test_months_below_minimum_is_rejected() -> None:
    client = TestClient(create_app())
    _confirm_human(client)

    response = client.post("/ui/lifestyle", data={"lifestyle_tier": "Low", "lifestyle_months": "0"})

    assert response.status_code == 200
    assert "months must be between" in response.text


def test_months_above_maximum_is_rejected() -> None:
    client = TestClient(create_app())
    _confirm_human(client)

    response = client.post(
        "/ui/lifestyle",
        data={"lifestyle_tier": "Low", "lifestyle_months": str(MAX_LIFESTYLE_MONTHS + 1)},
    )

    assert response.status_code == 200
    assert "months must be between" in response.text


def test_lifestyle_and_gear_share_one_nuyen_budget() -> None:
    """Buying gear that alone fits the budget, then selecting a Lifestyle that alone also fits,
    but the combination doesn't -- must be rejected (Resources D's budget is 50,000).
    """
    client = TestClient(create_app())
    _confirm_human(client)
    predator = next(item for item in STARTER_GEAR_CATALOG if item.name == "Ares Predator V")
    # 60 * 725 = 43,500 -- fits 50,000 alone.
    client.post("/ui/resources", data={f"gear_{predator.name}": "60"})

    # Luxury (100,000¥/month) alone would never fit either, so use a combination where only the
    # *sum* crosses the boundary: High costs 10,000/month; 43,500 + 10,000 = 53,500 > 50,000.
    response = client.post(
        "/ui/lifestyle", data={"lifestyle_tier": "High", "lifestyle_months": "1"}
    )

    assert response.status_code == 200
    assert "gear (43500) + lifestyle (10000)" in response.text
    assert "exceeds Resources priority" in response.text


def test_buying_gear_after_a_lifestyle_that_together_overspend_is_rejected() -> None:
    """The mirror-image ordering of the above: lifestyle first, then gear that alone fits but
    combined does not.
    """
    client = TestClient(create_app())
    _confirm_human(client)
    client.post("/ui/lifestyle", data={"lifestyle_tier": "High", "lifestyle_months": "1"})
    predator = next(item for item in STARTER_GEAR_CATALOG if item.name == "Ares Predator V")

    response = client.post("/ui/resources", data={f"gear_{predator.name}": "60"})

    assert response.status_code == 200
    assert "exceeds Resources priority" in response.text


def test_reconfirming_priorities_keeps_the_lifestyle_selection() -> None:
    """WP19's re-validate-in-place precedent applies to lifestyle too: reconfirming with an
    unchanged Resources letter must not reset an already-selected Lifestyle.
    """
    client = TestClient(create_app())
    _confirm_human(client)
    client.post("/ui/lifestyle", data={"lifestyle_tier": "Low", "lifestyle_months": "2"})

    heritage = PRIORITIES.heritage["A"]
    human_choice = next(
        c for c in metatype_choices(heritage, METATYPES) if c.metatype.name == "Human"
    )
    response = client.post(
        "/ui/priorities",
        data={
            "heritage_letter": "A",
            "attributes_letter": "B",
            "skills_letter": "D",
            "resources_letter": "C",
            "talent_letter": "E",
            "metatype_id": human_choice.metatype.id,
        },
    )
    response = client.get("/ui/page/equipment")  # WP97

    assert 'value="Low" selected' in response.text
    assert 'value="2"' in response.text
    sheet = client.get("/character/sheet")
    assert "Low (2 months, 4000¥)" in sheet.text


def test_reconfirming_priorities_with_a_lower_resources_budget_flags_the_existing_lifestyle() -> (
    None
):
    client = TestClient(create_app())
    client.get("/")
    heritage = PRIORITIES.heritage["B"]
    human_choice = next(
        c for c in metatype_choices(heritage, METATYPES) if c.metatype.name == "Human"
    )
    # Confirm with Resources A (450,000) first, where Luxury fits comfortably.
    client.post(
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
    client.post("/ui/lifestyle", data={"lifestyle_tier": "Luxury", "lifestyle_months": "1"})

    # Reconfirm with Resources dropped to D (50,000) -- Luxury (100,000¥) no longer fits at all.
    response = client.post(
        "/ui/priorities",
        data={
            "heritage_letter": "A",
            "attributes_letter": "B",
            "skills_letter": "C",
            "resources_letter": "D",
            "talent_letter": "E",
            "metatype_id": human_choice.metatype.id,
        },
    )
    response = client.get("/ui/page/equipment")  # WP97

    assert response.status_code == 200
    assert 'value="Luxury" selected' in response.text  # still shown, not reset
    assert "No longer fits since priorities were last confirmed" in response.text
    assert "exceeds Resources priority" in response.text


def test_lifestyle_endpoint_before_confirmation_does_not_crash() -> None:
    client = TestClient(create_app())
    client.get("/")

    response = client.post("/ui/lifestyle", data={})

    assert response.status_code == 200
    assert "Confirm a metatype and priorities" in response.text


# --- WP113: the troll tax re-prices a committed Lifestyle when the metatype changes ---------------


def test_becoming_a_troll_doubles_the_committed_lifestyle_and_shows_reach() -> None:
    from chummer5.data.metatypes import load_metatypes
    from chummer5.data.priorities import load_priorities
    from chummer5.engine.character import metatype_choices

    priorities = load_priorities()
    metatypes = load_metatypes()
    client = TestClient(create_app())
    client.get("/")

    def confirm(name: str) -> None:
        choice = next(
            c
            for c in metatype_choices(priorities.heritage["A"], metatypes)
            if c.metatype.name == name
        )
        client.post(
            "/ui/priorities",
            data={
                "heritage_letter": "A",
                "attributes_letter": "B",
                "skills_letter": "C",
                "resources_letter": "D",
                "talent_letter": "E",
                "metatype_id": choice.metatype.id,
            },
        )

    confirm("Human")
    client.post("/ui/lifestyle", data={"lifestyle_tier": "Low", "lifestyle_months": "3"})
    confirm("Troll")
    saved = client.get("/character/save").json()
    assert saved["metatype_name"] == "Troll"
    sheet = client.get("/character/sheet").text
    assert "Low (3 months, 12000¥)" in sheet
    assert "<th>Reach</th><td>+1</td>" in sheet
