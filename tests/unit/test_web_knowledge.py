"""WP49: Knowledge & Language skills UI, backed by `chummer5.engine.knowledge
.create_knowledge_selection` directly.

Cross-checks the UI's result against that engine function called directly with the same inputs,
same acceptance bar as WP15/WP16's own test modules: "manual walkthrough; values match engine
output for the same inputs."
"""

from fastapi.testclient import TestClient

from chummer5.data.metatypes import load_metatypes
from chummer5.data.priorities import load_priorities
from chummer5.data.qualities import load_qualities
from chummer5.engine.character import create_character, metatype_choices
from chummer5.engine.knowledge import (
    KnowledgeSkillPick,
    LanguageSkillPick,
    create_knowledge_selection,
)
from chummer5.web.app import create_app

METATYPES = load_metatypes()
PRIORITIES = load_priorities()
QUALITIES = load_qualities()

BILINGUAL_ID = next(q.id for q in QUALITIES if q.name == "Bilingual")


def _confirm_human(client: TestClient) -> None:
    """Same Heritage A / Attributes B / Skills C / Resources D combination WP14/WP15's own tests
    use, giving every test here a known, real (INT+LOG)*2 budget to check against (Human metatype
    minimum 1 for both, unspent -- a 4-point floor).
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


def _human_character(attribute_points: dict[str, int] | None = None):
    heritage = PRIORITIES.heritage["A"]
    human_choice = next(
        c for c in metatype_choices(heritage, METATYPES) if c.metatype.name == "Human"
    )
    return create_character(human_choice, "A", "B", PRIORITIES, attribute_points or {})


def test_index_before_confirmation_shows_placeholder() -> None:
    client = TestClient(create_app())

    response = client.get("/")

    assert (
        "Confirm a metatype and priorities above before adding knowledge/language skills."
        in response.text
    )


def test_index_after_confirmation_shows_full_budget() -> None:
    client = TestClient(create_app())
    _confirm_human(client)

    response = client.get("/")

    character = _human_character()
    free_points = character.attribute_value("INT") + character.attribute_value("LOG")
    free_points *= 2
    assert f"Free points remaining: {free_points} / {free_points}" in response.text
    assert "Native languages: up to 1 free" in response.text


def test_submitting_valid_knowledge_and_language_matches_engine_output() -> None:
    client = TestClient(create_app())
    _confirm_human(client)

    response = client.post(
        "/ui/knowledge",
        data={
            "knowledge_name_0": "Corporations",
            "knowledge_category_0": "Street",
            "knowledge_rating_0": "2",
            "language_name_0": "English",
            "language_rating_0": "0",
            "language_native_0": "on",
        },
    )

    assert response.status_code == 200
    character = _human_character()
    expected = create_knowledge_selection(
        character,
        (KnowledgeSkillPick(name="Corporations", category="Street", rating=2),),
        (LanguageSkillPick(name="English", rating=0, native=True),),
    )
    assert f"Free points remaining: {expected.free_points - expected.points_spent}" in (
        response.text
    )
    assert 'value="Corporations"' in response.text
    assert 'value="English"' in response.text


def test_submitting_over_budget_knowledge_is_rejected_and_state_unchanged() -> None:
    client = TestClient(create_app())
    _confirm_human(client)  # 4-point budget

    response = client.post(
        "/ui/knowledge",
        data={
            "knowledge_name_0": "Corporations",
            "knowledge_category_0": "Street",
            "knowledge_rating_0": "6",
        },
    )

    assert response.status_code == 200
    assert "exceeds the free budget" in response.text
    # Submitted (invalid) value is echoed back, per the skill-allocation precedent.
    assert 'value="Corporations"' in response.text

    index = client.get("/")
    assert "Free points remaining: 4 / 4" in index.text


def test_rejects_a_second_native_language_without_bilingual() -> None:
    client = TestClient(create_app())
    _confirm_human(client)

    response = client.post(
        "/ui/knowledge",
        data={
            "language_name_0": "English",
            "language_rating_0": "0",
            "language_native_0": "on",
            "language_name_1": "Sperethiel",
            "language_rating_1": "0",
            "language_native_1": "on",
        },
    )

    assert "at most 1 language" in response.text


def test_bilingual_quality_allows_a_second_native_language() -> None:
    client = TestClient(create_app())
    _confirm_human(client)
    client.post("/ui/qualities", data={"quality_id": [BILINGUAL_ID]})

    response = client.post(
        "/ui/knowledge",
        data={
            "language_name_0": "English",
            "language_rating_0": "0",
            "language_native_0": "on",
            "language_name_1": "Sperethiel",
            "language_rating_1": "0",
            "language_native_1": "on",
        },
    )

    assert response.status_code == 200
    assert "at most 1 language" not in response.text
    assert "Native languages: up to 2 free" in response.text


def test_reconfirming_a_lower_attributes_budget_flags_the_existing_knowledge_spend() -> None:
    client = TestClient(create_app())
    _confirm_human(client)
    # Raise INT so the free-point budget is large enough to spend more than the Human-minimum
    # 4-point floor.
    client.post("/ui/attributes", data={"attr_INT": "3"})
    client.post(
        "/ui/knowledge",
        data={
            "knowledge_name_0": "Corporations",
            "knowledge_category_0": "Street",
            "knowledge_rating_0": "6",
        },
    )

    # Lower INT back to 0 -- the knowledge spend no longer fits the shrunk budget. The attributes
    # POST response itself only re-renders `_attribute_allocation.html`, not every section -- the
    # staleness warning surfaces on the next full-page render instead (same as every other
    # carried-forward selection's WP19-style re-validation).
    client.post("/ui/attributes", data={"attr_INT": "0"})
    response = client.get("/")

    assert "No longer fits since attributes were last confirmed" in response.text
    # The committed selection itself survives (still shown, not discarded).
    assert 'value="Corporations"' in response.text


# WP53: Karma-funded Knowledge/Language rating increases.


def test_submitting_karma_knowledge_points_matches_engine_output() -> None:
    client = TestClient(create_app())
    _confirm_human(client)  # 4-point free budget

    response = client.post(
        "/ui/knowledge",
        data={
            "knowledge_name_0": "Corporations",
            "knowledge_category_0": "Street",
            "knowledge_rating_0": "2",
            "knowledge_karma_0": "1",
        },
    )

    assert response.status_code == 200
    # 2->3 costs new_rating x 1 = 3 Karma.
    assert "Karma remaining for knowledge/language: 22 / 25" in response.text


def test_submitting_karma_language_points_matches_engine_output() -> None:
    client = TestClient(create_app())
    _confirm_human(client)

    response = client.post(
        "/ui/knowledge",
        data={
            "language_name_0": "Japanese",
            "language_rating_0": "1",
            "language_karma_0": "2",
        },
    )

    assert response.status_code == 200
    # 1->2 (2) + 2->3 (3) = 5 Karma.
    assert "Karma remaining for knowledge/language: 20 / 25" in response.text


def test_submitting_karma_knowledge_points_above_the_chargen_rating_cap_is_rejected() -> None:
    client = TestClient(create_app())
    _confirm_human(client)
    # Raise the free-point budget enough to legally spend 5 points on one pick (4-point floor is
    # too small on its own).
    client.post("/ui/attributes", data={"attr_INT": "1"})

    response = client.post(
        "/ui/knowledge",
        data={
            "knowledge_name_0": "Corporations",
            "knowledge_category_0": "Street",
            "knowledge_rating_0": "5",
            "knowledge_karma_0": "2",  # 5 + 2 = 7, over the chargen cap of 6
        },
    )

    assert response.status_code == 200
    assert "exceeds the chargen skill rating maximum" in response.text


def test_character_sheet_shows_karma_boosted_knowledge_rating() -> None:
    client = TestClient(create_app())
    _confirm_human(client)
    client.post(
        "/ui/knowledge",
        data={
            "knowledge_name_0": "Corporations",
            "knowledge_category_0": "Street",
            "knowledge_rating_0": "2",
            "knowledge_karma_0": "1",
        },
    )

    response = client.get("/character/sheet")

    assert response.status_code == 200
    assert "Knowledge/language karma cost: 3." in response.text
