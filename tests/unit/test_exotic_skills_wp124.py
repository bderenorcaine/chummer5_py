"""WP124: an exotic skill is bought once per named weapon or vehicle, as separate skills (p. 131,
p. 147), each keyed `"{skill_id}|{specific}"` in the ordinary skill maps."""

from __future__ import annotations

import json
import re
from dataclasses import replace
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from chummer5.data.metatypes import load_metatypes
from chummer5.data.priorities import load_priorities
from chummer5.data.skills import load_skills
from chummer5.engine.character import Character, create_character, metatype_choices
from chummer5.engine.skills import (
    character_skills,
    create_karma_skill_selection,
    create_skill_allocation,
    dice_pool,
    exotic_instance,
    exotic_skill_key,
    skill_points_spent,
    skill_rating,
    split_skill_key,
)
from chummer5.io.legacy_chum5 import load_chum5
from chummer5.web.app import create_app

METATYPES = load_metatypes()
PRIORITIES = load_priorities()
SKILLS = load_skills()
BY_NAME = {s.name: s for s in SKILLS}
EXOTIC_RANGED = BY_NAME["Exotic Ranged Weapon"]
FLAMETHROWER = exotic_skill_key(EXOTIC_RANGED.id, "Flamethrower")
HARPOON = exotic_skill_key(EXOTIC_RANGED.id, "Harpoon Gun")
LEGACY_TEST_FILES = Path(__file__).resolve().parents[2] / "legacy" / "Chummer.Tests" / "TestFiles"


def _human() -> Character:
    choice = next(
        c
        for c in metatype_choices(PRIORITIES.heritage["A"], METATYPES)
        if c.metatype.name == "Human"
    )
    return create_character(choice, "A", "A", PRIORITIES, {"AGI": 3})


def _allocate(skill_points: dict[str, int], specializations: dict[str, str] | None = None):  # type: ignore[no-untyped-def]
    return create_skill_allocation("A", PRIORITIES, SKILLS, skill_points, {}, specializations or {})


def test_keys_split_back_into_skill_and_item() -> None:
    assert split_skill_key(FLAMETHROWER) == (EXOTIC_RANGED.id, "Flamethrower")
    assert split_skill_key(BY_NAME["Pistols"].id) == (BY_NAME["Pistols"].id, None)
    assert exotic_skill_key(EXOTIC_RANGED.id, "  Flamethrower ") == FLAMETHROWER


def test_two_instances_are_separate_skills_with_their_own_ratings() -> None:
    """The plan's acceptance, engine side: Flamethrower 3 and Harpoon Gun 2."""
    allocation = _allocate({FLAMETHROWER: 3, HARPOON: 2})
    character = replace(_human(), skill_allocation=allocation)
    flamethrower = exotic_instance(EXOTIC_RANGED, "Flamethrower")
    harpoon = exotic_instance(EXOTIC_RANGED, "Harpoon Gun")
    assert flamethrower.name == "Exotic Ranged Weapon" and flamethrower.specific == "Flamethrower"
    assert skill_rating(character, allocation, flamethrower) == 3
    assert skill_rating(character, allocation, harpoon) == 2
    agility = character.attribute_value("AGI")
    assert dice_pool(character, allocation, flamethrower) == 3 + agility
    assert skill_points_spent(allocation.skill_points, {}, SKILLS) == 5
    ids = {s.id for s in character_skills(character, SKILLS)}
    assert {FLAMETHROWER, HARPOON} <= ids


def test_the_catalog_entry_itself_cannot_be_bought() -> None:
    with pytest.raises(ValueError, match="needs one named"):
        _allocate({EXOTIC_RANGED.id: 3})


def test_a_blank_item_or_a_non_exotic_skill_with_an_item_is_rejected() -> None:
    with pytest.raises(ValueError, match="must not be blank"):
        _allocate({f"{EXOTIC_RANGED.id}| ": 3})
    with pytest.raises(ValueError, match="only an exotic skill"):
        _allocate({exotic_skill_key(BY_NAME["Pistols"].id, "Ares Predator"): 3})


def test_an_exotic_skill_has_no_specializations() -> None:
    """p. 131, Exotic Ranged Weapon: "Specializations: None"; p. 147: "N/A"."""
    with pytest.raises(ValueError, match="no specializations"):
        _allocate({FLAMETHROWER: 3}, {FLAMETHROWER: "Short bursts"})


def test_karma_raises_an_instance_or_buys_a_new_one() -> None:
    allocation = _allocate({FLAMETHROWER: 3})
    character = replace(_human(), skill_allocation=allocation)
    selection = create_karma_skill_selection(
        character, SKILLS, {FLAMETHROWER: 1, HARPOON: 1}, karma_budget=100
    )
    assert selection.karma_cost == 4 * 2 + 1 * 2
    character = replace(character, karma_skill_selection=selection)
    harpoon = exotic_instance(EXOTIC_RANGED, "Harpoon Gun")
    assert skill_rating(character, allocation, harpoon) == 1
    assert HARPOON in {s.id for s in character_skills(character, SKILLS)}
    with pytest.raises(ValueError, match="needs one named"):
        create_karma_skill_selection(character, SKILLS, {EXOTIC_RANGED.id: 1}, karma_budget=100)


def _start(client: TestClient) -> None:
    client.get("/")
    human = next(
        c
        for c in metatype_choices(PRIORITIES.heritage["A"], METATYPES)
        if c.metatype.name == "Human"
    )
    client.post(
        "/ui/priorities",
        data={
            "heritage_letter": "A",
            "talent_letter": "E",
            "attributes_letter": "C",
            "skills_letter": "B",
            "resources_letter": "D",
            "metatype_id": human.metatype.id,
        },
    )


def _add(client: TestClient, specific: str, points: int, keys: list[str]) -> str:
    data: dict[str, object] = {
        "exotic_new_skill": EXOTIC_RANGED.id,
        "exotic_new_specific": specific,
        "exotic_new_points": str(points),
        "exotic_key": keys,
    }
    for key, value in _committed(client).items():
        data[f"skill_{key}"] = str(value)
    return client.post("/ui/skills", data=data).text


def _committed(client: TestClient) -> dict[str, int]:
    return dict(json.loads(client.get("/character/save").content)["skill_points"])


def test_the_skills_page_adds_two_instances_and_they_survive_a_save() -> None:
    """The plan's acceptance: Flamethrower 3 and Harpoon Gun 2 round-trip."""
    client = TestClient(create_app())
    _start(client)
    page = _add(client, "Flamethrower", 3, [])
    assert "<td>Flamethrower</td>" in page  # WP148: the Special tab's Detail column
    assert f'name="exotic_key" value="{FLAMETHROWER}"' in page
    _add(client, "Harpoon Gun", 2, [FLAMETHROWER])
    assert _committed(client) == {FLAMETHROWER: 3, HARPOON: 2}

    sheet = re.sub(r"\s+", " ", client.get("/character/sheet").text)
    assert "Exotic Ranged Weapon (Flamethrower)" in sheet
    assert "Exotic Ranged Weapon (Harpoon Gun)" in sheet

    saved = client.get("/character/save").content
    fresh = TestClient(create_app())
    fresh.get("/")
    fresh.post(
        "/characters/upload?open=true", files={"files": ("c.json", saved, "application/json")}
    )
    assert _committed(fresh) == {FLAMETHROWER: 3, HARPOON: 2}


def test_a_half_filled_add_row_is_kept_and_a_duplicate_is_refused() -> None:
    client = TestClient(create_app())
    _start(client)
    page = _add(client, "Flamethrower", 0, [])
    assert 'value="Flamethrower"' in page  # no points yet: echoed, not bought
    assert _committed(client) == {}
    _add(client, "Flamethrower", 3, [])
    page = _add(client, "Flamethrower", 2, [FLAMETHROWER])
    assert "already has that exotic skill for Flamethrower" in page
    assert _committed(client) == {FLAMETHROWER: 3}


def test_setting_an_instance_to_zero_removes_it() -> None:
    client = TestClient(create_app())
    _start(client)
    _add(client, "Flamethrower", 3, [])
    page = client.post(
        "/ui/skills", data={"exotic_key": [FLAMETHROWER], f"skill_{FLAMETHROWER}": "0"}
    ).text
    assert "(Flamethrower)" not in page
    assert _committed(client) == {}


def test_a_pre_wp124_save_moves_a_bare_exotic_spend_onto_an_unspecified_instance() -> None:
    client = TestClient(create_app())
    _start(client)
    data = json.loads(client.get("/character/save").content)
    data["skill_points"] = {EXOTIC_RANGED.id: 2}
    data["specializations"] = {EXOTIC_RANGED.id: "Blowguns"}
    fresh = TestClient(create_app())
    fresh.get("/")
    fresh.post(
        "/characters/upload?open=true",
        files={"files": ("c.json", json.dumps(data).encode(), "application/json")},
    )
    saved = json.loads(fresh.get("/character/save").content)
    assert saved["skill_points"] == {exotic_skill_key(EXOTIC_RANGED.id, "Unspecified"): 2}
    assert saved["specializations"] == {}


def test_the_legacy_parser_reads_the_specific_item() -> None:
    legacy = load_chum5(LEGACY_TEST_FILES / "Gentle Earthquake.chum5")
    assert "Horns" in {s.specific for s in legacy.skills}
