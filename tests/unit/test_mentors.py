"""Tests for `chummer5.data.mentors` (WP48's Mentor Spirit archetype loader). See that module's
docstring for the full 3-slot-model/bonus-classification reasoning this file exercises.
"""

from __future__ import annotations

from chummer5.data.mentors import (
    BonusSupport,
    ConditionalPool,
    FlatBonus,
    FreePower,
    MentorSpiritArchetype,
    count_by_support,
    gated_choice,
    load_mentors,
)

MENTORS = load_mentors()


def test_loads_exactly_the_confirmed_sr5_count() -> None:
    # mentors.xml has 81 <mentor> entries total; 16 are source == "SR5" -- see module docstring.
    assert len(MENTORS) == 16
    assert all(m.source == "SR5" for m in MENTORS)


def test_no_duplicate_ids_or_names() -> None:
    ids = [m.id for m in MENTORS]
    assert len(ids) == len(set(ids))
    names = [m.name for m in MENTORS]
    assert len(names) == len(set(names))


def test_every_archetype_has_both_gated_choices() -> None:
    for archetype in MENTORS:
        assert archetype.magician_choice.name.startswith("Magician:")
        assert archetype.adept_choice.name.startswith("Adept:")
        assert len(archetype.general_options) in (1, 2)


def test_gated_choice_resolves_by_magic_type() -> None:
    bear = next(m for m in MENTORS if m.name == "Bear")
    assert gated_choice(bear, "Magician") is bear.magician_choice
    assert gated_choice(bear, "Adept") is bear.adept_choice


def test_gated_choice_rejects_non_magic_active_type() -> None:
    bear = next(m for m in MENTORS if m.name == "Bear")
    try:
        gated_choice(bear, "Mundane")
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError")


def test_dog_general_bonus_is_flat() -> None:
    # Hand-checked: <bonus><specificskill><name>Tracking</name><bonus>2</bonus></specificskill>.
    dog = next(m for m in MENTORS if m.name == "Dog")
    assert len(dog.general_options) == 1
    general = dog.general_options[0]
    assert general.bonus_support == BonusSupport.FLAT_BONUS
    assert general.flat_bonuses[0].target_kind == "skill"
    assert general.flat_bonuses[0].target_name == "Tracking"
    assert general.flat_bonuses[0].value == 2


def test_cat_general_bonus_is_a_real_two_option_choice() -> None:
    # Rulebook p. 321: "All: +2 dice to either Gymnastics or Sneaking Tests (choose one)".
    cat = next(m for m in MENTORS if m.name == "Cat")
    assert len(cat.general_options) == 2
    names = {c.name for c in cat.general_options}
    assert names == {"+2 dice on Gymnastics Tests", "+2 dice on Sneaking Tests"}
    for option in cat.general_options:
        assert option.bonus_support == BonusSupport.FLAT_BONUS
        assert option.flat_bonuses[0].value == 2


def test_fire_bringer_and_wise_warrior_also_have_a_two_option_general_choice() -> None:
    fire_bringer = next(m for m in MENTORS if m.name == "Fire-Bringer")
    assert {c.name for c in fire_bringer.general_options} == {
        "+2 dice on Artisan Tests",
        "+2 dice on Alchemy Tests",
    }
    wise_warrior = next(m for m in MENTORS if m.name == "Wise Warrior")
    assert {c.name for c in wise_warrior.general_options} == {
        "+2 dice for Leadership skill tests",
        "+2 dice for Instruction skill tests",
    }


def test_bear_general_bonus_is_damage_resistance() -> None:
    # <bonus><damageresistance>2</damageresistance></bonus> -- WP48 left it unsupported; WP122
    # applies it into WP109's Damage Resistance pool (p. 321: "+2 dice for tests to resist damage
    # (not including Drain)").
    bear = next(m for m in MENTORS if m.name == "Bear")
    general = bear.general_options[0]
    assert general.bonus_support == BonusSupport.FLAT_BONUS
    assert general.flat_bonuses == (FlatBonus("damage_resistance", "", 2),)


def test_dragonslayer_general_bonus_is_a_social_skill_of_choice() -> None:
    # <bonus><selectskill skillcategory="Social Active"><val>2</val></selectskill></bonus> -- "+2
    # dice pool modifier for one social skill of choice" (p. 321), a choice since WP122.
    general = next(m for m in MENTORS if m.name == "Dragonslayer").general_options[0]
    assert general.bonus_support == BonusSupport.FLAT_BONUS
    assert general.flat_bonuses == (FlatBonus("skill", "", 2),)
    assert general.skill_choice_categories == ("Social Active",)


def test_eagle_general_bonus_grants_perception_and_an_allergy() -> None:
    # Compound <addqualities>+<specificskill> -- WP122 recognizes both halves.
    general = next(m for m in MENTORS if m.name == "Eagle").general_options[0]
    assert general.bonus_support == BonusSupport.FLAT_BONUS
    assert general.flat_bonuses == (FlatBonus("skill", "Perception", 2),)
    assert general.granted_qualities == (("Allergy (Common, Mild)", "Pollutants"),)


def test_mountain_magician_choice_is_flat_bonus() -> None:
    # The one Magician-slot <specificskill> with no <condition> child -- Counterspelling, +2.
    mountain = next(m for m in MENTORS if m.name == "Mountain")
    assert mountain.magician_choice.bonus_support == BonusSupport.FLAT_BONUS
    assert len(mountain.magician_choice.flat_bonuses) == 1
    bonus = mountain.magician_choice.flat_bonuses[0]
    assert bonus.target_kind == "skill"
    assert bonus.target_name == "Counterspelling"
    assert bonus.value == 2


def test_eagle_and_sea_and_thunderbird_magician_choices_are_conditional_pools() -> None:
    # <specificskill> with a <condition> child ("Spirits of Air") -- WP48 left it unsupported;
    # WP122 shows it as a conditional Summoning pool.
    for name, spirits in (
        ("Eagle", "Spirits of Air"),
        ("Sea", "Spirits of Water"),
        ("Thunderbird", "Spirits of Air"),
    ):
        choice = next(m for m in MENTORS if m.name == name).magician_choice
        assert choice.bonus_support == BonusSupport.FLAT_BONUS, name
        assert choice.conditional_pools == (
            ConditionalPool(("Summoning",), 2, f"summoning {spirits}"),
        )


def test_spell_category_choices_cover_spells_rituals_and_preparations() -> None:
    choice = next(m for m in MENTORS if m.name == "Bear").magician_choice
    assert choice.conditional_pools == (
        ConditionalPool(
            ("Spellcasting", "Ritual Spellcasting", "Alchemy"),
            2,
            "Health spells, preparations and rituals",
        ),
    )


def test_rat_magician_choice_is_verified_no_effect() -> None:
    # No <bonus> element at all in the raw XML -- confirmed a deliberate legacy-data choice
    # (harvesting reagents isn't a tracked dice pool), not an extraction gap.
    rat = next(m for m in MENTORS if m.name == "Rat")
    assert rat.magician_choice.bonus_support == BonusSupport.NO_EFFECT
    assert rat.magician_choice.flat_bonuses == ()


def test_every_adept_choice_grants_free_powers() -> None:
    # Every Adept-slot choice is <specificpower> -- WP122 grants them outside the PP budget.
    for archetype in MENTORS:
        assert archetype.adept_choice.bonus_support == BonusSupport.FLAT_BONUS, archetype.name
        assert archetype.adept_choice.free_powers, archetype.name
    wolf = next(m for m in MENTORS if m.name == "Wolf").adept_choice
    assert wolf.free_powers == (FreePower("Attribute Boost", 2, target_attributes=("AGI",)),)


def test_supported_vs_unsupported_counts_are_visible() -> None:
    # WP122: every slot is supported but Rat's reagent harvesting, which has no <bonus>.
    counts = count_by_support(MENTORS)
    assert counts[BonusSupport.FLAT_BONUS] == 50
    assert counts[BonusSupport.NO_EFFECT] == 1
    assert counts[BonusSupport.NOT_YET_SUPPORTED] == 0
    assert sum(counts.values()) == 51


def test_every_archetype_but_eagle_registers_its_disadvantage() -> None:
    for archetype in MENTORS:
        if archetype.name == "Eagle":  # its disadvantage is the granted Allergy
            assert archetype.unmodeled_effect_note is None
        else:
            assert archetype.unmodeled_effect_note, archetype.name


def test_archetype_fields_hand_checked_against_the_raw_xml() -> None:
    dog = next(m for m in MENTORS if m.name == "Dog")
    assert isinstance(dog, MentorSpiritArchetype)
    assert dog.id == "98785f59-5739-4998-b334-ec4501c75cf8"
    assert dog.source == "SR5"
    assert dog.page == 321
    assert dog.advantage.startswith("All: +2 dice for Tracking tests")
    assert "stubbornly loyal" in dog.disadvantage
