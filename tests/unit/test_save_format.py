"""Synthetic tests for `chummer5.io.save_format`'s JSON (de)serialization, proving the wire format
round-trips exactly before any real fixture data touches it -- same "prove the mechanism in
isolation first" pattern WP5 used for the Improvement engine and WP7 used for the dice-pool
formula. The engine-reconstruction half (`build_character`) is covered against a real fixture in
`tests/integration/test_save_format.py`, mirroring the unit/integration split every prior WP used.
"""

from __future__ import annotations

import json
from decimal import Decimal

import pytest

from chummer5.data.cyberware import load_cyberware
from chummer5.data.lifestyle import load_lifestyles
from chummer5.data.metatypes import load_metatypes
from chummer5.data.powers import load_powers
from chummer5.data.priorities import load_priorities
from chummer5.data.qualities import load_qualities
from chummer5.data.skills import load_skills
from chummer5.data.spells import load_spells
from chummer5.data.traditions import load_traditions
from chummer5.engine.derived import essence
from chummer5.engine.resources import Contact
from chummer5.io.save_format import (
    FORMAT_VERSION,
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
TRADITIONS = load_traditions()
SPELLS = load_spells()
POWERS = load_powers()
CYBERWARE = load_cyberware()


def _sample_save() -> CharacterSave:
    return create_character_save(
        metatype_name="Human",
        heritage_letter="D",
        attributes_letter="A",
        attribute_points={"BOD": 3, "AGI": 2, "EDG": 1},
        skills_letter="C",
        skill_points={"skill-hacking": 2},
        group_points={"Firearms": 4},
        quality_ids=("qual-catlike",),
        contacts=(
            Contact(name="Fixer", connection=3, loyalty=3),
            Contact(name="GM Plot", connection=1, loyalty=1, free=True),
        ),
        resources_letter="B",
        gear_names=("Meta Link", "Combat Knife"),
        lifestyle_tier_name="Low",
        lifestyle_months=1,
    )


def test_json_round_trip_preserves_every_field() -> None:
    save = _sample_save()
    assert from_json(to_json(save)) == save


def test_json_round_trip_empty_selections() -> None:
    save = create_character_save(
        metatype_name="Elf",
        heritage_letter="A",
        attributes_letter="D",
        attribute_points={},
        skills_letter="E",
        skill_points={},
        group_points={},
        quality_ids=(),
        contacts=(),
        resources_letter="C",
        gear_names=(),
        lifestyle_tier_name="Street",
        lifestyle_months=1,
    )
    assert from_json(to_json(save)) == save


def test_to_json_produces_the_documented_wire_shape() -> None:
    """Spot-checks the actual JSON text, not just round-trip self-consistency -- a round trip alone
    wouldn't catch e.g. an accidentally-renamed key, since `from_json` would just fail loudly on
    that (still fine), but this pins the documented shape in a way a future reader can see without
    executing anything.
    """
    save = _sample_save()
    data = json.loads(to_json(save))
    assert data["format_version"] == FORMAT_VERSION
    assert data["metatype_name"] == "Human"
    assert data["attribute_points"] == {"BOD": 3, "AGI": 2, "EDG": 1}
    assert data["contacts"] == [
        {"name": "Fixer", "connection": 3, "loyalty": 3, "free": False},
        {"name": "GM Plot", "connection": 1, "loyalty": 1, "free": True},
    ]
    assert data["gear_names"] == ["Meta Link", "Combat Knife"]
    assert data["lifestyle_tier_name"] == "Low"
    assert data["lifestyle_months"] == 1


def test_from_json_rejects_unknown_format_version() -> None:
    data = json.loads(to_json(_sample_save()))
    data["format_version"] = 99
    with pytest.raises(ValueError, match="unsupported save format version"):
        from_json(json.dumps(data))


def test_from_json_rejects_missing_format_version() -> None:
    data = json.loads(to_json(_sample_save()))
    del data["format_version"]
    with pytest.raises(ValueError, match="unsupported save format version"):
        from_json(json.dumps(data))


def test_build_character_derives_metatype_qualities_not_from_the_save_file() -> None:
    """WP23: `metatype_qualities` is never a `CharacterSave` field (see this module's own
    "selections, not derived values" docstring) -- `build_character` re-derives it purely from
    `metatype_name` on every load, so an Elf save's `metatype_qualities` comes back populated with
    Low-Light Vision even though nothing in the save's own JSON says so.
    """
    save = create_character_save(
        metatype_name="Elf",
        heritage_letter="A",
        attributes_letter="D",
        attribute_points={},
        skills_letter="E",
        skill_points={},
        group_points={},
        quality_ids=(),
        contacts=(),
        resources_letter="C",
        gear_names=(),
        lifestyle_tier_name="Street",
        lifestyle_months=1,
    )
    # Round-tripped through JSON too, so this also proves the derivation survives a real save/load,
    # not just a freshly-built save object.
    reloaded = from_json(to_json(save))
    character = build_character(
        reloaded,
        metatypes=METATYPES,
        priorities=PRIORITIES,
        skills=SKILLS,
        qualities=QUALITIES,
        lifestyles=LIFESTYLES,
    )
    assert [q.name for q in character.metatype_qualities] == ["Low-Light Vision"]
    assert character.improvements.improvements == ()  # NO_EFFECT -- no Improvement to apply


def test_json_round_trip_preserves_magic_attribute_points() -> None:
    save = create_character_save(
        metatype_name="Human",
        heritage_letter="A",
        attributes_letter="B",
        attribute_points={"EDG": 1},
        skills_letter="C",
        skill_points={},
        group_points={},
        quality_ids=(),
        contacts=(),
        resources_letter="D",
        gear_names=(),
        lifestyle_tier_name="Street",
        lifestyle_months=1,
        talent_letter="D",
        talent_codename="Adept",
        magic_attribute_points=3,
    )
    assert from_json(to_json(save)) == save
    assert json.loads(to_json(save))["magic_attribute_points"] == 3


def test_build_character_applies_magic_attribute_points_to_the_finished_mag_rating() -> None:
    """Post-WP29 correction: Human at Heritage A has a 9-point special-attribute-points budget
    (hand-checked against `priorities.xml`); Talent letter D's Adept option grants Magic 2 with a
    metatype maximum of 6, leaving 4 points of headroom -- spending 3 of them (plus 1 on EDG, well
    within the shared 9-point budget) should raise the finished MAG rating from 2 to 5, and Power
    Points (Adept, 1:1 with the *finished* Magic rating) should track that, not the raw 2.
    """
    save = create_character_save(
        metatype_name="Human",
        heritage_letter="A",
        attributes_letter="B",
        attribute_points={"EDG": 1},
        skills_letter="C",
        skill_points={},
        group_points={},
        quality_ids=(),
        contacts=(),
        resources_letter="D",
        gear_names=(),
        lifestyle_tier_name="Street",
        lifestyle_months=1,
        talent_letter="D",
        talent_codename="Adept",
        magic_attribute_points=3,
    )
    character = build_character(
        from_json(to_json(save)),
        metatypes=METATYPES,
        priorities=PRIORITIES,
        skills=SKILLS,
        qualities=QUALITIES,
        lifestyles=LIFESTYLES,
        traditions=TRADITIONS,
        spells=SPELLS,
        powers=POWERS,
    )
    assert character.magic_rating == 2
    assert character.magic_attribute_points == 3
    assert character.attribute_value("MAG") == 5
    assert character.power_points == 5


def test_build_character_rejects_magic_attribute_points_exceeding_the_shared_budget() -> None:
    save = create_character_save(
        metatype_name="Human",
        heritage_letter="E",  # Human's Heritage-E special-attribute-points budget is only 1
        attributes_letter="B",
        attribute_points={},
        skills_letter="C",
        skill_points={},
        group_points={},
        quality_ids=(),
        contacts=(),
        resources_letter="D",
        gear_names=(),
        lifestyle_tier_name="Street",
        lifestyle_months=1,
        talent_letter="D",
        talent_codename="Adept",
        magic_attribute_points=2,
    )
    with pytest.raises(ValueError, match="special-attribute-points budget"):
        build_character(
            save,
            metatypes=METATYPES,
            priorities=PRIORITIES,
            skills=SKILLS,
            qualities=QUALITIES,
            lifestyles=LIFESTYLES,
            traditions=TRADITIONS,
            spells=SPELLS,
            powers=POWERS,
        )


def test_json_round_trip_preserves_cyberware_item_ids() -> None:
    save = create_character_save(
        metatype_name="Human",
        heritage_letter="D",
        attributes_letter="A",
        attribute_points={},
        skills_letter="C",
        skill_points={},
        group_points={},
        quality_ids=(),
        contacts=(),
        resources_letter="B",
        gear_names=(),
        lifestyle_tier_name="Street",
        lifestyle_months=1,
        cyberware_item_ids=("cyber-datajack", "cyber-datajack"),
    )
    assert from_json(to_json(save)) == save
    assert json.loads(to_json(save))["cyberware_item_ids"] == ["cyber-datajack", "cyber-datajack"]


def test_build_character_applies_cyberware_selection() -> None:
    """WP33: `build_character` validates `cyberware_item_ids` against WP32's
    `create_cyberware_selection`, using the Resources-priority letter's nuyen remaining *after*
    gear/Lifestyle as the shared budget cyberware draws from (see `chummer5.engine.cyberware`'s own
    docstring) -- and applies the resulting Essence Improvement to the built `Character`.
    """
    datajack = next(c for c in CYBERWARE if c.name == "Datajack")
    save = create_character_save(
        metatype_name="Human",
        heritage_letter="D",
        attributes_letter="A",
        attribute_points={},
        skills_letter="C",
        skill_points={},
        group_points={},
        quality_ids=(),
        contacts=(),
        resources_letter="B",
        gear_names=(),
        lifestyle_tier_name="Street",
        lifestyle_months=1,
        cyberware_item_ids=(datajack.id,),
    )
    character = build_character(
        save,
        metatypes=METATYPES,
        priorities=PRIORITIES,
        skills=SKILLS,
        qualities=QUALITIES,
        lifestyles=LIFESTYLES,
        cyberware=CYBERWARE,
    )
    assert character.cyberware_selection is not None
    assert datajack.id in {c.id for c in character.cyberware_selection.items}
    assert essence(character) == Decimal(6) - datajack.essence_cost


def test_build_character_rejects_cyberware_exceeding_the_shared_nuyen_budget() -> None:
    """Cyberware shares its nuyen budget with gear/Lifestyle -- a Resources letter whose remaining
    budget (after Lifestyle) can't cover an expensive item's cost must reject the build, mirroring
    `chummer5.engine.cyberware.create_cyberware_selection`'s own over-budget check.
    """
    synthetic_full_arm = next(c for c in CYBERWARE if c.name == "Synthetic Full Arm")
    save = create_character_save(
        metatype_name="Human",
        heritage_letter="D",
        attributes_letter="A",
        attribute_points={},
        skills_letter="C",
        skill_points={},
        group_points={},
        quality_ids=(),
        contacts=(),
        resources_letter="E",  # smallest nuyen budget
        gear_names=(),
        lifestyle_tier_name="Street",
        lifestyle_months=1,
        cyberware_item_ids=(synthetic_full_arm.id,),
    )
    with pytest.raises(ValueError, match="nuyen budget"):
        build_character(
            save,
            metatypes=METATYPES,
            priorities=PRIORITIES,
            skills=SKILLS,
            qualities=QUALITIES,
            lifestyles=LIFESTYLES,
            cyberware=CYBERWARE,
        )
