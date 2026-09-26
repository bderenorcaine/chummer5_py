"""WP117: qualities that change purchase rules -- Uncouth, Uneducated, Incompetent, Sensitive
System."""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from chummer5.data.metatypes import load_metatypes
from chummer5.data.priorities import load_priorities
from chummer5.data.qualities import load_qualities
from chummer5.data.skills import load_skills
from chummer5.engine.bioware import bioware_disabled, create_bioware_selection
from chummer5.engine.character import Character, create_character, metatype_choices
from chummer5.engine.cyberware_subsystems import (
    CyberwarePurchaseRequest,
    create_cyberware_tree_selection,
    cyberware_essence_multiplier,
)
from chummer5.engine.derived import notoriety
from chummer5.engine.knowledge import (
    KnowledgeSkillPick,
    create_karma_knowledge_selection,
    create_knowledge_selection,
)
from chummer5.engine.qualities import (
    QualityPickRequest,
    apply_quality_improvements,
    choice_options,
    create_quality_selection,
)
from chummer5.engine.skills import (
    create_karma_skill_selection,
    create_skill_allocation,
    dice_pool,
    is_unaware,
    skill_points_spent,
    skill_purchase_rules,
)
from chummer5.web.app import create_app
from chummer5.web.catalogs import BIOWARE, CYBERWARE_ENTRIES, CYBERWARE_STANDALONE

QUALITIES = load_qualities()
BY_NAME = {q.name: q for q in QUALITIES}
METATYPES = load_metatypes()
PRIORITIES = load_priorities()
SKILLS = load_skills()
SKILL = {s.name: s for s in SKILLS}
SMARTLINK = next(c for c in CYBERWARE_STANDALONE if c.name == "Smartlink")


def _character(*picks: str | QualityPickRequest, magic_type: str | None = None) -> Character:
    choice = next(
        c
        for c in metatype_choices(PRIORITIES.heritage["A"], METATYPES)
        if c.metatype.name == "Human"
    )
    points = {"AGI": 3, "CHA": 3, "LOG": 3}
    character = create_character(choice, "A", "A", PRIORITIES, points)
    selection = create_quality_selection(list(picks), QUALITIES, magic_type=magic_type)
    apply_quality_improvements(character, selection.qualities)
    return replace(character, quality_selection=selection, magic_type=magic_type)


def _allocate(character: Character, points: dict[str, int], groups: dict[str, int] | None = None):  # type: ignore[no-untyped-def]
    return create_skill_allocation(
        "A",
        PRIORITIES,
        SKILLS,
        {SKILL[name].id: rating for name, rating in points.items()},
        groups or {},
        rules=skill_purchase_rules(character),
    )


def _incompetent(group: str) -> QualityPickRequest:
    return QualityPickRequest(BY_NAME["Incompetent"].id, choice=group)


# --- Uncouth ---------------------------------------------------------------------------------


def test_uncouth_doubles_a_social_skills_points() -> None:
    """The plan's acceptance: Uncouth doubles an Etiquette 3 purchase to 6 points. Legacy doubles
    the specialization's point with it."""
    rules = skill_purchase_rules(_character(BY_NAME["Uncouth"].id))
    etiquette, pistols = SKILL["Etiquette"].id, SKILL["Pistols"].id
    assert skill_points_spent({etiquette: 3}, {}, SKILLS, rules) == 6
    assert skill_points_spent({etiquette: 3}, {etiquette: "Corporate"}, SKILLS, rules) == 8
    assert skill_points_spent({pistols: 3}, {}, SKILLS, rules) == 3
    assert skill_points_spent({etiquette: 3}, {}, SKILLS) == 3
    # Skills A has 46 points: seven skills at 6 (42) plus Etiquette 3 (6) overspends by 2.
    uncouth = _character(BY_NAME["Uncouth"].id)
    six_each = {name: 6 for name in ("Pistols", "Blades", "Sneaking", "Perception", "Running")}
    _allocate(uncouth, {**six_each, "Gymnastics": 4, "Etiquette": 6})
    with pytest.raises(ValueError, match="skill point spend 48"):
        _allocate(uncouth, {**six_each, "Gymnastics": 6, "Etiquette": 6})


def test_uncouth_doubles_social_karma_and_bans_social_groups() -> None:
    uncouth = _character(BY_NAME["Uncouth"].id)
    with pytest.raises(ValueError, match="may never learn"):
        _allocate(uncouth, {}, {"Influence": 1})
    _allocate(uncouth, {}, {"Firearms": 1})
    character = replace(uncouth, skill_allocation=_allocate(uncouth, {"Etiquette": 2}))
    selection = create_karma_skill_selection(
        character, SKILLS, {SKILL["Etiquette"].id: 1}, karma_budget=100
    )
    assert selection.karma_cost == 3 * 2 * 2  # new rating x 2, doubled
    with pytest.raises(ValueError, match="may never learn"):
        create_karma_skill_selection(
            character, SKILLS, karma_group_points={"Acting": 1}, karma_budget=100
        )


def test_uncouth_is_unaware_in_social_skills_it_lacks() -> None:
    uncouth = _character(BY_NAME["Uncouth"].id)
    plain = _character()
    allocation = _allocate(plain, {"Etiquette": 2})
    charisma = plain.attribute_value("CHA")
    assert dice_pool(plain, allocation, SKILL["Con"]) == charisma - 1  # defaulting
    assert is_unaware(uncouth, SKILL["Con"])
    assert dice_pool(uncouth, allocation, SKILL["Con"]) == 0
    assert dice_pool(uncouth, allocation, SKILL["Etiquette"]) == 2 + charisma  # known
    assert notoriety(uncouth) == 1


# --- Uneducated ------------------------------------------------------------------------------


def test_uneducated_doubles_technical_karma_but_not_points() -> None:
    """p. 87 doubles "the Karma cost"; the data has no point multiplier, unlike Uncouth's."""
    uneducated = _character(BY_NAME["Uneducated"].id)
    allocation = _allocate(uneducated, {"Hardware": 3})
    character = replace(uneducated, skill_allocation=allocation)
    skill_cost = create_karma_skill_selection(
        character, SKILLS, {SKILL["Hardware"].id: 1}, karma_budget=100
    ).karma_cost
    assert skill_cost == 4 * 2 * 2
    # Outdoors has Technical members (Navigation), so its group cost doubles too.
    group_cost = create_karma_skill_selection(
        character, SKILLS, karma_group_points={"Outdoors": 1}, karma_budget=100
    ).karma_cost
    assert group_cost == 1 * 5 * 2
    spec_cost = create_karma_skill_selection(
        character,
        SKILLS,
        karma_specializations={SKILL["Hardware"].id: "Cyberdecks"},
        karma_budget=100,
    ).karma_cost
    assert spec_cost == 7 * 2
    assert is_unaware(uneducated, SKILL["Computer"])
    assert not is_unaware(uneducated, SKILL["Pistols"])


def test_uneducated_doubles_academic_and_professional_knowledge_karma() -> None:
    uneducated = _character(BY_NAME["Uneducated"].id)
    knowledge = create_knowledge_selection(
        uneducated,
        [
            KnowledgeSkillPick(name="Chemistry", category="Academic", rating=2),
            KnowledgeSkillPick(name="Gangs", category="Street", rating=2),
        ],
        [],
    )
    character = replace(uneducated, knowledge_selection=knowledge)
    academic = create_karma_knowledge_selection(character, {"Chemistry": 1}, 100)
    street = create_karma_knowledge_selection(character, {"Gangs": 1}, 100)
    assert (academic.karma_cost, street.karma_cost) == (3 * 2, 3)


# --- Incompetent -----------------------------------------------------------------------------


def test_incompetent_names_a_group_and_the_magic_groups_only_for_a_magician() -> None:
    incompetent = BY_NAME["Incompetent"]
    mundane = choice_options(incompetent, None)
    assert "Firearms" in mundane and "Sorcery" not in mundane and "Tasking" not in mundane
    assert "Sorcery" not in choice_options(incompetent, "Adept")
    assert "Sorcery" in choice_options(incompetent, "Magician")
    with pytest.raises(ValueError, match="needs one of"):
        create_quality_selection([_incompetent("Sorcery")], QUALITIES)


def test_incompetent_bans_the_group_and_its_skills_and_makes_them_unaware() -> None:
    character = _character(_incompetent("Firearms"))
    with pytest.raises(ValueError, match="Incompetent"):
        _allocate(character, {}, {"Firearms": 1})
    with pytest.raises(ValueError, match="Incompetent"):
        _allocate(character, {"Pistols": 1})
    allocation = _allocate(character, {"Blades": 1})
    agility = character.attribute_value("AGI")
    assert dice_pool(character, allocation, SKILL["Pistols"]) == 0  # would default to AGI - 1
    assert dice_pool(character, allocation, SKILL["Blades"]) == 1 + agility
    with pytest.raises(ValueError, match="Incompetent"):
        create_karma_skill_selection(
            replace(character, skill_allocation=allocation),
            SKILLS,
            {SKILL["Longarms"].id: 1},
            karma_budget=100,
        )


# --- Sensitive System ------------------------------------------------------------------------


def test_sensitive_system_doubles_cyberware_essence() -> None:
    """The plan's acceptance: a 0.2-Essence implant costs 0.4."""
    sensitive = _character(BY_NAME["Sensitive System"].id)
    assert cyberware_essence_multiplier(sensitive) == 2
    selection = create_cyberware_tree_selection(
        [CyberwarePurchaseRequest(item_id=SMARTLINK.id)],
        CYBERWARE_ENTRIES,
        10**6,
        essence_multiplier=cyberware_essence_multiplier(sensitive),
    )
    assert selection.essence_spent == Decimal("0.4")


def test_sensitive_system_rejects_bioware() -> None:
    sensitive = _character(BY_NAME["Sensitive System"].id)
    assert bioware_disabled(sensitive)
    assert not bioware_disabled(_character())
    with pytest.raises(ValueError, match="rejects every bioware implant"):
        create_bioware_selection([BIOWARE[0].id], BIOWARE, 10**6, bioware_disabled=True)
    create_bioware_selection([], BIOWARE, 10**6, bioware_disabled=True)


def test_picking_sensitive_system_after_the_implant_reprices_it() -> None:
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
            "skills_letter": "C",
            "resources_letter": "A",
            "talent_letter": "E",
            "metatype_id": human.metatype.id,
        },
    )
    client.post("/ui/cyberware", data={f"cyberware_{SMARTLINK.id}": "1"})
    assert "Essence: 5.8 / 6." in client.get("/character/sheet").text
    client.post("/ui/qualities", data={"quality_id": BY_NAME["Sensitive System"].id})
    assert "Essence: 5.6 / 6." in client.get("/character/sheet").text
    page = client.post("/ui/cyberware", data={f"bioware_{BIOWARE[0].id}": "1"}).text
    assert "rejects every bioware implant" in page
