"""Tests for `chummer5.data.foci` (WP47's Foci loader). See that module's docstring for the full
Rating-scaled-cost/Availability, category-classification, and `<bonus>`-classification reasoning
this file exercises.
"""

from __future__ import annotations

from chummer5.data.foci import (
    BONDING_KARMA_PER_FORCE,
    FOCUS_MAX_RATING,
    BonusSupport,
    Focus,
    FocusFlatBonus,
    count_by_support,
    load_foci,
)

FOCI = load_foci()


def test_loads_exactly_the_confirmed_sr5_count() -> None:
    # gear.xml has 116 Foci entries total; 32 are source == "SR5" -- see module docstring.
    assert len(FOCI) == 32
    assert all(f.source == "SR5" for f in FOCI)


def test_no_duplicate_ids_or_names() -> None:
    ids = [f.id for f in FOCI]
    assert len(ids) == len(set(ids))
    names = [f.name for f in FOCI]
    assert len(names) == len(set(names))


def test_every_item_has_the_uniform_max_rating() -> None:
    assert all(f.availability_per_force > 0 for f in FOCI)
    assert FOCUS_MAX_RATING == 18


def test_focus_categories_match_the_rulebook_focus_table() -> None:
    by_category: dict[str, int] = {}
    for f in FOCI:
        by_category[f.focus_category] = by_category.get(f.focus_category, 0) + 1
    assert by_category == {
        "Enchanting": 2,
        "Metamagic": 4,
        "Power": 1,
        "Qi": 1,
        "Spell": 20,
        "Spirit": 3,
        "Weapon": 1,
    }


def test_bonding_karma_per_force_matches_the_focus_table() -> None:
    # Core rulebook p. 318 FOCUS TABLE.
    assert BONDING_KARMA_PER_FORCE == {
        "Enchanting": 3,
        "Metamagic": 3,
        "Power": 6,
        "Qi": 2,
        "Spell": 2,
        "Spirit": 2,
        "Weapon": 3,
    }
    by_name = {f.name: f for f in FOCI}
    assert by_name["Alchemical Focus"].bonding_karma_per_force == 3
    assert by_name["Power Focus"].bonding_karma_per_force == 6
    assert by_name["Qi Focus"].bonding_karma_per_force == 2
    assert by_name["Weapon Focus"].bonding_karma_per_force == 3


def test_hand_checked_fields_match_the_raw_xml() -> None:
    by_name = {f.name: f for f in FOCI}
    alchemical = by_name["Alchemical Focus"]
    assert alchemical.cost_per_force == 5000
    assert alchemical.availability_per_force == 3
    assert alchemical.focus_category == "Enchanting"

    power = by_name["Power Focus"]
    assert power.cost_per_force == 18000
    assert power.availability_per_force == 4
    assert power.focus_category == "Power"

    spellcasting_combat = by_name["Spellcasting Focus, Combat"]
    assert spellcasting_combat.focus_category == "Spell"
    assert spellcasting_combat.cost_per_force == 4000
    assert spellcasting_combat.availability_per_force == 3


def test_enchanting_foci_are_flat_bonus_with_rating_scaled_skill_target() -> None:
    # <specificskill><name>Alchemy/Disenchanting</name><bonus>Rating</bonus></specificskill>, plus
    # a stripped <selecttradition/> -- see module docstring.
    by_name = {f.name: f for f in FOCI}
    alchemical = by_name["Alchemical Focus"]
    assert alchemical.bonus_support == BonusSupport.FLAT_BONUS
    assert alchemical.flat_bonuses == (FocusFlatBonus(target_kind="skill", target_name="Alchemy"),)

    disenchanting = by_name["Disenchanting Focus"]
    assert disenchanting.bonus_support == BonusSupport.FLAT_BONUS
    assert disenchanting.flat_bonuses == (
        FocusFlatBonus(target_kind="skill", target_name="Disenchanting"),
    )


def test_metamagic_and_most_spell_and_spirit_foci_are_no_effect() -> None:
    # Each reduces to nothing after stripping a lone <selecttradition/>/<selecttext> -- their real
    # rulebook effect (Initiation grade, Counterspelling/Ritual Spellcasting/Sustaining/Summoning/
    # Banishing/Binding Tests) targets a mechanic this engine doesn't model. See module docstring.
    by_name = {f.name: f for f in FOCI}
    for name in (
        "Centering Focus",
        "Flexible Signature Focus",
        "Masking Focus",
        "Spell Shaping Focus",
        "Counterspelling Focus, Combat",
        "Ritual Spellcasting Focus, Combat",
        "Sustaining Focus, Combat",
        "Summoning Focus",
        "Banishing Focus",
        "Binding Focus",
    ):
        item = by_name[name]
        assert item.bonus_support == BonusSupport.NO_EFFECT, name
        assert item.flat_bonuses == ()


def test_power_qi_spellcasting_and_weapon_foci_are_not_yet_supported() -> None:
    # Power Focus (<skillattribute>, a blanket MAG-linked-skill bonus); Qi Focus (<selectpowers>, a
    # power-selection mechanism); Spellcasting Focus x5 (<spellcategory> with a <condition> child --
    # this engine's Improvement has no condition field); Weapon Focus (<weaponspecificdice>, no
    # weapon/combat dice-pool system). See module docstring.
    by_name = {f.name: f for f in FOCI}
    for name in (
        "Power Focus",
        "Qi Focus",
        "Spellcasting Focus, Combat",
        "Spellcasting Focus, Detection",
        "Spellcasting Focus, Health",
        "Spellcasting Focus, Illusion",
        "Spellcasting Focus, Manipulation",
        "Weapon Focus",
    ):
        item = by_name[name]
        assert item.bonus_support == BonusSupport.NOT_YET_SUPPORTED, name
        assert item.flat_bonuses == ()
        assert item.raw_bonus is not None


def test_supported_vs_unsupported_counts_are_visible() -> None:
    counts = count_by_support(FOCI)
    assert counts[BonusSupport.FLAT_BONUS] == 2
    assert counts[BonusSupport.NO_EFFECT] == 22
    assert counts[BonusSupport.NOT_YET_SUPPORTED] == 8
    assert sum(counts.values()) == 32


def test_focus_fields_hand_checked_against_the_raw_xml() -> None:
    alchemical = next(f for f in FOCI if f.name == "Alchemical Focus")
    assert alchemical == Focus(
        id="93d81bd8-52bf-4461-b2da-394aca4ce262",
        name="Alchemical Focus",
        focus_category="Enchanting",
        cost_per_force=5000,
        availability_per_force=3,
        bonding_karma_per_force=3,
        source="SR5",
        page=318,
        bonus_support=BonusSupport.FLAT_BONUS,
        flat_bonuses=(FocusFlatBonus(target_kind="skill", target_name="Alchemy"),),
        raw_bonus=alchemical.raw_bonus,
    )
    assert alchemical.raw_bonus is not None and "selecttradition" in alchemical.raw_bonus
