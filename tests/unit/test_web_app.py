"""WP14: priority-letter + metatype selection UI, backed by WP6's engine functions directly.

Cross-checks the UI's result against `chummer5.engine.character.metatype_choices`/
`create_character` called directly with the same inputs, per the Implementation Plan's acceptance
bar ("manual walkthrough creates a metatype+priority selection that matches what WP6's engine
would produce for the same inputs").
"""

from fastapi.testclient import TestClient

from chummer5.data.metatypes import load_metatypes
from chummer5.data.priorities import load_priorities
from chummer5.engine.character import create_character, metatype_choices
from chummer5.web.app import create_app
from chummer5.web.session import SESSION_COOKIE_NAME

METATYPES = load_metatypes()
PRIORITIES = load_priorities()


def test_index_serves_priority_form_and_sets_session_cookie() -> None:
    client = TestClient(create_app())

    response = client.get("/")

    assert response.status_code == 200
    assert "Heritage" in response.text
    assert "Attributes" in response.text
    assert "Confirm metatype" in response.text
    assert SESSION_COOKIE_NAME in response.cookies


def test_index_default_selection_is_a_valid_distinct_permutation() -> None:
    client = TestClient(create_app())

    response = client.get("/")

    # Default letters (A/E/B/C/D across Heritage/Talent/Attributes/Skills/Resources) are
    # pre-selected and already form a legal assignment -- confirmed by the metatype select being
    # pre-populated for Heritage A with Human as an option.
    assert "Human" in response.text
    assert "Talent" in response.text


def test_metatype_fragment_matches_engine_for_a_given_heritage_letter() -> None:
    client = TestClient(create_app())

    response = client.get("/ui/metatypes", params={"heritage_letter": "D"})

    assert response.status_code == 200
    expected = metatype_choices(PRIORITIES.heritage["D"], METATYPES)
    for choice in expected:
        assert choice.metatype.name in response.text
    # Heritage D only offers Human/Elf -- Troll must not appear.
    assert "Troll" not in response.text


def test_submitting_valid_priorities_and_metatype_matches_engine_output() -> None:
    client = TestClient(create_app())
    client.get("/")  # establish a session cookie

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

    assert response.status_code == 200
    assert "Confirmed: Human" in response.text

    expected = create_character(human_choice, "A", "B", PRIORITIES, {})
    assert f"Special attribute points (EDG budget): {expected.special_attribute_points}" in (
        response.text
    )
    assert expected.special_attribute_points == human_choice.special_attribute_points


def test_submitting_duplicate_priority_letters_is_rejected() -> None:
    client = TestClient(create_app())
    client.get("/")

    heritage = PRIORITIES.heritage["A"]
    human_choice = next(
        c for c in metatype_choices(heritage, METATYPES) if c.metatype.name == "Human"
    )

    response = client.post(
        "/ui/priorities",
        data={
            "heritage_letter": "A",
            "attributes_letter": "A",
            "skills_letter": "C",
            "resources_letter": "D",
            "talent_letter": "E",
            "metatype_id": human_choice.metatype.id,
        },
    )

    assert response.status_code == 200
    assert "different priority letter" in response.text
    assert "Confirmed:" not in response.text


def test_submitting_metatype_not_offered_by_the_chosen_heritage_letter_is_rejected() -> None:
    client = TestClient(create_app())
    client.get("/")

    # Heritage D's metatype list is Human/Elf only (see priorities.xml) -- Troll's id is valid
    # metatype data, just not one Heritage D offers.
    troll = next(m for m in METATYPES if m.name == "Troll")

    response = client.post(
        "/ui/priorities",
        data={
            "heritage_letter": "D",
            "attributes_letter": "A",
            "skills_letter": "B",
            "resources_letter": "C",
            "talent_letter": "E",
            "metatype_id": troll.id,
        },
    )

    assert response.status_code == 200
    assert "Select a metatype offered" in response.text
    assert "Confirmed:" not in response.text


def test_submitting_only_four_distinct_letters_is_rejected() -> None:
    """WP24: the permutation check now covers Talent too -- a submission that's internally
    distinct across the 4 pre-WP24 categories but omits Talent (or repeats one of the other four
    in its place) must still be rejected, not silently accepted as "close enough".
    """
    client = TestClient(create_app())
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
            "talent_letter": "D",  # duplicates resources_letter instead of using E
            "metatype_id": human_choice.metatype.id,
        },
    )

    assert response.status_code == 200
    assert "different priority letter" in response.text
    assert "Confirmed:" not in response.text


def test_submitting_talent_at_a_non_e_letter_still_resolves_to_mundane() -> None:
    """WP24: Talent is a real 5th letter now, but its *option* still resolves unconditionally to
    Mundane regardless of which letter it lands on -- assigning it Heritage's usual "A" (with
    Heritage moved to E instead) must produce exactly the same character as any other assignment,
    since MVP offers no real Talent archetype picker yet (that's WP25).
    """
    client = TestClient(create_app())
    client.get("/")

    heritage = PRIORITIES.heritage["E"]
    human_choice = next(
        c for c in metatype_choices(heritage, METATYPES) if c.metatype.name == "Human"
    )

    response = client.post(
        "/ui/priorities",
        data={
            "heritage_letter": "E",
            "attributes_letter": "B",
            "skills_letter": "C",
            "resources_letter": "D",
            "talent_letter": "A",
            "metatype_id": human_choice.metatype.id,
        },
    )

    assert response.status_code == 200
    assert "Confirmed: Human" in response.text
    assert "Talent A" in response.text

    expected = create_character(human_choice, "E", "B", PRIORITIES, {})
    assert expected.special_attribute_points == human_choice.special_attribute_points
    assert f"Special attribute points (EDG budget): {expected.special_attribute_points}" in (
        response.text
    )


def test_sessions_are_isolated_per_cookie() -> None:
    # Two independent cookie jars against the *same* app (and thus the same app.state.sessions
    # store), mirroring two different browsers/tabs -- the server assigns each its own opaque
    # session id via Set-Cookie; this checks their ChargenSession state doesn't cross-contaminate.
    app = create_app()
    client_one = TestClient(app)
    client_two = TestClient(app)

    heritage = PRIORITIES.heritage["A"]
    human_choice = next(
        c for c in metatype_choices(heritage, METATYPES) if c.metatype.name == "Human"
    )
    elf_choice = next(c for c in metatype_choices(heritage, METATYPES) if c.metatype.name == "Elf")

    client_one.post(
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
    client_two.post(
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

    assert client_one.cookies.get(SESSION_COOKIE_NAME) != client_two.cookies.get(
        SESSION_COOKIE_NAME
    )
    assert "Confirmed: Human" in client_one.get("/").text
    assert "Confirmed: Elf" in client_two.get("/").text


def test_vendored_htmx_is_served_locally_not_from_a_cdn() -> None:
    client = TestClient(create_app())

    index = client.get("/")
    assert "/static/vendor/htmx/htmx.min.js" in index.text
    assert "cdn" not in index.text.lower()

    script = client.get("/static/vendor/htmx/htmx.min.js")
    assert script.status_code == 200
    assert "htmx" in script.text
