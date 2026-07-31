"""WP48: the Mentor Spirit archetype picker reaching the browser (`POST /ui/qualities`), plus the
character sheet's new Mentor Spirit line. Same "no real fixture exercises this" honesty caveat as
WP46/47's own web tests -- neither of the corpus's 2 real magic fixtures has a selected Mentor
Spirit, so this module builds a Magician/Adept from scratch through the browser, reusing
`test_web_foci.py`'s own `_confirm_human`/`_confirm_magician`/`_confirm_adept` shape.
"""

from __future__ import annotations

import json
import re

from fastapi.testclient import TestClient

from chummer5.data.mentors import load_mentors
from chummer5.data.metatypes import load_metatypes
from chummer5.data.priorities import load_priorities
from chummer5.data.qualities import load_qualities
from chummer5.data.skills import load_skills
from chummer5.data.traditions import load_traditions
from chummer5.engine.character import metatype_choices
from chummer5.web.app import create_app

METATYPES = load_metatypes()
PRIORITIES = load_priorities()
SKILLS = load_skills()
TRADITIONS = load_traditions()
MENTORS = load_mentors()
QUALITIES = load_qualities()

HERMETIC = next(t for t in TRADITIONS if t.name == "Hermetic")
SPELLCASTING = next(s for s in SKILLS if s.name == "Spellcasting")
COUNTERSPELLING = next(s for s in SKILLS if s.name == "Counterspelling")
PISTOLS = next(s for s in SKILLS if s.name == "Pistols")
DOG = next(m for m in MENTORS if m.name == "Dog")  # single-option General, FLAT_BONUS
CAT = next(m for m in MENTORS if m.name == "Cat")  # 2-option General
CAT_SNEAKING = next(c for c in CAT.general_options if c.name == "+2 dice on Sneaking Tests")
MENTOR_SPIRIT_QUALITY_ID = next(q.id for q in QUALITIES if q.name == "Mentor Spirit")
CATLIKE_ID = next(q.id for q in QUALITIES if q.name == "Catlike")


def _compact(html: str) -> str:
    return re.sub(r">\s+<", "><", html)


def _confirm_human(client: TestClient, *, talent_letter: str) -> None:
    client.get("/")
    heritage_letter = "D" if talent_letter == "E" else "E"
    other = [letter for letter in ("B", "C", "D") if letter != talent_letter]
    heritage = PRIORITIES.heritage[heritage_letter]
    human_choice = next(
        c for c in metatype_choices(heritage, METATYPES) if c.metatype.name == "Human"
    )
    response = client.post(
        "/ui/priorities",
        data={
            "heritage_letter": heritage_letter,
            "talent_letter": talent_letter,
            "attributes_letter": other[0],
            "skills_letter": other[1],
            "resources_letter": "A",
            "metatype_id": human_choice.metatype.id,
        },
    )
    assert "Confirmed: Human" in response.text


def _confirm_magician(client: TestClient, *, talent_letter: str = "B") -> None:
    _confirm_human(client, talent_letter=talent_letter)
    response = client.post(
        "/ui/talent",
        data={
            "talent_letter": talent_letter,
            "talent_codename": "Magician",
            "tradition_id": HERMETIC.id,
            "granted_skill_id": [SPELLCASTING.id, COUNTERSPELLING.id],
        },
    )
    assert "Confirmed: Magician (Hermetic)" in response.text


def _confirm_adept(client: TestClient, *, talent_letter: str = "D") -> None:
    _confirm_human(client, talent_letter=talent_letter)
    response = client.post(
        "/ui/talent",
        data={"talent_letter": talent_letter, "talent_codename": "Adept"},
    )
    assert "Confirmed: Adept" in response.text


def test_archetype_picker_hidden_for_mundane() -> None:
    client = TestClient(create_app())
    _confirm_human(client, talent_letter="E")

    response = client.get("/")

    assert "Mentor Spirit" not in response.text


def test_archetype_picker_shown_for_magician() -> None:
    client = TestClient(create_app())
    _confirm_magician(client)

    response = client.get("/")

    assert "Mentor Spirit archetype" in response.text
    assert DOG.name in response.text


def test_archetype_picker_shown_for_adept_too() -> None:
    client = TestClient(create_app())
    _confirm_adept(client)

    response = client.get("/")

    assert "Mentor Spirit archetype" in response.text


def test_picking_a_single_option_archetype_shows_on_the_sheet() -> None:
    client = TestClient(create_app())
    _confirm_magician(client)

    response = client.post(
        "/ui/qualities",
        data={"quality_id": [MENTOR_SPIRIT_QUALITY_ID], "mentor_spirit_archetype_id": DOG.id},
    )

    assert response.status_code == 200
    assert "Positive Quality karma: 5" in _compact(response.text)

    sheet = client.get("/character/sheet")
    assert "Dog" in sheet.text
    assert DOG.magician_choice.name in sheet.text


def test_two_option_general_choice_requires_a_pick() -> None:
    client = TestClient(create_app())
    _confirm_magician(client)

    response = client.post(
        "/ui/qualities",
        data={"quality_id": [MENTOR_SPIRIT_QUALITY_ID], "mentor_spirit_archetype_id": CAT.id},
    )

    assert "a General bonus option must be chosen" in response.text


def test_two_option_general_choice_resolves_when_picked() -> None:
    client = TestClient(create_app())
    _confirm_magician(client)

    client.post(
        "/ui/qualities",
        data={
            "quality_id": [MENTOR_SPIRIT_QUALITY_ID],
            "mentor_spirit_archetype_id": CAT.id,
            "mentor_spirit_general_choice_id": CAT_SNEAKING.id,
        },
    )

    sheet = client.get("/character/sheet")
    assert CAT_SNEAKING.name in sheet.text


def test_unchecking_mentor_spirit_ignores_a_stale_archetype_dropdown() -> None:
    # The archetype/general-choice fields are only meaningful when the Mentor Spirit checkbox
    # itself is checked -- unchecking it must not require also resetting the dropdown, mirroring
    # create_quality_selection's own "orphaned pick" guard being meant for a tampered request, not
    # this ordinary UI interaction (see submit_qualities's own comment).
    client = TestClient(create_app())
    _confirm_magician(client)
    client.post(
        "/ui/qualities",
        data={"quality_id": [MENTOR_SPIRIT_QUALITY_ID], "mentor_spirit_archetype_id": DOG.id},
    )

    response = client.post(
        "/ui/qualities", data={"quality_id": [], "mentor_spirit_archetype_id": DOG.id}
    )

    assert response.status_code == 200
    assert "Positive Quality karma: 0" in _compact(response.text)
    sheet = client.get("/character/sheet")
    assert "Dog" not in sheet.text


def test_talent_change_strips_mentor_spirit_but_keeps_other_qualities() -> None:
    client = TestClient(create_app())
    _confirm_magician(client)
    client.post(
        "/ui/qualities",
        data={
            "quality_id": [MENTOR_SPIRIT_QUALITY_ID, CATLIKE_ID],
            "mentor_spirit_archetype_id": DOG.id,
        },
    )

    # Switch from Magician to Adept (letter B offers both).
    client.post(
        "/ui/talent",
        data={"talent_letter": "B", "talent_codename": "Adept", "granted_skill_id": [PISTOLS.id]},
    )

    sheet = client.get("/character/sheet")
    assert "Catlike" in sheet.text
    assert "Dog" not in sheet.text


def test_save_load_round_trip_preserves_mentor_spirit() -> None:
    client = TestClient(create_app())
    _confirm_magician(client)
    client.post(
        "/ui/qualities",
        data={"quality_id": [MENTOR_SPIRIT_QUALITY_ID], "mentor_spirit_archetype_id": DOG.id},
    )
    client.post("/ui/skills", data={})

    save_response = client.get("/character/save")
    data = json.loads(save_response.text)
    assert data["mentor_spirit_archetype_id"] == DOG.id

    fresh_client = TestClient(create_app())
    fresh_client.get("/")
    load_response = fresh_client.post(
        "/character/load",
        files={"save_file": ("character.json", save_response.content, "application/json")},
    )
    assert "Character loaded." in load_response.text
    sheet = fresh_client.get("/character/sheet")
    assert "Dog" in sheet.text


def test_adept_can_pick_a_mentor_spirit() -> None:
    client = TestClient(create_app())
    _confirm_adept(client)

    response = client.post(
        "/ui/qualities",
        data={"quality_id": [MENTOR_SPIRIT_QUALITY_ID], "mentor_spirit_archetype_id": DOG.id},
    )

    assert response.status_code == 200
    sheet = client.get("/character/sheet")
    assert DOG.adept_choice.name in sheet.text
