"""WP116: Aptitude -- one skill bought to 7 at creation, and rated up to 13 (p. 72)."""

from __future__ import annotations

from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from chummer5.data.metatypes import load_metatypes
from chummer5.data.priorities import load_priorities
from chummer5.data.qualities import load_qualities
from chummer5.data.skills import load_skills
from chummer5.engine.character import Character, create_character, metatype_choices
from chummer5.engine.improvements import Improvement, ImprovementSource, ImprovementType
from chummer5.engine.qualities import (
    QualityPickRequest,
    apply_quality_improvements,
    create_quality_selection,
)
from chummer5.engine.skills import (
    MAX_SKILL_RATING,
    create_karma_skill_selection,
    create_skill_allocation,
    natural_skill_rating,
    skill_maximum_bonuses,
    skill_rating,
)
from chummer5.web.app import create_app

QUALITIES = load_qualities()
APTITUDE = next(q for q in QUALITIES if q.name == "Aptitude")
METATYPES = load_metatypes()
PRIORITIES = load_priorities()
SKILLS = load_skills()
SKILL = {s.name: s for s in SKILLS}


def _character(aptitude_for: str | None = "Pistols") -> Character:
    choice = next(
        c
        for c in metatype_choices(PRIORITIES.heritage["A"], METATYPES)
        if c.metatype.name == "Human"
    )
    character = create_character(choice, "A", "A", PRIORITIES, {})
    if aptitude_for is not None:
        selection = create_quality_selection(
            [QualityPickRequest(APTITUDE.id, choice=aptitude_for)], QUALITIES
        )
        apply_quality_improvements(character, selection.qualities)
        character = replace(character, quality_selection=selection)
    return character


def _allocate(character: Character, points: dict[str, int]):  # type: ignore[no-untyped-def]
    return create_skill_allocation(
        "A",
        PRIORITIES,
        SKILLS,
        {SKILL[name].id: rating for name, rating in points.items()},
        {},
        maximum_bonus=skill_maximum_bonuses(character),
    )


def test_aptitude_takes_a_skill_choice() -> None:
    assert APTITUDE.choice_kind == "skill"
    with pytest.raises(ValueError, match="needs one of"):
        create_quality_selection([APTITUDE.id], QUALITIES)


def test_aptitude_allows_its_skill_at_seven_and_no_other() -> None:
    """The plan's acceptance: Aptitude (Pistols) allows Pistols 7 and still rejects Blades 7."""
    character = _character()
    allocation = _allocate(character, {"Pistols": 7})
    character = replace(character, skill_allocation=allocation)
    assert natural_skill_rating(character, allocation, SKILL["Pistols"]) == 7
    assert skill_rating(character, allocation, SKILL["Pistols"]) == 7
    with pytest.raises(ValueError, match="exceeds the chargen skill rating maximum of 6"):
        _allocate(character, {"Blades": 7})
    with pytest.raises(ValueError, match="exceeds the chargen skill rating maximum of 7"):
        _allocate(character, {"Pistols": 8})


def test_without_aptitude_seven_is_rejected() -> None:
    with pytest.raises(ValueError, match="maximum of 6"):
        _allocate(_character(None), {"Pistols": 7})


def test_karma_can_raise_the_aptitude_skill_to_seven() -> None:
    character = _character()
    allocation = _allocate(character, {"Pistols": 6, "Blades": 6})
    character = replace(character, skill_allocation=allocation)
    selection = create_karma_skill_selection(
        character, SKILLS, {SKILL["Pistols"].id: 1}, karma_budget=100
    )
    assert selection.karma_cost == 7 * 2  # new rating x 2
    with pytest.raises(ValueError, match="maximum of 6"):
        create_karma_skill_selection(character, SKILLS, {SKILL["Blades"].id: 1}, karma_budget=100)


def test_the_augmented_ceiling_is_thirteen_for_the_aptitude_skill_only() -> None:
    character = _character()
    allocation = _allocate(character, {"Pistols": 7, "Blades": 6})
    character = replace(character, skill_allocation=allocation)
    for name in ("Pistols", "Blades"):
        character.improvements.add(
            Improvement(
                improvement_type=ImprovementType.SKILL,
                target=name,
                value=10,
                source_type=ImprovementSource.CYBERWARE,
                source_id=f"synthetic-{name}",
            )
        )
    assert skill_rating(character, allocation, SKILL["Pistols"]) == MAX_SKILL_RATING + 1
    assert skill_rating(character, allocation, SKILL["Blades"]) == MAX_SKILL_RATING


def test_aptitude_round_trips_through_the_page_and_a_save() -> None:
    pistols = SKILL["Pistols"]
    client = TestClient(create_app())
    client.get("/")
    human = next(
        c
        for c in metatype_choices(PRIORITIES.heritage["A"], METATYPES)
        if c.metatype.name == "Human"
    )
    client.post(
        "/ui/priorities",
        data={
            "heritage_letter": "D",
            "attributes_letter": "B",
            "skills_letter": "A",
            "resources_letter": "C",
            "talent_letter": "E",
            "metatype_id": human.metatype.id,
        },
    )
    assert "maximum of 6" in client.post("/ui/skills", data={f"skill_{pistols.id}": "7"}).text
    client.post(
        "/ui/qualities",
        data={"quality_id": APTITUDE.id, f"quality_choice_{APTITUDE.id}": "Pistols"},
    )
    page = client.post("/ui/skills", data={f"skill_{pistols.id}": "7"}).text
    assert "maximum of" not in page
    assert 'max="7"' in page

    saved = client.get("/character/save").content
    fresh = TestClient(create_app())
    fresh.get("/")
    loaded = fresh.post(
        "/character/load", files={"save_file": ("c.json", saved, "application/json")}
    )
    assert "Character loaded." in loaded.text
    sheet = fresh.get("/character/sheet").text
    assert "Aptitude (Pistols)" in sheet
