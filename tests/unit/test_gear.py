"""Tests for `chummer5.data.gear` (WP21's gear/armor/weapon loaders) and
`chummer5.engine.resources.build_starter_gear_catalog` (the purchasable-catalog builder on top of
them). See both modules' docstrings for the full "flat-cost", `<hide/>`, and armor-stacking
reasoning this file exercises.
"""

from __future__ import annotations

from chummer5.data.gear import (
    Armor,
    Gear,
    RatingGear,
    Weapon,
    load_armor,
    load_gear,
    load_rating_gear,
    load_weapons,
    parse_rating_availability,
)
from chummer5.engine.resources import StarterGearItem, build_starter_gear_catalog

GEAR = load_gear()
ARMOR = load_armor()
WEAPONS = load_weapons()
RATING_GEAR = load_rating_gear()


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


# --- WP66: Rating-priced gear loader -------------------------------------------------------------


def test_loads_the_confirmed_rating_priced_count() -> None:
    # 120 SR5-sourced <gear> entries whose <cost> is a `Rating * N` formula -- the exact complement
    # of load_gear's flat-cost filter over the same file (the "120 Rating-formula excluded" figure
    # WP21's docstring already named).
    assert len(RATING_GEAR) == 120
    assert all(isinstance(g, RatingGear) for g in RATING_GEAR)
    assert {g.source for g in RATING_GEAR} == {"SR5"}


def test_rating_gear_carries_unit_cost_max_rating_and_avail() -> None:
    by_name = {g.name: g for g in RATING_GEAR}
    fake_sin = by_name["Fake SIN"]
    assert fake_sin.cost_per_rating == 2500
    assert fake_sin.max_rating == 6
    assert fake_sin.availability == "(Rating * 3)F"


def test_rating_gear_and_flat_gear_are_disjoint_over_the_same_file() -> None:
    # A gear entry is either flat-cost (load_gear) or rating-priced (load_rating_gear), never both.
    assert not ({g.name for g in RATING_GEAR} & {g.name for g in GEAR if g.cost != 0})


def test_parse_rating_availability_forms() -> None:
    # slope * rating + intercept; R/F suffix and surrounding parens ignored.
    assert parse_rating_availability("0") == (0, 0)
    assert parse_rating_availability("12F") == (0, 12)
    assert parse_rating_availability("Rating") == (1, 0)
    assert parse_rating_availability("(Rating)R") == (1, 0)
    assert parse_rating_availability("Rating * 2") == (2, 0)
    assert parse_rating_availability("(Rating * 3)F") == (3, 0)
    assert parse_rating_availability("(Rating + 2)R") == (1, 2)


def test_parse_rating_availability_rejects_modifiers() -> None:
    # A leading `+` marks an accessory added to a parent's availability, not a standalone value.
    assert parse_rating_availability("+Rating") is None
    assert parse_rating_availability("+(Rating * 2)") is None


# --- WP66: Rating-priced catalog builder ---------------------------------------------------------

FULL_CATALOG = build_starter_gear_catalog(GEAR, ARMOR, WEAPONS, RATING_GEAR)
FULL_BY_NAME = {item.name: item for item in FULL_CATALOG}


def test_catalog_includes_rating_priced_items_with_capped_max_rating() -> None:
    # Fake SIN's avail is (Rating * 3)F -> the offered range is clamped to rating 4 (=12F), even
    # though its <rating> cap is 6.
    fake_sin = FULL_BY_NAME["Fake SIN"]
    assert fake_sin.cost_per_rating == 2500
    assert fake_sin.max_rating == 4
    assert fake_sin.cost == 0  # a catalog entry has no price until a rating is picked
    assert fake_sin.rating is None


def test_catalog_includes_the_reported_missing_items() -> None:
    for name in ("Glasses", "Goggles", "Contacts", "Earbuds", "Headphones"):
        assert name in FULL_BY_NAME
        assert FULL_BY_NAME[name].cost_per_rating is not None


def test_catalog_excludes_rating_priced_foci_and_formulae() -> None:
    # The Rating(Force)-priced Foci/Formulae are owned by the dedicated Foci bonding system
    # (chummer5.engine.foci), not offered as plain gear. (The flat-cost "Spell Formula, X" entries
    # in the Formulae category are a different thing -- spell formulae, offered since WP21 -- so the
    # exclusion is scoped to rating-priced items, not the whole category.)
    assert all(
        item.category not in {"Foci", "Formulae"}
        for item in FULL_CATALOG
        if item.cost_per_rating is not None
    )
    assert "Power Focus" not in FULL_BY_NAME
    assert "Sustaining Focus, Combat" not in FULL_BY_NAME


def test_catalog_excludes_items_over_availability_cap_at_every_rating() -> None:
    # Plastic Explosive's avail is a flat 16F -- over 12 at every rating, so it's dropped entirely.
    assert "Plastic Explosive" not in FULL_BY_NAME
    # Foam Explosive is a flat 12F -- exactly on the cap, so it stays.
    assert "Foam Explosive" in FULL_BY_NAME


def test_rating_item_displaces_zero_cost_flat_namesake() -> None:
    # "Camera" is both a 0-cost Sensor-Functions component (flat) and the real Rating*100 Vision
    # Devices item -- the rating-priced one must win.
    camera = FULL_BY_NAME["Camera"]
    assert camera.cost_per_rating == 100
    assert camera.category == "Vision Devices"
