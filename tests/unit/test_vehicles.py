"""Tests for `chummer5.data.vehicles` (WP91's SR5 vehicle/drone loader).

The bulk of this file is the four printed catalog tables (SR5 pp. 462-466), transcribed from the
PDF and asserted stat-for-stat against `vehicles.xml`. That is a stronger check than spot-checking
one row per table, and it pays off twice:

- The printed tables cover **exactly 40** of the loader's 42 rows -- and the 2 they don't cover are
  precisely the 2 rows Phase P's research pass (WP90 §2) identified as unprintable and therefore
  unpurchasable (`Ocular Drone`, `Horizon Flying Eye w/Flash-Pak and Grenade`). The exclusion list
  the engine layer will carry is thus *derived* here, not asserted on faith.
- It found a real data error: `vehicles.xml` gives the Renault-Fiat Fokker Tundra-9 a Handling of 2
  where p. 465 prints 3. See `KNOWN_XML_DIVERGENCES` below.

Rows are keyed by their `vehicles.xml` name; the abbreviated name each printed table actually uses
("C-N Jackrabbit" for "Chrysler-Nissan Jackrabbit (Subcompact)") is in the chapter extract at
`spec/rulebooks/vehicles_and_riggers_chapter.md` §6, not duplicated here.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

import pytest
from tests.fixtures.mundane_chum5 import LEGACY_TESTFILES_DIR

from chummer5.data.vehicles import Vehicle, load_vehicles

VEHICLES = load_vehicles()
BY_NAME = {v.name: v for v in VEHICLES}

# --- The printed catalogs (SR5 pp. 462-466), transcribed from the PDF ----------------------------
#
# Column order, matching the book's own: handling, speed, accel, body, armor, pilot, sensor, seats,
# avail, cost. Handling/Speed/Avail stay *strings* so the printed on-road/off-road slash form
# ("4/3") and the R/F legality marker ("14R") are compared as printed rather than pre-parsed; a
# printed "—" Avail is "0". Seats is None where the table prints "—" (every drone).
_Row = tuple[str, str, int, int, int, int, int, int | None, str, int]

# fmt: off
PRINTED_GROUNDCRAFT: dict[str, _Row] = {
    "Dodge Scoot (Scooter)": ("4/3", "3", 1, 4, 4, 1, 1, 1, "0", 3_000),
    "Harley-Davidson Scorpion (Chopper)": ("4/3", "4", 2, 8, 9, 1, 2, 1, "0", 12_000),
    "Yamaha Growler (Off-Road Bike)": ("4/5", "3/4", 1, 5, 5, 1, 1, 1, "0", 5_000),
    "Suzuki Mirage (Racing Bike)": ("5/3", "6", 3, 5, 6, 1, 2, 1, "0", 8_500),
    "Chrysler-Nissan Jackrabbit (Subcompact)": ("4/3", "3", 2, 8, 4, 1, 2, 2, "0", 10_000),
    "Honda Spirit (Subcompact)": ("3/2", "4", 2, 8, 6, 1, 2, 2, "0", 12_000),
    "Hyundai Shin-Hyung (Sport Sedan)": ("5/4", "6", 3, 10, 6, 1, 2, 4, "0", 28_500),
    "Eurocar Westwind 3000 (Luxury Sports Car)": ("6/4", "7", 3, 10, 8, 3, 5, 2, "13", 110_000),
    "Ford Americar (Sedan)": ("4/3", "3", 2, 11, 6, 1, 2, 4, "0", 16_000),
    "Saeder-Krupp-Bentley Concordat (Luxury Sedan)": ("5/4", "5", 2, 12, 12, 2, 4, 4, "10", 65_000),
    "Mitsubishi Nightsky (Limousine)": ("4/3", "4", 2, 15, 15, 3, 5, 8, "16", 320_000),
    "Toyota Gopher (Heavy-Duty Pickup)": ("5/5", "4", 2, 14, 10, 1, 2, 3, "0", 25_000),
    "GMC Bulldog Step-Van (Van)": ("3/3", "3", 1, 16, 12, 1, 2, 6, "0", 35_000),
    "Rover 2072 (SUV)": ("5/5", "4", 2, 15, 12, 2, 4, 6, "10", 68_000),
    "Ares Roadmaster (Armored Transport)": ("3/3", "3", 1, 18, 18, 3, 3, 8, "8", 52_000),
}

PRINTED_WATERCRAFT: dict[str, _Row] = {
    "Samuvani Criscraft Otter (Sport Cruiser)": ("4", "3", 2, 12, 6, 2, 2, 8, "0", 21_000),
    "Yongkang Gala Trinity (Speedboat)": ("5", "6", 3, 10, 6, 1, 1, 3, "8", 37_000),
    "Morgan Cutlass (Patrol Boat)": ("5", "4", 2, 16, 10, 3, 5, 6, "14R", 96_000),
    "Proteus Lamprey (Sea Sled)": ("3", "2", 1, 6, 6, 1, 3, 4, "0", 14_000),
    "Vulkan Electronaut (Mini-sub)": ("3", "3", 1, 12, 10, 4, 4, 2, "10", 108_000),
}

PRINTED_AIRCRAFT: dict[str, _Row] = {
    "Artemis Industries Nightwing (Glider)": ("6", "3", 1, 4, 0, 1, 1, 1, "8", 20_000),
    "Cessna C750 (Twin-Prop Airplane)": ("3", "5", 3, 18, 4, 2, 2, 4, "8", 146_000),
    "Renault-Fiat Fokker Tundra-9 (Amphibious Jet)": ("3", "4", 3, 20, 10, 3, 3, 24, "12", 300_000),
    "Ares Dragon (Cargo Helicopter)": ("4", "4", 3, 22, 8, 3, 3, 18, "12", 355_000),
    "Nissan Hound (Transport Helicopter)": ("5", "4", 3, 16, 16, 2, 4, 12, "13R", 425_000),
    "Northrup Wasp (Autogyro)": ("5", "5", 3, 10, 8, 3, 3, 1, "12R", 86_000),
    "Ares Venture (LAV)": ("5", "7", 4, 16, 14, 4, 4, 6, "12F", 400_000),
    "GMC Banshee (Thunderbird)": ("6", "8", 4, 20, 18, 4, 6, 12, "24F", 2_500_000),
    "Federated Boeing Commuter (Tilt-Wing Airplane)": ("3", "3", 3, 16, 8, 3, 3, 30, "10", 350_000),
}

PRINTED_DRONES: dict[str, _Row] = {
    "Shiawase Kanmushi (Microdrone)": ("4", "2", 1, 0, 0, 3, 3, None, "8", 1_000),
    "Sikorsky-Bell Microskimmer (Microdrone)": ("3", "3", 1, 0, 0, 3, 3, None, "6", 1_000),
    "MCT Fly-Spy (Minidrone)": ("4", "3", 2, 1, 0, 3, 3, None, "8", 2_000),
    "Horizon Flying Eye (Minidrone)": ("4", "3", 2, 1, 0, 3, 3, None, "8", 2_000),
    "Aztechnology Crawler (Small)": ("4", "3", 1, 3, 3, 4, 3, None, "4", 4_000),
    "Lockheed Optic-X2 (Small)": ("4", "4", 3, 2, 2, 3, 3, None, "10", 21_000),
    "Ares Duelist (Medium)": ("3", "3", 1, 4, 4, 3, 3, None, "5R", 4_500),
    "GM-Nissan Doberman (Medium)": ("5", "3", 1, 4, 4, 3, 3, None, "4R", 5_000),
    "MCT-Nissan Roto-drone (Medium)": ("4", "4", 2, 4, 4, 3, 3, None, "6", 5_000),
    "Cyberspace Designs Dalmatian (Large)": ("5", "5", 3, 5, 5, 3, 3, None, "6R", 10_000),
    "Steel Lynx Combat Drone (Large)": ("5", "4", 2, 6, 12, 3, 3, None, "10R", 25_000),
}
# fmt: on

PRINTED_TABLES: dict[str, _Row] = {
    **PRINTED_GROUNDCRAFT,
    **PRINTED_WATERCRAFT,
    **PRINTED_AIRCRAFT,
    **PRINTED_DRONES,
}

# The one place `vehicles.xml` and the printed page disagree, found by the exhaustive comparison
# below. p. 465's AIRCRAFT table prints the R-F Fokker Tundra-9 at Handling 3; the XML row (whose
# own <page>464</page> points at that very table) says 2. There is no second Tundra-9 row in the
# file, in any sourcebook, so this isn't a later-book reprint being preferred -- it's a plain data
# error. The loader stays literal (it reports what the XML says); the correction to the printed
# value lives in the engine's catalog layer, where policy belongs. See
# spec/rulebooks/learnings/phase-p.md and spec/decisions-log.md's 2026-08-01 entry.
# Keyed (xml name, stat) -> (printed value, xml value).
KNOWN_XML_DIVERGENCES: dict[tuple[str, str], tuple[str, str]] = {
    ("Renault-Fiat Fokker Tundra-9 (Amphibious Jet)", "handling"): ("3", "2"),
}


def _as_printed(vehicle: Vehicle) -> dict[str, str]:
    """The loader's own fields, rendered back into the printed table's notation."""
    handling = str(vehicle.handling)
    if vehicle.handling_offroad is not None:
        handling = f"{vehicle.handling}/{vehicle.handling_offroad}"
    speed = str(vehicle.speed)
    if vehicle.speed_offroad is not None:
        speed = f"{vehicle.speed}/{vehicle.speed_offroad}"
    return {
        "handling": handling,
        "speed": speed,
        "accel": str(vehicle.acceleration),
        "body": str(vehicle.body),
        "armor": str(vehicle.armor),
        "pilot": str(vehicle.pilot),
        "sensor": str(vehicle.sensor),
        "seats": str(vehicle.seats),
        "avail": f"{vehicle.availability}{vehicle.availability_restriction}",
        "cost": str(vehicle.cost),
    }


# --- Counts and the SR5 filter -------------------------------------------------------------------


def test_loads_exactly_the_confirmed_sr5_row_count() -> None:
    # 42 of vehicles.xml's 380 <vehicle> rows are SR5-sourced (WP90 §2). The loader returns all of
    # them; the Availability<=12 cap and the 2 unprinted exclusions are the engine layer's job.
    assert len(VEHICLES) == 42


def test_vehicle_drone_split() -> None:
    assert len([v for v in VEHICLES if not v.is_drone]) == 29
    assert len([v for v in VEHICLES if v.is_drone]) == 13


def test_every_row_is_sr5_sourced() -> None:
    assert {v.source for v in VEHICLES} == {"SR5"}


def test_names_are_unique_so_a_name_keyed_catalog_is_safe() -> None:
    assert len(BY_NAME) == len(VEHICLES)


def test_drones_carry_no_seating_and_vehicles_all_do() -> None:
    # p. 466's DRONES table prints "—" in the Seats column for every row; every vehicle table
    # prints a number.
    assert all(v.seats is None for v in VEHICLES if v.is_drone)
    assert all(v.seats is not None for v in VEHICLES if not v.is_drone)


# --- Against the printed tables ------------------------------------------------------------------


@pytest.mark.parametrize("xml_name", sorted(PRINTED_TABLES))
def test_every_printed_row_matches_the_xml(xml_name: str) -> None:
    handling, speed, accel, body, armor, pilot, sensor, seats, avail, cost = PRINTED_TABLES[
        xml_name
    ]
    expected = {
        "handling": handling,
        "speed": speed,
        "accel": str(accel),
        "body": str(body),
        "armor": str(armor),
        "pilot": str(pilot),
        "sensor": str(sensor),
        "seats": str(seats),
        "avail": avail,
        "cost": str(cost),
    }
    actual = _as_printed(BY_NAME[xml_name])
    for stat, printed in expected.items():
        divergence = KNOWN_XML_DIVERGENCES.get((xml_name, stat))
        if divergence is not None:
            assert (printed, actual[stat]) == divergence
            continue
        assert actual[stat] == printed, f"{xml_name} {stat}"


def test_the_printed_tables_cover_every_row_except_the_two_unprintable_ones() -> None:
    # WP90 §2: the only two SR5-sourced rows with no printed entry are a Chummer convenience bundle
    # and the cyberware Ocular Drone's vehicle stat block. Deriving the pair from the transcribed
    # tables is what makes the engine layer's exclusion list an observation rather than a claim.
    assert set(BY_NAME) - set(PRINTED_TABLES) == {
        "Horizon Flying Eye w/Flash-Pak and Grenade (Minidrone)",
        "Ocular Drone",
    }


def test_the_two_unprintable_rows_are_what_wp90_described() -> None:
    bundle = BY_NAME["Horizon Flying Eye w/Flash-Pak and Grenade (Minidrone)"]
    printed = BY_NAME["Horizon Flying Eye (Minidrone)"]
    # A 2,500Y bundle of the 2,000Y printed drone plus two pieces of gear -- same stat block.
    assert bundle.cost == 2_500
    assert printed.cost == 2_000
    assert (bundle.body, bundle.armor, bundle.pilot, bundle.sensor) == (
        printed.body,
        printed.armor,
        printed.pilot,
        printed.sensor,
    )
    ocular = BY_NAME["Ocular Drone"]
    # <page>453</page> is the *cyberware* chapter -- this row exists only so the legacy app can give
    # that implant a vehicle stat block. It's the file's one <hide/> SR5 row, and costs nothing.
    assert (ocular.page, ocular.cost, ocular.hidden) == (453, 0, True)
    assert [v.name for v in VEHICLES if v.hidden] == ["Ocular Drone"]


def test_the_tundra_9_divergence_is_the_only_one() -> None:
    # Guards the KNOWN_XML_DIVERGENCES list itself: if a data drop fixes the Handling, this fails
    # loudly rather than leaving a stale exemption in place.
    assert BY_NAME["Renault-Fiat Fokker Tundra-9 (Amphibious Jet)"].handling == 2
    assert len(KNOWN_XML_DIVERGENCES) == 1


# --- Field parsing -------------------------------------------------------------------------------


def test_splits_the_on_road_off_road_pair() -> None:
    growler = BY_NAME["Yamaha Growler (Off-Road Bike)"]
    # The only SR5 row printing a pair in *both* columns (p. 462).
    assert (growler.handling, growler.handling_offroad) == (4, 5)
    assert (growler.speed, growler.speed_offroad) == (3, 4)


def test_a_single_printed_number_leaves_the_offroad_value_none() -> None:
    scorpion = BY_NAME["Harley-Davidson Scorpion (Chopper)"]
    assert (scorpion.handling, scorpion.handling_offroad) == (4, 3)
    assert (scorpion.speed, scorpion.speed_offroad) == (4, None)
    # Watercraft/aircraft/drones print one Handling number, never a pair.
    assert all(v.handling_offroad is None for v in VEHICLES if v.is_drone)


def test_availability_splits_magnitude_from_the_legality_marker() -> None:
    scoot = BY_NAME["Dodge Scoot (Scooter)"]
    assert (scoot.availability, scoot.availability_restriction) == (0, "")
    duelist = BY_NAME["Ares Duelist (Medium)"]
    assert (duelist.availability, duelist.availability_restriction) == (5, "R")
    venture = BY_NAME["Ares Venture (LAV)"]
    assert (venture.availability, venture.availability_restriction) == (12, "F")
    lynx = BY_NAME["Steel Lynx Combat Drone (Large)"]
    assert (lynx.availability, lynx.availability_restriction) == (10, "R")


_TEMPLATE = """
<vehicle>
  <id>x</id><name>Test Rig</name><category>Cars</category><source>SR5</source><page>1</page>
  <cost>{cost}</cost><avail>{avail}</avail><handling>{handling}</handling><speed>3</speed>
  <accel>1</accel><body>4</body><armor>4</armor><pilot>1</pilot><sensor>1</sensor><seats>2</seats>
</vehicle>
"""


def _write_xml(tmp_path: Path, **fields: str) -> Path:
    path = tmp_path / "vehicles.xml"
    body = _TEMPLATE.format(**{"cost": "3000", "avail": "8", "handling": "4", **fields})
    path.write_text(f"<chummer><vehicles>{body}</vehicles></chummer>", encoding="utf-8")
    return path


def test_fails_closed_on_a_rating_scaled_cost(tmp_path: Path) -> None:
    # No SR5-sourced row has a formula anywhere today (WP90 §2). If one appears, the loader must
    # refuse rather than coerce -- a silently-dropped or silently-zeroed price is worse than a
    # crash pointing at the row.
    with pytest.raises(ValueError, match="Test Rig.*<cost>"):
        load_vehicles(_write_xml(tmp_path, cost="Rating * 2500"))


def test_fails_closed_on_an_unparseable_availability(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="Test Rig.*<avail>"):
        load_vehicles(_write_xml(tmp_path, avail="(Rating * 3)R"))


def test_fails_closed_on_an_unparseable_handling(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="Test Rig.*<handling>"):
        load_vehicles(_write_xml(tmp_path, handling="4/3/2"))


# --- Against real legacy-computed output ---------------------------------------------------------


def test_scorpion_matches_wessons_legacy_computed_vehicle_node() -> None:
    """`Wesson.chum5` (Human Adept, Priority-built) is the corpus's one stock-SR5-vehicle purchase
    (WP90 §6) -- real legacy-computed output for a row this loader also reads. Its 7 modifications
    are all Rigger 5.0 content this project doesn't model, but they change none of the base stats
    asserted here (a stock Scorpion and Wesson's modified one agree stat-for-stat)."""
    root = ET.parse(LEGACY_TESTFILES_DIR / "Wesson.chum5").getroot()
    node = next(
        v
        for v in root.iter("vehicle")
        if (v.findtext("name") or "") == "Harley-Davidson Scorpion (Chopper)"
    )
    scorpion = BY_NAME["Harley-Davidson Scorpion (Chopper)"]
    # A saved vehicle carries both: <id> is the catalog row's id, <guid> the purchase instance's.
    assert node.findtext("id") == scorpion.id
    assert node.findtext("guid") != scorpion.id
    assert node.findtext("category") == scorpion.category
    assert int(node.findtext("cost", "")) == scorpion.cost
    assert int(node.findtext("avail", "")) == scorpion.availability
    assert int(node.findtext("body", "")) == scorpion.body
    assert int(node.findtext("armor", "")) == scorpion.armor
    assert int(node.findtext("pilot", "")) == scorpion.pilot
    assert int(node.findtext("sensor", "")) == scorpion.sensor
    assert int(node.findtext("accel", "")) == scorpion.acceleration
    assert int(node.findtext("seats", "")) == scorpion.seats
    assert int(node.findtext("handling", "")) == scorpion.handling
    assert int(node.findtext("offroadhandling", "")) == scorpion.handling_offroad
    assert int(node.findtext("speed", "")) == scorpion.speed
    # The legacy save repeats the on-road value when the XML prints a single number; this loader
    # leaves the off-road field None and means the same thing (see the module docstring).
    assert scorpion.speed_offroad is None
    assert int(node.findtext("offroadspeed", "")) == scorpion.speed
    assert int(node.findtext("page", "")) == scorpion.page
