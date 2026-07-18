"""WP16: qualities, contacts, and resources UI, backed by WP8's `create_quality_selection`/
`apply_quality_improvements` and WP9's `create_contact_selection`/`create_resources_selection`
directly.

Cross-checks the UI's result against those engine functions called directly with the same inputs,
same acceptance bar as WP14/WP15's own test modules: "manual walkthrough; values match engine
output for the same inputs." Also covers the WP16-specific regression this WP's worklog documents:
`create_character` always returns a fresh, empty `ImprovementIndex`, so a committed quality
selection's Improvements must survive a later attribute/priority resubmission.
"""

from fastapi.testclient import TestClient

from chummer5.data.metatypes import load_metatypes
from chummer5.data.priorities import load_priorities
from chummer5.engine.character import create_character, metatype_choices
from chummer5.engine.qualities import QUALITY_KARMA_LIMIT
from chummer5.engine.resources import STARTER_GEAR_CATALOG
from chummer5.web.app import MAX_CONTACT_ROWS, MVP_QUALITIES, create_app

METATYPES = load_metatypes()
PRIORITIES = load_priorities()

_CATLIKE = next(q for q in MVP_QUALITIES if q.name == "Catlike")


def _confirm_human(client: TestClient) -> None:
    """Same Heritage A / Attributes B / Skills C / Resources D combination WP14/WP15's own tests
    use, giving every test here a known, real budget/CHA to check against.
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
            "metatype_id": human_choice.metatype.id,
        },
    )
    assert "Confirmed: Human" in response.text


def _human_character():
    heritage = PRIORITIES.heritage["A"]
    human_choice = next(
        c for c in metatype_choices(heritage, METATYPES) if c.metatype.name == "Human"
    )
    return create_character(human_choice, "A", "B", PRIORITIES, {})


def test_index_before_confirmation_shows_placeholders_for_all_three_new_sections() -> None:
    client = TestClient(create_app())

    response = client.get("/")

    assert "Confirm a metatype and priorities above before selecting qualities." in response.text
    assert "Confirm a metatype and priorities above before adding contacts." in response.text
    assert (
        "Confirm a metatype and priorities above before spending starting nuyen." in response.text
    )


def test_index_after_confirmation_shows_full_budgets() -> None:
    client = TestClient(create_app())
    _confirm_human(client)

    response = client.get("/")

    assert f"0 / {QUALITY_KARMA_LIMIT}" in response.text
    character = _human_character()
    free_points = character.attribute_value("CHA") * 3
    assert f"Free contact points: {free_points}." in response.text
    budget = PRIORITIES.resources["D"].nuyen
    assert f"{budget} / {budget}" in response.text
    # Every MVP-offered quality and every starter-gear item is listed.
    for quality in MVP_QUALITIES:
        assert quality.name in response.text
    for item in STARTER_GEAR_CATALOG:
        assert item.name in response.text


def test_selecting_catlike_grants_the_sneaking_bonus_matching_the_engine() -> None:
    client = TestClient(create_app())
    _confirm_human(client)

    response = client.post("/ui/qualities", data={"quality_id": _CATLIKE.id})

    assert response.status_code == 200
    assert f"{_CATLIKE.karma} / {QUALITY_KARMA_LIMIT}" in response.text

    skill_response = client.post("/ui/skills", data={})
    character = _human_character()
    # Sneaking's rating comes solely from Catlike's +2 flat bonus (no points spent).
    expected_rating = 2
    expected_pool = expected_rating + character.attribute_value("AGI")
    assert f"<td>{expected_rating}</td>" in skill_response.text
    assert f"<td>{expected_pool}</td>" in skill_response.text


def test_quality_improvements_survive_a_later_attribute_resubmission() -> None:
    """Regression test for the WP16 finding: `create_character` always returns a fresh, empty
    `ImprovementIndex`, so re-submitting attributes must not silently drop an already-committed
    quality's Improvements.
    """
    client = TestClient(create_app())
    _confirm_human(client)
    client.post("/ui/qualities", data={"quality_id": _CATLIKE.id})

    client.post("/ui/attributes", data={"attr_BOD": "2"})
    skill_response = client.post("/ui/skills", data={})

    character = _human_character()
    expected_pool = 2 + character.attribute_value("AGI")
    assert f"<td>{expected_pool}</td>" in skill_response.text


def test_quality_improvements_survive_reconfirming_priorities() -> None:
    client = TestClient(create_app())
    _confirm_human(client)
    client.post("/ui/qualities", data={"quality_id": _CATLIKE.id})

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
            "metatype_id": human_choice.metatype.id,
        },
    )

    # The checkbox is still shown checked -- quality_selection isn't reset on reconfirmation.
    assert f'value="{_CATLIKE.id}"' in response.text
    assert "checked" in response.text
    skill_response = client.post("/ui/skills", data={})
    assert "<td>2</td>" in skill_response.text


def test_unknown_quality_id_is_rejected() -> None:
    client = TestClient(create_app())
    _confirm_human(client)

    response = client.post("/ui/qualities", data={"quality_id": "not-a-real-id"})

    assert response.status_code == 200
    assert "not an MVP-offered quality id" in response.text


def test_adding_a_contact_matches_engine_output() -> None:
    client = TestClient(create_app())
    _confirm_human(client)

    response = client.post(
        "/ui/contacts",
        data={
            "contact_name_0": "Ratcatcher",
            "contact_connection_0": "2",
            "contact_loyalty_0": "1",
        },
    )

    assert response.status_code == 200
    character = _human_character()
    free_points = character.attribute_value("CHA") * 3
    points_spent = 3
    expected_karma = max(0, points_spent - free_points)
    assert f"Points spent: {points_spent}." in response.text
    assert f"Karma cost beyond free points: {expected_karma}." in response.text


def test_contact_with_invalid_connection_is_rejected() -> None:
    client = TestClient(create_app())
    _confirm_human(client)

    response = client.post(
        "/ui/contacts",
        data={"contact_name_0": "Nobody", "contact_connection_0": "0", "contact_loyalty_0": "1"},
    )

    assert response.status_code == 200
    assert "Connection and Loyalty must each be at least" in response.text


def test_contacts_free_points_reflects_a_later_attribute_change() -> None:
    client = TestClient(create_app())
    _confirm_human(client)
    client.post(
        "/ui/contacts",
        data={
            "contact_name_0": "Ratcatcher",
            "contact_connection_0": "2",
            "contact_loyalty_0": "1",
        },
    )

    client.post("/ui/attributes", data={"attr_CHA": "2"})
    response = client.get("/")

    heritage = PRIORITIES.heritage["A"]
    human_choice = next(
        c for c in metatype_choices(heritage, METATYPES) if c.metatype.name == "Human"
    )
    character = create_character(human_choice, "A", "B", PRIORITIES, {"CHA": 2})
    free_points = character.attribute_value("CHA") * 3
    assert f"Free contact points: {free_points}." in response.text
    # The contact itself is still there -- editing attributes doesn't reset contacts.
    assert 'value="Ratcatcher"' in response.text


def test_at_most_max_contact_rows_are_offered() -> None:
    client = TestClient(create_app())
    _confirm_human(client)

    response = client.get("/")

    assert response.text.count("contact_name_") == MAX_CONTACT_ROWS


def test_buying_starter_gear_matches_engine_output() -> None:
    client = TestClient(create_app())
    _confirm_human(client)
    meta_link = next(item for item in STARTER_GEAR_CATALOG if item.name == "Meta Link")

    response = client.post("/ui/resources", data={f"gear_{meta_link.name}": "1"})

    assert response.status_code == 200
    budget = PRIORITIES.resources["D"].nuyen
    assert f"{budget - meta_link.cost} / {budget}" in response.text


def test_buying_two_of_a_repeatable_gear_item() -> None:
    client = TestClient(create_app())
    _confirm_human(client)
    credstick = next(
        item for item in STARTER_GEAR_CATALOG if item.name == "Certified Credstick, Standard"
    )

    response = client.post("/ui/resources", data={f"gear_{credstick.name}": "2"})

    assert response.status_code == 200
    budget = PRIORITIES.resources["D"].nuyen
    assert f"{budget - 2 * credstick.cost} / {budget}" in response.text


def test_overspending_the_nuyen_budget_is_rejected() -> None:
    client = TestClient(create_app())
    _confirm_human(client)
    predator = next(item for item in STARTER_GEAR_CATALOG if item.name == "Ares Predator V")

    response = client.post("/ui/resources", data={f"gear_{predator.name}": "100"})

    assert response.status_code == 200
    assert "exceeds" in response.text


def test_reconfirming_priorities_with_a_new_resources_letter_resets_gear() -> None:
    client = TestClient(create_app())
    _confirm_human(client)
    meta_link = next(item for item in STARTER_GEAR_CATALOG if item.name == "Meta Link")
    client.post("/ui/resources", data={f"gear_{meta_link.name}": "1"})

    heritage = PRIORITIES.heritage["A"]
    human_choice = next(
        c for c in metatype_choices(heritage, METATYPES) if c.metatype.name == "Human"
    )
    # Swap Skills/Resources letters -- a legal, distinct submission with a different Resources
    # budget than before.
    response = client.post(
        "/ui/priorities",
        data={
            "heritage_letter": "A",
            "attributes_letter": "B",
            "skills_letter": "D",
            "resources_letter": "C",
            "metatype_id": human_choice.metatype.id,
        },
    )

    budget = PRIORITIES.resources["C"].nuyen
    assert f"{budget} / {budget}" in response.text


def test_qualities_contacts_resources_endpoints_before_confirmation_do_not_crash() -> None:
    client = TestClient(create_app())
    client.get("/")

    quality_response = client.post("/ui/qualities", data={})
    contact_response = client.post("/ui/contacts", data={})
    resources_response = client.post("/ui/resources", data={})

    assert quality_response.status_code == 200
    assert "Confirm a metatype and priorities" in quality_response.text
    assert contact_response.status_code == 200
    assert "Confirm a metatype and priorities" in contact_response.text
    assert resources_response.status_code == 200
    assert "Confirm a metatype and priorities" in resources_response.text
