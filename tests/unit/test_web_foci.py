"""WP47: Foci reaching the browser (`POST /ui/foci`), plus the character sheet's new Foci section.
Same "manual walkthrough; values match engine output for the same inputs" acceptance bar as
WP46's own `test_web_spirits.py` -- and the same "no real fixture exercises this" honesty caveat
as `chummer5.engine.foci` itself: neither of the corpus's 2 real magic fixtures has any bonded
foci, so this module builds a Magician/Adept from scratch through the browser, reusing
`test_web_spirits.py`'s own `_confirm_human`/`_confirm_magician` shape.
"""

from __future__ import annotations

import json
import re

from fastapi.testclient import TestClient

from chummer5.data.foci import load_foci
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
FOCI = load_foci()

HERMETIC = next(t for t in TRADITIONS if t.name == "Hermetic")
SPELLCASTING = next(s for s in SKILLS if s.name == "Spellcasting")
COUNTERSPELLING = next(s for s in SKILLS if s.name == "Counterspelling")
PISTOLS = next(s for s in SKILLS if s.name == "Pistols")
ALCHEMICAL = next(f for f in FOCI if f.name == "Alchemical Focus")
DISENCHANTING = next(f for f in FOCI if f.name == "Disenchanting Focus")
SUMMONING = next(f for f in FOCI if f.name == "Summoning Focus")


def _compact(html: str) -> str:
    return re.sub(r">\s+<", "><", html)


def _confirm_human(client: TestClient, *, talent_letter: str) -> None:
    """Unlike `test_web_spirits.py`'s identical-shaped helper (which always leaves Resources at
    the lowest-budget letter E, fine for Karma-only Bound Spirits tests), Foci also spends real
    nuyen -- so this pins Resources at the highest-budget letter A instead, filling Heritage/
    Attributes/Skills from whatever's left of {B, C, D, E} once `talent_letter` (always one of
    B/C/D, the only letters offering Magician/Adept) and Resources' own A are both spoken for.
    """
    client.get("/")
    # Talent E ("Mundane") can't also double as Heritage below -- swap Heritage to D for that
    # one case so all 5 letters stay distinct; every other letter (B/C/D, the Magician/Adept
    # ones) leaves Heritage at E.
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
    # Letter D's Adept option grants no free skill (see chummer5.data.priorities) -- keeps this
    # fixture minimal, mirroring test_foci_selection.py's own `_adept` helper.
    _confirm_human(client, talent_letter=talent_letter)
    response = client.post(
        "/ui/talent",
        data={"talent_letter": talent_letter, "talent_codename": "Adept"},
    )
    assert "Confirmed: Adept" in response.text


def test_foci_section_hidden_for_mundane() -> None:
    client = TestClient(create_app())
    _confirm_human(client, talent_letter="E")

    response = client.get("/")

    assert "<summary>Foci" not in response.text


def test_foci_section_shown_for_magician() -> None:
    client = TestClient(create_app())
    _confirm_magician(client)

    response = client.get("/")

    assert "<summary>Foci" in response.text
    assert ALCHEMICAL.name in response.text


def test_foci_section_shown_for_adept_too() -> None:
    # Bonding only requires being Awakened at all, not specifically a Magician -- see
    # chummer5.engine.foci's module docstring.
    client = TestClient(create_app())
    _confirm_adept(client)

    response = client.get("/")

    assert "<summary>Foci" in response.text


def test_bonding_a_focus_within_budget_shows_on_the_sheet() -> None:
    client = TestClient(create_app())
    _confirm_magician(client)  # letter B -> Magic 4

    response = client.post("/ui/foci", data={f"focus_force_{ALCHEMICAL.id}": "2"})

    assert response.status_code == 200
    assert "Karma remaining 19 / 25" in _compact(response.text)

    sheet = client.get("/character/sheet")
    assert "Alchemical Focus" in sheet.text
    assert f"Alchemical Focus (Force 2, {2 * ALCHEMICAL.cost_per_force}" in sheet.text
    assert f"Foci karma cost: {2 * ALCHEMICAL.bonding_karma_per_force}." in sheet.text


def test_rejects_exceeding_the_chargen_force_cap() -> None:
    # Letter B -> Magic 4, chargen cap = 8. Split across 3 different items so no single item's
    # own Availability (Force x 3, capped at 4 each) trips first -- Alchemical(4) + Disenchanting
    # (4) + Summoning(1) = total Force 9 > 8.
    client = TestClient(create_app())
    _confirm_magician(client)

    response = client.post(
        "/ui/foci",
        data={
            f"focus_force_{ALCHEMICAL.id}": "4",
            f"focus_force_{DISENCHANTING.id}": "4",
            f"focus_force_{SUMMONING.id}": "1",
        },
    )

    assert "exceeds the character-creation cap of 8" in response.text


def test_rejects_exceeding_the_availability_cap() -> None:
    client = TestClient(create_app())
    _confirm_magician(client)

    # Alchemical Focus: availability_per_force == 3 -> Force 5 gives Availability 15 > 12.
    response = client.post("/ui/foci", data={f"focus_force_{ALCHEMICAL.id}": "5"})

    assert "Availability 15 exceeds 12" in response.text


def test_talent_change_resets_foci_selection() -> None:
    client = TestClient(create_app())
    _confirm_magician(client)
    client.post("/ui/foci", data={f"focus_force_{ALCHEMICAL.id}": "2"})

    # Switch from Magician to Adept (letter B offers both) -- resets spell/power/spirit/foci
    # selections (see `_replace_committed_talent`'s own docstring).
    client.post(
        "/ui/talent",
        data={"talent_letter": "B", "talent_codename": "Adept", "granted_skill_id": [PISTOLS.id]},
    )

    sheet = client.get("/character/sheet")
    assert "Alchemical Focus" not in sheet.text


def test_save_load_round_trip_preserves_foci() -> None:
    client = TestClient(create_app())
    _confirm_magician(client)
    client.post("/ui/foci", data={f"focus_force_{ALCHEMICAL.id}": "2"})
    client.post("/ui/skills", data={})

    save_response = client.get("/character/save")
    data = json.loads(save_response.text)
    assert data["foci_picks"] == [{"focus_id": ALCHEMICAL.id, "force": 2}]

    fresh_client = TestClient(create_app())
    fresh_client.get("/")
    load_response = fresh_client.post(
        "/character/load",
        files={"save_file": ("character.json", save_response.content, "application/json")},
    )
    assert "Character loaded." in load_response.text
    sheet = fresh_client.get("/character/sheet")
    assert "Alchemical Focus" in sheet.text
    assert f"Foci karma cost: {2 * ALCHEMICAL.bonding_karma_per_force}." in sheet.text


def test_bound_spirits_and_foci_share_the_karma_pool() -> None:
    # 20 Karma on a Bound Spirit + a Force-2 Alchemical Focus (6 Karma) = 26 > STARTING_KARMA (25)
    # -- only caught because create_foci_selection's own budget already accounts for Bound
    # Spirits' cost (see chummer5.engine.foci's module docstring's "fixed evaluation order"
    # paragraph, applied here to the web layer's symmetric re-validation instead).
    client = TestClient(create_app())
    _confirm_magician(client)
    client.post("/ui/spirits", data={"spirit_type_0": "Spirit of Fire", "spirit_services_0": "20"})

    response = client.post("/ui/foci", data={f"focus_force_{ALCHEMICAL.id}": "2"})

    assert "exceeds the Karma budget" in response.text
