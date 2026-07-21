"""WP34: the cyberware purchase UI (`POST /ui/cyberware`), backed directly by
`chummer5.engine.cyberware.create_cyberware_selection`/`apply_cyberware_improvements` and sharing
a nuyen budget with `chummer5.engine.resources.create_resources_selection`'s starter-gear spend and
`chummer5.engine.lifestyle`'s primary-Lifestyle purchase (see `chummer5.web.app._cyberware_
context`'s docstring for the cross-section wiring, and WP20's own precedent for "a new peer
section despite sharing a budget").

Same "manual walkthrough; values match engine output for the same inputs" acceptance bar as
WP14-WP16/WP20's own test modules, plus the WP19-style still-valid/now-invalid reconfirmation
checks those modules already established for carried-forward selections.

WP45 folds bioware into this same section/route -- see `tests/unit/test_web_bioware.py` for the
bioware-specific tests (shared-budget/shared-Essence-floor interaction with cyberware included).
"""

from fastapi.testclient import TestClient

from chummer5.data.metatypes import load_metatypes
from chummer5.data.priorities import load_priorities
from chummer5.engine.character import metatype_choices
from chummer5.web.app import CYBERWARE, create_app

METATYPES = load_metatypes()
PRIORITIES = load_priorities()

DATAJACK = next(c for c in CYBERWARE if c.name == "Datajack")
SYNTHETIC_FULL_ARM = next(c for c in CYBERWARE if c.name == "Synthetic Full Arm")
# Essence 1, cost 4800 -- cheap enough that 6 copies (Essence exactly 6) still fits Resources D's
# 50,000¥ budget, unlike Synthetic Full Arm (20,000¥ each), which would hit the nuyen cap first.
SUBMACHINE_GUN = next(c for c in CYBERWARE if c.name == "Submachine Gun")


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

    response = client.get("/")

    assert (
        "Confirm a metatype and priorities above before installing cyberware or bioware."
        in response.text
    )


def test_index_after_confirmation_lists_every_catalog_item() -> None:
    client = TestClient(create_app())
    _confirm_human(client)

    response = client.get("/")

    assert "Datajack" in response.text
    assert "Synthetic Full Arm" in response.text


def test_buying_an_item_matches_engine_output() -> None:
    client = TestClient(create_app())
    _confirm_human(client)

    response = client.post("/ui/cyberware", data={f"cyberware_{DATAJACK.id}": "1"})

    assert response.status_code == 200
    assert f"{DATAJACK.cost}" in response.text
    sheet = client.get("/character/sheet")
    assert "Datajack × 1" in sheet.text
    # Essence 6 - 0.1 == 5.9.
    assert "Essence: 5.9 / 6." in sheet.text


def test_duplicate_purchases_are_allowed_and_sum_costs() -> None:
    client = TestClient(create_app())
    _confirm_human(client)

    response = client.post("/ui/cyberware", data={f"cyberware_{DATAJACK.id}": "2"})

    assert response.status_code == 200
    sheet = client.get("/character/sheet")
    assert "Datajack × 2" in sheet.text
    assert "Essence: 5.8 / 6." in sheet.text


def test_essence_floor_rejects_a_purchase_that_would_leave_no_essence() -> None:
    client = TestClient(create_app())
    _confirm_human(client)

    # 6 Submachine Guns at Essence 1 each == 6, leaving exactly 0 -- rejected (nuyen cost, 28,800,
    # comfortably fits Resources D's 50,000¥ budget, so this exercises the Essence floor
    # specifically, not the nuyen cap).
    response = client.post("/ui/cyberware", data={f"cyberware_{SUBMACHINE_GUN.id}": "6"})

    assert response.status_code == 200
    assert "would leave no Essence remaining" in response.text


def test_cyberlimb_raises_physical_condition_monitor() -> None:
    client = TestClient(create_app())
    _confirm_human(client)
    sheet_before = client.get("/character/sheet")
    base_cm = int(sheet_before.text.split("Physical condition monitor</th><td>")[1].split(" ")[0])

    client.post("/ui/cyberware", data={f"cyberware_{SYNTHETIC_FULL_ARM.id}": "1"})

    sheet_after = client.get("/character/sheet")
    new_cm = int(sheet_after.text.split("Physical condition monitor</th><td>")[1].split(" ")[0])
    assert new_cm == base_cm + 1


def test_cyberware_gear_and_lifestyle_share_one_nuyen_budget() -> None:
    """Buying cyberware that alone fits the budget, then Lifestyle that alone also fits, but the
    combination doesn't -- must be rejected (Resources D's budget is 50,000).
    """
    client = TestClient(create_app())
    _confirm_human(client)
    # Synthetic Full Arm costs 20,000 -- fits 50,000 alone.
    client.post("/ui/cyberware", data={f"cyberware_{SYNTHETIC_FULL_ARM.id}": "1"})

    # Luxury (100,000¥/month) alone would never fit, so use High (10,000¥/month):
    # 20,000 + 10,000 = 30,000 <= 50,000, still fits -- confirm it succeeds first.
    ok_response = client.post(
        "/ui/lifestyle", data={"lifestyle_tier": "High", "lifestyle_months": "1"}
    )
    assert "exceeds Resources priority" not in ok_response.text

    # Quantities are absolute, not incremental (see `_parse_cyberware`) -- resubmitting "3" arms
    # (60,000) leaves only 40,000 available for cyberware (50,000 budget minus Lifestyle's 10,000),
    # rejected by `create_cyberware_selection`'s own nuyen-budget check (the amount *available for
    # cyberware specifically*, computed the same way `submit_lifestyle` computes what's available
    # for Lifestyle -- see `submit_cyberware`'s own shape).
    response = client.post(
        "/ui/cyberware",
        data={f"cyberware_{SYNTHETIC_FULL_ARM.id}": "3"},
    )

    assert response.status_code == 200
    assert "exceeds the nuyen budget" in response.text


def test_unknown_catalog_id_is_rejected() -> None:
    client = TestClient(create_app())
    _confirm_human(client)

    response = client.post("/ui/cyberware", data={"cyberware_not-a-real-id": "1"})

    # An id the picker form never offers is simply ignored by `_parse_cyberware` (it only reads
    # `cyberware_{item.id}` keys for items in the real catalog), so this is a no-op submission, not
    # a rejection -- mirrors `_parse_gear`'s identical "unknown keys are just not in the catalog to
    # iterate" shape.
    assert response.status_code == 200
    sheet = client.get("/character/sheet")
    assert "None installed." in sheet.text


def test_reconfirming_priorities_keeps_the_cyberware_selection() -> None:
    """WP19's re-validate-in-place precedent applies to cyberware too: reconfirming with an
    unchanged Resources letter must not reset an already-purchased item.
    """
    client = TestClient(create_app())
    _confirm_human(client)
    client.post("/ui/cyberware", data={f"cyberware_{DATAJACK.id}": "1"})

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

    assert f'name="cyberware_{DATAJACK.id}"\n                value="1"' in response.text
    sheet = client.get("/character/sheet")
    assert "Datajack × 1" in sheet.text


def test_reconfirming_priorities_with_a_lower_resources_budget_flags_the_existing_cyberware() -> (
    None
):
    client = TestClient(create_app())
    client.get("/")
    heritage = PRIORITIES.heritage["B"]
    human_choice = next(
        c for c in metatype_choices(heritage, METATYPES) if c.metatype.name == "Human"
    )
    # Confirm with Resources A (450,000) first, where the arm fits comfortably.
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
    client.post("/ui/cyberware", data={f"cyberware_{SYNTHETIC_FULL_ARM.id}": "1"})

    # Reconfirm with Resources dropped to E (6,000) -- the arm (20,000¥) no longer fits at all.
    # Talent moves to D here (not E) so the 5 letters stay a valid A-E permutation.
    response = client.post(
        "/ui/priorities",
        data={
            "heritage_letter": "A",
            "attributes_letter": "B",
            "skills_letter": "C",
            "resources_letter": "E",
            "talent_letter": "D",
            "metatype_id": human_choice.metatype.id,
        },
    )

    assert response.status_code == 200
    # still shown, not reset
    assert f'name="cyberware_{SYNTHETIC_FULL_ARM.id}"\n                value="1"' in response.text
    assert "No longer fits since priorities were last confirmed" in response.text
    assert "exceeds the nuyen budget" in response.text


def test_cyberware_endpoint_before_confirmation_does_not_crash() -> None:
    client = TestClient(create_app())
    client.get("/")

    response = client.post("/ui/cyberware", data={})

    assert response.status_code == 200
    assert "Confirm a metatype and priorities" in response.text


def test_essence_defaults_to_six_before_any_cyberware_purchase() -> None:
    client = TestClient(create_app())
    _confirm_human(client)

    sheet = client.get("/character/sheet")

    assert "Essence: 6 / 6." in sheet.text


def test_save_load_round_trips_cyberware_selection() -> None:
    client = TestClient(create_app())
    _confirm_human(client)
    client.post("/ui/cyberware", data={f"cyberware_{DATAJACK.id}": "1"})

    save_response = client.get("/character/save")
    assert save_response.status_code == 200

    fresh_client = TestClient(create_app())
    fresh_client.get("/")
    load_response = fresh_client.post(
        "/character/load",
        files={"save_file": ("character.json", save_response.content, "application/json")},
    )

    assert "Character loaded." in load_response.text
    sheet = fresh_client.get("/character/sheet")
    assert "Datajack × 1" in sheet.text
    assert "Essence: 5.9 / 6." in sheet.text
