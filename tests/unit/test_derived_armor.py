"""WP109: Overflow, the wound-modifier rule, Armor and the Damage Resistance pool.

Built end to end through `build_character`, so the gear catalog, the cyberware classifier and the
save format are all on the path the numbers come from.
"""

from __future__ import annotations

import json
from dataclasses import replace

from chummer5.data.cyberware_subsystems import load_cyberware_entries
from chummer5.data.lifestyle import load_lifestyles
from chummer5.data.metatypes import load_metatypes
from chummer5.data.priorities import load_priorities
from chummer5.data.qualities import load_qualities
from chummer5.data.skills import load_skills
from chummer5.engine.character import Character
from chummer5.engine.cyberware_subsystems import CyberwarePurchaseRequest
from chummer5.engine.derived import (
    armor,
    armor_breakdown,
    damage_resistance,
    overflow,
    wound_modifier_rule,
)
from chummer5.engine.improvements import Improvement, ImprovementSource, ImprovementType
from chummer5.io.save_format import (
    CharacterSave,
    build_character,
    create_character_save,
    from_json,
    to_json,
)

METATYPES = load_metatypes()
PRIORITIES = load_priorities()
SKILLS = load_skills()
QUALITIES = load_qualities()
LIFESTYLES = load_lifestyles()
CYBERWARE_ENTRIES = load_cyberware_entries()
CYBERWARE = {e.name: e for e in CYBERWARE_ENTRIES}


def _street_sam(
    gear: tuple[str, ...] = ("Armor Jacket", "Helmet"),
    cyberware: tuple[CyberwarePurchaseRequest, ...] = (
        CyberwarePurchaseRequest(item_id=CYBERWARE["Dermal Plating"].id, rating=2),
    ),
    attribute_points: dict[str, int] | None = None,
    unworn_armor: tuple[str, ...] = (),
) -> CharacterSave:
    """A Human with BOD 4 and STR 3 (Attributes A buys them), Resources A for the gear."""
    return create_character_save(
        metatype_name="Human",
        heritage_letter="D",
        attributes_letter="A",
        attribute_points=attribute_points if attribute_points is not None else {"BOD": 3, "STR": 2},
        skills_letter="E",
        skill_points={},
        group_points={},
        quality_picks=(),
        contacts=(),
        resources_letter="A",
        gear_names=gear,
        lifestyle_tier_name="Street",
        lifestyle_months=1,
        cyberware_purchases=cyberware,
        unworn_armor=unworn_armor,
    )


def _build(save: CharacterSave) -> Character:
    return build_character(
        save,
        metatypes=METATYPES,
        priorities=PRIORITIES,
        skills=SKILLS,
        qualities=QUALITIES,
        lifestyles=LIFESTYLES,
        cyberware=CYBERWARE_ENTRIES,
    )


def test_the_acceptance_street_sam_hand_computed() -> None:
    """Armor Jacket 12 + Helmet +2 (within STR 3) + Dermal Plating 2 = Armor 16.
    Damage Resistance = BOD 4 + 16 = 20. Overflow = BOD 4. Wound modifiers: -1 per 3, none
    ignored."""
    character = _build(_street_sam())
    breakdown = armor_breakdown(character)
    assert breakdown.body_armor is not None and breakdown.body_armor.name == "Armor Jacket"
    assert (breakdown.accessory_total, breakdown.accessory_bonus) == (2, 2)
    assert breakdown.improvements == 2
    assert breakdown.encumbrance_penalty == 0
    assert armor(character) == 16
    assert damage_resistance(character) == 20
    assert overflow(character) == 4
    rule = wound_modifier_rule(character)
    assert (rule.boxes_per_modifier, rule.physical_boxes_ignored, rule.stun_boxes_ignored) == (
        3,
        0,
        0,
    )


def test_only_the_highest_body_armor_counts() -> None:
    """p. 169: Full Deck's Actioneer Business Clothes (8) under an Urban Explorer jumpsuit (9)
    count as 9. Here: Armor Vest 9 and Armor Jacket 12 worn together count as 12."""
    character = _build(_street_sam(gear=("Armor Vest", "Armor Jacket"), cyberware=()))
    assert armor(character) == 12


def test_accessories_are_capped_at_strength_and_the_excess_encumbers() -> None:
    """p. 169: Caster (STR 2) with a riot shield (+6) is 4 over -- -2 Agility and Reaction. Here
    STR 3 with a Riot Shield +6 and a Helmet +2: 8 total, 3 counts, 5 over, -2."""
    character = _build(_street_sam(gear=("Riot Shield", "Helmet"), cyberware=()))
    breakdown = armor_breakdown(character)
    assert breakdown.body_armor is None
    assert (breakdown.accessory_total, breakdown.accessory_bonus) == (8, 3)
    assert breakdown.encumbrance_penalty == 2
    assert armor(character) == 3


def test_unworn_armor_does_not_count() -> None:
    character = _build(_street_sam(unworn_armor=("Armor Jacket",)))
    assert armor_breakdown(character).body_armor is None
    assert armor(character) == 4  # Helmet +2, Dermal Plating 2


def test_bone_lacing_adds_armor_and_damage_resistance_dice() -> None:
    save = _street_sam(
        gear=(),
        cyberware=(CyberwarePurchaseRequest(item_id=CYBERWARE["Bone Lacing (Titanium)"].id),),
    )
    character = _build(save)
    assert armor(character) == 3
    assert damage_resistance(character) == 4 + 3 + 3


def test_two_group0_armor_sources_keep_only_the_highest() -> None:
    """Dermal Plating's `<armor group="0">` becomes the dedup group "group0" -- the same group the
    Troll's racial dermal armor carries, so the two never stack (WP113/WP129 rely on this)."""
    character = _build(_street_sam(gear=()))
    character.improvements.add(
        Improvement(
            improvement_type=ImprovementType.ARMOR,
            target="",
            value=1,
            source_type=ImprovementSource.METATYPE,
            source_id="troll",
            unique_name="group0",
        )
    )
    assert armor(character) == 2


def test_the_new_improvement_types_feed_their_numbers() -> None:
    character = _build(_street_sam(gear=(), cyberware=()))
    for improvement_type, value in (
        (ImprovementType.CM_OVERFLOW, 2),
        (ImprovementType.CM_THRESHOLD, -1),
        (ImprovementType.CM_THRESHOLD_OFFSET, 1),
        (ImprovementType.CM_SHARED_THRESHOLD_OFFSET, 2),
        (ImprovementType.DAMAGE_RESISTANCE, 1),
    ):
        character.improvements.add(
            Improvement(
                improvement_type=improvement_type,
                target="",
                value=value,
                source_type=ImprovementSource.QUALITY,
                source_id=improvement_type.name,
            )
        )
    assert overflow(character) == 4 + 2
    rule = wound_modifier_rule(character)
    assert (rule.boxes_per_modifier, rule.physical_boxes_ignored, rule.stun_boxes_ignored) == (
        2,
        3,
        3,
    )
    assert damage_resistance(character) == 4 + 0 + 1


def test_overflow_uses_augmented_body() -> None:
    character = _build(_street_sam(gear=(), cyberware=()))
    character.improvements.add(
        Improvement(
            improvement_type=ImprovementType.ATTRIBUTE,
            target="BOD",
            value=1,
            source_type=ImprovementSource.CYBERWARE,
            source_id="x",
        )
    )
    assert overflow(character) == 5


def test_unworn_armor_round_trips_and_defaults_to_empty() -> None:
    save = _street_sam(unworn_armor=("Helmet", "Armor Jacket"))
    assert from_json(to_json(save)) == save
    assert json.loads(to_json(save))["unworn_armor"] == ["Armor Jacket", "Helmet"]
    data = json.loads(to_json(_street_sam()))
    del data["unworn_armor"]
    assert from_json(json.dumps(data)).unworn_armor == ()
    assert _build(save).unworn_armor == frozenset({"Helmet", "Armor Jacket"})


def test_a_character_without_resources_has_no_armor() -> None:
    character = replace(_build(_street_sam(gear=(), cyberware=())), resources_selection=None)
    assert armor(character) == 0
