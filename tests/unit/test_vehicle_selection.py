"""Tests for `chummer5.engine.vehicles` (WP92's offerable catalog, `VehicleSelection` builder and
Condition Monitor), plus the shared-nuyen-pool wiring into `chummer5.engine.resources`.

Catalog-shape assertions run against the real 42-row loader output (the policy filters are the
whole point of the module, so stubbing them out would test nothing); purchase/budget assertions use
synthetic rows, mirroring `tests/unit/test_bioware_selection.py`'s "prove the mechanism in
isolation" pattern. Save/load round-tripping lives in `tests/unit/test_save_format.py`.
"""

from __future__ import annotations

import pytest

from chummer5.data.priorities import load_priorities
from chummer5.data.vehicles import Vehicle, load_vehicles
from chummer5.engine.resources import MAX_AVAILABILITY, create_resources_selection
from chummer5.engine.vehicles import (
    VEHICLE_CATALOG,
    VehicleSelection,
    build_vehicle_catalog,
    condition_monitor,
    create_vehicle_selection,
)

PRIORITIES = load_priorities()
ALL_VEHICLES = load_vehicles()
BY_NAME = {vehicle.name: vehicle for vehicle in VEHICLE_CATALOG}

# The 5 rows the Availability<=12 ruling removes, with their printed availability -- WP90 §2.
OVER_AVAILABILITY = {
    "Eurocar Westwind 3000 (Luxury Sports Car)": 13,
    "Mitsubishi Nightsky (Limousine)": 16,
    "Morgan Cutlass (Patrol Boat)": 14,
    "Nissan Hound (Transport Helicopter)": 13,
    "GMC Banshee (Thunderbird)": 24,
}
UNPRINTED = (
    "Horizon Flying Eye w/Flash-Pak and Grenade (Minidrone)",
    "Ocular Drone",
)


def _vehicle(name: str, cost: int, *, body: int = 4, is_drone: bool = False) -> Vehicle:
    return Vehicle(
        id=f"id-{name}",
        name=name,
        category="Drones: Mini" if is_drone else "Cars",
        cost=cost,
        availability=4,
        availability_restriction="",
        handling=4,
        handling_offroad=None,
        speed=3,
        speed_offroad=None,
        acceleration=1,
        body=body,
        armor=4,
        pilot=1,
        sensor=1,
        seats=None if is_drone else 2,
        is_drone=is_drone,
        hidden=False,
        source="SR5",
        page=462,
    )


# --- The offerable catalog -----------------------------------------------------------------------


def test_offerable_catalog_is_exactly_thirty_five_rows() -> None:
    # 42 SR5 rows - 5 over the Availability cap - 2 unprinted = 35 (WP90 §2).
    assert len(VEHICLE_CATALOG) == 35
    assert len([v for v in VEHICLE_CATALOG if not v.is_drone]) == 24
    assert len([v for v in VEHICLE_CATALOG if v.is_drone]) == 11


@pytest.mark.parametrize("name", sorted(OVER_AVAILABILITY))
def test_over_availability_rows_are_excluded_by_name(name: str) -> None:
    assert name not in BY_NAME
    # ...and they're excluded *because* of the cap, not incidentally.
    assert OVER_AVAILABILITY[name] > MAX_AVAILABILITY
    assert {v.name for v in ALL_VEHICLES if v.availability > MAX_AVAILABILITY} == set(
        OVER_AVAILABILITY
    )


@pytest.mark.parametrize("name", UNPRINTED)
def test_unprinted_rows_are_excluded_by_name(name: str) -> None:
    assert name in {v.name for v in ALL_VEHICLES}
    assert name not in BY_NAME


def test_every_retained_row_is_within_the_availability_cap() -> None:
    assert all(v.availability <= MAX_AVAILABILITY for v in VEHICLE_CATALOG)


def test_catalog_is_sorted_by_category_then_name() -> None:
    # The web layer groups rows by category straight off catalog order (same contract
    # build_starter_gear_catalog has), so this ordering is a real interface, not an incidental.
    keys = [(v.category, v.name) for v in VEHICLE_CATALOG]
    assert keys == sorted(keys)


def test_every_offered_row_is_affordable_at_resources_a() -> None:
    # WP90 §2: no second (cost) filter is needed, because the cap already removed everything a
    # Resources A budget couldn't reach. This pins that claim rather than trusting it.
    budget = PRIORITIES.resources["A"].nuyen
    assert max(v.cost for v in VEHICLE_CATALOG) <= budget


def test_applies_the_printed_handling_correction() -> None:
    # p. 465 prints Handling 3; vehicles.xml says 2 (see spec/decisions-log.md, 2026-08-01). The
    # loader stays literal, the catalog corrects.
    name = "Renault-Fiat Fokker Tundra-9 (Amphibious Jet)"
    assert next(v for v in ALL_VEHICLES if v.name == name).handling == 2
    assert BY_NAME[name].handling == 3
    # Nothing else about the row is touched by the correction.
    raw = next(v for v in ALL_VEHICLES if v.name == name)
    assert (BY_NAME[name].speed, BY_NAME[name].body, BY_NAME[name].cost) == (
        raw.speed,
        raw.body,
        raw.cost,
    )


def test_the_handling_correction_is_the_only_row_the_catalog_alters() -> None:
    raw_by_name = {v.name: v for v in ALL_VEHICLES}
    altered = [v.name for v in VEHICLE_CATALOG if v != raw_by_name[v.name]]
    assert altered == ["Renault-Fiat Fokker Tundra-9 (Amphibious Jet)"]


def test_build_vehicle_catalog_is_a_pure_function_of_its_input() -> None:
    assert build_vehicle_catalog(()) == ()
    stub = _vehicle("Test Car", 1_000)
    assert build_vehicle_catalog((stub,)) == (stub,)


# --- Condition Monitor ---------------------------------------------------------------------------


def test_vehicle_condition_monitor() -> None:
    # p. 199: 12 + ceil(Body/2). Ford Americar, Body 11 -> 12 + 6 = 18.
    assert condition_monitor(BY_NAME["Ford Americar (Sedan)"]) == 18
    # Ares Roadmaster, Body 18 -> 12 + 9 = 21.
    assert condition_monitor(BY_NAME["Ares Roadmaster (Armored Transport)"]) == 21


def test_drone_condition_monitor() -> None:
    # p. 199: 6 + ceil(Body/2). Steel Lynx, Body 6 -> 6 + 3 = 9.
    assert condition_monitor(BY_NAME["Steel Lynx Combat Drone (Large)"]) == 9
    # MCT Fly-Spy, Body 1 -> 6 + 1 = 7 (ceil, not floor -- the rounding case that matters).
    assert condition_monitor(BY_NAME["MCT Fly-Spy (Minidrone)"]) == 7
    # Shiawase Kanmushi, Body 0 -> 6 + 0 = 6, the catalog's floor.
    assert condition_monitor(BY_NAME["Shiawase Kanmushi (Microdrone)"]) == 6


def test_the_vehicle_drone_split_is_the_only_difference() -> None:
    # Same Body, different constant -- the whole content of the p. 199 split.
    assert condition_monitor(_vehicle("Car", 1, body=5)) == 15
    assert condition_monitor(_vehicle("Drone", 1, body=5, is_drone=True)) == 9


# --- Purchases -----------------------------------------------------------------------------------


def test_buys_a_vehicle_and_reports_its_cost() -> None:
    catalog = (_vehicle("Cheap Car", 10_000),)
    selection = create_vehicle_selection(["id-Cheap Car"], catalog, 20_000)
    assert selection == VehicleSelection(vehicles=catalog, nuyen_budget=20_000, nuyen_spent=10_000)


def test_repeats_are_allowed_because_a_rigger_buys_four_fly_spies() -> None:
    catalog = (_vehicle("Fly-Spy", 2_000, is_drone=True),)
    selection = create_vehicle_selection(["id-Fly-Spy"] * 4, catalog, 10_000)
    assert len(selection.vehicles) == 4
    assert selection.nuyen_spent == 8_000


def test_rejects_an_unknown_id() -> None:
    with pytest.raises(ValueError, match="not a vehicle catalog id"):
        create_vehicle_selection(["nope"], (_vehicle("Car", 1_000),), 10_000)


def test_an_excluded_row_is_rejected_as_an_unknown_id() -> None:
    # The catalog *is* the filter -- there's no second "is this offerable" check to forget.
    banshee = next(v for v in ALL_VEHICLES if v.name == "GMC Banshee (Thunderbird)")
    with pytest.raises(ValueError, match="not a vehicle catalog id"):
        create_vehicle_selection([banshee.id], VEHICLE_CATALOG, 5_000_000)


def test_rejects_a_spend_over_the_budget() -> None:
    catalog = (_vehicle("Pricey", 30_000),)
    with pytest.raises(ValueError, match="vehicle spend 30000 exceeds the nuyen budget of 20000"):
        create_vehicle_selection(["id-Pricey"], catalog, 20_000)


def test_an_empty_purchase_is_legal_and_costs_nothing() -> None:
    assert create_vehicle_selection([], VEHICLE_CATALOG, 0).nuyen_spent == 0


def test_vehicle_ids_round_trips_the_input() -> None:
    catalog = (_vehicle("A", 1_000), _vehicle("B", 2_000))
    ids = ["id-A", "id-B", "id-A"]
    assert list(create_vehicle_selection(ids, catalog, 10_000).vehicle_ids) == ids


# --- The shared Step Six nuyen pool ---------------------------------------------------------------


def test_vehicle_cost_spends_from_the_same_pool_as_gear() -> None:
    # p. 94's Step Six Gear Checklist names Vehicle(s)/Drones alongside gear and cyberware.
    selection = create_resources_selection("C", PRIORITIES, gear_names=(), vehicle_cost=20_000)
    assert selection.vehicle_cost == 20_000
    assert selection.nuyen_remaining == selection.nuyen_budget - 20_000


def test_a_vehicle_can_overrun_the_shared_budget() -> None:
    budget = PRIORITIES.resources["E"].nuyen
    with pytest.raises(ValueError, match=r"vehicles \(\d+\)"):
        create_resources_selection("E", PRIORITIES, gear_names=(), vehicle_cost=budget + 1)


def test_vehicle_cost_defaults_to_zero_so_pre_wp92_callers_are_unaffected() -> None:
    assert create_resources_selection("C", PRIORITIES, gear_names=()).vehicle_cost == 0
