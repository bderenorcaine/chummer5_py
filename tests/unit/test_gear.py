"""Tests for `chummer5.data.gear` (WP21's gear/armor/weapon loaders) and
`chummer5.engine.resources.build_starter_gear_catalog` (the purchasable-catalog builder on top of
them). See both modules' docstrings for the full "flat-cost", `<hide/>`, and armor-stacking
reasoning this file exercises.
"""

from __future__ import annotations

from chummer5.data.gear import Armor, Gear, Weapon, load_armor, load_gear, load_weapons
from chummer5.engine.resources import StarterGearItem, build_starter_gear_catalog

GEAR = load_gear()
ARMOR = load_armor()
WEAPONS = load_weapons()


# --- Data loaders --------------------------------------------------------------------------------


def test_loads_exactly_the_confirmed_flat_cost_counts() -> None:
    # 266 gear + 11 armor + 134 weapons = 411 -- see chummer5.data.gear's module docstring for the
    # full derivation (391/12/134 SR5-sourced entries, minus Rating/FixedValues/Variable/"+N"
    # costs).
    assert len(GEAR) == 266
    assert len(ARMOR) == 11
    assert len(WEAPONS) == 134


def test_excludes_rating_scaled_gear_cost() -> None:
    # Fake SIN's <cost> is "Rating * 2500" -- a formula, not a flat integer.
    assert "Fake SIN" not in {g.name for g in GEAR}


def test_excludes_fixedvalues_gear_cost() -> None:
    assert "Custom Commlink" not in {g.name for g in GEAR}


def test_excludes_variable_cost_gear_and_armor() -> None:
    assert "Custom Item" not in {g.name for g in GEAR}
    assert "Clothing" not in {a.name for a in ARMOR}


def test_excludes_cost_modifier_shorthand() -> None:
    # Card Reader's only entry has a "+50" cost (added to a parent's cost, not standalone) -- it
    # never appears in the flat-cost catalog. Biometric Reader has *two* SR5 entries with the same
    # name -- a "+200" modifier (excluded) and a genuine flat-cost 200 accessory (kept) -- so it's
    # a poor example of "always excluded" and is checked separately below.
    names = {g.name for g in GEAR}
    assert "Card Reader" not in names


def test_keeps_the_flat_cost_entry_when_a_name_also_has_a_cost_modifier_variant() -> None:
    by_name = {g.name: g for g in GEAR}
    assert by_name["Biometric Reader"].cost == 200


def test_every_flat_gear_entry_is_sr5_sourced() -> None:
    assert {g.source for g in GEAR} == {"SR5"}
    assert {a.source for a in ARMOR} == {"SR5"}
    assert {w.source for w in WEAPONS} == {"SR5"}


def test_hand_checked_flat_costs_match_the_xml() -> None:
    by_name = {g.name: g for g in GEAR}
    assert by_name["Meta Link"].cost == 100
    assert by_name["Meta Link"].category == "Commlinks"
    assert by_name["Certified Credstick, Standard"].cost == 5

    armor_by_name = {a.name: a for a in ARMOR}
    assert armor_by_name["Armor Jacket"].cost == 1000
    assert armor_by_name["Armor Jacket"].armor_rating == 12
    assert armor_by_name["Armor Jacket"].armor_stacks is False

    weapon_by_name = {w.name: w for w in WEAPONS}
    assert weapon_by_name["Ares Predator V"].cost == 725
    assert weapon_by_name["Combat Knife"].cost == 300


def test_marks_additive_stacking_armor() -> None:
    by_name = {a.name: a for a in ARMOR}
    assert by_name["Helmet"].armor_stacks is True
    assert by_name["Helmet"].armor_rating == 2
    assert by_name["Ballistic Shield"].armor_stacks is True
    assert by_name["Ballistic Shield"].armor_rating == 6
    assert by_name["Riot Shield"].armor_stacks is True
    # A normal, single-rating armor item is not marked as stacking.
    assert by_name["Armor Vest"].armor_stacks is False


def test_marks_hidden_weapon_profiles() -> None:
    weapon_by_name = {w.name: w for w in WEAPONS}
    # Ballistic Shield's weapon-profile entry (cost 0, auto-granted by buying the armor item) is
    # hidden; the armor item itself has no equivalent concept.
    assert weapon_by_name["Ballistic Shield"].hidden is True
    assert weapon_by_name["Ballistic Shield"].cost == 0
    assert weapon_by_name["Ares Predator V"].hidden is False


# --- Catalog builder -----------------------------------------------------------------------------


def test_catalog_excludes_additive_stacking_armor() -> None:
    catalog_names = {item.name for item in build_starter_gear_catalog(GEAR, ARMOR, WEAPONS)}
    assert "Helmet" not in catalog_names
    assert "Ballistic Shield" not in catalog_names
    assert "Riot Shield" not in catalog_names


def test_catalog_resolves_hidden_weapon_profile_collisions_by_keeping_the_real_price() -> None:
    catalog = build_starter_gear_catalog(GEAR, ARMOR, WEAPONS)
    by_name = {item.name: item for item in catalog}
    # Ballistic Shield/Riot Shield themselves are excluded (armor_stacks), but Grapple Gun and
    # Micro Flare Launcher are real, purchasable gear items that also have a 0-cost hidden weapon
    # profile in weapons.xml -- the catalog must keep the real price, not silently pick 0 or crash
    # on the collision.
    assert by_name["Grapple Gun"].cost == 500
    assert by_name["Micro Flare Launcher"].cost == 175


def test_catalog_resolves_internal_gear_collision() -> None:
    # Vision Magnification exists both as a real 250-cost accessory and as a 0-cost sensor-housing
    # component slot (gated behind a <required> parent) -- same name, same file, different cost.
    catalog = build_starter_gear_catalog(GEAR, ARMOR, WEAPONS)
    by_name = {item.name: item for item in catalog}
    assert by_name["Vision Magnification"].cost == 250


def test_catalog_is_sorted_by_category_then_name() -> None:
    catalog = build_starter_gear_catalog(GEAR, ARMOR, WEAPONS)
    keys = [(item.category or "", item.name) for item in catalog]
    assert keys == sorted(keys)


def test_catalog_has_no_duplicate_names() -> None:
    catalog = build_starter_gear_catalog(GEAR, ARMOR, WEAPONS)
    names = [item.name for item in catalog]
    assert len(names) == len(set(names))


def test_catalog_carries_category_and_armor_rating() -> None:
    catalog = build_starter_gear_catalog(GEAR, ARMOR, WEAPONS)
    by_name = {item.name: item for item in catalog}
    armor_jacket = by_name["Armor Jacket"]
    assert armor_jacket.category == "Armor"
    assert armor_jacket.armor_rating == 12

    meta_link = by_name["Meta Link"]
    assert meta_link.category == "Commlinks"
    assert meta_link.armor_rating is None


def test_empty_inputs_produce_an_empty_catalog() -> None:
    assert build_starter_gear_catalog() == ()


def test_starter_gear_item_still_constructible_with_only_name_and_cost() -> None:
    # Every pre-WP21 caller/test builds a bare StarterGearItem(name, cost) -- both new fields must
    # default so that keeps working unchanged.
    item = StarterGearItem("Widget", 42)
    assert item.category is None
    assert item.armor_rating is None


def test_gear_dataclass_fields_are_accessible() -> None:
    # Smoke test that the three dataclasses actually carry the fields their type hints promise --
    # guards against a future refactor silently dropping one.
    gear = next(g for g in GEAR if g.name == "Meta Link")
    assert isinstance(gear, Gear)
    assert gear.id
    assert gear.page > 0

    armor = next(a for a in ARMOR if a.name == "Armor Jacket")
    assert isinstance(armor, Armor)
    assert armor.id

    weapon = next(w for w in WEAPONS if w.name == "Combat Knife")
    assert isinstance(weapon, Weapon)
    assert weapon.id
