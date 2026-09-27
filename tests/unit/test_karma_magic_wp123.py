"""WP123: Step Seven Karma may raise Magic, like any attribute (p. 106), from the Essence-reduced
current rating (p. 278)."""

from __future__ import annotations

import re
from dataclasses import replace
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from chummer5.data.metatypes import load_metatypes
from chummer5.data.priorities import load_priorities
from chummer5.data.qualities import load_qualities
from chummer5.data.skills import load_skills
from chummer5.engine.character import (
    Character,
    create_character,
    create_karma_attribute_points,
    metatype_choices,
)
from chummer5.engine.improvements import Improvement, ImprovementSource, ImprovementType
from chummer5.engine.qualities import (
    QualityPickRequest,
    apply_quality_improvements,
    create_quality_selection,
    requested_attribute_maximum_bonuses,
)
from chummer5.web.app import create_app

METATYPES = load_metatypes()
PRIORITIES = load_priorities()
QUALITIES = load_qualities()
EXCEPTIONAL = next(q for q in QUALITIES if q.name == "Exceptional Attribute")


def _adept(magic: int = 4, *, exceptional: bool = False) -> Character:
    choice = next(
        c
        for c in metatype_choices(PRIORITIES.heritage["A"], METATYPES)
        if c.metatype.name == "Human"
    )
    picks = [QualityPickRequest(EXCEPTIONAL.id, choice="MAG")] if exceptional else []
    character = create_character(
        choice,
        "A",
        "A",
        PRIORITIES,
        {},
        maximum_bonus=requested_attribute_maximum_bonuses(picks, QUALITIES),
    )
    character = replace(character, magic_type="Adept", magic_rating=magic)
    if exceptional:
        selection = create_quality_selection(picks, QUALITIES, magic_type="Adept")
        apply_quality_improvements(character, selection.qualities)
    return character


def _raise(character: Character, points: int) -> Character:
    selection = create_karma_attribute_points(character, {"MAG": points}, 1000)
    return replace(character, karma_attribute_selection=selection)


def test_a_magic_4_adept_pays_25_karma_for_magic_5_and_gets_5_power_points() -> None:
    """The plan's acceptance."""
    adept = _raise(_adept(4), 1)
    assert adept.karma_attribute_selection.karma_cost == 25  # type: ignore[union-attr]
    assert adept.attribute_value("MAG") == 5
    assert adept.power_points == 5


def test_the_raise_stops_at_the_maximum_and_exceptional_attribute_lifts_it() -> None:
    with pytest.raises(ValueError, match="exceeds the maximum of 6"):
        _raise(_adept(4), 3)
    assert _raise(_adept(4, exceptional=True), 3).attribute_value("MAG") == 7


def test_essence_loss_lowers_the_start_and_the_maximum() -> None:
    """p. 278's example: an implant costing 0.2 Essence takes Magic 4 (max 6) to 3 (max 5). Karma
    then raises the 3: to 5 costs 4 x 5 + 5 x 5 = 45, and 6 is past the reduced maximum."""
    adept = _adept(4)
    adept.improvements.add(
        Improvement(
            improvement_type=ImprovementType.ESSENCE,
            target="",
            value=0,
            source_type=ImprovementSource.CYBERWARE,
            source_id="cybereyes",
            essence_value=-Decimal("0.2"),
        )
    )
    assert adept.attribute_value("MAG") == 3
    raised = _raise(adept, 2)
    assert raised.karma_attribute_selection.karma_cost == 45  # type: ignore[union-attr]
    assert raised.attribute_value("MAG") == 5
    with pytest.raises(ValueError, match="maximum of 5 after Essence loss"):
        _raise(adept, 3)


def test_a_mundane_character_has_no_magic_to_raise() -> None:
    mundane = replace(_adept(), magic_type=None, magic_rating=0)
    with pytest.raises(ValueError, match="not allocatable"):
        create_karma_attribute_points(mundane, {"MAG": 1}, 100)


def test_the_attributes_page_raises_magic_with_karma_and_it_survives_a_save() -> None:
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
            "heritage_letter": "A",
            "talent_letter": "C",
            "attributes_letter": "B",
            "skills_letter": "D",
            "resources_letter": "E",
            "metatype_id": human.metatype.id,
        },
    )
    pistols = next(s for s in load_skills() if s.name == "Pistols")
    client.post(
        "/ui/talent",
        data={"talent_letter": "C", "talent_codename": "Adept", "granted_skill_id": [pistols.id]},
    )
    page = client.post("/ui/attributes", data={"karma_attr_MAG": "1"}).text
    assert 'name="karma_attr_MAG"' in page
    sheet = re.sub(r"\s+", " ", client.get("/character/sheet").text)
    assert "Magic rating: 5" in sheet

    saved = client.get("/character/save").content
    fresh = TestClient(create_app())
    fresh.get("/")
    fresh.post("/character/load", files={"save_file": ("c.json", saved, "application/json")})
    assert "Magic rating: 5" in fresh.get("/character/sheet").text
