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
from chummer5.data.cyberware_subsystems import load_cyberware_entries
from chummer5.data.foci import load_foci
from chummer5.data.lifestyle import load_lifestyles
from chummer5.data.mentors import load_mentors
from chummer5.data.metatypes import load_metatypes
from chummer5.data.powers import load_powers
from chummer5.data.priorities import load_priorities
from chummer5.data.qualities import load_qualities
from chummer5.data.skills import load_skills
from chummer5.data.spells import load_spells
from chummer5.data.traditions import load_traditions
from chummer5.data.vehicles import load_vehicles
from chummer5.engine.bioware import BiowarePurchaseRequest
from chummer5.engine.build_method import PRIORITY_BUILD_METHOD, SUM_TO_TEN_BUILD_METHOD
from chummer5.engine.cyberware_subsystems import CyberwarePurchaseRequest
from chummer5.engine.derived import essence, mental_limit
from chummer5.engine.improvements import ImprovementType
from chummer5.engine.qualities import QualityPickRequest
from chummer5.engine.resources import Contact
from chummer5.engine.vehicles import VEHICLE_CATALOG
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
CYBERWARE = load_cyberware_entries()
BIOWARE = load_bioware()
FOCI = load_foci()
MENTORS = load_mentors()


def _sample_save() -> CharacterSave:
    return create_character_save(
        metatype_name="Human",
        heritage_letter="D",
        attributes_letter="A",
        attribute_points={"BOD": 3, "AGI": 2, "EDG": 1},
        skills_letter="C",
        skill_points={"skill-hacking": 2},
        group_points={"Firearms": 4},
        specializations={"skill-hacking": "Networks"},
        quality_picks=("qual-catlike",),
        contacts=(
            Contact(name="Fixer", connection=3, loyalty=3),
            Contact(name="GM Plot", connection=1, loyalty=1, free=True),
        ),
        resources_letter="B",
        gear_names=("Meta Link", "Combat Knife"),
        rating_gear_picks=(("Fake SIN", 4), ("Glasses", 2)),
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
        quality_picks=(),
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
    assert data["rating_gear_picks"] == [
        {"name": "Fake SIN", "rating": 4},
        {"name": "Glasses", "rating": 2},
    ]
    assert data["lifestyle_tier_name"] == "Low"
    assert data["lifestyle_months"] == 1
    assert data["specializations"] == {"skill-hacking": "Networks"}


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
        quality_picks=(),
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
        quality_picks=(),
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
        quality_picks=(),
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
        quality_picks=(),
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


def test_json_round_trip_preserves_cyberware_purchases() -> None:
    save = create_character_save(
        metatype_name="Human",
        heritage_letter="D",
        attributes_letter="A",
        attribute_points={},
        skills_letter="C",
        skill_points={},
        group_points={},
        quality_picks=(),
        contacts=(),
        resources_letter="B",
        gear_names=(),
        lifestyle_tier_name="Street",
        lifestyle_months=1,
        cyberware_purchases=(
            CyberwarePurchaseRequest(item_id="cyber-datajack"),
            CyberwarePurchaseRequest(item_id="cyber-datajack"),
            CyberwarePurchaseRequest(
                item_id="cyber-cybereyes",
                rating=3,
                plugins=(CyberwarePurchaseRequest(item_id="cyber-vision-enh", rating=2),),
            ),
        ),
    )
    assert from_json(to_json(save)) == save
    assert json.loads(to_json(save))["cyberware_purchases"] == [
        {"item_id": "cyber-datajack", "rating": 1, "plugins": []},
        {"item_id": "cyber-datajack", "rating": 1, "plugins": []},
        {
            "item_id": "cyber-cybereyes",
            "rating": 3,
            "plugins": [{"item_id": "cyber-vision-enh", "rating": 2, "plugins": []}],
        },
    ]


def test_a_pre_wp41_save_falls_back_to_the_flat_cyberware_item_ids_key() -> None:
    """WP41's one non-default backward-compatibility path (see `chummer5.io.save_format`'s own
    docstring): a save written before this WP has `cyberware_item_ids`, not `cyberware_purchases`.
    Each id maps to a zero-plugin, rating-1 request -- exact rather than approximate, since every
    row WP31's flat catalog offered is unrated.
    """
    save = create_character_save(
        metatype_name="Human",
        heritage_letter="D",
        attributes_letter="A",
        attribute_points={},
        skills_letter="C",
        skill_points={},
        group_points={},
        quality_picks=(),
        contacts=(),
        resources_letter="B",
        gear_names=(),
        lifestyle_tier_name="Street",
        lifestyle_months=1,
    )
    legacy_shaped = json.loads(to_json(save))
    del legacy_shaped["cyberware_purchases"]
    legacy_shaped["cyberware_item_ids"] = ["cyber-datajack", "cyber-datajack"]

    reloaded = from_json(json.dumps(legacy_shaped))
    assert reloaded.cyberware_purchases == (
        CyberwarePurchaseRequest(item_id="cyber-datajack"),
        CyberwarePurchaseRequest(item_id="cyber-datajack"),
    )


def test_build_character_applies_cyberware_selection() -> None:
    """WP33: `build_character` validates `cyberware_purchases` against WP38's
    `create_cyberware_tree_selection` (WP41), using the Resources-priority letter's nuyen remaining
    *after* gear/Lifestyle as the shared budget cyberware draws from (see
    `chummer5.engine.cyberware_subsystems`'s own
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
        quality_picks=(),
        contacts=(),
        resources_letter="B",
        gear_names=(),
        lifestyle_tier_name="Street",
        lifestyle_months=1,
        cyberware_purchases=(CyberwarePurchaseRequest(item_id=datajack.id),),
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
    assert datajack.id in {n.item.id for n in character.cyberware_selection.walk()}
    assert essence(character) == Decimal(6) - datajack.essence_cost.resolve(rating=1)


def test_build_character_rebuilds_a_nested_cyberware_purchase_tree() -> None:
    """WP41: a save carries the *tree*, so a cybereye's plugins survive save/load instead of being
    lost the way WP33's flat id list lost them. Numbers are p. 454's eyeware table: Rating 2
    cybereyes cost 6,000 nuyen / 0.3 Essence with Capacity 8, and a Rating 2 `Vision Enhancement`
    installed in it costs 8,000 nuyen and Capacity 2 -- **zero** Essence, per the dual-costing rule.
    """
    cybereyes = next(c for c in CYBERWARE if c.name == "Cybereyes Basic System")
    vision = next(c for c in CYBERWARE if c.name == "Vision Enhancement")
    save = create_character_save(
        metatype_name="Human",
        heritage_letter="D",
        attributes_letter="A",
        attribute_points={},
        skills_letter="C",
        skill_points={},
        group_points={},
        quality_picks=(),
        contacts=(),
        resources_letter="A",
        gear_names=(),
        lifestyle_tier_name="Street",
        lifestyle_months=1,
        cyberware_purchases=(
            CyberwarePurchaseRequest(
                item_id=cybereyes.id,
                rating=2,
                plugins=(CyberwarePurchaseRequest(item_id=vision.id, rating=2),),
            ),
        ),
    )
    character = build_character(
        from_json(to_json(save)),  # through the wire format, not just the in-memory object
        metatypes=METATYPES,
        priorities=PRIORITIES,
        skills=SKILLS,
        qualities=QUALITIES,
        lifestyles=LIFESTYLES,
        cyberware=CYBERWARE,
    )
    selection = character.cyberware_selection
    assert selection is not None
    (purchase,) = selection.purchases
    assert purchase.rating == 2
    assert purchase.capacity_budget == Decimal(8)
    assert selection.nuyen_spent == 6000 + 8000
    assert selection.essence_spent == Decimal("0.3")
    assert essence(character) == Decimal(6) - Decimal("0.3")
    # `Image Link` is bundled with the basic system and re-attached on load, free.
    assert {p.item.name for p in purchase.plugins} == {"Vision Enhancement", "Image Link"}
    # And the tree survives a second round trip back out to a save.
    assert selection.to_requests() == save.cyberware_purchases


def test_build_character_rejects_cyberware_exceeding_the_shared_nuyen_budget() -> None:
    """Cyberware shares its nuyen budget with gear/Lifestyle -- a Resources letter whose remaining
    budget (after Lifestyle) can't cover an expensive item's cost must reject the build, mirroring
    `chummer5.engine.cyberware_subsystems.create_cyberware_tree_selection`'s own over-budget
    check.
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
        quality_picks=(),
        contacts=(),
        resources_letter="E",  # smallest nuyen budget
        gear_names=(),
        lifestyle_tier_name="Street",
        lifestyle_months=1,
        cyberware_purchases=(CyberwarePurchaseRequest(item_id=synthetic_full_arm.id),),
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


def test_json_round_trip_preserves_bioware_purchases() -> None:
    save = create_character_save(
        metatype_name="Human",
        heritage_letter="D",
        attributes_letter="A",
        attribute_points={},
        skills_letter="C",
        skill_points={},
        group_points={},
        quality_picks=(),
        contacts=(),
        resources_letter="B",
        gear_names=(),
        lifestyle_tier_name="Street",
        lifestyle_months=1,
        bioware_purchases=("bio-cats-eyes", "bio-cats-eyes"),
    )
    assert from_json(to_json(save)) == save
    # WP80: bare ids are accepted as "no player choice" and stored as full requests.
    assert json.loads(to_json(save))["bioware_purchases"] == [
        {"item_id": "bio-cats-eyes", "chosen_skill": None},
        {"item_id": "bio-cats-eyes", "chosen_skill": None},
    ]


def test_json_round_trip_preserves_a_bioware_skill_pick() -> None:
    """WP80: a `Reflex Recorder`'s chosen skill is part of the purchase, so it has to survive the
    round trip -- the save-format half of that WP's acceptance criteria."""
    reflex_recorder = next(b for b in BIOWARE if b.name == "Reflex Recorder")
    save = create_character_save(
        metatype_name="Human",
        heritage_letter="D",
        attributes_letter="A",
        attribute_points={},
        skills_letter="C",
        skill_points={},
        group_points={},
        quality_picks=(),
        contacts=(),
        resources_letter="A",
        gear_names=(),
        lifestyle_tier_name="Street",
        lifestyle_months=1,
        bioware_purchases=(
            BiowarePurchaseRequest(item_id=reflex_recorder.id, chosen_skill="Longarms"),
        ),
    )
    reloaded = from_json(to_json(save))
    assert reloaded == save
    assert reloaded.bioware_purchases[0].chosen_skill == "Longarms"

    character = build_character(
        reloaded,
        metatypes=METATYPES,
        priorities=PRIORITIES,
        skills=SKILLS,
        qualities=QUALITIES,
        lifestyles=LIFESTYLES,
        bioware=BIOWARE,
    )
    assert character.bioware_selection is not None
    assert character.bioware_selection.purchases[0].chosen_skill == "Longarms"
    assert character.improvements.resolve(ImprovementType.SKILL, "Longarms") == 1


def test_a_pre_wp80_save_reads_its_flat_bioware_item_ids() -> None:
    """WP80's backward-compatibility fallback, mirroring WP41's own `cyberware_item_ids` one: a
    save written before this WP has no `bioware_purchases` key at all, and each id becomes a
    request with no pick. Exact for every row except `Reflex Recorder`, whose pick was never
    persisted -- see `chummer5.io.save_format`'s docstring.
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
        quality_picks=(),
        contacts=(),
        resources_letter="B",
        gear_names=(),
        lifestyle_tier_name="Street",
        lifestyle_months=1,
    )
    data = json.loads(to_json(save))
    del data["bioware_purchases"]
    data["bioware_item_ids"] = [cats_eyes.id]
    reloaded = from_json(json.dumps(data))
    assert reloaded.bioware_purchases == (BiowarePurchaseRequest(item_id=cats_eyes.id),)


def test_build_character_applies_bioware_selection() -> None:
    """WP45 mirrors WP33's own cyberware test: `build_character` validates `bioware_purchases`
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
        quality_picks=(),
        contacts=(),
        resources_letter="B",
        gear_names=(),
        lifestyle_tier_name="Street",
        lifestyle_months=1,
        bioware_purchases=(cats_eyes.id,),
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
        quality_picks=(),
        contacts=(),
        resources_letter="B",
        gear_names=(),
        lifestyle_tier_name="Street",
        lifestyle_months=1,
        cyberware_purchases=(CyberwarePurchaseRequest(item_id=datajack.id),),
        bioware_purchases=(cats_eyes.id,),
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
    assert (
        essence(character)
        == Decimal(6) - datajack.essence_cost.resolve(rating=1) - cats_eyes.essence_cost
    )
    assert character.resources_selection is not None
    assert character.resources_selection.bioware_cost == cats_eyes.cost
    assert character.resources_selection.cyberware_cost == datajack.cost.resolve(rating=1)


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
        quality_picks=(),
        contacts=(),
        resources_letter="E",  # smallest nuyen budget
        gear_names=(),
        lifestyle_tier_name="Street",
        lifestyle_months=1,
        bioware_purchases=(enhanced_articulation.id,),
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
        quality_picks=(),
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
        quality_picks=(),
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
        quality_picks=(),
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
        quality_picks=(),
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
        quality_picks=(),
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


def _magician_save(
    bound_spirit_picks: tuple[tuple[str, int | None, int], ...] = (),
    foci_picks: tuple[tuple[str, int], ...] = (),
    resources_letter: str = "C",
    quality_picks: tuple[str, ...] = (),
    mentor_spirit_archetype_id: str | None = None,
    mentor_spirit_general_choice_id: str | None = None,
) -> CharacterSave:
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
        quality_picks=quality_picks,
        contacts=(),
        resources_letter=resources_letter,
        gear_names=(),
        lifestyle_tier_name="Street",
        lifestyle_months=1,
        talent_letter="C",
        talent_codename="Magician",
        tradition_id=HERMETIC_ID,
        bound_spirit_picks=bound_spirit_picks,
        foci_picks=foci_picks,
        mentor_spirit_archetype_id=mentor_spirit_archetype_id,
        mentor_spirit_general_choice_id=mentor_spirit_general_choice_id,
    )


def test_json_round_trip_preserves_bound_spirit_picks() -> None:
    # WP70: a None Force ("default to Magic") round-trips as JSON null.
    save = _magician_save((("Spirit of Fire", None, 3), ("Spirit of Air", None, 2)))
    assert from_json(to_json(save)) == save
    assert json.loads(to_json(save))["bound_spirit_picks"] == [
        {"spirit_type": "Spirit of Fire", "force": None, "services": 3},
        {"spirit_type": "Spirit of Air", "force": None, "services": 2},
    ]


def test_json_round_trip_preserves_an_explicit_bound_spirit_force() -> None:
    # WP70: a player-chosen Force below Magic is persisted as an integer, not re-derived on load.
    save = _magician_save((("Spirit of Fire", 1, 3),))
    assert from_json(to_json(save)) == save
    assert json.loads(to_json(save))["bound_spirit_picks"] == [
        {"spirit_type": "Spirit of Fire", "force": 1, "services": 3},
    ]


def test_from_json_defaults_bound_spirit_picks_for_a_pre_wp46_save() -> None:
    save = _sample_save()
    data = json.loads(to_json(save))
    assert "bound_spirit_picks" not in data or data["bound_spirit_picks"] == []
    assert from_json(to_json(save)).bound_spirit_picks == ()


def test_from_json_defaults_force_to_none_for_a_pre_wp70_save() -> None:
    # WP70: a pre-WP70 save's spirit entries have no "force" key at all -- from_json fills None
    # ("default to Magic"), preserving the old "Force = live Magic rating" behavior on load.
    save = _magician_save((("Spirit of Fire", None, 3),))
    data = json.loads(to_json(save))
    for entry in data["bound_spirit_picks"]:
        del entry["force"]
    reloaded = from_json(json.dumps(data))
    assert reloaded.bound_spirit_picks == (("Spirit of Fire", None, 3),)


def test_build_character_applies_bound_spirit_selection() -> None:
    save = _magician_save((("Spirit of Fire", None, 3),))
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
    # A None Force resolves to the live Magic rating at load time (see module docstring).
    assert spirit.force == character.attribute_value("MAG") == 3


def test_build_character_applies_an_explicit_bound_spirit_force() -> None:
    # WP70: a persisted Force below Magic is honored on load, not re-derived to Magic.
    save = _magician_save((("Spirit of Fire", 1, 3),))
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
    (spirit,) = character.bound_spirit_selection.spirits
    assert spirit.force == 1
    assert character.attribute_value("MAG") == 3


def test_build_character_rejects_bound_spirits_exceeding_the_karma_budget() -> None:
    # STARTING_KARMA is 25 -- 26 services on one spirit alone already exceeds it, with nothing else
    # spent from qualities/contacts in this fixture.
    save = _magician_save((("Spirit of Fire", None, 26),))
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
    save = _magician_save((("Spirit of Beasts", None, 1),))  # Hermetic never offers Beasts
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


# -- WP47: foci_picks -----------------------------------------------------------------------------

ALCHEMICAL_ID = next(f.id for f in FOCI if f.name == "Alchemical Focus")
POWER_FOCUS_ID = next(f.id for f in FOCI if f.name == "Power Focus")


def _build_magician(save: CharacterSave) -> object:
    return build_character(
        save,
        metatypes=METATYPES,
        priorities=PRIORITIES,
        skills=SKILLS,
        qualities=QUALITIES,
        lifestyles=LIFESTYLES,
        traditions=TRADITIONS,
        spells=SPELLS,
        powers=POWERS,
        foci=FOCI,
        mentors=MENTORS,
    )


def test_json_round_trip_preserves_foci_picks() -> None:
    save = _magician_save(foci_picks=((ALCHEMICAL_ID, 2),))
    assert from_json(to_json(save)) == save
    assert json.loads(to_json(save))["foci_picks"] == [{"focus_id": ALCHEMICAL_ID, "force": 2}]


def test_from_json_defaults_foci_picks_for_a_pre_wp47_save() -> None:
    save = _sample_save()
    data = json.loads(to_json(save))
    assert "foci_picks" not in data or data["foci_picks"] == []
    assert from_json(to_json(save)).foci_picks == ()


def test_build_character_applies_foci_selection() -> None:
    save = _magician_save(foci_picks=((ALCHEMICAL_ID, 2),))
    character = _build_magician(save)
    assert character.foci_selection is not None
    assert character.foci_selection.nuyen_cost == 10000
    assert character.foci_selection.karma_cost == 6
    (pick,) = character.foci_selection.picks
    assert pick.focus.name == "Alchemical Focus"
    assert pick.force == 2
    from chummer5.engine.improvements import ImprovementType

    assert character.improvements.resolve(ImprovementType.SKILL, "Alchemy") == 2


def test_build_character_folds_foci_nuyen_cost_into_resources_selection() -> None:
    save = _magician_save(foci_picks=((ALCHEMICAL_ID, 1),))
    character = _build_magician(save)
    assert character.resources_selection is not None
    assert character.resources_selection.foci_cost == 5000
    budget = PRIORITIES.resources["C"].nuyen
    assert character.resources_selection.nuyen_remaining == budget - 5000


def test_build_character_rejects_foci_exceeding_the_shared_nuyen_budget() -> None:
    # Resources priority E's nuyen budget is far smaller than a single Force-2 Alchemical Focus
    # (10,000 nuyen).
    save = _magician_save(foci_picks=((ALCHEMICAL_ID, 2),), resources_letter="E")
    with pytest.raises(ValueError, match="exceeds the nuyen budget"):
        _build_magician(save)


def test_build_character_rejects_foci_exceeding_the_karma_budget() -> None:
    # Talent letter C -> Magic 3, so the chargen Force cap is 6 and the count cap is 3 -- two
    # Power Foci at Force 3 each (total Force 6, count 2, Availability 12 each, all within their own
    # caps) cost 6 Karma/Force x 2 x 3 = 36 Karma, already over STARTING_KARMA (25) with nothing
    # else spent.
    save = _magician_save(foci_picks=((POWER_FOCUS_ID, 3), (POWER_FOCUS_ID, 3)))
    with pytest.raises(ValueError, match="exceeds the Karma budget"):
        _build_magician(save)


def test_build_character_shares_the_karma_pool_between_bound_spirits_and_foci() -> None:
    # 20 Karma on Bound Spirits (Talent letter C -> Magic 3, so 1 spirit at 20 services fits the
    # Charisma/count cap) + a Force-2 Alchemical Focus (6 Karma) = 26 > STARTING_KARMA (25) -- only
    # caught because create_foci_selection's own budget already accounts for Bound Spirits' cost
    # (see chummer5.engine.foci's module docstring's "fixed evaluation order" paragraph).
    save = _magician_save(
        bound_spirit_picks=(("Spirit of Fire", None, 20),), foci_picks=((ALCHEMICAL_ID, 2),)
    )
    with pytest.raises(ValueError, match="exceeds the Karma budget"):
        _build_magician(save)


def test_build_character_allows_an_adept_to_bond_a_focus() -> None:
    # Bonding only requires being Awakened at all (core rulebook p. 317), not specifically a
    # Magician -- see chummer5.engine.foci's module docstring.
    save = create_character_save(
        metatype_name="Human",
        heritage_letter="D",
        attributes_letter="A",
        attribute_points={},
        skills_letter="E",
        skill_points={},
        group_points={},
        quality_picks=(),
        contacts=(),
        resources_letter="C",
        gear_names=(),
        lifestyle_tier_name="Street",
        lifestyle_months=1,
        talent_letter="D",
        talent_codename="Adept",
        foci_picks=((ALCHEMICAL_ID, 1),),
    )
    character = _build_magician(save)
    assert character.foci_selection is not None
    assert character.foci_selection.nuyen_cost == 5000


# -- WP48: mentor_spirit_archetype_id / mentor_spirit_general_choice_id ---------------------------

MENTOR_SPIRIT_ID = next(q.id for q in QUALITIES if q.name == "Mentor Spirit")
CATLIKE_ID = next(q.id for q in QUALITIES if q.name == "Catlike")
DOG_ID = next(m.id for m in MENTORS if m.name == "Dog")
CAT_ARCHETYPE_ID = next(m.id for m in MENTORS if m.name == "Cat")
CAT_SNEAKING_CHOICE_ID = next(
    c.id
    for m in MENTORS
    if m.name == "Cat"
    for c in m.general_options
    if c.name == "+2 dice on Sneaking Tests"
)


def test_json_round_trip_preserves_mentor_spirit_pick() -> None:
    save = _magician_save(
        quality_picks=(MENTOR_SPIRIT_ID,),
        mentor_spirit_archetype_id=CAT_ARCHETYPE_ID,
        mentor_spirit_general_choice_id=CAT_SNEAKING_CHOICE_ID,
    )
    assert from_json(to_json(save)) == save
    data = json.loads(to_json(save))
    assert data["mentor_spirit_archetype_id"] == CAT_ARCHETYPE_ID
    assert data["mentor_spirit_general_choice_id"] == CAT_SNEAKING_CHOICE_ID


def test_from_json_defaults_mentor_spirit_fields_for_a_pre_wp48_save() -> None:
    save = _sample_save()
    data = json.loads(to_json(save))
    assert "mentor_spirit_archetype_id" not in data or data["mentor_spirit_archetype_id"] is None
    loaded = from_json(to_json(save))
    assert loaded.mentor_spirit_archetype_id is None
    assert loaded.mentor_spirit_general_choice_id is None


def test_build_character_applies_mentor_spirit_pick() -> None:
    save = _magician_save(quality_picks=(MENTOR_SPIRIT_ID,), mentor_spirit_archetype_id=DOG_ID)
    character = _build_magician(save)
    assert character.quality_selection is not None
    pick = character.quality_selection.mentor_spirit
    assert pick is not None
    assert pick.archetype.name == "Dog"
    assert pick.gated_choice is pick.archetype.magician_choice
    from chummer5.engine.improvements import ImprovementType

    assert character.improvements.resolve(ImprovementType.SKILL, "Tracking") == 2


def test_build_character_mentor_spirit_karma_shares_the_positive_quality_pool() -> None:
    # Mentor Spirit (5) + Catlike (7) = 12, well under QUALITY_KARMA_LIMIT (25) -- the ordinary
    # positive_karma path, not a separate provisional budget (unlike Bound Spirits/Foci).
    save = _magician_save(
        quality_picks=(MENTOR_SPIRIT_ID, CATLIKE_ID), mentor_spirit_archetype_id=DOG_ID
    )
    character = _build_magician(save)
    assert character.quality_selection is not None
    assert character.quality_selection.positive_karma == 12


def test_build_character_two_option_general_choice_resolves() -> None:
    save = _magician_save(
        quality_picks=(MENTOR_SPIRIT_ID,),
        mentor_spirit_archetype_id=CAT_ARCHETYPE_ID,
        mentor_spirit_general_choice_id=CAT_SNEAKING_CHOICE_ID,
    )
    character = _build_magician(save)
    assert character.quality_selection is not None
    pick = character.quality_selection.mentor_spirit
    assert pick is not None
    assert pick.general_choice.id == CAT_SNEAKING_CHOICE_ID
    from chummer5.engine.improvements import ImprovementType

    assert character.improvements.resolve(ImprovementType.SKILL, "Sneaking") == 2


def test_build_character_rejects_mentor_spirit_without_an_archetype() -> None:
    save = _magician_save(quality_picks=(MENTOR_SPIRIT_ID,))
    with pytest.raises(ValueError, match="requires an archetype"):
        _build_magician(save)


def test_build_character_allows_an_adept_to_pick_a_mentor_spirit() -> None:
    save = create_character_save(
        metatype_name="Human",
        heritage_letter="D",
        attributes_letter="A",
        attribute_points={},
        skills_letter="E",
        skill_points={},
        group_points={},
        quality_picks=(MENTOR_SPIRIT_ID,),
        contacts=(),
        resources_letter="C",
        gear_names=(),
        lifestyle_tier_name="Street",
        lifestyle_months=1,
        talent_letter="D",
        talent_codename="Adept",
        mentor_spirit_archetype_id=DOG_ID,
        # WP122: Dog's Adept slot grants two Improved Sense powers, each naming a sense.
        mentor_spirit_power_targets=("Low-light vision", "Direction Sense"),
    )
    character = _build_magician(save)
    assert character.quality_selection is not None
    pick = character.quality_selection.mentor_spirit
    assert pick is not None
    assert pick.gated_choice is pick.archetype.adept_choice
    assert [p.target for p in pick.free_powers] == ["Low-light vision", "Direction Sense"]


# -- WP49: knowledge_skill_picks / language_skill_picks -------------------------------------------

BILINGUAL_ID = next(q.id for q in QUALITIES if q.name == "Bilingual")


def _mundane_save_with_knowledge(
    knowledge_skill_picks: tuple[tuple[str, str, int], ...] = (),
    language_skill_picks: tuple[tuple[str, int, bool], ...] = (),
    quality_picks: tuple[str, ...] = (),
    attribute_points: dict[str, int] | None = None,
) -> CharacterSave:
    return create_character_save(
        metatype_name="Human",
        heritage_letter="D",
        attributes_letter="A",
        attribute_points=attribute_points or {"INT": 3, "LOG": 2},
        skills_letter="E",
        skill_points={},
        group_points={},
        quality_picks=quality_picks,
        contacts=(),
        resources_letter="C",
        gear_names=(),
        lifestyle_tier_name="Street",
        lifestyle_months=1,
        knowledge_skill_picks=knowledge_skill_picks,
        language_skill_picks=language_skill_picks,
    )


def _build_mundane(save: CharacterSave) -> object:
    return build_character(
        save,
        metatypes=METATYPES,
        priorities=PRIORITIES,
        skills=SKILLS,
        qualities=QUALITIES,
        lifestyles=LIFESTYLES,
    )


def test_json_round_trip_preserves_knowledge_and_language_picks() -> None:
    save = _mundane_save_with_knowledge(
        knowledge_skill_picks=(("Corporations", "Street", 3),),
        language_skill_picks=(("English", 0, True), ("Japanese", 2, False)),
    )
    assert from_json(to_json(save)) == save
    data = json.loads(to_json(save))
    assert data["knowledge_skill_picks"] == [
        {"name": "Corporations", "category": "Street", "rating": 3}
    ]
    assert data["language_skill_picks"] == [
        {"name": "English", "rating": 0, "native": True},
        {"name": "Japanese", "rating": 2, "native": False},
    ]


def test_from_json_defaults_knowledge_picks_for_a_pre_wp49_save() -> None:
    save = _sample_save()
    data = json.loads(to_json(save))
    assert "knowledge_skill_picks" not in data or data["knowledge_skill_picks"] == []
    loaded = from_json(to_json(save))
    assert loaded.knowledge_skill_picks == ()
    assert loaded.language_skill_picks == ()


def test_build_character_applies_knowledge_selection() -> None:
    save = _mundane_save_with_knowledge(
        knowledge_skill_picks=(("Corporations", "Street", 3),),
        language_skill_picks=(("English", 0, True), ("Japanese", 2, False)),
    )
    character = _build_mundane(save)
    assert character.knowledge_selection is not None
    assert character.knowledge_selection.free_points == 14  # (INT 4 + LOG 3) * 2
    assert character.knowledge_selection.points_spent == 5  # native English costs 0
    assert {k.name: k.rating for k in character.knowledge_selection.knowledge_skills} == {
        "Corporations": 3
    }


def test_build_character_pays_knowledge_spend_past_the_free_budget_from_active_points() -> None:
    """WP125, p. 88: a spend past the free pool draws on the Active skill points."""
    save = _mundane_save_with_knowledge(
        knowledge_skill_picks=(("Corporations", "Street", 6),),
        attribute_points={"INT": 0, "LOG": 0},  # (1+1)*2 = 4-point budget
    )
    character = _build_mundane(save)
    assert character.knowledge_selection.active_points_used == 2  # type: ignore[attr-defined]


def test_build_character_rejects_knowledge_spend_exceeding_free_and_active_points() -> None:
    save = _mundane_save_with_knowledge(
        knowledge_skill_picks=tuple((f"K{i}", "Street", 6) for i in range(4)),
        attribute_points={"INT": 0, "LOG": 0},  # 4 free + Skills E's 18 < 24
    )
    with pytest.raises(ValueError, match="exceeds the free budget"):
        _build_mundane(save)


def test_build_character_bilingual_raises_the_native_language_limit() -> None:
    # WP49's real fixture-independent finding: Bilingual was NOT_YET_SUPPORTED before this WP (see
    # spec/rulebooks/learnings.md's WP49 entry) -- this proves its ImprovementType
    # .NATIVE_LANGUAGE_LIMIT bonus is applied *before* create_knowledge_selection reads it.
    save = _mundane_save_with_knowledge(
        quality_picks=(BILINGUAL_ID,),
        language_skill_picks=(("English", 0, True), ("Sperethiel", 0, True)),
    )
    character = _build_mundane(save)
    assert character.knowledge_selection is not None
    assert character.knowledge_selection.native_language_limit == 2
    assert character.knowledge_selection.points_spent == 0


def test_build_character_rejects_a_second_native_language_without_bilingual() -> None:
    save = _mundane_save_with_knowledge(
        language_skill_picks=(("English", 0, True), ("Sperethiel", 0, True)),
    )
    with pytest.raises(ValueError, match="at most 1 language"):
        _build_mundane(save)


# -- WP50: specializations -------------------------------------------------------------------------

ARCHERY_ID = next(s.id for s in SKILLS if s.name == "Archery")


def _mundane_save_with_skills(
    skill_points: dict[str, int] | None = None,
    group_points: dict[str, int] | None = None,
    specializations: dict[str, str] | None = None,
) -> CharacterSave:
    return create_character_save(
        metatype_name="Human",
        heritage_letter="D",
        attributes_letter="A",
        attribute_points={},
        skills_letter="C",
        skill_points=skill_points or {},
        group_points=group_points or {},
        specializations=specializations or {},
        quality_picks=(),
        contacts=(),
        resources_letter="C",
        gear_names=(),
        lifestyle_tier_name="Street",
        lifestyle_months=1,
    )


def test_json_round_trip_preserves_specializations() -> None:
    save = _mundane_save_with_skills(
        skill_points={ARCHERY_ID: 4}, specializations={ARCHERY_ID: "Longbow"}
    )
    assert from_json(to_json(save)) == save
    data = json.loads(to_json(save))
    assert data["specializations"] == {ARCHERY_ID: "Longbow"}


def test_from_json_defaults_specializations_for_a_pre_wp50_save() -> None:
    data = json.loads(to_json(_mundane_save_with_skills()))
    del data["specializations"]
    loaded = from_json(json.dumps(data))
    assert loaded.specializations == {}


def test_build_character_applies_specialization() -> None:
    save = _mundane_save_with_skills(
        skill_points={ARCHERY_ID: 4}, specializations={ARCHERY_ID: "Longbow"}
    )
    character = _build_mundane(save)
    assert character.skill_allocation is not None
    assert character.skill_allocation.specializations[ARCHERY_ID] == "Longbow"


def test_build_character_rejects_specialization_on_an_unbought_skill() -> None:
    save = _mundane_save_with_skills(specializations={ARCHERY_ID: "Longbow"})
    with pytest.raises(ValueError, match="cannot add a specialization"):
        _build_mundane(save)


# -- karma_attribute_points (WP52) ---------------------------------------------------------------


def _mundane_save_with_karma_attribute_points(
    karma_attribute_points: dict[str, int] | None = None,
) -> CharacterSave:
    return create_character_save(
        metatype_name="Human",
        heritage_letter="D",
        attributes_letter="A",
        attribute_points={"EDG": 1},
        skills_letter="C",
        skill_points={},
        group_points={},
        quality_picks=(),
        contacts=(),
        resources_letter="C",
        gear_names=(),
        lifestyle_tier_name="Street",
        lifestyle_months=1,
        karma_attribute_points=karma_attribute_points or {},
    )


def test_json_round_trip_preserves_karma_attribute_points() -> None:
    save = _mundane_save_with_karma_attribute_points({"EDG": 1})
    assert from_json(to_json(save)) == save
    assert json.loads(to_json(save))["karma_attribute_points"] == {"EDG": 1}


def test_from_json_defaults_karma_attribute_points_for_a_pre_wp52_save() -> None:
    save = _sample_save()
    data = json.loads(to_json(save))
    assert "karma_attribute_points" not in data or data["karma_attribute_points"] == {}
    loaded = from_json(to_json(save))
    assert loaded.karma_attribute_points == {}


def test_build_character_applies_karma_attribute_points() -> None:
    # Human, Heritage D: EDG minimum 2, 1 priority point (rating 3); 1 Karma point raises it to 4
    # at a real cost of (3 + 1) x 5 = 20 -- well within the 25-Karma starting pool with no
    # qualities/contacts committed.
    save = _mundane_save_with_karma_attribute_points({"EDG": 1})
    character = _build_mundane(save)
    assert character.karma_attribute_selection is not None
    assert character.karma_attribute_selection.points == {"EDG": 1}
    assert character.karma_attribute_selection.karma_cost == 20
    assert character.attribute_value("EDG") == 4
    assert character.karma_remaining == 25 - 20


def test_build_character_rejects_karma_attribute_points_exceeding_the_karma_budget() -> None:
    # BOD 1 -> 6 (5 Karma points, no priority points spent) costs 100 Karma, far beyond the
    # 25-Karma starting pool.
    save = create_character_save(
        metatype_name="Human",
        heritage_letter="D",
        attributes_letter="A",
        attribute_points={},
        skills_letter="C",
        skill_points={},
        group_points={},
        quality_picks=(),
        contacts=(),
        resources_letter="C",
        gear_names=(),
        lifestyle_tier_name="Street",
        lifestyle_months=1,
        karma_attribute_points={"BOD": 5},
    )
    with pytest.raises(ValueError, match="exceeds the Karma budget"):
        _build_mundane(save)


# -- karma_skill_points / karma_group_points / karma_specializations / karma_knowledge_points ---
# -- (WP53) ---------------------------------------------------------------------------------------


def _mundane_save_with_karma_skills(
    *,
    skill_points: dict[str, int] | None = None,
    group_points: dict[str, int] | None = None,
    karma_skill_points: dict[str, int] | None = None,
    karma_group_points: dict[str, int] | None = None,
    karma_specializations: dict[str, str] | None = None,
    knowledge_skill_picks: tuple[tuple[str, str, int], ...] = (),
    karma_knowledge_points: dict[str, int] | None = None,
) -> CharacterSave:
    return create_character_save(
        metatype_name="Human",
        heritage_letter="D",
        attributes_letter="A",
        attribute_points={},
        skills_letter="A",
        skill_points=skill_points or {},
        group_points=group_points or {},
        quality_picks=(),
        contacts=(),
        resources_letter="C",
        gear_names=(),
        lifestyle_tier_name="Street",
        lifestyle_months=1,
        knowledge_skill_picks=knowledge_skill_picks,
        karma_skill_points=karma_skill_points or {},
        karma_group_points=karma_group_points or {},
        karma_specializations=karma_specializations or {},
        karma_knowledge_points=karma_knowledge_points or {},
    )


def test_json_round_trip_preserves_karma_skill_fields() -> None:
    archery_id = next(s.id for s in SKILLS if s.name == "Archery")
    save = _mundane_save_with_karma_skills(
        skill_points={archery_id: 2},
        karma_skill_points={archery_id: 1},
        karma_group_points={"Firearms": 1},
        karma_specializations={archery_id: "Longbow"},
        karma_knowledge_points={"Corporations": 1},
    )
    assert from_json(to_json(save)) == save
    data = json.loads(to_json(save))
    assert data["karma_skill_points"] == {archery_id: 1}
    assert data["karma_group_points"] == {"Firearms": 1}
    assert data["karma_specializations"] == {archery_id: "Longbow"}
    assert data["karma_knowledge_points"] == {"Corporations": 1}


def test_from_json_defaults_karma_skill_fields_for_a_pre_wp53_save() -> None:
    save = _sample_save()
    data = json.loads(to_json(save))
    for key in (
        "karma_skill_points",
        "karma_group_points",
        "karma_specializations",
        "karma_knowledge_points",
    ):
        assert key not in data or data[key] == {}
    loaded = from_json(to_json(save))
    assert loaded.karma_skill_points == {}
    assert loaded.karma_group_points == {}
    assert loaded.karma_specializations == {}
    assert loaded.karma_knowledge_points == {}


def test_build_character_applies_karma_skill_points() -> None:
    archery_id = next(s.id for s in SKILLS if s.name == "Archery")
    save = _mundane_save_with_karma_skills(
        skill_points={archery_id: 2}, karma_skill_points={archery_id: 2}
    )
    character = _build_mundane(save)
    assert character.karma_skill_selection is not None
    # 2->3 (6) + 3->4 (8) = 14 Karma.
    assert character.karma_skill_selection.karma_cost == 14
    assert character.karma_remaining == 25 - 14


def test_build_character_applies_karma_group_breaking_specialization() -> None:
    automatics_id = next(s.id for s in SKILLS if s.name == "Automatics")
    save = _mundane_save_with_karma_skills(
        group_points={"Firearms": 2}, karma_specializations={automatics_id: "Assault Rifles"}
    )
    character = _build_mundane(save)
    assert character.karma_skill_selection is not None
    assert character.karma_skill_selection.broken_groups == frozenset({"Firearms"})
    assert character.karma_skill_selection.karma_cost == 7
    assert character.karma_remaining == 25 - 7


def test_build_character_applies_karma_knowledge_points() -> None:
    save = _mundane_save_with_karma_skills(
        knowledge_skill_picks=(("Corporations", "Street", 2),),
        karma_knowledge_points={"Corporations": 1},
    )
    character = _build_mundane(save)
    assert character.karma_knowledge_selection is not None
    # 2->3 costs new_rating x 1 = 3 Karma.
    assert character.karma_knowledge_selection.karma_cost == 3
    assert character.karma_remaining == 25 - 3


def test_build_character_rejects_karma_skill_points_exceeding_the_karma_budget() -> None:
    archery_id = next(s.id for s in SKILLS if s.name == "Archery")
    save = _mundane_save_with_karma_skills(karma_skill_points={archery_id: 6})
    with pytest.raises(ValueError, match="exceeds the Karma budget"):
        _build_mundane(save)


# -- WP55/WP107: quality picks (free-text detail, rating) -----------------------------------------

SINNER_NATIONAL_ID = next(q.id for q in QUALITIES if q.name == "SINner (National)")
INDOMITABLE_MENTAL_ID = next(q.id for q in QUALITIES if q.name == "Indomitable (Mental)")
CODEBLOCK_ID = next(q.id for q in QUALITIES if q.name == "Codeblock")


def _mundane_save_with_quality_picks(
    quality_picks: tuple[str | QualityPickRequest, ...],
) -> CharacterSave:
    return create_character_save(
        metatype_name="Human",
        heritage_letter="D",
        attributes_letter="A",
        attribute_points={},
        skills_letter="E",
        skill_points={},
        group_points={},
        quality_picks=quality_picks,
        contacts=(),
        resources_letter="C",
        gear_names=(),
        lifestyle_tier_name="Street",
        lifestyle_months=1,
    )


def test_json_round_trip_preserves_quality_pick_text_and_rating() -> None:
    save = _mundane_save_with_quality_picks(
        (
            QualityPickRequest(SINNER_NATIONAL_ID, text="UCAS"),
            QualityPickRequest(INDOMITABLE_MENTAL_ID, rating=2),
        )
    )
    assert from_json(to_json(save)) == save
    assert json.loads(to_json(save))["quality_picks"] == [
        {"quality_id": SINNER_NATIONAL_ID, "rating": 1, "text": "UCAS", "choice": None},
        {"quality_id": INDOMITABLE_MENTAL_ID, "rating": 2, "text": None, "choice": None},
    ]


def test_from_json_migrates_a_version_1_save_s_quality_ids_and_text() -> None:
    save = _mundane_save_with_quality_picks(
        (QualityPickRequest(SINNER_NATIONAL_ID, text="UCAS"), CATLIKE_ID)
    )
    data = json.loads(to_json(save))
    del data["quality_picks"]
    data["format_version"] = 1
    data["quality_ids"] = [SINNER_NATIONAL_ID, CATLIKE_ID]
    data["quality_text"] = {SINNER_NATIONAL_ID: "UCAS"}
    assert from_json(json.dumps(data)) == save


def test_from_json_migrates_a_version_1_save_that_predates_quality_text() -> None:
    save = _mundane_save_with_quality_picks((CATLIKE_ID,))
    data = json.loads(to_json(save))
    del data["quality_picks"]
    data["format_version"] = 1
    data["quality_ids"] = [CATLIKE_ID]
    assert from_json(json.dumps(data)) == save


def test_build_character_applies_quality_text() -> None:
    save = _mundane_save_with_quality_picks((QualityPickRequest(SINNER_NATIONAL_ID, text="UCAS"),))
    character = _build_mundane(save)
    assert character.quality_selection is not None
    assert character.quality_selection.qualities[0].text == "UCAS"
    assert character.quality_selection.negative_karma == 5


def test_build_character_rejects_select_text_quality_with_missing_text() -> None:
    save = _mundane_save_with_quality_picks((SINNER_NATIONAL_ID,))
    with pytest.raises(ValueError, match="requires a free-text detail"):
        _build_mundane(save)


def test_build_character_applies_a_rated_quality_times_its_rating() -> None:
    save = _mundane_save_with_quality_picks((QualityPickRequest(INDOMITABLE_MENTAL_ID, rating=2),))
    character = _build_mundane(save)
    assert character.quality_selection is not None
    assert character.quality_selection.positive_karma == 16
    baseline = _build_mundane(_mundane_save_with_quality_picks(()))
    assert mental_limit(character) == mental_limit(baseline) + 2


def test_build_character_round_trips_two_instances_of_a_repeatable_quality() -> None:
    save = _mundane_save_with_quality_picks(
        (
            QualityPickRequest(CODEBLOCK_ID, text="Matrix Perception"),
            QualityPickRequest(CODEBLOCK_ID, text="Hack on the Fly"),
        )
    )
    reloaded = from_json(to_json(save))
    character = _build_mundane(reloaded)
    assert character.quality_selection is not None
    assert character.quality_selection.negative_karma == 20


# --- WP92: vehicles/drones ------------------------------------------------------------------------

# A cheap drone and an affordable vehicle from the real offerable catalog, so these tests exercise
# the same rows the UI offers rather than a stub.
FLY_SPY = next(v for v in VEHICLE_CATALOG if v.name == "MCT Fly-Spy (Minidrone)")
AMERICAR = next(v for v in VEHICLE_CATALOG if v.name == "Ford Americar (Sedan)")


def _mundane_save_with_vehicles(
    vehicle_ids: tuple[str, ...], resources_letter: str = "A"
) -> CharacterSave:
    return create_character_save(
        metatype_name="Human",
        heritage_letter="D",
        attributes_letter="B",
        attribute_points={},
        skills_letter="C",
        skill_points={},
        group_points={},
        quality_picks=(),
        contacts=(),
        resources_letter=resources_letter,
        gear_names=(),
        lifestyle_tier_name="Street",
        lifestyle_months=1,
        vehicle_ids=vehicle_ids,
    )


def test_json_round_trip_preserves_vehicle_ids_including_repeats() -> None:
    save = _mundane_save_with_vehicles((FLY_SPY.id, FLY_SPY.id, AMERICAR.id))
    assert from_json(to_json(save)) == save
    # Repeats are quantity, so order and multiplicity both have to survive the wire.
    assert json.loads(to_json(save))["vehicle_ids"] == [FLY_SPY.id, FLY_SPY.id, AMERICAR.id]


def test_from_json_defaults_vehicle_ids_for_a_pre_wp92_save() -> None:
    save = _sample_save()
    data = json.loads(to_json(save))
    del data["vehicle_ids"]
    assert from_json(json.dumps(data)).vehicle_ids == ()


def test_build_character_resolves_a_multi_vehicle_purchase() -> None:
    save = _mundane_save_with_vehicles((FLY_SPY.id, FLY_SPY.id, AMERICAR.id))
    character = build_character(
        save,
        metatypes=METATYPES,
        priorities=PRIORITIES,
        skills=SKILLS,
        qualities=QUALITIES,
        lifestyles=LIFESTYLES,
    )
    assert character.vehicle_selection is not None
    assert [v.name for v in character.vehicle_selection.vehicles] == [
        FLY_SPY.name,
        FLY_SPY.name,
        AMERICAR.name,
    ]
    spent = FLY_SPY.cost * 2 + AMERICAR.cost
    assert character.vehicle_selection.nuyen_spent == spent
    # WP92: the cost reaches the shared Step Six pool via resources_selection, not a second budget.
    assert character.resources_selection is not None
    assert character.resources_selection.vehicle_cost == spent
    assert (
        character.resources_selection.nuyen_remaining
        == character.resources_selection.nuyen_budget - spent
    )


def test_build_character_rejects_a_vehicle_purchase_over_the_shared_budget() -> None:
    # Resources E is 6,000Y; a Ford Americar is 16,000Y.
    save = _mundane_save_with_vehicles((AMERICAR.id,), resources_letter="E")
    with pytest.raises(ValueError, match="vehicle spend"):
        build_character(
            save,
            metatypes=METATYPES,
            priorities=PRIORITIES,
            skills=SKILLS,
            qualities=QUALITIES,
            lifestyles=LIFESTYLES,
        )


def test_build_character_rejects_an_unoffered_vehicle() -> None:
    # The GMC Banshee (Avail 24F) is in vehicles.xml but not in the offerable catalog.
    banshee = next(v for v in load_vehicles() if v.name == "GMC Banshee (Thunderbird)")
    save = _mundane_save_with_vehicles((banshee.id,))
    with pytest.raises(ValueError, match="not a vehicle catalog id"):
        build_character(
            save,
            metatypes=METATYPES,
            priorities=PRIORITIES,
            skills=SKILLS,
            qualities=QUALITIES,
            lifestyles=LIFESTYLES,
        )
