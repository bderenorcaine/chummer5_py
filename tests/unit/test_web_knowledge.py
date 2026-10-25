"""WP49: Knowledge & Language skills UI, backed by `chummer5.engine.knowledge
.create_knowledge_selection` directly. WP149: one table for both kinds -- a Language row is a
`knowledge_*_<i>` row whose category is Language -- and the Kn/Ka figures are the Skills strip's
counters.

Cross-checks the UI's result against that engine function called directly with the same inputs,
same acceptance bar as WP15/WP16's own test modules: "manual walkthrough; values match engine
output for the same inputs."
"""

import re

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


def _counter(client: TestClient, label: str) -> str:
    """WP148: one of the Skills strip's counters, as "remaining/budget"."""
    strip = client.get("/ui/tabs/skills?tab=knowledge").text
    match = re.search(
        rf'<abbr[^>]*>{label}</abbr></dt>\s*<dd class="view-counter__value">([^<]+)</dd>', strip
    )
    assert match is not None, label
    return match.group(1)


def _language(i: int, name: str, rating: int = 0, *, native: bool = False) -> dict[str, str]:
    """WP149: a Language row of the Knowledge tab's table."""
    row = {
        f"knowledge_name_{i}": name,
        f"knowledge_category_{i}": "Language",
        f"knowledge_rating_{i}": str(rating),
    }
    return row | ({f"knowledge_native_{i}": "on"} if native else {})


def _human_character(attribute_points: dict[str, int] | None = None):
    heritage = PRIORITIES.heritage["A"]
    human_choice = next(
        c for c in metatype_choices(heritage, METATYPES) if c.metatype.name == "Human"
    )
    return create_character(human_choice, "A", "B", PRIORITIES, attribute_points or {})


def test_index_before_confirmation_shows_placeholder() -> None:
    client = TestClient(create_app())

    response = client.get("/ui/page/skills")

    assert (
        "Confirm a metatype and priorities on the Priorities page before adding knowledge/"
        "language skills." in response.text
    )


def test_index_after_confirmation_shows_full_budget() -> None:
    client = TestClient(create_app())
    _confirm_human(client)

    response = client.get("/ui/page/skills")

    character = _human_character()
    free_points = character.attribute_value("INT") + character.attribute_value("LOG")
    free_points *= 2
    assert response.status_code == 200
    assert _counter(client, "Kn") == f"{free_points}/{free_points}"
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
            **_language(1, "English", native=True),
        },
    )

    assert response.status_code == 200
    character = _human_character()
    expected = create_knowledge_selection(
        character,
        (KnowledgeSkillPick(name="Corporations", category="Street", rating=2),),
        (LanguageSkillPick(name="English", rating=0, native=True),),
    )
    remaining = expected.free_points - expected.points_spent
    assert _counter(client, "Kn") == f"{remaining}/{expected.free_points}"
    assert 'value="Corporations"' in response.text
    assert 'value="English"' in response.text


def test_pool_column_renders_dice_pools_for_knowledge_and_language() -> None:
    # WP68. Human A/B/C/D: INT 1, LOG 1 unspent. Street knowledge links to INT (pool = 1 + rating);
    # every language links to INT too; a native language shows "N", not a number.
    client = TestClient(create_app())
    _confirm_human(client)

    response = client.post(
        "/ui/knowledge",
        data={
            "knowledge_name_0": "Corporations",
            "knowledge_category_0": "Street",
            "knowledge_rating_0": "2",
            **_language(1, "Japanese", 1),
            **_language(2, "English", native=True),
        },
    )

    assert response.status_code == 200
    assert "<th>Pool</th>" in response.text
    assert "<td>3</td>" in response.text  # Street knowledge: INT 1 + rating 2
    assert "<td>2</td>" in response.text  # Japanese: INT 1 + rating 1
    assert "<td>N</td>" in response.text  # native English: fluency "N", no numeric pool


def _six_knowledge_skills_at_6() -> dict[str, str]:
    names = ("Corporations", "Gangs", "Fixers", "Bars", "Clinics", "Docks")
    data: dict[str, str] = {}
    for i, name in enumerate(names):
        data |= {
            f"knowledge_name_{i}": name,
            f"knowledge_category_{i}": "Street",
            f"knowledge_rating_{i}": "6",
        }
    return data


def test_submitting_over_budget_knowledge_is_rejected_and_state_unchanged() -> None:
    client = TestClient(create_app())
    _confirm_human(client)  # 4-point budget

    # WP125: past the 4 free points, Skills C's 28 Active points pay too -- 36 exceeds both.
    response = client.post("/ui/knowledge", data=_six_knowledge_skills_at_6())

    assert response.status_code == 200
    assert "exceeds the free budget" in response.text
    # Submitted (invalid) value is echoed back, per the skill-allocation precedent.
    assert 'value="Corporations"' in response.text

    assert _counter(client, "Kn") == "4/4"


def test_rejects_a_second_native_language_without_bilingual() -> None:
    client = TestClient(create_app())
    _confirm_human(client)

    response = client.post(
        "/ui/knowledge",
        data=_language(0, "English", native=True) | _language(1, "Sperethiel", native=True),
    )

    assert "at most 1 language" in response.text


def test_bilingual_quality_allows_a_second_native_language() -> None:
    client = TestClient(create_app())
    _confirm_human(client)
    client.post("/ui/qualities", data={"quality_id": [BILINGUAL_ID]})

    response = client.post(
        "/ui/knowledge",
        data=_language(0, "English", native=True) | _language(1, "Sperethiel", native=True),
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
    # WP125: 36 points fit 10 free + 28 Active, and stop fitting when the free pool drops to 4.
    client.post("/ui/knowledge", data=_six_knowledge_skills_at_6())

    # Lower INT back to 0 -- the knowledge spend no longer fits the shrunk budget. The attributes
    # POST response itself only re-renders `_attribute_allocation.html`, not every section -- the
    # staleness warning surfaces on the next full-page render instead (same as every other
    # carried-forward selection's WP19-style re-validation).
    client.post("/ui/attributes", data={"attr_INT": "0"})
    response = client.get("/ui/page/skills")

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
    assert _counter(client, "Ka") == "22/25"


def test_submitting_karma_language_points_matches_engine_output() -> None:
    client = TestClient(create_app())
    _confirm_human(client)

    response = client.post(
        "/ui/knowledge",
        data=_language(0, "Japanese", 1) | {"knowledge_karma_0": "2"},
    )

    assert response.status_code == 200
    # 1->2 (2) + 2->3 (3) = 5 Karma.
    assert _counter(client, "Ka") == "20/25"


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
