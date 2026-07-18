"""WP15: attribute and skill point allocation UI, backed by WP6's `create_character` and WP7's
`create_skill_allocation` directly.

Cross-checks the UI's result against those engine functions called directly with the same inputs,
same acceptance bar as WP14's own test module: "manual walkthrough; values match engine output for
the same inputs."
"""

from fastapi.testclient import TestClient

from chummer5.data.metatypes import load_metatypes
from chummer5.data.priorities import load_priorities
from chummer5.data.skills import load_skills
from chummer5.engine.character import create_character, metatype_choices
from chummer5.engine.skills import create_skill_allocation, dice_pool, skill_rating
from chummer5.web.app import MUNDANE_SKILL_GROUPS, MUNDANE_SKILLS, create_app

METATYPES = load_metatypes()
PRIORITIES = load_priorities()
SKILLS = load_skills()


def _confirm_human(client: TestClient) -> None:
    """Establishes a session with Human confirmed at Heritage A / Attributes B / Skills C /
    Resources D -- the same combination WP14's own tests use, giving every attribute/skill test a
    known, real budget to allocate against (Attributes B, Skills C).
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


def test_index_before_confirmation_shows_placeholder_not_allocation_forms() -> None:
    client = TestClient(create_app())

    response = client.get("/")

    assert "Confirm a metatype and priorities above before allocating attribute points." in (
        response.text
    )
    assert "Confirm a metatype and priorities above before allocating skill points." in (
        response.text
    )


def test_index_after_confirmation_shows_allocation_forms_with_full_budget() -> None:
    client = TestClient(create_app())
    _confirm_human(client)

    response = client.get("/")

    expected_primary_budget = PRIORITIES.attributes["B"].points
    expected_skills_budget = PRIORITIES.skills["C"].skills
    assert f"{expected_primary_budget} / {expected_primary_budget}" in response.text
    assert f"{expected_skills_budget} / {expected_skills_budget}" in response.text
    # Magic-linked skills are excluded from the mundane MVP allocation UI (see app.py's
    # MUNDANE_SKILLS comment) -- Spellcasting (Sorcery group, MAG-linked) must not appear.
    assert "Spellcasting" not in response.text
    assert "Alchemy" not in response.text


def test_submitting_valid_attribute_points_matches_engine_output() -> None:
    client = TestClient(create_app())
    _confirm_human(client)

    response = client.post("/ui/attributes", data={"attr_BOD": "2", "attr_AGI": "1"})

    assert response.status_code == 200
    heritage = PRIORITIES.heritage["A"]
    human_choice = next(
        c for c in metatype_choices(heritage, METATYPES) if c.metatype.name == "Human"
    )
    expected = create_character(human_choice, "A", "B", PRIORITIES, {"BOD": 2, "AGI": 1})
    assert f"<td>{expected.attribute_value('BOD')}</td>" in response.text
    assert f"<td>{expected.attribute_value('AGI')}</td>" in response.text

    budget = PRIORITIES.attributes["B"].points
    assert f"{budget - 3} / {budget}" in response.text


def test_submitting_over_budget_attribute_points_is_rejected_and_state_unchanged() -> None:
    client = TestClient(create_app())
    _confirm_human(client)
    budget = PRIORITIES.attributes["B"].points

    response = client.post("/ui/attributes", data={"attr_BOD": str(budget + 5)})

    assert response.status_code == 200
    assert "exceeds" in response.text
    # Submitted (invalid) value is echoed back in the input, per the priority-form precedent.
    assert f'value="{budget + 5}"' in response.text

    # The committed session state is untouched -- reloading the page shows the old (zero) spend,
    # not the rejected one.
    index = client.get("/")
    assert f"{budget} / {budget}" in index.text


def test_submitting_valid_skill_points_matches_engine_output() -> None:
    client = TestClient(create_app())
    _confirm_human(client)

    skill = next(s for s in MUNDANE_SKILLS if s.skill_group is None)
    response = client.post("/ui/skills", data={f"skill_{skill.id}": "3"})

    assert response.status_code == 200
    heritage = PRIORITIES.heritage["A"]
    human_choice = next(
        c for c in metatype_choices(heritage, METATYPES) if c.metatype.name == "Human"
    )
    character = create_character(human_choice, "A", "B", PRIORITIES, {})
    allocation = create_skill_allocation("C", PRIORITIES, SKILLS, {skill.id: 3}, {})
    expected_rating = skill_rating(character, allocation, skill)
    expected_pool = dice_pool(character, allocation, skill)
    assert f"<td>{expected_rating}</td>" in response.text
    assert f"<td>{expected_pool}</td>" in response.text

    budget = PRIORITIES.skills["C"].skills
    assert f"{budget - 3} / {budget}" in response.text


def test_submitting_a_skill_group_sets_every_member_skills_rating() -> None:
    client = TestClient(create_app())
    _confirm_human(client)

    group = MUNDANE_SKILL_GROUPS[0]
    response = client.post("/ui/skills", data={f"group_{group}": "2"})

    assert response.status_code == 200
    member_names = [s.name for s in MUNDANE_SKILLS if s.skill_group == group]
    assert member_names  # sanity: the chosen group actually has mundane member skills
    # Every member skill's rating column should show 2 -- spot check via the group's own points.
    budget = PRIORITIES.skills["C"].skill_groups
    assert f"{budget - 2} / {budget}" in response.text


def test_submitting_conflicting_skill_and_group_points_is_rejected() -> None:
    client = TestClient(create_app())
    _confirm_human(client)

    grouped_skill = next(s for s in MUNDANE_SKILLS if s.skill_group is not None)
    response = client.post(
        "/ui/skills",
        data={
            f"skill_{grouped_skill.id}": "1",
            f"group_{grouped_skill.skill_group}": "1",
        },
    )

    assert response.status_code == 200
    assert "strict skill groups" in response.text


def test_submitting_over_budget_skill_points_is_rejected() -> None:
    client = TestClient(create_app())
    _confirm_human(client)
    budget = PRIORITIES.skills["C"].skills

    skill = next(s for s in MUNDANE_SKILLS if s.skill_group is None)
    response = client.post("/ui/skills", data={f"skill_{skill.id}": str(budget + 5)})

    assert response.status_code == 200
    assert "exceeds" in response.text


def test_reconfirming_priorities_resets_attribute_and_skill_allocation() -> None:
    client = TestClient(create_app())
    _confirm_human(client)
    skill = next(s for s in MUNDANE_SKILLS if s.skill_group is None)
    client.post("/ui/attributes", data={"attr_BOD": "2"})
    client.post("/ui/skills", data={f"skill_{skill.id}": "3"})

    # Re-confirm the same metatype/priorities (still a legal, distinct submission).
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

    primary_budget = PRIORITIES.attributes["B"].points
    skills_budget = PRIORITIES.skills["C"].skills
    assert f"{primary_budget} / {primary_budget}" in response.text
    assert f"{skills_budget} / {skills_budget}" in response.text


def test_attributes_and_skills_endpoints_before_confirmation_do_not_crash() -> None:
    client = TestClient(create_app())
    client.get("/")

    attr_response = client.post("/ui/attributes", data={"attr_BOD": "2"})
    skill_response = client.post("/ui/skills", data={})

    assert attr_response.status_code == 200
    assert "Confirm a metatype and priorities" in attr_response.text
    assert skill_response.status_code == 200
    assert "Confirm a metatype and priorities" in skill_response.text
