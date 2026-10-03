"""WP125: Active skill points fund Knowledge/Language past the free pool (p. 88), Karma buys a new
one from rating 0 (p. 107), and both kinds take specializations (p. 148, p. 150)."""

from __future__ import annotations

import json
import re
from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from chummer5.data.metatypes import load_metatypes
from chummer5.data.priorities import load_priorities
from chummer5.data.skills import load_skills
from chummer5.engine.character import Character, create_character, metatype_choices
from chummer5.engine.knowledge import (
    KnowledgeSkillPick,
    LanguageSkillPick,
    create_karma_knowledge_selection,
    create_knowledge_selection,
)
from chummer5.engine.skills import create_skill_allocation
from chummer5.web.app import create_app

METATYPES = load_metatypes()
PRIORITIES = load_priorities()
SKILLS = load_skills()


def _rob() -> Character:
    """Rob's INT 3 / LOG 3 (12 free points, Step Five worked example)."""
    human = next(
        c
        for c in metatype_choices(PRIORITIES.heritage["D"], METATYPES)
        if c.metatype.name == "Human"
    )
    return create_character(human, "D", "A", PRIORITIES, {"INT": 2, "LOG": 2})


ENGLISH = LanguageSkillPick("English", 0, native=True)
DAKOTA = LanguageSkillPick("Dakota", 1)


def test_the_rob_example_raises_dakota_to_2_for_2_karma() -> None:
    """p. 101's Step Seven example: "Dakota language to 2 (2 Karma)"."""
    rob = _rob()
    selection = create_knowledge_selection(rob, (), (ENGLISH, DAKOTA))
    rob = replace(rob, knowledge_selection=selection)
    karma = create_karma_knowledge_selection(rob, {"Dakota": 1}, 16)
    assert karma.karma_cost == 2


def test_a_spend_past_the_free_pool_uses_active_points() -> None:
    rob = _rob()
    picks = [KnowledgeSkillPick(f"K{i}", "Street", 4) for i in range(3)]  # 12 free
    picks.append(KnowledgeSkillPick("Sioux Nation", "Academic", 2))
    with pytest.raises(ValueError, match="plus the 0 Active skill point"):
        create_knowledge_selection(rob, picks, ())
    selection = create_knowledge_selection(rob, picks, (), active_points_available=5)
    assert selection.points_spent == 14
    assert selection.active_points_used == 2


def test_the_active_budget_counts_the_knowledge_overflow() -> None:
    pistols = next(s for s in SKILLS if s.name == "Pistols")
    # Skills E: 18 points. 16 on Active skills leaves 2, and a 3-point overflow doesn't fit.
    points = {pistols.id: 6} | {s.id: 5 for s in SKILLS if s.name in ("Perception", "Sneaking")}
    create_skill_allocation("E", PRIORITIES, SKILLS, points, {}, knowledge_active_points=2)
    with pytest.raises(ValueError, match="3 spent on Knowledge/Language skills"):
        create_skill_allocation("E", PRIORITIES, SKILLS, points, {}, knowledge_active_points=3)


def test_karma_buys_a_new_skill_from_zero_at_new_rating_times_one() -> None:
    rob = _rob()
    selection = create_knowledge_selection(rob, (KnowledgeSkillPick("Bars", "Street", 0),), ())
    assert selection.points_spent == 0
    rob = replace(rob, knowledge_selection=selection)
    assert create_karma_knowledge_selection(rob, {"Bars": 2}, 100).karma_cost == 1 + 2
    with pytest.raises(ValueError, match="needs Karma to buy it"):
        create_karma_knowledge_selection(rob, {}, 100)


def test_a_point_funded_specialization_costs_a_point_and_needs_a_rating() -> None:
    rob = _rob()
    picks = (KnowledgeSkillPick("Corporations", "Street", 3),)
    selection = create_knowledge_selection(rob, picks, (ENGLISH,), {"Corporations": "Evo"})
    assert selection.points_spent == 4
    # A native language may be specialized: p. 150's lingos.
    selection = create_knowledge_selection(rob, (), (ENGLISH,), {"English": "Cityspeak"})
    assert selection.points_spent == 1
    with pytest.raises(ValueError, match="at least rating 1"):
        create_knowledge_selection(
            rob, (KnowledgeSkillPick("Bars", "Street", 0),), (), {"Bars": "Seattle"}
        )
    with pytest.raises(ValueError, match="not a committed"):
        create_knowledge_selection(rob, picks, (), {"Gangs": "Ancients"})


def test_a_karma_specialization_costs_7_and_one_per_skill() -> None:
    rob = _rob()
    selection = create_knowledge_selection(
        rob, (KnowledgeSkillPick("Bars", "Street", 0),), (DAKOTA,), {"Dakota": "Speak"}
    )
    rob = replace(rob, knowledge_selection=selection)
    karma = create_karma_knowledge_selection(rob, {"Bars": 1}, 100, {"Bars": "Seattle"})
    assert karma.karma_cost == 1 + 7
    with pytest.raises(ValueError, match="already has a specialization"):
        create_karma_knowledge_selection(rob, {"Bars": 1}, 100, {"Dakota": "Read/Write"})
    with pytest.raises(ValueError, match="not a committed"):
        create_karma_knowledge_selection(rob, {"Bars": 1}, 100, {"Missing": "x"})


def _confirm(client: TestClient) -> None:
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
            "attributes_letter": "B",
            "skills_letter": "C",
            "resources_letter": "D",
            "talent_letter": "E",
            "metatype_id": human.metatype.id,
        },
    )


def test_the_web_pages_share_the_active_pool_and_a_save_keeps_everything() -> None:
    """A point-funded knowledge rank past the 4 free points, a Karma-bought language, and both
    kinds of specialization, surviving a save."""
    client = TestClient(create_app())
    _confirm(client)
    page = client.post(
        "/ui/knowledge",
        data={
            "knowledge_name_0": "Corporations",
            "knowledge_category_0": "Street",
            "knowledge_rating_0": "5",
            "knowledge_spec_0": "Evo",
            "language_name_0": "Japanese",
            "language_rating_0": "0",
            "language_karma_0": "2",
            "language_karma_spec_0": "Speak",
        },
    ).text
    assert "Active skill points used: 2 / 28." in page
    skills = re.sub(r"\s+", " ", client.get("/ui/page/skills/active").text)
    assert "Skill points remaining: 26 / 28" in skills

    saved = json.loads(client.get("/character/save").content)
    assert saved["knowledge_specializations"] == {"Corporations": "Evo"}
    assert saved["karma_knowledge_specializations"] == {"Japanese": "Speak"}
    assert saved["karma_knowledge_points"] == {"Japanese": 2}

    fresh = TestClient(create_app())
    fresh.get("/")
    fresh.post(
        "/characters/upload?open=true",
        files={"files": ("c.json", json.dumps(saved).encode(), "application/json")},
    )
    sheet = re.sub(r"\s+", " ", fresh.get("/character/sheet").text)
    assert "Corporations (Evo)" in sheet
    assert "Japanese (Speak)" in sheet
