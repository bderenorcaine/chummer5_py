from decimal import Decimal

from chummer5.data.powers import BonusSupport, Power, PowerFlatBonus, count_by_support, load_powers

POWERS = load_powers()


def test_only_sr5_sourced_powers_are_loaded() -> None:
    # legacy/Chummer/data/powers.xml has 136 <power> entries total; 28 are source == "SR5".
    assert len(POWERS) == 28
    assert all(p.source == "SR5" for p in POWERS)


def test_no_duplicate_ids() -> None:
    ids = [p.id for p in POWERS]
    assert len(ids) == len(set(ids))


def test_enhanced_perception_grants_two_named_skill_bonuses() -> None:
    # Hand-checked: <bonus><specificskill><name>Perception</name><bonus>Rating</bonus>
    # </specificskill><specificskill><name>Assensing</name><bonus>Rating</bonus></specificskill>
    # </bonus> -- rulebook p.309: "Add +1 die per level to all Perception and Assensing Tests."
    power = next(p for p in POWERS if p.name == "Enhanced Perception")
    assert power.bonus_support == BonusSupport.FLAT_BONUS
    assert set(power.flat_bonuses) == {
        PowerFlatBonus(target_kind="skill", target_name="Perception", attribute_options=()),
        PowerFlatBonus(target_kind="skill", target_name="Assensing", attribute_options=()),
    }
    assert power.points == Decimal("0.5")
    assert power.levels is True


def test_improved_physical_attribute_is_a_select_attribute_flat_bonus() -> None:
    # <bonus><selectattribute><attribute>BOD</attribute>...<val>Rating</val>
    # </selectattribute></bonus>
    power = next(p for p in POWERS if p.name == "Improved Physical Attribute")
    assert power.bonus_support == BonusSupport.FLAT_BONUS
    assert power.flat_bonuses == (
        PowerFlatBonus(
            target_kind="select_attribute",
            target_name="",
            attribute_options=("BOD", "AGI", "REA", "STR"),
        ),
    )
    assert power.points == Decimal("1")
    assert power.limit == 12


def test_attribute_boost_applies_no_bonus_despite_sharing_selectattribute() -> None:
    # The exact regression this WP's intro exists to prevent: Attribute Boost's <bonus> uses the
    # same <selectattribute> tag and attribute list as Improved Physical Attribute, but has no
    # <val> child -- its real effect (rulebook p.309) is a temporary, test-gated, Drain-costing
    # boost, not a permanent bonus. A classifier keyed only on the "selectattribute" tag would
    # silently misapply it as a flat attribute bonus. WP120 offers it as a registry row: NO_EFFECT,
    # still with no flat bonus, and a note saying the attribute isn't raised.
    power = next(p for p in POWERS if p.name == "Attribute Boost")
    assert power.bonus_support == BonusSupport.NO_EFFECT
    assert power.flat_bonuses == ()
    assert power.unmodeled_effect_note and "not raised" in power.unmodeled_effect_note
    assert power.raw_bonus is not None
    assert "selectattribute" in power.raw_bonus
    assert "<val>" not in power.raw_bonus


def test_improved_potential_trio_maps_to_the_three_limit_kinds() -> None:
    # Each of the 3 Improved Potential (Social/Mental/Physical) powers is levels=False (single
    # purchase, rulebook p.309: "raise one of your inherent limits... by 1"), mirroring
    # chummer5.data.qualities's Indomitable trio shape exactly.
    social = next(p for p in POWERS if p.name == "Improved Potential (Social)")
    mental = next(p for p in POWERS if p.name == "Improved Potential (Mental)")
    physical = next(p for p in POWERS if p.name == "Improved Potential (Physical)")
    trio = ((social, "social_limit"), (mental, "mental_limit"), (physical, "physical_limit"))
    for power, kind in trio:
        assert power.bonus_support == BonusSupport.FLAT_BONUS
        assert power.flat_bonuses == (
            PowerFlatBonus(target_kind=kind, target_name="", attribute_options=()),
        )
        assert power.levels is False
        assert power.limit == 1


def test_improved_potential_chaos_mentor_variant_is_not_yet_supported() -> None:
    # <bonus><selectlimit><val>1</val></selectlimit></bonus> -- a different shape from the other 3
    # (a player-selects-which-limit choice, not one of the 3 named limit tags) and the raw XML
    # marks it <hide/> -- a legacy-internal variant (used by a mentor-spirit selection elsewhere),
    # not a standalone offerable power. Falls through to NOT_YET_SUPPORTED via the ordinary
    # unrecognized-shape rule; no special-casing needed.
    power = next(p for p in POWERS if p.name == "Improved Potential (Chaos Mentor)")
    assert power.bonus_support == BonusSupport.NOT_YET_SUPPORTED


def test_voice_control_is_a_verified_flat_bonus_not_named_in_the_implementation_plan() -> None:
    # Confirmed via rulebook p.311: "+1 per level to your Social limit" AND "[Impersonation] test...
    # adding the level of this power as a bonus to your dice pool" -- both real, computable, and
    # each individually matching an already-established flat shape (sociallimit like Improved
    # Potential; specificskill like Enhanced Perception). The Implementation Plan's WP27 entry names
    # only 3 FLAT_BONUS candidates (Improved Physical Attribute, the Improved Potential trio,
    # Enhanced Perception); this is a 4th, found by this WP's own required rulebook pass rather than
    # assumed from the plan text -- see spec/worklogs/WP27.md.
    power = next(p for p in POWERS if p.name == "Voice Control")
    assert power.bonus_support == BonusSupport.FLAT_BONUS
    assert set(power.flat_bonuses) == {
        PowerFlatBonus(target_kind="social_limit", target_name="", attribute_options=()),
        PowerFlatBonus(target_kind="skill", target_name="Impersonation", attribute_options=()),
    }
    assert power.levels is True
    assert power.limit == 20


def test_improved_ability_skill_targets_a_known_skill() -> None:
    # WP27 deferred it: its rule needs the target skill already known at rating >= 1 and caps the
    # improvement (p. 309). WP119 built both checks (`chummer5.engine.magic.power_max_rating`).
    power = next(p for p in POWERS if p.name == "Improved Ability (skill)")
    assert power.bonus_support == BonusSupport.FLAT_BONUS
    assert power.target_kind == "skill"
    assert power.target_minimum_rating == 1


def test_empty_or_absent_bonus_powers_are_registry_rows() -> None:
    # Light Body, Missile Parry, Traceless Walk, Wall Running all have an empty/absent <bonus> --
    # each individually confirmed via the rulebook text (this WP's own research pass) to have a
    # real, unmodeled in-play effect (jump distance, ranged-attack defense, stealth, wall-climbing),
    # not a verified-inert one. Unlike chummer5.data.qualities's NO_EFFECT tranche, none of these
    # qualify. WP120 offers them anyway, as NO_EFFECT registry rows with a note each.
    for name in ("Light Body", "Missile Parry", "Traceless Walk", "Wall Running"):
        power = next(p for p in POWERS if p.name == name)
        assert power.bonus_support == BonusSupport.NO_EFFECT
        assert power.flat_bonuses == ()
        assert power.unmodeled_effect_note


def test_supported_vs_unsupported_counts_are_visible() -> None:
    # FLAT_BONUS: Enhanced Perception, Improved Physical Attribute, Improved Potential x3, Voice
    # Control = 6. NOT_YET_SUPPORTED: 28 - 6 = 22. No NO_EFFECT value exists in this module. WP118
    # adds Astral Perception (its Assensing unlock). WP119 adds Improved Ability, Improved Reflexes,
    # Mystic Armor and Pain Resistance, and the NO_EFFECT value for Critical Strike, Enhanced
    # Accuracy and Killing Hands. WP120 makes the other 13 registry rows; only Improved Potential
    # (Chaos Mentor) is left, and it is out of scope by name.
    counts = count_by_support(POWERS)
    assert counts[BonusSupport.FLAT_BONUS] == 11
    assert counts[BonusSupport.NO_EFFECT] == 16
    assert counts[BonusSupport.NOT_YET_SUPPORTED] == 1


def test_power_fields_hand_checked_against_the_raw_xml() -> None:
    danger_sense = next(p for p in POWERS if p.name == "Danger Sense")
    assert danger_sense == Power(
        id="980d6575-c28f-4076-9b36-881cea018335",
        name="Danger Sense",
        points=Decimal("0.25"),
        levels=True,
        limit=1,
        source="SR5",
        page=309,
        bonus_support=BonusSupport.NO_EFFECT,
        flat_bonuses=(),
        raw_bonus=danger_sense.raw_bonus,
        unmodeled_effect_note=danger_sense.unmodeled_effect_note,
    )
    assert danger_sense.raw_bonus is not None and "surprise" in danger_sense.raw_bonus
