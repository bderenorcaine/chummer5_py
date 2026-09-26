"""WP122: every core mentor spirit slot, applied."""

from __future__ import annotations

import re
from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from chummer5.data.mentors import load_mentors
from chummer5.data.metatypes import load_metatypes
from chummer5.data.priorities import load_priorities
from chummer5.data.qualities import load_qualities
from chummer5.data.skills import load_skills
from chummer5.engine.character import Character, create_character, metatype_choices
from chummer5.engine.derived import damage_resistance, unmodeled_effect_notes
from chummer5.engine.improvements import ImprovementType
from chummer5.engine.qualities import (
    apply_mentor_spirit_improvements,
    create_quality_selection,
    mentor_free_power_options,
)
from chummer5.web.app import create_app

QUALITIES = load_qualities()
MENTOR_SPIRIT = next(q for q in QUALITIES if q.name == "Mentor Spirit")
MENTORS = {m.name: m for m in load_mentors()}
METATYPES = load_metatypes()
PRIORITIES = load_priorities()
SKILL = {s.name: s for s in load_skills()}


def _character(magic_type: str) -> Character:
    choice = next(
        c
        for c in metatype_choices(PRIORITIES.heritage["A"], METATYPES)
        if c.metatype.name == "Human"
    )
    return replace(create_character(choice, "A", "A", PRIORITIES, {}), magic_type=magic_type)


def _follow(mentor: str, magic_type: str = "Adept", **kwargs: object) -> Character:
    character = _character(magic_type)
    selection = create_quality_selection(
        [MENTOR_SPIRIT.id],
        QUALITIES,
        magic_type=magic_type,
        mentor_catalog=tuple(MENTORS.values()),
        mentor_spirit_archetype_id=MENTORS[mentor].id,
        **kwargs,  # type: ignore[arg-type]
    )
    assert selection.mentor_spirit is not None
    apply_mentor_spirit_improvements(character, selection.mentor_spirit)
    return replace(character, quality_selection=selection)


# --- the plan's acceptance -------------------------------------------------------------------


def test_an_adept_following_bear_gets_damage_resistance_and_rapid_healing() -> None:
    plain = _character("Adept")
    bear = _follow("Bear")
    assert damage_resistance(bear) == damage_resistance(plain) + 2
    pick = bear.quality_selection.mentor_spirit  # type: ignore[union-attr]
    assert [(p.power.name, p.rating) for p in pick.free_powers] == [("Rapid Healing", 1)]


def test_an_adept_following_eagle_gets_perception_combat_sense_and_the_allergy() -> None:
    eagle = _follow("Eagle")
    pick = eagle.quality_selection.mentor_spirit  # type: ignore[union-attr]
    assert eagle.improvements.resolve(ImprovementType.SKILL, "Perception") == 2
    assert [(p.power.name, p.rating) for p in pick.free_powers] == [("Combat Sense", 1)]
    assert [(g.quality.name, g.text, g.karma) for g in pick.granted_qualities] == [
        ("Allergy (Common, Mild)", "Pollutants", -10)
    ]
    # The Allergy is granted, not bought: no Karma moves.
    assert eagle.quality_selection.karma_cost == MENTOR_SPIRIT.karma  # type: ignore[union-attr]
    notes = dict(unmodeled_effect_notes(eagle))
    assert "Allergy (Common, Mild)" in notes and "Combat Sense" in notes


# --- choices ---------------------------------------------------------------------------------


def test_dragonslayer_needs_a_social_skill_of_choice() -> None:
    with pytest.raises(ValueError, match="skill of choice must be one of"):
        _follow("Dragonslayer")
    with pytest.raises(ValueError, match="skill of choice must be one of"):
        _follow(
            "Dragonslayer",
            mentor_spirit_skill_choice="Pistols",
            mentor_spirit_power_targets=("Pistols",),
        )
    dragonslayer = _follow(
        "Dragonslayer",
        mentor_spirit_skill_choice="Negotiation",
        mentor_spirit_power_targets=("Pistols",),  # its free Enhanced Accuracy
    )
    assert dragonslayer.improvements.resolve(ImprovementType.SKILL, "Negotiation") == 2
    with pytest.raises(ValueError, match="has no skill of choice"):
        _follow("Bear", mentor_spirit_skill_choice="Negotiation")


def test_a_free_power_names_a_target_within_the_mentors_narrowing() -> None:
    """Sea's Improved Ability is "on an athletic skill"; Thunderbird's Critical Strike on one of
    the power's melee skills; Wolf's Attribute Boost is Agility's, so it asks nothing."""
    sea = MENTORS["Sea"].adept_choice.free_powers[0]
    assert "Swimming" in mentor_free_power_options(sea)
    assert "Pistols" not in mentor_free_power_options(sea)
    with pytest.raises(ValueError, match="needs one of"):
        _follow("Sea", mentor_spirit_power_targets=("Pistols",))
    swimmer = _follow("Sea", mentor_spirit_power_targets=("Swimming",))
    assert swimmer.improvements.resolve(ImprovementType.SKILL, "Swimming") == 2 + 1
    with pytest.raises(ValueError, match="need 1 target"):
        _follow("Thunderbird")
    wolf = _follow("Wolf")
    pick = wolf.quality_selection.mentor_spirit  # type: ignore[union-attr]
    assert [(p.power.name, p.rating, p.target) for p in pick.free_powers] == [
        ("Attribute Boost", 2, "AGI")
    ]


def test_a_magician_gets_no_free_powers() -> None:
    bear = _follow("Bear", "Magician")
    assert bear.quality_selection.mentor_spirit.free_powers == ()  # type: ignore[union-attr]


# --- the page --------------------------------------------------------------------------------


def _confirm_magician(client: TestClient) -> None:
    from chummer5.data.traditions import load_traditions

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
    hermetic = next(t for t in load_traditions() if t.name == "Hermetic")
    client.post(
        "/ui/talent",
        data={
            "talent_letter": "B",
            "talent_codename": "Magician",
            "tradition_id": hermetic.id,
            "granted_skill_id": [SKILL["Spellcasting"].id, SKILL["Counterspelling"].id],
        },
    )


def test_a_bear_magicians_health_spell_pool_is_on_the_sheet() -> None:
    client = TestClient(create_app())
    _confirm_magician(client)
    client.post("/ui/skills", data={})
    client.post(
        "/ui/qualities",
        data={"quality_id": [MENTOR_SPIRIT.id], "mentor_spirit_archetype_id": MENTORS["Bear"].id},
    )
    sheet = re.sub(r"\s+", " ", client.get("/character/sheet").text)
    # Spellcasting 4 (the Talent grant) + MAG 4 = 8, and 10 for a Health spell.
    assert "Spellcasting: 10 dice for Health spells, preparations and rituals (+2" in sheet
    assert "Disadvantage: may go berserk" in sheet  # the registry note
