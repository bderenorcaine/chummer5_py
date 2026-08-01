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


def test_submitting_sum_to_ten_with_repeated_letters_summing_to_10_is_accepted() -> None:
    """WP44: Sum-to-Ten allows repeats across the 5 categories, as long as their point values
    (A=4/B=3/C=2/D=1/E=0) total exactly 10 -- Bastion.chum5's own real letters (Heritage E,
    Talent C, Attributes A, Skills E, Resources A -- repeats both E and A) confirm this is a real,
    fixture-backed combination, not just a hand-picked one.
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
            "attributes_letter": "A",
            "skills_letter": "E",
            "resources_letter": "A",
            "talent_letter": "C",
            "build_method": "SumtoTen",
            "metatype_id": human_choice.metatype.id,
        },
    )

    assert response.status_code == 200
    assert "Confirmed: Human" in response.text
    assert "different priority letter" not in response.text


def test_submitting_sum_to_ten_under_target_is_rejected() -> None:
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
            "attributes_letter": "E",
            "skills_letter": "E",
            "resources_letter": "E",
            "talent_letter": "E",
            "build_method": "SumtoTen",
            "metatype_id": human_choice.metatype.id,
        },
    )

    assert response.status_code == 200
    assert "must total exactly 10" in response.text
    assert "Confirmed:" not in response.text


def test_submitting_sum_to_ten_over_target_is_rejected() -> None:
    """Confirms the rule is exact equality, not a ceiling -- exceeding 10 is just as invalid as
    falling short (see `chummer5.engine.build_method`'s own docstring for the legacy citation this
    corrects against the Implementation Plan's original "must not exceed" phrasing).
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
            "attributes_letter": "A",
            "skills_letter": "A",
            "resources_letter": "A",
            "talent_letter": "A",
            "build_method": "SumtoTen",
            "metatype_id": human_choice.metatype.id,
        },
    )

    assert response.status_code == 200
    assert "must total exactly 10" in response.text
    assert "Confirmed:" not in response.text


def test_submitting_unsupported_build_method_is_rejected() -> None:
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
            "talent_letter": "E",
            "build_method": "Karma",
            "metatype_id": human_choice.metatype.id,
        },
    )

    assert response.status_code == 200
    assert "Unsupported build method" in response.text
    assert "Confirmed:" not in response.text


def test_priority_form_defaults_to_priority_build_method_when_field_omitted() -> None:
    """Pre-WP44 form submissions (and every other test in this file) never send `build_method` at
    all -- the route's own `Form(PRIORITY_BUILD_METHOD)` default must keep applying Priority's
    bijection rule rather than erroring on a missing field.
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
            "attributes_letter": "A",  # repeats Heritage -- illegal under Priority
            "skills_letter": "C",
            "resources_letter": "D",
            "talent_letter": "E",
            "metatype_id": human_choice.metatype.id,
        },
    )

    assert response.status_code == 200
    assert "different priority letter" in response.text


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


def test_stylesheet_is_served_locally_and_separates_the_chargen_sections() -> None:
    # The chargen page stacks ~14 sections in one #chargen-body (see _chargen_body.html); without
    # a stylesheet they ran together as undifferentiated text. Served from the same local /static
    # mount as htmx, for the same no-CDN reason.
    client = TestClient(create_app())

    index = client.get("/")
    assert "/static/app.css" in index.text

    sheet = client.get("/static/app.css")
    assert sheet.status_code == 200
    # Each section is its own box, and adjacent ones are told apart two ways (rule + alternating
    # tint) so two *collapsed* neighbours still read as two things.
    assert "#chargen-body > div {" in sheet.text
    assert "border-top" in sheet.text
    assert "#chargen-body > div:nth-child(even)" in sheet.text
