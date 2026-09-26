"""WP119: power instances with a target, and the powers whose effect this engine computes."""

from __future__ import annotations

import json
from dataclasses import replace
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from chummer5.data.metatypes import load_metatypes
from chummer5.data.powers import load_powers
from chummer5.data.priorities import load_priorities
from chummer5.data.skills import load_skills
from chummer5.engine.character import Character, create_character, metatype_choices
from chummer5.engine.derived import armor, initiative_dice, wound_modifier_rule
from chummer5.engine.improvements import Improvement, ImprovementSource, ImprovementType
from chummer5.engine.magic import (
    apply_power_improvements,
    create_power_selection,
    power_max_rating,
    power_target_options,
)
from chummer5.engine.skills import create_skill_allocation, skill_rating
from chummer5.io.save_format import from_json
from chummer5.web.app import create_app

METATYPES = load_metatypes()
PRIORITIES = load_priorities()
SKILLS = load_skills()
SKILL = {s.name: s for s in SKILLS}
POWERS = load_powers()
POWER = {p.name: p for p in POWERS}


def _pick(name: str, rating: int = 1, target: str | None = None) -> tuple[str, int, str | None]:
    return (POWER[name].id, rating, target)


def _adept(*picks: tuple[str, int, str | None], magic: int = 6) -> Character:
    choice = next(
        c
        for c in metatype_choices(PRIORITIES.heritage["A"], METATYPES)
        if c.metatype.name == "Human"
    )
    character = replace(
        create_character(choice, "A", "A", PRIORITIES, {"AGI": 2, "REA": 2}), magic_type="Adept"
    )
    selection = create_power_selection(list(picks), POWERS, magic)
    apply_power_improvements(character, selection)
    return replace(character, power_selection=selection)


# --- costs and caps --------------------------------------------------------------------------


@pytest.mark.parametrize(("level", "cost"), [(1, "1.5"), (2, "2.5"), (3, "3.5")])
def test_improved_reflexes_costs_the_printed_table(level: int, cost: str) -> None:
    """p. 310's Improved Reflexes Table: 1.5, 2.5, 3.5 PP."""
    selection = create_power_selection([_pick("Improved Reflexes", level)], POWERS, 6)
    assert selection.power_points_spent == Decimal(cost)


def test_levels_cap_at_magic_and_the_powers_own_maximum() -> None:
    """p. 308: "equal to your Magic Rating, or up to a limit listed by the power, whichever is
    less". WP27 read `<limit>` as the cap, which held Enhanced Perception at 1."""
    assert power_max_rating(POWER["Improved Reflexes"], 6) == 3
    assert power_max_rating(POWER["Improved Reflexes"], 2) == 2
    assert power_max_rating(POWER["Enhanced Perception"], 5) == 5
    assert power_max_rating(POWER["Killing Hands"], 6) == 1
    with pytest.raises(ValueError, match="out of range 1..3"):
        create_power_selection([_pick("Improved Reflexes", 4)], POWERS, 6)
    create_power_selection([_pick("Enhanced Perception", 4)], POWERS, 6)


# --- computed effects ------------------------------------------------------------------------


def test_improved_reflexes_adds_reaction_and_initiative_dice() -> None:
    plain = _adept()
    adept = _adept(_pick("Improved Reflexes", 2))
    assert adept.attribute_value("REA") == plain.attribute_value("REA") + 2
    assert initiative_dice(adept) == initiative_dice(plain) + 2


def test_improved_reflexes_does_not_combine_with_wired_reflexes() -> None:
    """p. 310: "cannot be combined with other technological or magical increases to Initiative".
    The higher of the two counts, for both the dice and the Reaction."""
    adept = _adept(_pick("Improved Reflexes", 1))
    before_dice, before_rea = initiative_dice(adept), adept.attribute_value("REA")
    for improvement_type, target in (
        (ImprovementType.INITIATIVE_DICE, ""),
        (ImprovementType.ATTRIBUTE, "REA"),
    ):
        adept.improvements.add(
            Improvement(
                improvement_type=improvement_type,
                target=target,
                value=2,
                source_type=ImprovementSource.CYBERWARE,
                source_id="wired-reflexes-2",
                unique_name="precedence0",
            )
        )
    assert initiative_dice(adept) == before_dice + 1  # 2 replaces 1, not 1 + 2
    assert adept.attribute_value("REA") == before_rea + 1


def test_mystic_armor_and_pain_resistance() -> None:
    adept = _adept(_pick("Mystic Armor", 2), _pick("Pain Resistance", 3))
    assert armor(adept) == 2
    assert wound_modifier_rule(adept).physical_boxes_ignored == 3


def test_pain_resistance_excludes_high_pain_tolerance_note() -> None:
    assert POWER["Pain Resistance"].unmodeled_effect_note
    assert POWER["Mystic Armor"].unmodeled_effect_note


# --- instances and targets -------------------------------------------------------------------


def test_repeatable_powers_take_a_distinct_target_each() -> None:
    selection = create_power_selection(
        [
            _pick("Critical Strike", target="Blades"),
            _pick("Critical Strike", target="Unarmed Combat"),
            _pick("Improved Physical Attribute", 1, "BOD"),
            _pick("Improved Physical Attribute", 1, "AGI"),
        ],
        POWERS,
        6,
    )
    assert len(selection.picks) == 4
    with pytest.raises(ValueError, match="twice for one target"):
        create_power_selection(
            [_pick("Critical Strike", target="Blades"), _pick("Critical Strike", target="Blades")],
            POWERS,
            6,
        )
    with pytest.raises(ValueError, match="more than once"):
        create_power_selection([_pick("Killing Hands"), _pick("Killing Hands")], POWERS, 6)


def test_target_options_follow_the_printed_lists() -> None:
    assert power_target_options(POWER["Critical Strike"]) == (
        "Astral Combat",
        "Blades",
        "Clubs",
        "Exotic Melee Weapon",
        "Unarmed Combat",
    )
    accuracy = power_target_options(POWER["Enhanced Accuracy (skill)"])
    assert "Pistols" in accuracy and "Unarmed Combat" not in accuracy
    ability = power_target_options(POWER["Improved Ability (skill)"])
    assert "Pistols" in ability and "Perception" in ability and "Spellcasting" not in ability
    with pytest.raises(ValueError, match="needs one of"):
        create_power_selection([_pick("Critical Strike", target="Pistols")], POWERS, 6)
    with pytest.raises(ValueError, match="needs one of"):
        create_power_selection([_pick("Critical Strike")], POWERS, 6)


def test_improved_ability_needs_the_skill_and_caps_at_half_its_rating() -> None:
    pick = _pick("Improved Ability (skill)", 2, "Pistols")
    with pytest.raises(ValueError, match="Pistols at rating 1 or higher; it is at 0"):
        create_power_selection([pick], POWERS, 6, learned_skill_ratings={})
    with pytest.raises(ValueError, match="out of range 1..1"):
        create_power_selection([pick], POWERS, 6, learned_skill_ratings={"Pistols": 2})
    create_power_selection([pick], POWERS, 6, learned_skill_ratings={"Pistols": 3})


def test_improved_ability_raises_the_skill_rating() -> None:
    adept = _adept(_pick("Improved Ability (skill)", 2, "Pistols"))
    allocation = create_skill_allocation("A", PRIORITIES, SKILLS, {SKILL["Pistols"].id: 4}, {})
    adept = replace(adept, skill_allocation=allocation)
    assert skill_rating(adept, allocation, SKILL["Pistols"]) == 6


def test_kyras_power_list_builds_for_an_adept() -> None:
    """Step Three's worked example. Kyra is a Mystic Adept (out of scope), so her 2 bought Power
    Points become an Adept's free ones. Her line prints Voice Control at .25, but the power costs
    0.5 PP per level (p. 311), so the list costs 2.25, not 2."""
    selection = create_power_selection(
        [
            _pick("Enhanced Accuracy (skill)", target="Pistols"),
            _pick("Improved Ability (skill)", 1, "Pistols"),
            _pick("Improved Potential (Social)"),
            _pick("Mystic Armor", 1),
            _pick("Voice Control", 1),
        ],
        POWERS,
        6,
        learned_skill_ratings={"Pistols": 3},  # her Step Five Pistols 3
    )
    assert selection.power_points_spent == Decimal("2.25")


# --- persistence -----------------------------------------------------------------------------


def _confirm_adept(client: TestClient) -> None:
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
    client.post(
        "/ui/talent",
        data={
            "talent_letter": "B",
            "talent_codename": "Adept",
            "granted_skill_id": [SKILL["Pistols"].id],
        },
    )


def test_two_critical_strikes_through_the_page_and_a_save() -> None:
    critical = POWER["Critical Strike"]
    client = TestClient(create_app())
    _confirm_adept(client)
    page = client.post(
        "/ui/powers",
        data={f"power_rating_{critical.id}": "1", f"power_target_{critical.id}": "Blades"},
    ).text
    assert f'name="power_rating_{critical.id}:1"' in page  # the "another" row
    client.post(
        "/ui/powers",
        data={
            f"power_rating_{critical.id}": "1",
            f"power_target_{critical.id}": "Blades",
            f"power_rating_{critical.id}:1": "1",
            f"power_target_{critical.id}:1": "Clubs",
        },
    )
    sheet = client.get("/character/sheet").text
    assert "Critical Strike (rating 1, Blades)" in sheet
    assert "Critical Strike (rating 1, Clubs)" in sheet

    saved = client.get("/character/save").content
    fresh = TestClient(create_app())
    fresh.get("/")
    fresh.post("/character/load", files={"save_file": ("c.json", saved, "application/json")})
    assert "Critical Strike (rating 1, Clubs)" in fresh.get("/character/sheet").text


def test_improved_ability_on_the_talent_granted_skill_is_known() -> None:
    """The Adept's free Talent skill (Pistols 4 at letter B) counts as learned."""
    ability = POWER["Improved Ability (skill)"]
    client = TestClient(create_app())
    _confirm_adept(client)
    page = client.post(
        "/ui/powers",
        data={f"power_rating_{ability.id}": "2", f"power_target_{ability.id}": "Pistols"},
    ).text
    assert "it is at" not in page
    assert "Improved Ability (skill) (rating 2, Pistols)" in client.get("/character/sheet").text


def test_a_save_written_before_wp119_still_loads() -> None:
    """WP119 renamed the saved key `selected_attribute` to `target`; the old key still reads."""
    client = TestClient(create_app())
    _confirm_adept(client)
    ipa = POWER["Improved Physical Attribute"]
    client.post("/ui/powers", data={f"power_rating_{ipa.id}": "1", f"power_target_{ipa.id}": "BOD"})
    data = json.loads(client.get("/character/save").content)
    assert data["power_picks"] == [{"power_id": ipa.id, "rating": 1, "target": "BOD"}]
    for pick in data["power_picks"]:
        pick["selected_attribute"] = pick.pop("target")
    assert from_json(json.dumps(data)).power_picks == ((ipa.id, 1, "BOD"),)


def test_pain_resistance_and_high_pain_tolerance_exclude_each_other() -> None:
    """p. 74: High Pain Tolerance is "incompatible with [the] Pain Resistance adept power". Both
    data rows say so; WP114 parsed the quality side before any power could fire it."""
    from chummer5.data.qualities import load_qualities
    from chummer5.engine.qualities import QualityPickRequest, create_quality_selection

    hpt = next(q for q in load_qualities() if q.name == "High Pain Tolerance")
    with pytest.raises(ValueError, match="cannot be taken together with"):
        create_power_selection(
            [_pick("Pain Resistance", 1)], POWERS, 6, quality_names=["High Pain Tolerance"]
        )
    with pytest.raises(ValueError, match="cannot be taken together with"):
        create_quality_selection(
            [QualityPickRequest(hpt.id, rating=1)],
            load_qualities(),
            magic_type="Adept",
            power_names=["Pain Resistance"],
        )
