"""WP61: whole-page one-section-open-at-a-time accordion, bundled into the same WP as the
Magical-Active-skill-picker fix and skill-category grouping per an explicit follow-up request.

All 14 `_chargen_body.html` sections share `<details name="chargen-section">` -- native browser
mutual exclusion, no JS. `ChargenSession.open_section` tracks which one currently renders open;
every section's own successful `POST` sets it to that section's own id. A collapsed section with an
active error/budget-warning shows a visible marker (`⚠`) on its `<summary>` so a WP19-style
"no longer fits" diagnostic isn't hidden just because that section happens to be collapsed.
"""

from fastapi.testclient import TestClient

from chummer5.data.metatypes import load_metatypes
from chummer5.data.priorities import load_priorities
from chummer5.engine.character import metatype_choices
from chummer5.web.app import create_app

METATYPES = load_metatypes()
PRIORITIES = load_priorities()


def _confirm_human(client: TestClient) -> None:
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


def test_fresh_session_shows_only_the_priority_section_open() -> None:
    client = TestClient(create_app())

    response = client.get("/")

    assert response.text.count('<details name="chargen-section"') == 1
    assert '<details name="chargen-section" open>' in response.text


def test_confirming_priorities_and_attributes_moves_the_open_section() -> None:
    client = TestClient(create_app())
    _confirm_human(client)

    response = client.get("/")
    priority_idx = response.text.find('id="priority-section"')
    priority_segment = response.text[priority_idx : priority_idx + 200]
    assert '<details name="chargen-section" open>' in priority_segment

    client.post("/ui/attributes", data={"attr_BOD": "2"})
    response2 = client.get("/")

    priority_idx2 = response2.text.find('id="priority-section"')
    priority_segment2 = response2.text[priority_idx2 : priority_idx2 + 200]
    assert '<details name="chargen-section" open>' not in priority_segment2

    attribute_idx = response2.text.find('id="attribute-allocation"')
    attribute_segment = response2.text[attribute_idx : attribute_idx + 200]
    assert '<details name="chargen-section" open>' in attribute_segment

    # Exactly one section open at a time across the whole page.
    assert response2.text.count('<details name="chargen-section" open>') == 1


def test_submitting_a_sections_own_form_reopens_it_even_on_a_validation_error() -> None:
    client = TestClient(create_app())
    _confirm_human(client)
    client.post("/ui/attributes", data={"attr_BOD": "2"})  # attribute-allocation now open

    budget = PRIORITIES.skills["C"].skills
    response = client.post("/ui/skills", data={"karma_skill_nonexistent": "1"})
    # A structurally-invalid submission (unknown id) still opens the section that was submitted --
    # confirms the "open_section" update isn't conditional on the submission actually validating.
    assert response.status_code == 200

    index = client.get("/")
    skill_idx = index.text.find('id="skill-allocation"')
    skill_segment = index.text[skill_idx : skill_idx + 200]
    assert '<details name="chargen-section" open>' in skill_segment
    assert budget >= 0  # sanity: PRIORITIES loaded correctly for this session


def test_collapsed_section_with_an_active_warning_shows_a_marker_on_its_summary() -> None:
    """The WP19 acceptance scenario (see test_web_attribute_skill_allocation.py's own version),
    re-run here to confirm the new warning marker survives that section being collapsed.
    """
    client = TestClient(create_app())
    _confirm_human(client)  # Attributes letter B, budget 20
    client.post("/ui/attributes", data={"attr_BOD": "5", "attr_AGI": "5", "attr_REA": "5"})

    heritage = PRIORITIES.heritage["A"]
    human_choice = next(
        c for c in metatype_choices(heritage, METATYPES) if c.metatype.name == "Human"
    )
    # Reconfirming priorities opens the priority-section, not attribute-allocation -- so the
    # Attributes section is collapsed on this render despite now being invalid.
    response = client.post(
        "/ui/priorities",
        data={
            "heritage_letter": "A",
            "attributes_letter": "D",
            "skills_letter": "C",
            "resources_letter": "B",
            "talent_letter": "E",
            "metatype_id": human_choice.metatype.id,
        },
    )

    attribute_idx = response.text.find('id="attribute-allocation"')
    attribute_segment = response.text[attribute_idx : attribute_idx + 200]
    assert '<details name="chargen-section" >' in attribute_segment  # collapsed, not open
    assert "<summary>Attributes ⚠</summary>" in attribute_segment
