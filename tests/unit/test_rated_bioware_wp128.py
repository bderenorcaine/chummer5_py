"""WP128: the 15 rated core bioware rows (pp. 459-461), with their computed effects."""

from __future__ import annotations

import json
import re
from copy import deepcopy
from dataclasses import replace
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from chummer5.data.bioware import load_bioware
from chummer5.data.metatypes import load_metatypes
from chummer5.data.priorities import load_priorities
from chummer5.data.skills import load_skills
from chummer5.engine.bioware import (
    BiowarePurchaseRequest,
    apply_bioware_improvements,
    bioware_rating_maximum,
    create_bioware_selection,
)
from chummer5.engine.character import Character, create_character, metatype_choices
from chummer5.engine.derived import (
    armor,
    damage_resistance,
    initiative_dice,
    memory,
    mental_limit,
    social_limit,
    wound_modifier_rule,
)
from chummer5.engine.knowledge import knowledge_dice_pool, language_dice_pool
from chummer5.engine.skills import create_skill_allocation, dice_pool
from chummer5.web.app import create_app

BIOWARE = {b.name: b for b in load_bioware()}
METATYPES = load_metatypes()
PRIORITIES = load_priorities()
SKILLS = {s.name: s for s in load_skills()}


def _human(**attributes: int) -> Character:
    choice = next(
        c
        for c in metatype_choices(PRIORITIES.heritage["A"], METATYPES)
        if c.metatype.name == "Human"
    )
    return create_character(choice, "A", "A", PRIORITIES, attributes)


def _with(
    character: Character, *purchases: tuple[str, int], others: frozenset[str] = frozenset()
) -> Character:
    """`character` plus these purchases -- on a copy of its Improvement index, so the caller's
    `character` stays the unaugmented baseline (`replace` alone would share the index)."""
    selection = create_bioware_selection(
        [BiowarePurchaseRequest(BIOWARE[name].id, rating=rating) for name, rating in purchases],
        BIOWARE.values(),
        10**7,
        other_augmentations=others,
        availability_exempt=frozenset(),
    )
    character = replace(
        character, bioware_selection=selection, improvements=deepcopy(character.improvements)
    )
    apply_bioware_improvements(character, selection)
    return character


def test_muscle_toner_2_raises_agility_under_the_augmentation_cap() -> None:
    """The plan's acceptance: +2 AGI, within the +4 augmentation cap (p. 94)."""
    human = _human(AGI=3)
    base = human.attribute_value("AGI")
    toned = _with(human, ("Muscle Toner", 2))
    assert toned.attribute_value("AGI") == base + 2
    assert toned.bioware_selection.nuyen_spent == 64000  # type: ignore[union-attr]
    assert toned.bioware_selection.essence_spent == Decimal("0.4")  # type: ignore[union-attr]


def test_the_offered_ratings_stop_at_availability_12() -> None:
    assert bioware_rating_maximum(BIOWARE["Muscle Toner"]) == 2  # (Rating x 5)R
    assert bioware_rating_maximum(BIOWARE["Damage Compensators"]) == 4  # (Rating x 3)F
    assert bioware_rating_maximum(BIOWARE["Pathogenic Defense"]) == 6  # (Rating x 2)
    with pytest.raises(ValueError, match="over Availability 12"):
        _with(_human(), ("Muscle Toner", 3))


def test_the_books_incompatibilities_not_the_plans() -> None:
    """p. 459: Toner and Augmentation are each incompatible with what raises *their* attribute,
    muscle replacement included -- not with each other, which touch different attributes. The
    plan's "Toner plus Augmentation is rejected" is overruled by the book (decisions log)."""
    both = _with(_human(STR=3, AGI=3), ("Muscle Toner", 1), ("Muscle Augmentation", 1))
    assert both.attribute_value("STR") == _human(STR=3).attribute_value("STR") + 1
    with pytest.raises(ValueError, match="can't be combined with Muscle Replacement"):
        _with(_human(), ("Muscle Toner", 1), others=frozenset({"Muscle Replacement"}))
    with pytest.raises(ValueError, match="can't be combined with Dermal Plating"):
        _with(_human(), ("Orthoskin", 1), others=frozenset({"Dermal Plating"}))
    with pytest.raises(ValueError, match="Wired Reflexes"):
        _with(_human(), ("Synaptic Booster", 1), others=frozenset({"Wired Reflexes"}))
    with pytest.raises(ValueError, match="Bone Lacing"):
        _with(
            _human(), ("Bone Density Augmentation", 1), others=frozenset({"Bone Lacing (Plastic)"})
        )
    with pytest.raises(ValueError, match="High Pain Tolerance"):
        _with(_human(), ("Damage Compensators", 1), others=frozenset({"High Pain Tolerance"}))


def test_a_rated_row_is_bought_once() -> None:
    with pytest.raises(ValueError, match="bought once"):
        _with(_human(), ("Cerebral Booster", 1), ("Cerebral Booster", 1))


def test_orthoskin_2_shows_in_armor() -> None:
    """The plan's acceptance."""
    assert armor(_with(_human(), ("Orthoskin", 2))) == armor(_human()) + 2


def test_the_attribute_and_initiative_rows() -> None:
    human = _human(LOG=2, REA=2)
    boosted = _with(human, ("Cerebral Booster", 2), ("Synaptic Booster", 1))
    assert boosted.attribute_value("LOG") == human.attribute_value("LOG") + 2
    assert boosted.attribute_value("REA") == human.attribute_value("REA") + 1
    assert initiative_dice(boosted) == initiative_dice(human) + 1


def test_mnemonic_enhancer_reaches_memory_the_mental_limit_and_knowledge_pools() -> None:
    """p. 460: its Rating as dice to Knowledge, Language and memory tests, and to the Mental
    limit."""
    human = _human(LOG=2)
    enhanced = _with(human, ("Mnemonic Enhancer", 2))
    assert memory(enhanced) == memory(human) + 2
    assert mental_limit(enhanced) > mental_limit(human)
    assert (
        knowledge_dice_pool(enhanced, "Academic", 3)
        == knowledge_dice_pool(human, "Academic", 3) + 2
    )
    assert language_dice_pool(enhanced, 2) == language_dice_pool(human, 2) + 2


def test_synthacardium_adds_dice_to_every_athletics_skill() -> None:
    human = _human()
    allocation = create_skill_allocation(
        "A", PRIORITIES, tuple(SKILLS.values()), {}, {"Athletics": 2}
    )
    human = replace(human, skill_allocation=allocation)
    hearty = _with(human, ("Synthacardium", 3))
    running = SKILLS["Running"]
    assert dice_pool(hearty, allocation, running) == dice_pool(human, allocation, running) + 3
    pistols = SKILLS["Pistols"]
    assert dice_pool(hearty, allocation, pistols) == dice_pool(human, allocation, pistols)


def test_the_resistance_and_wound_rows() -> None:
    human = _human()
    dense = _with(human, ("Bone Density Augmentation", 2), ("Damage Compensators", 3))
    assert damage_resistance(dense) == damage_resistance(human) + 2
    rule = wound_modifier_rule(dense)
    assert rule.physical_boxes_ignored == wound_modifier_rule(human).physical_boxes_ignored + 3
    assert rule.stun_boxes_ignored == wound_modifier_rule(human).stun_boxes_ignored + 3


def test_tailored_pheromones_raise_the_social_limit() -> None:
    human = _human()
    assert social_limit(_with(human, ("Tailored Pheromones", 2))) == social_limit(human) + 2


def _confirm(client: TestClient) -> None:
    client.get("/")
    human = next(
        c
        for c in metatype_choices(PRIORITIES.heritage["B"], METATYPES)
        if c.metatype.name == "Human"
    )
    client.post(
        "/ui/priorities",
        data={
            "heritage_letter": "B",
            "attributes_letter": "C",
            "skills_letter": "D",
            "resources_letter": "A",
            "talent_letter": "E",
            "metatype_id": human.metatype.id,
        },
    )


def test_the_picker_buys_a_rated_row_and_the_save_keeps_its_rating() -> None:
    toner = BIOWARE["Muscle Toner"]
    client = TestClient(create_app())
    _confirm(client)
    page = client.post(
        "/ui/cyberware",
        data={f"bioware_{toner.id}": "1", f"bioware_rating_{toner.id}_0": "2"},
    ).text
    select = re.search(rf'name="bioware_rating_{toner.id}_0">(.*?)</select>', page, re.S)
    assert select is not None
    assert re.findall(r'value="(\d+)"', select.group(1)) == ["1", "2"]
    saved = json.loads(client.get("/character/save").content)
    assert saved["bioware_purchases"] == [
        {"item_id": toner.id, "chosen_skill": None, "grade": "Standard", "rating": 2}
    ]
    sheet = re.sub(r"\s+", " ", client.get("/character/sheet").text)
    assert "Muscle Toner (Rating 2)" in sheet
