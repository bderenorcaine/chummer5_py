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

from chummer5.data.bioware import load_bioware
from chummer5.data.cyberware import load_cyberware
from chummer5.data.lifestyle import load_lifestyles
from chummer5.data.metatypes import load_metatypes
from chummer5.data.powers import load_powers
from chummer5.data.priorities import load_priorities
from chummer5.data.qualities import load_qualities
from chummer5.data.skills import load_skills
from chummer5.data.spells import load_spells
from chummer5.data.traditions import load_traditions
from chummer5.engine.build_method import PRIORITY_BUILD_METHOD, SUM_TO_TEN_BUILD_METHOD
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
BIOWARE = load_bioware()


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


def test_json_round_trip_preserves_bioware_item_ids() -> None:
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
        bioware_item_ids=("bio-cats-eyes", "bio-cats-eyes"),
    )
    assert from_json(to_json(save)) == save
    assert json.loads(to_json(save))["bioware_item_ids"] == ["bio-cats-eyes", "bio-cats-eyes"]


def test_build_character_applies_bioware_selection() -> None:
    """WP45 mirrors WP33's own cyberware test: `build_character` validates `bioware_item_ids`
    against `create_bioware_selection`, using whatever nuyen cyberware left over as the shared
    budget bioware draws from, and applies the resulting Essence Improvement.
    """
    cats_eyes = next(b for b in BIOWARE if b.name == "Cat's Eyes")
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
        bioware_item_ids=(cats_eyes.id,),
    )
    character = build_character(
        save,
        metatypes=METATYPES,
        priorities=PRIORITIES,
        skills=SKILLS,
        qualities=QUALITIES,
        lifestyles=LIFESTYLES,
        bioware=BIOWARE,
    )
    assert character.bioware_selection is not None
    assert cats_eyes.id in {b.id for b in character.bioware_selection.items}
    assert essence(character) == Decimal(6) - cats_eyes.essence_cost


def test_build_character_shares_the_essence_pool_between_cyberware_and_bioware() -> None:
    """The cross-module composition this WP's whole design hinges on: cyberware is resolved first
    (unaware of bioware), bioware second (aware of cyberware's own essence_spent) -- their combined
    Essence cost must reduce the same one pool, not two independently-tracked ones.
    """
    datajack = next(c for c in CYBERWARE if c.name == "Datajack")
    cats_eyes = next(b for b in BIOWARE if b.name == "Cat's Eyes")
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
        bioware_item_ids=(cats_eyes.id,),
    )
    character = build_character(
        save,
        metatypes=METATYPES,
        priorities=PRIORITIES,
        skills=SKILLS,
        qualities=QUALITIES,
        lifestyles=LIFESTYLES,
        cyberware=CYBERWARE,
        bioware=BIOWARE,
    )
    assert essence(character) == Decimal(6) - datajack.essence_cost - cats_eyes.essence_cost
    assert character.resources_selection is not None
    assert character.resources_selection.bioware_cost == cats_eyes.cost
    assert character.resources_selection.cyberware_cost == datajack.cost


def test_build_character_rejects_bioware_exceeding_the_shared_nuyen_budget() -> None:
    """Bioware shares its nuyen budget with gear/Lifestyle/cyberware -- mirrors WP33's own
    cyberware over-budget test.
    """
    enhanced_articulation = next(b for b in BIOWARE if b.name == "Enhanced Articulation")
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
        bioware_item_ids=(enhanced_articulation.id,),
    )
    with pytest.raises(ValueError, match="nuyen budget"):
        build_character(
            save,
            metatypes=METATYPES,
            priorities=PRIORITIES,
            skills=SKILLS,
            qualities=QUALITIES,
            lifestyles=LIFESTYLES,
            bioware=BIOWARE,
        )


def test_json_round_trip_preserves_karma_converted() -> None:
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
        karma_converted=7,
    )
    assert from_json(to_json(save)) == save
    assert json.loads(to_json(save))["karma_converted"] == 7


def test_from_json_defaults_karma_converted_for_a_pre_wp43_save() -> None:
    """A save written before WP43 has no `karma_converted` key at all -- still the same
    `FORMAT_VERSION` (a purely additive shape change, the same precedent every prior WP28/WP33
    field addition already established), so it must load with the field defaulting to 0.
    """
    save = _sample_save()
    data = json.loads(to_json(save))
    del data["karma_converted"]
    assert from_json(json.dumps(data)).karma_converted == 0


def test_build_character_applies_karma_converted_to_the_nuyen_budget() -> None:
    """WP43: `build_character` folds `karma_converted` into `create_resources_selection`'s budget,
    letting a gear purchase that would exceed the base Resources budget succeed once Karma tops it
    up -- and the resulting `resources_selection.karma_converted` carries the committed amount.
    """
    budget = PRIORITIES.resources["E"].nuyen
    over_budget_item_count = (budget // 100) + 1  # Meta Link costs 100
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
        resources_letter="E",
        gear_names=("Meta Link",) * over_budget_item_count,
        lifestyle_tier_name="Street",
        lifestyle_months=1,
        karma_converted=10,
    )
    character = build_character(
        save,
        metatypes=METATYPES,
        priorities=PRIORITIES,
        skills=SKILLS,
        qualities=QUALITIES,
        lifestyles=LIFESTYLES,
    )
    assert character.resources_selection is not None
    assert character.resources_selection.karma_converted == 10
    assert character.resources_selection.nuyen_budget == budget


def test_build_character_rejects_karma_converted_above_the_cap() -> None:
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
        resources_letter="E",
        gear_names=(),
        lifestyle_tier_name="Street",
        lifestyle_months=1,
        karma_converted=11,
    )
    with pytest.raises(ValueError, match="between 0 and 10"):
        build_character(
            save,
            metatypes=METATYPES,
            priorities=PRIORITIES,
            skills=SKILLS,
            qualities=QUALITIES,
            lifestyles=LIFESTYLES,
        )


def test_default_build_method_is_priority() -> None:
    assert _sample_save().build_method == PRIORITY_BUILD_METHOD


def test_json_round_trip_preserves_build_method() -> None:
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
        build_method=SUM_TO_TEN_BUILD_METHOD,
    )
    assert from_json(to_json(save)) == save
    assert json.loads(to_json(save))["build_method"] == SUM_TO_TEN_BUILD_METHOD


def test_from_json_defaults_build_method_for_a_pre_wp44_save() -> None:
    """A save written before WP44 has no `build_method` key at all -- still the same
    `FORMAT_VERSION` (a purely additive shape change, the same precedent every prior WP28/WP33/WP43
    field addition already established), so it must load defaulting to Priority -- every save this
    project's own web layer produced before WP44 was Priority-built.
    """
    save = _sample_save()
    data = json.loads(to_json(save))
    del data["build_method"]
    assert from_json(json.dumps(data)).build_method == PRIORITY_BUILD_METHOD


def test_build_character_does_not_validate_build_method_against_the_letters() -> None:
    """WP44: `build_method` is carried through as plain descriptive state, not re-validated --
    neither `create_character` nor any other `create_*` function here has ever checked the letter
    *assignment*'s shape (only `chummer5.web.app.submit_priorities` does, at submission time; see
    `chummer5.io.save_format`'s own module docstring). A save claiming `SumtoTen` with letters that
    wouldn't actually satisfy Sum-to-Ten's sum-to-10 rule (or even Priority's bijection) still
    builds successfully -- proving there is genuinely nothing downstream for this field to feed.
    """
    save = create_character_save(
        metatype_name="Human",
        heritage_letter="D",
        attributes_letter="D",  # repeats Heritage -- illegal under Priority's own bijection
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
        build_method=SUM_TO_TEN_BUILD_METHOD,
    )
    character = build_character(
        save,
        metatypes=METATYPES,
        priorities=PRIORITIES,
        skills=SKILLS,
        qualities=QUALITIES,
        lifestyles=LIFESTYLES,
    )
    assert character.attributes_letter == "D"


# -- WP46: bound_spirit_picks --------------------------------------------------------------------

HERMETIC_ID = next(t.id for t in TRADITIONS if t.name == "Hermetic")


def _magician_save(bound_spirit_picks: tuple[tuple[str, int], ...] = ()) -> CharacterSave:
    # Talent letter C's Magician option (Magic 3, no free-skill grant -- see test_magic.py's own
    # "letter C grants no free skill" precedent) keeps this fixture minimal.
    return create_character_save(
        metatype_name="Human",
        heritage_letter="D",
        attributes_letter="A",
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
        talent_letter="C",
        talent_codename="Magician",
        tradition_id=HERMETIC_ID,
        bound_spirit_picks=bound_spirit_picks,
    )


def test_json_round_trip_preserves_bound_spirit_picks() -> None:
    save = _magician_save((("Spirit of Fire", 3), ("Spirit of Air", 2)))
    assert from_json(to_json(save)) == save
    assert json.loads(to_json(save))["bound_spirit_picks"] == [
        {"spirit_type": "Spirit of Fire", "services": 3},
        {"spirit_type": "Spirit of Air", "services": 2},
    ]


def test_from_json_defaults_bound_spirit_picks_for_a_pre_wp46_save() -> None:
    save = _sample_save()
    data = json.loads(to_json(save))
    assert "bound_spirit_picks" not in data or data["bound_spirit_picks"] == []
    assert from_json(to_json(save)).bound_spirit_picks == ()


def test_build_character_applies_bound_spirit_selection() -> None:
    save = _magician_save((("Spirit of Fire", 3),))
    character = build_character(
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
    assert character.bound_spirit_selection is not None
    assert character.bound_spirit_selection.karma_cost == 3
    (spirit,) = character.bound_spirit_selection.spirits
    assert spirit.spirit_type == "Spirit of Fire"
    assert spirit.services == 3
    # Force is never persisted -- always the live Magic rating at load time (see module docstring).
    assert spirit.force == character.attribute_value("MAG") == 3


def test_build_character_rejects_bound_spirits_exceeding_the_provisional_karma_budget() -> None:
    # STARTING_KARMA is 25 -- 26 services on one spirit alone already exceeds it, with nothing else
    # spent from qualities/contacts in this fixture.
    save = _magician_save((("Spirit of Fire", 26),))
    with pytest.raises(ValueError, match="exceeding the available budget"):
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


def test_build_character_rejects_a_spirit_type_not_offered_by_the_traditon() -> None:
    save = _magician_save((("Spirit of Beasts", 1),))  # Hermetic never offers Beasts
    with pytest.raises(ValueError, match="not an offered spirit type"):
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
