"""Tests for `chummer5.data.cyberware` (WP31's cyberware loader). See that module's docstring for
the full flat-cost/flat-Essence filter and `<bonus>`-classification reasoning this file exercises.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from decimal import Decimal

from chummer5.data.cyberware import (
    BonusSupport,
    Cyberware,
    CyberwareConditionalBonus,
    CyberwareFlatBonus,
    classify_bonus,
    count_by_support,
    load_cyberware,
)

CYBERWARE = load_cyberware()


def test_loads_exactly_the_confirmed_flat_count() -> None:
    # legacy/Chummer/data/cyberware.xml has 362 <cyberware> entries total; 87 are source == "SR5";
    # of those, 60 have both a bare-integer <cost> and a bare-decimal <ess> -- see module docstring.
    assert len(CYBERWARE) == 60
    assert all(c.source == "SR5" for c in CYBERWARE)


def test_no_duplicate_ids_or_names() -> None:
    ids = [c.id for c in CYBERWARE]
    assert len(ids) == len(set(ids))
    names = [c.name for c in CYBERWARE]
    assert len(names) == len(set(names))


def test_excludes_rating_scaled_essence_cost() -> None:
    # Wired Reflexes' <ess> is "FixedValues(2,3,5)" -- a per-rating formula, not a flat decimal.
    assert "Wired Reflexes" not in {c.name for c in CYBERWARE}


def test_excludes_rating_scaled_cost() -> None:
    # Data Lock's <ess> (0.1) is flat, but its <cost> ("Rating * 1000") is a formula -- excluded
    # despite having a flat Essence cost, confirming the loader requires *both* fields flat.
    assert "Data Lock" not in {c.name for c in CYBERWARE}


def test_excludes_essence_hole_and_antihole_rating_scaled_essence() -> None:
    # Both are utility items whose <ess> is "Rating * 0.01"/"Rating * -0.01" -- a per-rating
    # formula, not a flat decimal, despite a rating range (1-600) that looks superficially flat.
    names = {c.name for c in CYBERWARE}
    assert "Essence Hole" not in names
    assert "Essence Antihole" not in names


def test_hand_checked_fields_match_the_raw_xml() -> None:
    by_name = {c.name: c for c in CYBERWARE}
    datajack = by_name["Datajack"]
    assert datajack.category == "Headware"
    assert datajack.cost == 1000
    assert datajack.essence_cost == Decimal("0.1")
    assert datajack.page == 452
    assert datajack.bonus_support == BonusSupport.NO_EFFECT

    smartlink = by_name["Smartlink"]
    assert smartlink.category == "Eyeware"
    assert smartlink.cost == 4000
    assert smartlink.essence_cost == Decimal("0.2")


def test_smartlink_and_bone_lacing_are_not_yet_supported() -> None:
    # Smartlink's <smartlink>2</smartlink> and the 3 Bone Lacing variants' armor/unarmed-combat
    # bundle are real, unmodeled effects -- not shape-matched to FLAT_BONUS by accident.
    by_name = {c.name: c for c in CYBERWARE}
    for name in (
        "Smartlink",
        "Bone Lacing (Aluminum)",
        "Bone Lacing (Plastic)",
        "Bone Lacing (Titanium)",
    ):
        item = by_name[name]
        assert item.bonus_support == BonusSupport.NOT_YET_SUPPORTED
        assert item.flat_bonuses == ()
        assert item.raw_bonus is not None


def test_damper_is_not_yet_supported() -> None:
    by_name = {c.name: c for c in CYBERWARE}
    assert by_name["Damper"].bonus_support == BonusSupport.NOT_YET_SUPPORTED


def test_spatial_recognizer_is_the_flat_catalogs_one_conditional_bonus() -> None:
    # WP40 reclassifies this row from NOT_YET_SUPPORTED (where WP31 put it purely because nothing
    # could express "only during this kind of test") to a real, condition-gated bonus. p. 444:
    # "You get a +2 bonus on your limit in Perception Tests to find the source of a specific
    # sound." The other three conditional items are rating-scaled, so this is the only one that
    # reaches the flat catalog at all.
    conditional = [c for c in CYBERWARE if c.bonus_support == BonusSupport.CONDITIONAL_BONUS]
    assert [c.name for c in conditional] == ["Spatial Recognizer"]
    assert conditional[0].conditional_bonuses == (
        CyberwareConditionalBonus(
            target_kind="mental_limit",
            value=2,
            condition="LimitCondition_SkillsActivePerceptionSpatialRecognizer",
        ),
    )
    assert conditional[0].flat_bonuses == ()


def test_cyberlimb_condition_monitor_bonus_items_are_flat_bonus() -> None:
    # Every one of these carries <bonus><conditionmonitor><physical>1</physical></conditionmonitor>
    # (Obvious/Synthetic Full Leg additionally carry a <disablequality>Celerity</disablequality>
    # sibling -- see next test) -- confirmed hand-checked against the raw XML.
    by_name = {c.name: c for c in CYBERWARE}
    for name in (
        "Obvious Full Arm",
        "Obvious Full Leg",
        "Obvious Torso",
        "Obvious Skull",
        "Synthetic Full Arm",
        "Synthetic Full Leg",
        "Synthetic Torso",
        "Synthetic Skull",
    ):
        item = by_name[name]
        assert item.bonus_support == BonusSupport.FLAT_BONUS
        assert item.flat_bonuses == (CyberwareFlatBonus(target_kind="physical_cm", value=1),)


def test_disablequality_only_items_are_no_effect_not_not_yet_supported() -> None:
    # Obvious/Synthetic Foot and Lower Leg's entire <bonus> is a single
    # <disablequality>Celerity</disablequality> child, no <conditionmonitor> at all. Celerity is
    # source == "RF" (excluded from mvp_quality_catalog on source grounds) and additionally gated
    # behind a Changeling-SURGE <required> -- categorically unreachable by any character this engine
    # builds, so this disable is verified moot rather than a real, unmodeled effect. Stripping it
    # leaves nothing behind, so these land in NO_EFFECT (the same bucket as a genuinely empty
    # <bonus>), not NOT_YET_SUPPORTED.
    by_name = {c.name: c for c in CYBERWARE}
    for name in ("Obvious Foot", "Obvious Lower Leg", "Synthetic Foot", "Synthetic Lower Leg"):
        item = by_name[name]
        assert item.bonus_support == BonusSupport.NO_EFFECT
        assert item.flat_bonuses == ()
        assert item.raw_bonus is not None
        assert "disablequality" in item.raw_bonus


def test_full_leg_variants_keep_their_condition_monitor_bonus_despite_disablequality_sibling() -> (
    None
):
    # The real trap this test exists to catch: a classifier that bails out to NOT_YET_SUPPORTED on
    # *any* unrecognized child (rather than stripping the verified-moot <disablequality> first)
    # would misclassify these two, which is the exact regression WP31's docstring flags.
    by_name = {c.name: c for c in CYBERWARE}
    for name in ("Obvious Full Leg", "Synthetic Full Leg"):
        item = by_name[name]
        assert item.bonus_support == BonusSupport.FLAT_BONUS
        assert item.flat_bonuses == (CyberwareFlatBonus(target_kind="physical_cm", value=1),)
        assert item.raw_bonus is not None
        assert "disablequality" in item.raw_bonus


# -- WP78: the three new flat `<bonus>` shapes, classified from synthetic XML ------------------
#
# Synthetic first, per WP78's own acceptance criteria and this project's general "prove the
# mechanism, then point it at real content" posture. The real-catalog counterparts (the four rows
# these shapes reclassify) live in `tests/unit/test_cyberware_subsystems.py`, because all four are
# rating-scaled and so appear only in WP37's wider 87-row catalog, never in this module's 60.


def _classify(xml: str):
    return classify_bonus(ET.fromstring(xml))


def test_specific_attribute_bonus_is_flat_with_a_real_target() -> None:
    support, flat, conditional = _classify(
        "<bonus><specificattribute precedence='0'>"
        "<name>REA</name><val>Rating</val></specificattribute></bonus>"
    )
    assert support is BonusSupport.FLAT_BONUS
    assert conditional == ()
    assert flat == (
        CyberwareFlatBonus(
            target_kind="attribute", value=None, target_name="REA", unique_name="precedence0"
        ),
    )
    # `value=None` is "the purchased Rating", not "no bonus" -- read it through resolve_value.
    assert flat[0].resolve_value(3) == 3


def test_a_literal_attribute_value_is_kept_as_the_literal() -> None:
    _, flat, _ = _classify(
        "<bonus><specificattribute><name>AGI</name><val>2</val></specificattribute></bonus>"
    )
    assert flat == (CyberwareFlatBonus(target_kind="attribute", value=2, target_name="AGI"),)
    assert flat[0].resolve_value(5) == 2


def test_specific_skill_bonus_is_flat_and_names_the_skill() -> None:
    support, flat, _ = _classify(
        "<bonus><specificskill><name>Impersonation</name><bonus>Rating</bonus>"
        "</specificskill></bonus>"
    )
    assert support is BonusSupport.FLAT_BONUS
    assert flat == (
        CyberwareFlatBonus(target_kind="skill", value=None, target_name="Impersonation"),
    )


def test_initiativepass_maps_to_the_initiative_dice_kind() -> None:
    # Legacy's `initiativepass` handler is a one-line delegation to `initiativedice`; the name is
    # historical (SR4 "Initiative Passes"), the mechanic is Initiative Dice.
    support, flat, _ = _classify(
        "<bonus><initiativepass precedence='0'>Rating</initiativepass></bonus>"
    )
    assert support is BonusSupport.FLAT_BONUS
    assert flat == (
        CyberwareFlatBonus(
            target_kind="initiative_dice", value=None, target_name="", unique_name="precedence0"
        ),
    )


def test_the_bonus_elements_unique_attribute_is_the_default_dedup_group() -> None:
    # Muscle Replacement's own shape: <bonus unique="muscle"> with two children that carry no
    # `precedence` of their own, so both inherit "muscle".
    _, flat, _ = _classify(
        "<bonus unique='muscle'>"
        "<specificattribute><name>AGI</name><val>Rating</val></specificattribute>"
        "<specificattribute><name>STR</name><val>Rating</val></specificattribute>"
        "</bonus>"
    )
    assert [b.unique_name for b in flat] == ["muscle", "muscle"]


def test_a_childs_precedence_overrides_the_bonus_elements_unique() -> None:
    # Legacy's handlers each start from the collection-wide `_strUnique` and overwrite it with
    # "precedence" + value when the child carries one -- so the child wins.
    _, flat, _ = _classify(
        "<bonus unique='muscle'><specificattribute precedence='0'>"
        "<name>STR</name><val>Rating</val></specificattribute></bonus>"
    )
    assert flat[0].unique_name == "precedence0"


def test_no_dedup_marker_at_all_means_the_bonus_stacks() -> None:
    _, flat, _ = _classify(
        "<bonus><specificattribute><name>STR</name><val>1</val></specificattribute></bonus>"
    )
    assert flat[0].unique_name is None


def test_an_attribute_bound_modifier_is_not_half_applied() -> None:
    # Legacy's own `specificattribute` handler also reads <min>/<max>/<aug>/<affectbase>, which
    # change an attribute's *bounds* rather than its value -- a mechanic this engine has no
    # representation of. A row carrying one must fall through whole, not lose the bound silently.
    # (No SR5 cyberware row carries one; this pins the behaviour for whenever data drifts.)
    support, flat, conditional = _classify(
        "<bonus><specificattribute><name>REA</name><val>1</val><max>1</max>"
        "</specificattribute></bonus>"
    )
    assert support is BonusSupport.NOT_YET_SUPPORTED
    assert (flat, conditional) == ((), ())


def test_an_applytorating_skill_bonus_is_not_half_applied() -> None:
    support, flat, _ = _classify(
        "<bonus><specificskill><name>Longarms</name><bonus>1</bonus>"
        "<applytorating>True</applytorating></specificskill></bonus>"
    )
    assert support is BonusSupport.NOT_YET_SUPPORTED
    assert flat == ()


def test_an_arithmetic_bonus_value_is_not_guessed_at() -> None:
    # The whitelist is `Rating` or a bare integer. Anything else is a formula this loader does not
    # evaluate, exactly as WP31's <cost>/<ess> filter refuses to.
    support, _, _ = _classify(
        "<bonus><specificattribute><name>REA</name><val>Rating * 2</val>"
        "</specificattribute></bonus>"
    )
    assert support is BonusSupport.NOT_YET_SUPPORTED


def test_supported_vs_unsupported_counts_are_visible() -> None:
    # FLAT_BONUS: 8 Cyberlimb condition-monitor items. CONDITIONAL_BONUS: Spatial Recognizer (WP40).
    # NOT_YET_SUPPORTED: Smartlink, Damper, 3 Bone Lacing variants = 5. NO_EFFECT: 60 - 8 - 1 - 5 =
    # 46 (42 genuinely empty/absent <bonus> + 4 disablequality-only).
    #
    # WP78 widened `classify_bonus`'s whitelist but left every one of these numbers untouched: all
    # four rows it reclassifies are rating-scaled in <cost> and/or <ess>, so none of them is in this
    # 60-row catalog to begin with. Asserted, not assumed -- this is the pin that says so.
    counts = count_by_support(CYBERWARE)
    assert counts[BonusSupport.FLAT_BONUS] == 8
    assert counts[BonusSupport.CONDITIONAL_BONUS] == 1
    assert counts[BonusSupport.NOT_YET_SUPPORTED] == 5
    assert counts[BonusSupport.NO_EFFECT] == 46
    assert sum(counts.values()) == 60


def test_cyberware_fields_hand_checked_against_the_raw_xml() -> None:
    commlink = next(c for c in CYBERWARE if c.name == "Commlink")
    assert commlink == Cyberware(
        id="6b219dfa-310a-45ab-98af-40a62e2431cf",
        name="Commlink",
        category="Headware",
        cost=2000,
        essence_cost=Decimal("0.2"),
        source="SR5",
        page=451,
        bonus_support=BonusSupport.NO_EFFECT,
        flat_bonuses=(),
        conditional_bonuses=(),
        raw_bonus=None,
    )
