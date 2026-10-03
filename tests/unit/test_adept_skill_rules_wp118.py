"""WP118: Adepts can't use the magic groups' skills, and learn Assensing only with the Astral
Perception power (p. 69)."""

from __future__ import annotations

from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from chummer5.data.metatypes import load_metatypes
from chummer5.data.powers import load_powers
from chummer5.data.priorities import load_priorities
from chummer5.data.skills import load_skills
from chummer5.engine.character import Character, create_character, metatype_choices
from chummer5.engine.magic import (
    apply_power_improvements,
    create_power_selection,
    mvp_power_catalog,
)
from chummer5.engine.skills import (
    create_karma_skill_selection,
    create_skill_allocation,
    skill_purchase_rules,
)
from chummer5.web.app import create_app
from chummer5.web.catalogs import TRADITIONS, offered_skill_groups, offered_skills

METATYPES = load_metatypes()
PRIORITIES = load_priorities()
SKILLS = load_skills()
SKILL = {s.name: s for s in SKILLS}
POWERS = load_powers()
ASTRAL_PERCEPTION = next(p for p in POWERS if p.name == "Astral Perception")
HERMETIC = next(t for t in TRADITIONS if t.name == "Hermetic")


def _character(magic_type: str | None, *, astral_perception: bool = False) -> Character:
    choice = next(
        c
        for c in metatype_choices(PRIORITIES.heritage["A"], METATYPES)
        if c.metatype.name == "Human"
    )
    character = replace(create_character(choice, "A", "A", PRIORITIES, {}), magic_type=magic_type)
    if astral_perception:
        selection = create_power_selection([(ASTRAL_PERCEPTION.id, 1, None)], POWERS, 6)
        apply_power_improvements(character, selection)
        character = replace(character, power_selection=selection)
    return character


def _allocate(character: Character, points: dict[str, int], groups: dict[str, int] | None = None):  # type: ignore[no-untyped-def]
    return create_skill_allocation(
        "A",
        PRIORITIES,
        SKILLS,
        {SKILL[name].id: rating for name, rating in points.items()},
        groups or {},
        rules=skill_purchase_rules(character),
    )


def test_astral_perception_is_offered_and_unlocks_assensing() -> None:
    assert ASTRAL_PERCEPTION in mvp_power_catalog(POWERS)
    assert ASTRAL_PERCEPTION.unmodeled_effect_note


@pytest.mark.parametrize("name", ["Counterspelling", "Summoning", "Alchemy", "Assensing"])
def test_an_adept_cannot_buy_a_magic_group_skill_or_assensing(name: str) -> None:
    with pytest.raises(ValueError, match="an Adept"):
        _allocate(_character("Adept"), {name: 1})


@pytest.mark.parametrize("group", ["Sorcery", "Conjuring", "Enchanting"])
def test_an_adept_cannot_buy_a_magic_group(group: str) -> None:
    with pytest.raises(ValueError, match="an Adept"):
        _allocate(_character("Adept"), {}, {group: 1})


def test_an_adept_may_buy_arcana_and_astral_combat() -> None:
    _allocate(_character("Adept"), {"Arcana": 2, "Astral Combat": 2})


def test_astral_perception_lets_an_adept_buy_assensing() -> None:
    """The plan's acceptance: an Adept with Astral Perception can buy Assensing."""
    _allocate(_character("Adept", astral_perception=True), {"Assensing": 3})


def test_a_magician_is_unrestricted() -> None:
    _allocate(_character("Magician"), {"Counterspelling": 2, "Assensing": 2}, {"Conjuring": 1})


def test_karma_cannot_buy_a_banned_skill_either() -> None:
    adept = _character("Adept")
    character = replace(adept, skill_allocation=_allocate(adept, {}))
    with pytest.raises(ValueError, match="an Adept"):
        create_karma_skill_selection(
            character, SKILLS, {SKILL["Counterspelling"].id: 1}, karma_budget=100
        )
    with pytest.raises(ValueError, match="an Adept"):
        create_karma_skill_selection(
            character, SKILLS, karma_group_points={"Sorcery": 1}, karma_budget=100
        )


def test_the_picker_hides_what_an_adept_cannot_buy() -> None:
    adept = {s.name for s in offered_skills(_character("Adept"))}
    assert "Counterspelling" not in adept and "Assensing" not in adept
    assert "Arcana" in adept and "Astral Combat" in adept
    assert "Assensing" in {
        s.name for s in offered_skills(_character("Adept", astral_perception=True))
    }
    assert not {"Sorcery", "Conjuring", "Enchanting"} & set(
        offered_skill_groups(_character("Adept"))
    )
    assert "Sorcery" in offered_skill_groups(_character("Magician"))


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
            "talent_letter": "B",
            "attributes_letter": "C",
            "skills_letter": "D",
            "resources_letter": "E",
            "metatype_id": human.metatype.id,
        },
    )


def test_a_magician_turned_adept_keeps_the_spend_with_a_stale_warning() -> None:
    counterspelling = SKILL["Counterspelling"]
    spellcasting = SKILL["Spellcasting"]
    client = TestClient(create_app())
    _confirm(client)
    client.post(
        "/ui/talent",
        data={
            "talent_letter": "B",
            "talent_codename": "Magician",
            "tradition_id": HERMETIC.id,
            "granted_skill_id": [spellcasting.id, counterspelling.id],
        },
    )
    client.post("/ui/skills", data={f"skill_{SKILL['Ritual Spellcasting'].id}": "2"})
    client.post(
        "/ui/talent",
        data={
            "talent_letter": "B",
            "talent_codename": "Adept",
            "granted_skill_id": [SKILL["Pistols"].id],
        },
    )
    page = client.get("/ui/page/skills").text
    assert "an Adept cannot use magic skill groups" in page


def test_an_adept_with_astral_perception_buys_assensing_and_it_survives_a_save() -> None:
    assensing = SKILL["Assensing"]
    client = TestClient(create_app())
    _confirm(client)
    client.post(
        "/ui/talent",
        data={
            "talent_letter": "B",
            "talent_codename": "Adept",
            "granted_skill_id": [SKILL["Pistols"].id],
        },
    )
    assert f'name="skill_{assensing.id}"' not in client.get("/ui/page/skills").text
    client.post("/ui/powers", data={f"power_rating_{ASTRAL_PERCEPTION.id}": "1"})
    assert f'name="skill_{assensing.id}"' in client.get("/ui/page/skills").text
    page = client.post("/ui/skills", data={f"skill_{assensing.id}": "3"}).text
    assert "an Adept" not in page

    saved = client.get("/character/save").content
    fresh = TestClient(create_app())
    fresh.get("/")
    loaded = fresh.post(
        "/characters/upload?open=true", files={"files": ("c.json", saved, "application/json")}
    )
    assert "Character loaded." in loaded.text
    assert "Assensing" in fresh.get("/character/sheet").text
