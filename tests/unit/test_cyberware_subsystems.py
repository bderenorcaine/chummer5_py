"""Tests for `chummer5.data.cyberware_subsystems` (WP37's Capacity/subsystem-aware loader).

Two deliberate layers, mirroring `tests/unit/test_cyberware_formula.py`'s own split:

1. **Hand-checked rows** -- specific items' Capacity/rating/formula fields checked against values
   transcribed from the printed rulebook tables (`spec/rulebooks/learnings/phase-k.md`'s WP36
   entry), not merely against the XML string they were parsed from.
2. **Whole-data-set invariants** -- the parent/plugin split this WP was required to re-confirm, and
   the "WP31's loader is untouched" guarantee its acceptance criteria demand.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from collections import Counter
from decimal import Decimal

from chummer5.data.cyberware import (
    BonusSupport,
    CyberwareConditionalBonus,
    CyberwareFlatBonus,
    load_cyberware,
)
from chummer5.data.cyberware_formula import FormulaKind
from chummer5.data.cyberware_subsystems import CyberwareEntry, load_cyberware_entries
from chummer5.data.metatypes import load_metatypes
from chummer5.data.qualities import DEFAULT_QUALITIES_PATH, load_qualities
from chummer5.data.skills import load_skills

ENTRIES = load_cyberware_entries()
BY_NAME = {entry.name: entry for entry in ENTRIES}


# --------------------------------------------------------------------------------------------
# Layer 1: hand-checked rows
# --------------------------------------------------------------------------------------------


def test_loads_every_sr5_row_not_just_the_flat_ones() -> None:
    # cyberware.xml has 362 <cyberware> entries; 87 are source == "SR5". Unlike WP31's loader
    # (60 rows, flat cost/Essence only), this path applies no formula-flatness filter.
    assert len(ENTRIES) == 87
    assert all(entry.source == "SR5" for entry in ENTRIES)
    ids = [entry.id for entry in ENTRIES]
    assert len(ids) == len(set(ids))


def test_rating_scaled_rows_excluded_by_wp31_are_present_here() -> None:
    for name in (
        "Cybereyes Basic System",
        "Cyberears",
        "Wired Reflexes",
        "Data Lock",
        "Customized Agility",
        "Enhanced Agility",
        "Vision Enhancement",
    ):
        assert name in BY_NAME
    flat_names = {item.name for item in load_cyberware()}
    assert flat_names.isdisjoint(
        {"Cybereyes Basic System", "Cyberears", "Wired Reflexes", "Data Lock"}
    )


def test_cybereyes_basic_system_is_a_rating_scaled_parent() -> None:
    # Printed table (core rulebook p. 454, transcribed in learnings/phase-k.md's WP36 entry):
    # Rating 3 cybereyes cost 10,000 nuyen and 0.4 Essence, with Capacity 4 per rating point.
    eyes = BY_NAME["Cybereyes Basic System"]
    assert eyes.category == "Eyeware"
    assert eyes.is_rated
    assert (eyes.min_rating, eyes.max_rating) == (1, 4)
    assert eyes.cost.resolve(rating=3) == Decimal(10000)
    assert eyes.essence_cost.resolve(rating=3) == Decimal("0.4")
    assert eyes.capacity_budget is not None
    assert eyes.capacity_budget.resolve(rating=3) == Decimal(12)
    assert eyes.capacity_cost is None  # a budget, not a cost -- its <capacity> is unbracketed
    assert eyes.is_subsystem_parent
    assert eyes.allowed_subsystem_categories == ("Eyeware",)
    assert not eyes.is_plugin


def test_vision_enhancement_is_a_rating_scaled_plugin() -> None:
    # Printed table (p. 454): Vision Enhancement Rating 2 -> Capacity cost 2, Essence 0.1,
    # 8,000 nuyen. The Capacity value is bracketed ([Rating]) -- a cost, not a budget.
    vision = BY_NAME["Vision Enhancement"]
    assert vision.is_plugin
    assert not vision.is_subsystem_parent
    assert vision.capacity_budget is None
    assert vision.capacity_cost is not None
    assert vision.capacity_cost.kind is FormulaKind.RATING
    assert vision.capacity_cost.resolve(rating=2) == Decimal(2)
    assert vision.cost.resolve(rating=2) == Decimal(8000)
    assert vision.essence_cost.resolve(rating=2) == Decimal("0.1")
    # Its <bonus> is the condition-gated Mental limit modifier WP39/WP40 exist for. WP40 classifies
    # it for real; the value is the purchased Rating (value=None), not a literal -- p. 444, "It
    # adds its Rating as a positive modifier to your limit on visual Perception Tests."
    assert vision.bonus_support is BonusSupport.CONDITIONAL_BONUS
    assert vision.conditional_bonuses == (
        CyberwareConditionalBonus(
            target_kind="mental_limit",
            value=None,
            condition="LimitCondition_SkillsActivePerceptionVisual",
        ),
    )
    assert vision.conditional_bonuses[0].resolve_value(rating=2) == 2


def test_synthetic_full_arm_keeps_a_bare_integer_capacity_budget() -> None:
    # The 16 Cyberlimb variants are already in WP31's flat catalog; what's new here is their
    # Capacity budget and the categories they accept. Synthetic Full Arm -> 8 (raw XML, p. 456).
    arm = BY_NAME["Synthetic Full Arm"]
    assert arm.capacity_budget is not None
    assert arm.capacity_budget.kind is FormulaKind.LITERAL
    assert arm.capacity_budget.resolve(rating=1) == Decimal(8)
    assert not arm.is_rated
    assert "Cyberlimb Enhancement" in arm.allowed_subsystem_categories
    assert "Cyber Implant Weapon" in arm.allowed_subsystem_categories


def test_customized_agility_keeps_its_attribute_placeholder_bounds_raw() -> None:
    # <rating>{AGIMaximum}</rating> / <minrating>{AGIMinimum}+1</minrating> resolve against
    # character state, not arithmetic -- out of scope for both this loader and WP36's resolver.
    agility = BY_NAME["Customized Agility"]
    assert agility.raw_max_rating == "{AGIMaximum}"
    assert agility.raw_min_rating == "{AGIMinimum}+1"
    assert agility.max_rating is None
    assert agility.min_rating is None
    assert not agility.has_resolvable_rating_bounds
    assert agility.is_rated
    # Its cost formula is still resolvable given a rating and a min_rating (p. 457: each STR or AGI
    # point above 3 costs 5,000 nuyen; a limb's base is 3, so min_rating is 4).
    assert agility.cost.requires_min_rating
    assert agility.cost.resolve(rating=6, min_rating=4) == Decimal(15000)
    # [0] -- a plugin that costs no Capacity at all, distinct from the [*] bundled-free marker.
    assert agility.capacity_cost is not None
    assert agility.capacity_cost.resolve(rating=6) == Decimal(0)
    assert not agility.bundled_free
    assert agility.requires_parent


def test_only_the_two_customized_rows_have_unresolvable_rating_bounds() -> None:
    unresolvable = {e.name for e in ENTRIES if not e.has_resolvable_rating_bounds}
    assert unresolvable == {"Customized Agility", "Customized Strength"}


def test_bundled_free_marker_is_exactly_image_link_and_sound_link() -> None:
    bundled = {e.name for e in ENTRIES if e.bundled_free}
    assert bundled == {"Image Link", "Sound Link"}
    for name in bundled:
        entry = BY_NAME[name]
        # [*] is a marker, not a formula: neither a budget nor a cost, but still a plugin.
        assert entry.capacity_budget is None
        assert entry.capacity_cost is None
        assert entry.is_plugin


def test_subsystems_auto_include_list_has_three_rows_not_two() -> None:
    # The pre-Phase-K research entry read the bundled-free case as "[*] on Image Link/Sound Link".
    # The actual auto-inclusion list is a parent's <subsystems> element, and Control Rig -> Datajack
    # is a third instance that carries neither [*] nor <allowsubsystems> -- and is real fixture
    # content (Mittens Chargen.chum5). See the module docstring.
    bundling = {e.name: e.bundled_subsystem_names for e in ENTRIES if e.bundled_subsystem_names}
    assert bundling == {
        "Control Rig": ("Datajack",),
        "Cybereyes Basic System": ("Image Link",),
        "Cyberears": ("Sound Link",),
    }
    control_rig = BY_NAME["Control Rig"]
    assert not control_rig.is_subsystem_parent  # no <allowsubsystems> at all
    datajack = BY_NAME["Datajack"]
    assert not datajack.is_plugin  # bare <capacity>0</capacity>, not bracketed
    assert not datajack.bundled_free


def test_cyber_implant_weapons_are_parents_with_no_capacity_budget() -> None:
    # The two-level-nesting case WP37 had to settle for WP38: a cyber implant weapon declares
    # <allowsubsystems>Cyber Implant Weapon Accessory</allowsubsystems> but its own <capacity> is
    # bracketed, i.e. a cost -- so it has no budget for that accessory to be charged against
    # (legacy Cyberware.CapacityRemaining returns 0 for a purely-bracketed Capacity). Its
    # accessories instead carry <addtoparentcapacity>/<addtoparentess>: a fold-into-the-parent
    # mechanic, not one more level of the same one.
    blade = BY_NAME["Hand Blade"]
    assert blade.is_subsystem_parent
    assert blade.allowed_subsystem_categories == ("Cyber Implant Weapon Accessory",)
    assert blade.capacity_budget is None
    assert blade.capacity_cost is not None
    assert blade.capacity_cost.resolve(rating=1) == Decimal(2)
    assert blade.is_plugin

    accessories = [e for e in ENTRIES if e.category == "Cyber Implant Weapon Accessory"]
    assert {e.name for e in accessories} == {
        "External Clip Port",
        "Laser Sight",
        "Silencer/Suppressor",
    }
    assert all(e.adds_to_parent_capacity and e.adds_to_parent_essence for e in accessories)
    # Nothing else in the SR5 set uses those flags.
    assert [e.name for e in ENTRIES if e.adds_to_parent_capacity] == [e.name for e in accessories]
    assert [e.name for e in ENTRIES if e.adds_to_parent_essence] == [e.name for e in accessories]


def test_requires_parent_marks_the_plugin_only_rows() -> None:
    # <requireparent> = "installable only into a parent, never standalone" -- the rows for which
    # WP38's Essence-vs-Capacity dual-costing choice does not exist, because only one mode is legal.
    plugin_only = {e.name for e in ENTRIES if e.requires_parent}
    assert plugin_only == {
        "Ocular Drone",
        "Armor",
        "Customized Strength",
        "Customized Agility",
        "Enhanced Strength",
        "Enhanced Agility",
        "Cyber Holster",
        "Cyberarm Slide",
        "Large Smuggling Compartment",
    }
    assert all(BY_NAME[name].is_plugin for name in plugin_only)


# --------------------------------------------------------------------------------------------
# Layer 2: whole-data-set invariants
# --------------------------------------------------------------------------------------------


def test_parent_split_matches_the_phase_intros_survey() -> None:
    # WP37's own re-confirmation duty: the Phase K intro claimed "29 of the 87 SR5 entries carry
    # <allowsubsystems>: 16 Cyberlimb / 2 Cybereyes+Cyberears / 11 Cyber Implant Weapon."
    # Re-derived over the complete file -- exact, all three numbers.
    parents = [e for e in ENTRIES if e.is_subsystem_parent]
    assert len(parents) == 29
    assert Counter(e.category for e in parents) == {
        "Cyberlimb": 16,
        "Cyber Implant Weapon": 11,
        "Eyeware": 1,
        "Earware": 1,
    }
    assert {e.name for e in parents if e.category in {"Eyeware", "Earware"}} == {
        "Cybereyes Basic System",
        "Cyberears",
    }


def test_every_row_is_a_parent_a_plugin_or_standalone_only() -> None:
    plugins = [e for e in ENTRIES if e.is_plugin]
    standalone_only = [e for e in ENTRIES if not e.is_plugin and not e.is_subsystem_parent]
    both = [e for e in ENTRIES if e.is_plugin and e.is_subsystem_parent]
    assert len(plugins) == 50
    assert len(standalone_only) == 19
    # The only rows that are both are the 11 cyber implant weapons.
    assert {e.category for e in both} == {"Cyber Implant Weapon"}
    assert len(both) == 11
    # Standalone-only rows all carry a bare <capacity>0</capacity>: a budget of nothing.
    for entry in standalone_only:
        assert entry.capacity_budget is not None
        assert entry.capacity_budget.resolve(rating=1) == Decimal(0)


def test_budget_and_cost_are_never_both_set() -> None:
    for entry in ENTRIES:
        assert entry.capacity_budget is None or entry.capacity_cost is None
        if entry.bundled_free:
            assert entry.capacity_budget is None and entry.capacity_cost is None


def test_is_rated_splits_the_set_exactly_the_way_wp31s_flat_filter_did() -> None:
    # WP36 established that the 60 flat-cost/flat-Essence rows are exactly the 60 with no <rating>
    # tag. Restated here at the loader level: a row is rating-scaled iff WP31 excluded it.
    flat_ids = {item.id for item in load_cyberware()}
    rated_ids = {e.id for e in ENTRIES if e.is_rated}
    assert len(rated_ids) == 27
    assert rated_ids.isdisjoint(flat_ids)
    assert rated_ids | flat_ids == {e.id for e in ENTRIES}


def test_bonus_classification_matches_wp31_row_for_row() -> None:
    # This loader shares chummer5.data.cyberware.classify_bonus verbatim; nothing about the wider
    # scope may change how an already-loaded row's <bonus> is read.
    flat = {item.id: item for item in load_cyberware()}
    for entry in ENTRIES:
        original = flat.get(entry.id)
        if original is None:
            continue
        assert entry.bonus_support == original.bonus_support
        assert entry.flat_bonuses == original.flat_bonuses
        assert entry.conditional_bonuses == original.conditional_bonuses
        assert entry.raw_bonus == original.raw_bonus


def test_flat_rows_agree_with_wp31s_resolved_cost_and_essence() -> None:
    # A LITERAL formula resolved at any rating must reproduce WP31's plain int/Decimal, or the two
    # catalogs would silently disagree about the same purchase.
    flat = {item.id: item for item in load_cyberware()}
    for entry in ENTRIES:
        original = flat.get(entry.id)
        if original is None:
            continue
        assert entry.cost.kind is FormulaKind.LITERAL
        assert entry.essence_cost.kind is FormulaKind.LITERAL
        assert entry.cost.resolve(rating=1) == Decimal(original.cost)
        assert entry.essence_cost.resolve(rating=1) == original.essence_cost


def test_wp31s_loader_is_completely_unchanged() -> None:
    # WP37's acceptance criteria: additive to WP31/32/33, not a breaking change. The flat catalog's
    # count, field set and a hand-checked row all stay exactly as tests/unit/test_cyberware.py
    # pinned them. (WP40 adds one field, `conditional_bonuses` -- a deliberate, additive widening
    # of the shared classifier, not a change to which rows load or what any of them cost.)
    flat = load_cyberware()
    assert len(flat) == 60
    commlink = next(item for item in flat if item.name == "Commlink")
    assert (commlink.cost, commlink.essence_cost) == (2000, Decimal("0.2"))
    assert {field for field in vars(commlink)} == {
        "id",
        "name",
        "category",
        "cost",
        "essence_cost",
        "source",
        "page",
        "bonus_support",
        "flat_bonuses",
        "conditional_bonuses",
        "raw_bonus",
    }


def test_every_entry_is_frozen_and_hashable() -> None:
    # Mirrors the rest of the data layer: catalog rows are frozen values, safe to share.
    assert all(isinstance(entry, CyberwareEntry) for entry in ENTRIES)
    assert len({hash(entry) for entry in ENTRIES}) == len(ENTRIES)


def test_exactly_four_rows_carry_a_supported_conditional_bonus() -> None:
    # WP40. The complete set, enumerated rather than assumed -- WP39's own research found the fourth
    # (Hydraulic Jacks) after two earlier plan entries had named only the three Eyeware/Earware
    # items. Values/limits hand-checked against the rulebook text transcribed in
    # spec/rulebooks/learnings/phase-k.md's WP40 entry.
    conditional = {
        entry.name: entry.conditional_bonuses
        for entry in ENTRIES
        if entry.bonus_support is BonusSupport.CONDITIONAL_BONUS
    }
    assert conditional == {
        "Vision Enhancement": (
            CyberwareConditionalBonus(
                target_kind="mental_limit",
                value=None,  # p. 444: "adds its Rating ... to your limit on visual Perception"
                condition="LimitCondition_SkillsActivePerceptionVisual",
            ),
        ),
        "Audio Enhancement": (
            CyberwareConditionalBonus(
                target_kind="mental_limit",
                value=None,  # p. 444: "adds its Rating to your limit in audio Perception Tests"
                condition="LimitCondition_SkillsActivePerceptionHearing",
            ),
        ),
        "Spatial Recognizer": (
            CyberwareConditionalBonus(
                target_kind="mental_limit",
                value=2,  # p. 444: "+2 bonus on your limit in Perception Tests to find the source"
                condition="LimitCondition_SkillsActivePerceptionSpatialRecognizer",
            ),
        ),
        "Hydraulic Jacks": (
            CyberwareConditionalBonus(
                target_kind="physical_limit",
                value=None,  # p. 457: "Each Rating point adds a +1 to your Physical limit"
                condition="LimitCondition_CyberwareHydraulicJacks",
            ),
        ),
    }


def test_no_row_carries_an_unclassified_limitmodifier() -> None:
    # The whitelist's coverage claim: every <limitmodifier> in the SR5 rows is one of the four
    # above. A future data update adding a fifth would land in NOT_YET_SUPPORTED and fail here,
    # which is the point -- silently ignoring a real limit bonus is what this catches.
    for entry in ENTRIES:
        if entry.raw_bonus is not None and "<limitmodifier>" in entry.raw_bonus:
            assert entry.bonus_support is BonusSupport.CONDITIONAL_BONUS, entry.name


# --------------------------------------------------------------------------------------------
# WP78: the four rows the widened flat-bonus whitelist reclassifies
# --------------------------------------------------------------------------------------------


def test_wp78s_four_rows_carry_their_hand_checked_flat_bonuses() -> None:
    # Each value hand-checked against the printed entry (p. 452/455), not against the XML string
    # it was parsed from -- see `spec/rulebooks/learnings/phase-k.md`'s WP78 entry for the quotes.
    assert {
        name: BY_NAME[name].flat_bonuses
        for name in (
            "Reaction Enhancers",
            "Wired Reflexes",
            "Muscle Replacement",
            "Voice Modulator",
        )
    } == {
        # p. 455: "Add the Rating of reaction enhancers to your Reaction attribute."
        "Reaction Enhancers": (
            CyberwareFlatBonus(
                target_kind="attribute", value=None, target_name="REA", unique_name="precedence0"
            ),
        ),
        # p. 455: "each rating point ... gives you +1 Reaction ... and +1D6 Initiative Die."
        # Order follows the raw <bonus>: <initiativepass> precedes <specificattribute>.
        "Wired Reflexes": (
            CyberwareFlatBonus(
                target_kind="initiative_dice", value=None, unique_name="precedence0"
            ),
            CyberwareFlatBonus(
                target_kind="attribute", value=None, target_name="REA", unique_name="precedence0"
            ),
        ),
        # p. 455: "It increases both your Strength and Agility attributes by its rating."
        "Muscle Replacement": (
            CyberwareFlatBonus(
                target_kind="attribute", value=None, target_name="AGI", unique_name="muscle"
            ),
            CyberwareFlatBonus(
                target_kind="attribute", value=None, target_name="STR", unique_name="muscle"
            ),
        ),
        # p. 452: "Add the Rating of the modulator to your dice pool for Impersonation skill tests."
        "Voice Modulator": (
            CyberwareFlatBonus(target_kind="skill", value=None, target_name="Impersonation"),
        ),
    }
    for name in ("Reaction Enhancers", "Wired Reflexes", "Muscle Replacement", "Voice Modulator"):
        assert BY_NAME[name].bonus_support is BonusSupport.FLAT_BONUS


def test_the_not_yet_supported_count_drops_from_14_to_10() -> None:
    # WP77's audit found 14 NOT_YET_SUPPORTED cyberware rows: 10 genuinely out of scope (its
    # registry rows) and 4 computable today. This WP models the 4.
    unsupported = {e.name for e in ENTRIES if e.bonus_support is BonusSupport.NOT_YET_SUPPORTED}
    assert len(unsupported) == 10
    assert unsupported.isdisjoint(
        {"Reaction Enhancers", "Wired Reflexes", "Muscle Replacement", "Voice Modulator"}
    )


def test_wp31s_flat_catalog_classification_is_untouched() -> None:
    # WP37 pinned "load_cyberware() is completely unchanged" and WP40 narrowed that pin once (it
    # reclassified Spatial Recognizer). WP78 does not narrow it again: all four rows it touches are
    # rating-scaled, so none of them is in the 60.
    flat_by_name = {c.name: c for c in load_cyberware()}
    assert not {
        "Reaction Enhancers",
        "Wired Reflexes",
        "Muscle Replacement",
        "Voice Modulator",
    } & set(flat_by_name)
    assert sum(1 for c in flat_by_name.values() if c.bonus_support is BonusSupport.FLAT_BONUS) == 8


def test_every_attribute_and_skill_target_resolves_against_real_catalog_content() -> None:
    # The data layer deliberately does not whitelist attribute codes or skill names (mirroring
    # `chummer5.data.qualities`/`bioware`, neither of which does either) -- so this is the check
    # that a typo'd target would otherwise silently produce an Improvement nothing ever reads.
    skill_names = {s.name for s in load_skills()}
    attribute_codes = set(load_metatypes()[0].attributes)
    for entry in ENTRIES:
        for bonus in entry.flat_bonuses:
            if bonus.target_kind == "attribute":
                assert bonus.target_name in attribute_codes, entry.name
            elif bonus.target_kind == "skill":
                assert bonus.target_name in skill_names, entry.name
            else:
                assert bonus.target_name == "", entry.name


def test_the_disabled_quality_guid_resolves_to_a_non_sr5_quality() -> None:
    # `Wired Reflexes`' <bonus> carries <disablequality>3564b678-...</disablequality> -- a raw guid
    # rather than Celerity's plain name, which is why WP31's own "verified moot" note didn't cover
    # it. It resolves to Lightning Reflexes (source "RF"), so it is excluded from the SR5 quality
    # catalog on source grounds exactly as Celerity is, and stripping it drops nothing reachable.
    disabled_guid = "3564b678-7721-4a8d-ac79-1600cf92dc14"
    assert BY_NAME["Wired Reflexes"].raw_bonus is not None
    assert disabled_guid in BY_NAME["Wired Reflexes"].raw_bonus
    # load_qualities() is already source-filtered to SR5, so "absent from it" *is* the finding.
    assert disabled_guid not in {q.id for q in load_qualities()}
    # ... and the name behind the guid, read straight from the unfiltered file so the test says
    # which quality this is rather than only that it's missing.
    root = ET.parse(DEFAULT_QUALITIES_PATH).getroot()
    quality = next(q for q in root.iter("quality") if q.findtext("id") == disabled_guid)
    assert quality.findtext("name") == "Lightning Reflexes"
    assert quality.findtext("source") == "RF"
