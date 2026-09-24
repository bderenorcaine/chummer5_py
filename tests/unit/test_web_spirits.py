"""WP46: Bound Spirits reaching the browser (`POST /ui/spirits`), plus the character sheet's new
Bound Spirits section. Same "manual walkthrough; values match engine output for the same inputs"
acceptance bar as WP29's own `test_web_magic.py` -- and the same "no real fixture exercises this"
honesty caveat as `chummer5.engine.spirits` itself (see that module's docstring): neither of the
corpus's 2 real magic fixtures has any bound spirits, so this module builds a Magician from scratch
through the browser, reusing `test_web_magic.py`'s own `_confirm_human` letter/codename shape.
"""

from __future__ import annotations

import json
import re

from fastapi.testclient import TestClient

from chummer5.data.metatypes import load_metatypes
from chummer5.data.priorities import load_priorities
from chummer5.data.skills import load_skills
from chummer5.data.traditions import load_traditions
from chummer5.engine.character import metatype_choices
from chummer5.web.app import create_app

METATYPES = load_metatypes()
PRIORITIES = load_priorities()
SKILLS = load_skills()
TRADITIONS = load_traditions()

HERMETIC = next(t for t in TRADITIONS if t.name == "Hermetic")
SPELLCASTING = next(s for s in SKILLS if s.name == "Spellcasting")
COUNTERSPELLING = next(s for s in SKILLS if s.name == "Counterspelling")
PISTOLS = next(s for s in SKILLS if s.name == "Pistols")


def _compact(html: str) -> str:
    return re.sub(r">\s+<", "><", html)


def _confirm_human(client: TestClient, *, talent_letter: str) -> None:
    """Mirrors `test_web_magic.py`'s identical helper."""
    client.get("/")
    remaining = [letter for letter in ("B", "C", "D", "E") if letter != talent_letter]
    heritage = PRIORITIES.heritage["A"]
    human_choice = next(
        c for c in metatype_choices(heritage, METATYPES) if c.metatype.name == "Human"
    )
    response = client.post(
        "/ui/priorities",
        data={
            "heritage_letter": "A",
            "talent_letter": talent_letter,
            "attributes_letter": remaining[0],
            "skills_letter": remaining[1],
            "resources_letter": remaining[2],
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


def test_spirit_section_hidden_for_mundane() -> None:
    client = TestClient(create_app())
    _confirm_human(client, talent_letter="E")

    response = client.get("/ui/page/magic")

    assert "Bound Spirits" not in response.text


def test_spirit_section_shown_for_magician_with_offered_tradition_types() -> None:
    client = TestClient(create_app())
    _confirm_magician(client)

    response = client.get("/ui/page/magic")

    assert "Bound Spirits" in response.text
    for spirit_type in HERMETIC.spirits.offered_types:
        assert spirit_type in response.text
    assert "Karma spent: 0 / 25" in _compact(response.text)


def test_binding_a_spirit_within_budget_shows_on_the_sheet() -> None:
    client = TestClient(create_app())
    _confirm_magician(client)

    response = client.post(
        "/ui/spirits", data={"spirit_type_0": "Spirit of Fire", "spirit_services_0": "3"}
    )

    assert response.status_code == 200
    assert "Karma spent: 3 / 25 (22 remaining)" in response.text

    sheet = client.get("/character/sheet")
    assert "Spirit of Fire" in sheet.text
    assert "Bound Spirits karma cost: 3." in sheet.text
    # priorities.xml letter B's Magician option: magic=4 -- Force shown live, matching it.
    assert "(Force 4, 3 services owed)" in sheet.text


def test_binding_at_an_explicit_force_below_magic_shows_on_the_sheet() -> None:
    # WP70: a player-chosen Force below Magic is honored, and cost still 1 Karma per service.
    client = TestClient(create_app())
    _confirm_magician(client)

    response = client.post(
        "/ui/spirits",
        data={
            "spirit_type_0": "Spirit of Fire",
            "spirit_force_0": "2",
            "spirit_services_0": "3",
        },
    )

    assert response.status_code == 200
    assert "Karma spent: 3 / 25 (22 remaining)" in response.text

    sheet = client.get("/character/sheet")
    assert "(Force 2, 3 services owed)" in sheet.text


def test_rejects_a_force_above_the_magic_rating() -> None:
    # WP70: letter B's Magician option is Magic 4 -- Force 5 must be rejected.
    client = TestClient(create_app())
    _confirm_magician(client)

    response = client.post(
        "/ui/spirits",
        data={
            "spirit_type_0": "Spirit of Fire",
            "spirit_force_0": "5",
            "spirit_services_0": "1",
        },
    )

    assert "Force must be between 1 and the Magic rating of 4" in response.text


def test_rejects_a_spirit_type_not_offered_by_the_tradition() -> None:
    client = TestClient(create_app())
    _confirm_magician(client)

    response = client.post(
        "/ui/spirits", data={"spirit_type_0": "Spirit of Beasts", "spirit_services_0": "1"}
    )

    assert "not an offered spirit type" in response.text


def test_rejects_exceeding_the_charisma_limit() -> None:
    client = TestClient(create_app())
    _confirm_magician(client)
    # Human CHA minimum is 1, no points spent -- only 1 bound spirit fits.
    response = client.post(
        "/ui/spirits",
        data={
            "spirit_type_0": "Spirit of Fire",
            "spirit_services_0": "1",
            "spirit_type_1": "Spirit of Air",
            "spirit_services_1": "1",
        },
    )

    assert "exceeding the Charisma limit of 1" in response.text


def test_rejects_exceeding_the_karma_budget() -> None:
    client = TestClient(create_app())
    _confirm_magician(client)

    response = client.post(
        "/ui/spirits", data={"spirit_type_0": "Spirit of Fire", "spirit_services_0": "26"}
    )

    assert "exceeding the available budget of 25" in response.text


def test_talent_change_resets_bound_spirit_selection() -> None:
    client = TestClient(create_app())
    _confirm_magician(client)
    client.post("/ui/spirits", data={"spirit_type_0": "Spirit of Fire", "spirit_services_0": "3"})

    # Switch from Magician to Adept (letter B offers both; letter B never offers "Mundane" at all --
    # only letter E does, see chummer5.engine.magic's module docstring) -- resets spell/power/spirit
    # selections (see `_replace_committed_talent`'s own docstring).
    client.post(
        "/ui/talent",
        data={"talent_letter": "B", "talent_codename": "Adept", "granted_skill_id": [PISTOLS.id]},
    )

    sheet = client.get("/character/sheet")
    assert "Spirit of Fire" not in sheet.text


def test_save_load_round_trip_preserves_bound_spirits() -> None:
    client = TestClient(create_app())
    _confirm_magician(client)
    client.post("/ui/spirits", data={"spirit_type_0": "Spirit of Fire", "spirit_services_0": "3"})
    client.post("/ui/skills", data={})

    save_response = client.get("/character/save")
    data = json.loads(save_response.text)
    # WP70: Force is persisted; with no Force submitted it resolves to the live Magic rating (4 at
    # letter B's Magician option).
    assert data["bound_spirit_picks"] == [
        {"spirit_type": "Spirit of Fire", "force": 4, "services": 3}
    ]

    fresh_client = TestClient(create_app())
    fresh_client.get("/")
    load_response = fresh_client.post(
        "/character/load",
        files={"save_file": ("character.json", save_response.content, "application/json")},
    )
    assert "Character loaded." in load_response.text
    sheet = fresh_client.get("/character/sheet")
    assert "Spirit of Fire" in sheet.text
    assert "Bound Spirits karma cost: 3." in sheet.text
