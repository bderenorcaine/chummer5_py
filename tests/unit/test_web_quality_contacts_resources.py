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
            "talent_letter": "E",
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

    qualities = client.get("/ui/page/qualities").text
    contacts = client.get("/ui/page/contacts").text
    equipment = client.get("/ui/page/equipment").text

    placeholder = "Confirm a metatype and priorities on the Priorities page before"
    assert f"{placeholder} selecting qualities." in qualities
    assert f"{placeholder} adding contacts." in contacts
    assert f"{placeholder} spending starting nuyen." in equipment


def test_index_after_confirmation_shows_full_budgets() -> None:
    client = TestClient(create_app())
    _confirm_human(client)

    qualities = client.get("/ui/page/qualities").text
    contacts = client.get("/ui/page/contacts").text
    equipment = client.get("/ui/page/equipment").text

    assert f"0 / {QUALITY_KARMA_LIMIT}" in qualities
    character = _human_character()
    free_points = character.attribute_value("CHA") * 3
    assert f"Free contact points: {free_points}." in contacts
    budget = PRIORITIES.resources["D"].nuyen
    assert f"{budget} / {budget}" in equipment
    # Every MVP-offered quality and every starter-gear item is listed.
    for quality in MVP_QUALITIES:
        assert quality.name in qualities
    for item in STARTER_GEAR_CATALOG:
        assert item.name in equipment


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
    # WP82: the picker shows `bought (with bonuses)`; nothing was bought, so `0 (2)`.
    assert f"<td>0 ({expected_rating})</td>" in skill_response.text
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
            "talent_letter": "E",
            "metatype_id": human_choice.metatype.id,
        },
    )
    response = client.get("/ui/page/qualities")  # WP97

    # The checkbox is still shown checked -- quality_selection isn't reset on reconfirmation.
    assert f'value="{_CATLIKE.id}"' in response.text
    assert "checked" in response.text
    skill_response = client.post("/ui/skills", data={})
    assert "<td>0 (2)</td>" in skill_response.text  # WP82: bought 0, Catlike +2


def _confirm_elf(client: TestClient) -> None:
    """WP23: same Heritage A / Attributes B / Skills C / Resources D combination as
    `_confirm_human`, but Elf -- gives every WP23 test here a character whose metatype grants a
    free quality (Low-Light Vision).
    """
    client.get("/")
    heritage = PRIORITIES.heritage["A"]
    elf_choice = next(c for c in metatype_choices(heritage, METATYPES) if c.metatype.name == "Elf")
    response = client.post(
        "/ui/priorities",
        data={
            "heritage_letter": "A",
            "attributes_letter": "B",
            "skills_letter": "C",
            "resources_letter": "D",
            "talent_letter": "E",
            "metatype_id": elf_choice.metatype.id,
        },
    )
    assert "Confirmed: Elf" in response.text


def test_elf_metatype_quality_is_shown_free_and_not_purchasable() -> None:
    client = TestClient(create_app())
    _confirm_elf(client)
    low_light = next(q for q in MVP_QUALITIES if q.name == "Low-Light Vision")

    response = client.get("/ui/page/qualities")

    assert "Free from metatype:" in response.text
    assert "Low-Light Vision" in response.text
    assert f'value="{low_light.id}"' not in response.text


def test_elf_cannot_submit_already_metatype_granted_quality_id() -> None:
    client = TestClient(create_app())
    _confirm_elf(client)
    low_light = next(q for q in MVP_QUALITIES if q.name == "Low-Light Vision")

    response = client.post("/ui/qualities", data={"quality_id": low_light.id})

    assert "not an MVP-offered quality id" in response.text


def test_elf_character_sheet_shows_metatype_quality_separately_from_karma_cost() -> None:
    client = TestClient(create_app())
    _confirm_elf(client)

    response = client.get("/character/sheet")

    assert "Free from metatype:" in response.text
    assert "Low-Light Vision" in response.text
    # No quality was purchased -- confirms the metatype-granted quality isn't folded into
    # quality_names (the purchased-quality list), the actually-meaningful check here.
    assert "None selected." in response.text


def test_human_offerable_catalog_unaffected_by_wp23() -> None:
    """No metatype quality applies to Human -- the picker/karma math for a Human character must be
    byte-identical to pre-WP23 behavior."""
    client = TestClient(create_app())
    _confirm_human(client)

    response = client.get("/ui/page/qualities")

    assert "Free from metatype:" not in response.text
    for quality in MVP_QUALITIES:
        assert quality.name in response.text


def test_unknown_quality_id_is_rejected() -> None:
    client = TestClient(create_app())
    _confirm_human(client)

    response = client.post("/ui/qualities", data={"quality_id": "not-a-real-id"})

    assert response.status_code == 200
    assert "not an MVP-offered quality id" in response.text


# -- WP55: free-text quality-selection mechanism (SINner et al.) ---------------------------------

_SINNER_NATIONAL = next(q for q in MVP_QUALITIES if q.name == "SINner (National)")
_SINNER_CORPORATE = next(q for q in MVP_QUALITIES if q.name == "SINner (Corporate)")


def test_select_text_quality_without_a_detail_is_rejected() -> None:
    client = TestClient(create_app())
    _confirm_human(client)

    response = client.post("/ui/qualities", data={"quality_id": _SINNER_NATIONAL.id})

    assert response.status_code == 200
    assert "requires a free-text detail" in response.text


def test_select_text_quality_with_a_detail_is_accepted_and_echoed() -> None:
    client = TestClient(create_app())
    _confirm_human(client)

    response = client.post(
        "/ui/qualities",
        data={
            "quality_id": _SINNER_NATIONAL.id,
            f"quality_text_{_SINNER_NATIONAL.id}": "UCAS",
        },
    )

    assert response.status_code == 200
    assert f"5 / {QUALITY_KARMA_LIMIT}" in response.text  # Negative Quality karma
    assert 'value="UCAS"' in response.text

    sheet = client.get("/character/sheet")
    assert "SINner (National) (UCAS)" in sheet.text


def test_select_text_quality_mutual_exclusion_is_rejected() -> None:
    client = TestClient(create_app())
    _confirm_human(client)

    response = client.post(
        "/ui/qualities",
        data={
            "quality_id": [_SINNER_NATIONAL.id, _SINNER_CORPORATE.id],
            f"quality_text_{_SINNER_NATIONAL.id}": "UCAS",
            f"quality_text_{_SINNER_CORPORATE.id}": "Ares",
        },
    )

    assert response.status_code == 200
    assert "cannot be taken together with" in response.text


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
    response = client.get("/ui/page/contacts")

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

    response = client.get("/ui/page/contacts")

    assert response.text.count("contact_name_") == MAX_CONTACT_ROWS


def test_buying_starter_gear_matches_engine_output() -> None:
    client = TestClient(create_app())
    _confirm_human(client)
    meta_link = next(item for item in STARTER_GEAR_CATALOG if item.name == "Meta Link")

    response = client.post("/ui/resources", data={f"gear_{meta_link.name}": "1"})

    assert response.status_code == 200
    budget = PRIORITIES.resources["D"].nuyen
    assert f"{budget - meta_link.cost} / {budget}" in response.text


def test_gear_picker_offers_a_name_category_filter() -> None:
    # WP71: the gear picker renders a client-side filter input plus the per-row data attributes the
    # JS keys off (name + category). TestClient can't run JS, so pin the server contract instead.
    client = TestClient(create_app())
    _confirm_human(client)

    response = client.get("/ui/page/equipment")

    assert response.status_code == 200
    assert 'id="gear-filter"' in response.text
    meta_link = next(item for item in STARTER_GEAR_CATALOG if item.name == "Meta Link")
    assert f'data-gear-name="{meta_link.name.lower()}"' in response.text
    assert f'data-gear-category="{(meta_link.category or "Other").lower()}"' in response.text


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


def test_buying_rating_priced_gear_scales_cost_with_chosen_rating() -> None:
    # WP66: Fake SIN is Rating-priced (2500/rating). Bought at rating 4 -> 10000 nuyen.
    client = TestClient(create_app())
    _confirm_human(client)

    response = client.post("/ui/resources", data={"gear_Fake SIN": "1", "rating_Fake SIN": "4"})

    assert response.status_code == 200
    budget = PRIORITIES.resources["D"].nuyen
    assert f"{budget - 4 * 2500} / {budget}" in response.text


def test_rating_priced_gear_shows_availability_capped_rating_selector() -> None:
    # WP66: Fake SIN's <rating> is 6 but the (Rating*3)F availability cap clamps the offered range
    # to rating 4 -- the dropdown must not offer 5 or 6.
    client = TestClient(create_app())
    _confirm_human(client)

    response = client.post("/ui/resources", data={})

    assert 'name="rating_Fake SIN"' in response.text
    # A rough check that the option range stops at 4: option value 5 for that select must not exist.
    assert (
        '<option value="5"'
        not in response.text.split('name="rating_Fake SIN"')[1].split("</select>")[0]
    )


def test_save_load_round_trips_rating_priced_gear() -> None:
    # WP66: a Rating-priced purchase persists its chosen rating across save/load and shows it on
    # the reloaded character sheet.
    client = TestClient(create_app())
    _confirm_human(client)
    client.post("/ui/resources", data={"gear_Fake SIN": "1", "rating_Fake SIN": "4"})

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
    assert "Fake SIN (Rating 4) × 1" in sheet.text


def test_overspending_the_nuyen_budget_is_rejected() -> None:
    client = TestClient(create_app())
    _confirm_human(client)
    predator = next(item for item in STARTER_GEAR_CATALOG if item.name == "Ares Predator V")

    response = client.post("/ui/resources", data={f"gear_{predator.name}": "100"})

    assert response.status_code == 200
    assert "exceeds" in response.text


def test_converting_karma_to_nuyen_tops_up_the_displayed_budget() -> None:
    client = TestClient(create_app())
    _confirm_human(client)

    response = client.post("/ui/resources", data={"karma_converted": "5"})

    assert response.status_code == 200
    budget = PRIORITIES.resources["D"].nuyen
    assert f"{budget + 10000} / {budget + 10000}" in response.text
    assert "+10000 from" in response.text
    assert "Karma conversion" in response.text


def test_karma_conversion_enables_a_purchase_the_base_budget_alone_could_not() -> None:
    client = TestClient(create_app())
    _confirm_human(client)
    predator = next(item for item in STARTER_GEAR_CATALOG if item.name == "Ares Predator V")
    budget = PRIORITIES.resources["D"].nuyen
    # Enough Predators to exceed the base Resources D budget by less than 10 Karma's worth.
    quantity = (budget // predator.cost) + 1

    over_budget = client.post("/ui/resources", data={f"gear_{predator.name}": str(quantity)})
    assert "exceeds" in over_budget.text

    with_karma = client.post(
        "/ui/resources",
        data={f"gear_{predator.name}": str(quantity), "karma_converted": "10"},
    )
    assert "exceeds" not in with_karma.text
    assert with_karma.status_code == 200


def test_converting_more_than_ten_karma_is_rejected() -> None:
    client = TestClient(create_app())
    _confirm_human(client)

    response = client.post("/ui/resources", data={"karma_converted": "11"})

    assert response.status_code == 200
    assert "between 0 and 10" in response.text


def test_reconfirming_priorities_with_a_new_resources_letter_keeps_gear() -> None:
    """WP19: reconfirmation carries a committed gear purchase forward instead of resetting it (the
    pre-WP19 behavior recorded in `spec/worklogs/WP18.md`'s own manual check) -- the nuyen numbers
    are recomputed against the *new* Resources letter's budget, but the purchase itself survives.
    """
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
            "talent_letter": "E",
            "metatype_id": human_choice.metatype.id,
        },
    )
    response = client.get("/ui/page/equipment")  # WP97

    budget = PRIORITIES.resources["C"].nuyen
    assert f"{budget - meta_link.cost} / {budget}" in response.text
    assert 'value="1"' in response.text  # Meta Link's quantity is still shown, not reset to 0
    assert "No longer fits" not in response.text

    # The character sheet must also reflect the *new* budget, not a stale one carried over from
    # the old Resources letter (see `_resources_selection_for_display`'s own docstring).
    sheet = client.get("/character/sheet")
    assert f"{budget - meta_link.cost} / {budget}" in sheet.text


def test_reconfirming_priorities_with_a_lower_resources_budget_flags_the_existing_gear() -> None:
    client = TestClient(create_app())
    _confirm_human(client)  # Resources letter D, budget 50,000
    predator = next(item for item in STARTER_GEAR_CATALOG if item.name == "Ares Predator V")
    # 70 * 725 = 50,750 -- doesn't fit D's 50,000 budget, so confirm at Resources C (140,000)
    # first, where it does.
    heritage = PRIORITIES.heritage["A"]
    human_choice = next(
        c for c in metatype_choices(heritage, METATYPES) if c.metatype.name == "Human"
    )
    client.post(
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
    client.post("/ui/resources", data={f"gear_{predator.name}": "70"})

    # Now drop Resources back down to D -- the existing purchase no longer fits.
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
    new_budget = PRIORITIES.resources["D"].nuyen
    assert new_budget == 50000
    assert 'value="70"' in response.text
    assert f"-750 / {new_budget}" in response.text
    assert "No longer fits since priorities were last confirmed" in response.text
    assert "exceeds" in response.text


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


# --- WP107: quality instances (rating stepper, repeatable rows) -----------------------------------

_INDOMITABLE_MENTAL = next(q for q in MVP_QUALITIES if q.name == "Indomitable (Mental)")
_CODEBLOCK = next(q for q in MVP_QUALITIES if q.name == "Codeblock")


def test_a_rated_quality_gets_a_rating_stepper_and_costs_karma_times_rating() -> None:
    client = TestClient(create_app())
    _confirm_human(client)

    response = client.post(
        "/ui/qualities",
        data={
            "quality_id": _INDOMITABLE_MENTAL.id,
            f"quality_rating_{_INDOMITABLE_MENTAL.id}": "2",
        },
    )

    assert response.status_code == 200
    assert f"16 / {QUALITY_KARMA_LIMIT}" in response.text  # Positive Quality karma
    assert f'name="quality_rating_{_INDOMITABLE_MENTAL.id}"' in response.text
    assert 'value="2"' in response.text
    sheet = client.get("/character/sheet")
    assert "Indomitable (Mental) 2" in sheet.text


def test_a_rating_above_the_quality_s_maximum_is_rejected() -> None:
    client = TestClient(create_app())
    _confirm_human(client)

    response = client.post(
        "/ui/qualities",
        data={
            "quality_id": _INDOMITABLE_MENTAL.id,
            f"quality_rating_{_INDOMITABLE_MENTAL.id}": "4",
        },
    )

    assert "rating 4 is outside 1-3" in response.text


def test_a_repeatable_quality_offers_another_row_and_takes_two_instances() -> None:
    client = TestClient(create_app())
    _confirm_human(client)

    first = client.post(
        "/ui/qualities",
        data={"quality_id": _CODEBLOCK.id, f"quality_text_{_CODEBLOCK.id}": "Matrix Perception"},
    )
    # The committed instance keeps the bare-id key; the blank "another" row is `id:1`.
    assert f'value="{_CODEBLOCK.id}:1"' in first.text

    second = client.post(
        "/ui/qualities",
        data={
            "quality_id": [_CODEBLOCK.id, f"{_CODEBLOCK.id}:1"],
            f"quality_text_{_CODEBLOCK.id}": "Matrix Perception",
            f"quality_text_{_CODEBLOCK.id}:1": "Hack on the Fly",
        },
    )

    assert f"20 / {QUALITY_KARMA_LIMIT}" in second.text  # Negative Quality karma
    assert f'value="{_CODEBLOCK.id}:2"' in second.text
    sheet = client.get("/character/sheet")
    assert "Codeblock (Matrix Perception)" in sheet.text
    assert "Codeblock (Hack on the Fly)" in sheet.text


def test_two_instances_with_the_same_detail_are_rejected() -> None:
    client = TestClient(create_app())
    _confirm_human(client)

    response = client.post(
        "/ui/qualities",
        data={
            "quality_id": [_CODEBLOCK.id, f"{_CODEBLOCK.id}:1"],
            f"quality_text_{_CODEBLOCK.id}": "Matrix Perception",
            f"quality_text_{_CODEBLOCK.id}:1": "Matrix Perception",
        },
    )

    assert "the same quality instance was selected twice" in response.text


# --- WP108: a pick its gate no longer allows is flagged, not dropped ------------------------------

_LOW_LIGHT_VISION = next(q for q in MVP_QUALITIES if q.name == "Low-Light Vision")


def test_a_pick_that_stops_fitting_after_a_metatype_change_is_flagged_and_kept() -> None:
    """A Human buys Low-Light Vision, then becomes an Elf, who gets it free: the bought copy no
    longer fits. The page shows why and the nav marks the step, but nothing raises and the pick is
    kept for the player to remove."""
    client = TestClient(create_app())
    _confirm_human(client)
    client.post("/ui/qualities", data={"quality_id": _LOW_LIGHT_VISION.id})

    heritage = PRIORITIES.heritage["A"]
    elf = next(c for c in metatype_choices(heritage, METATYPES) if c.metatype.name == "Elf")
    client.post(
        "/ui/priorities",
        data={
            "heritage_letter": "A",
            "attributes_letter": "B",
            "skills_letter": "C",
            "resources_letter": "D",
            "talent_letter": "E",
            "metatype_id": elf.metatype.id,
        },
    )

    page = client.get("/ui/page/qualities")
    assert page.status_code == 200
    assert 'class="warning"' in page.text
    assert "not an MVP-offered quality id" in page.text
    assert "step-nav__item--stale" in page.text


# --- WP112: Exceptional Attribute's attribute choice ----------------------------------------------

_EXCEPTIONAL = next(q for q in MVP_QUALITIES if q.name == "Exceptional Attribute")


def test_exceptional_attribute_takes_an_attribute_and_raises_its_maximum() -> None:
    client = TestClient(create_app())
    _confirm_human(client)
    page = client.post("/ui/qualities", data={"quality_id": _EXCEPTIONAL.id})
    assert "needs one of" in page.text
    assert f'name="quality_choice_{_EXCEPTIONAL.id}"' in page.text

    client.post(
        "/ui/qualities",
        data={"quality_id": _EXCEPTIONAL.id, f"quality_choice_{_EXCEPTIONAL.id}": "STR"},
    )
    assert "Exceptional Attribute (STR)" in client.get("/character/sheet").text

    # Human STR is 1-6; with the quality, 7 (6 points) is legal.
    response = client.post("/ui/attributes", data={"attr_STR": "6"})
    assert "exceeds" not in response.text
    assert "STR" in client.get("/character/sheet").text
