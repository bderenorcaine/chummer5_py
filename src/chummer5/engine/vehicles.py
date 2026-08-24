"""Vehicle/drone purchase & the one derived vehicle number (Phase P, WP92).

Composes WP91's literal `chummer5.data.vehicles` loader with WP9's shared Step Six nuyen budget
into a buildable stock-vehicle purchase, mirroring `chummer5.engine.bioware`'s
`create_*_selection` shape. Deliberately the *smallest* possible new subsystem: a purchase is a
catalog row and a price, nothing is installed into anything, and exactly one number is computed.

**Only stock, unmodified vehicles.** The 2026-07-21 ruling excludes vehicle/drone modifications
from this phase, and WP90 sized what that costs precisely: the whole SR5-core modification system
is a four-row table (p. 461), of which 2 rows are purchasable modifications. The consequential one
is the **Rigger Interface** (1,000Y, Avail 4): p. 265 says drones ship with it built in and "nearly
all vehicles need to have the interface added as an after-factory option," so a vehicle bought here
is one no rigger can jump into. That is recorded as an unmodeled effect (WP95), not worked around.

**Three policy filters, all of them here rather than in the loader** -- the same loader/policy split
`chummer5.data.gear` and `chummer5.engine.resources.build_starter_gear_catalog` already use:

- **Availability <= 12** (Project Overview's 2026-07-21 ruling). Removes 5 of the 42 SR5 rows, all
  of which had no business in a starting build anyway: the Westwind 3000 (13), Nightsky (16),
  Morgan Cutlass (14R), Nissan Hound (13R) and GMC Banshee (24F).
- **Two rows that appear in no printed table** (`_UNPRINTED_VEHICLE_NAMES`), mirroring WP42's
  `_UNPURCHASABLE_CYBERWARE_NAMES` precedent. `tests/unit/test_vehicles.py` derives this pair from
  the transcribed printed tables rather than taking it on faith.
- **One printed-stat correction** (`_PRINTED_HANDLING_CORRECTIONS`). `vehicles.xml` gives the
  Renault-Fiat Fokker Tundra-9 a Handling of 2 where p. 465 prints 3; there is exactly one Tundra-9
  row in the file across every sourcebook, so this is a transcription slip rather than a later
  book's reprint being preferred. The printed value wins (see `spec/decisions-log.md`'s 2026-08-01
  entry). This is a one-row exemption, **not** the start of a general "reconcile every catalog
  against its printed table" programme -- no other catalog in this project has ever been checked
  that exhaustively, and doing so isn't scheduled.

42 - 5 - 2 = **35 offerable rows** (24 vehicles + 11 drones). Every one is affordable within
Resources A's 450,000Y, so no second cost filter is needed.

**The one computed number: Condition Monitor** (p. 199) -- `12 + ceil(Body / 2)` for a vehicle,
`6 + ceil(Body / 2)` for a drone. Same `+ ceil(attribute / 2)` shape as the character-level
Physical/Stun monitors `chummer5.engine.derived` already computes, with a different constant and a
vehicle-vs-drone split. It is worth deriving because it is the one printed-page number a player
can't read off the catalog table; every other vehicle stat is a constant carried straight through
from the catalog row (WP90 §5: "record and display, derive nothing").

**Repeats are legal.** A rigger buying four MCT Fly-Spies is an ordinary purchase, so this follows
`create_resources_selection`'s `gear_names` precedent rather than the qualities/foci "can't pick
twice" one. Unlike gear, purchases are keyed by **catalog id**, matching every other post-WP21
catalog (cyberware, bioware, foci, spells): `StarterGearItem` is name-keyed only because it is a
synthesized cross-file catalog with no single id to key on, which doesn't apply here.

**`chummer5.io.legacy_import` needs no change, and that's deliberate rather than an omission.** It
passes `gear_names=()` and imports no Step Six gear at all (WP90 §6), so a legacy character's
`<vehicles>` node was never going to arrive through it. The corpus's one Priority-built stock-SR5
vehicle (`Wesson.chum5`'s Harley-Davidson Scorpion) is still useful as a *stat-block* oracle --
`tests/unit/test_vehicles.py` cross-checks it -- but its 7 Rigger 5.0 modifications mean its nuyen
ledger can never be reproduced from a stock purchase, so importing it would produce a character
whose budget silently disagreed with the legacy file's.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, replace

from chummer5.data.vehicles import Vehicle, load_vehicles
from chummer5.engine.resources import MAX_AVAILABILITY

# p. 199: "they have a Condition Monitor equal to 12 plus half their Body (rounded up) ... Drones
# are a different story and have a Condition Monitor equal to 6 plus half their Body."
BASE_VEHICLE_CONDITION_MONITOR = 12
BASE_DRONE_CONDITION_MONITOR = 6

# The 2 SR5-sourced rows that appear in no printed table (WP90 §2), excluded exactly the way WP42's
# `_UNPURCHASABLE_CYBERWARE_NAMES` excludes rows a player can't buy:
#   - `Horizon Flying Eye w/Flash-Pak and Grenade` -- a 2,500Y Chummer convenience bundle of the
#     2,000Y printed drone plus two pieces of gear. Offering it would sell a gear bundle this
#     engine has no way to itemize.
#   - `Ocular Drone` -- <page>453</page>, <cost>0</cost>: the *cyberware* ocular drone, which this
#     project already carries in its cyberware catalog as a `requires_parent` plugin. It is a
#     vehicle row only so the legacy app can give that implant a vehicle stat block.
_UNPRINTED_VEHICLE_NAMES = frozenset(
    {
        "Horizon Flying Eye w/Flash-Pak and Grenade (Minidrone)",
        "Ocular Drone",
    }
)

# vehicle name -> the printed on-road Handling. See module docstring; one row, and the loader-side
# test `test_vehicles.KNOWN_XML_DIVERGENCES` pins the same pair from the data side so this can't go
# stale silently. Typed to the one stat that actually diverges rather than a general
# field -> value mapping: a second correction, in a different field, should have to be written
# deliberately (and argued for in the decisions log) rather than dropped into an open-ended dict.
_PRINTED_HANDLING_CORRECTIONS: dict[str, int] = {
    # p. 465's AIRCRAFT table: R-F Fokker Tundra-9, HANDL 3. The XML says 2.
    "Renault-Fiat Fokker Tundra-9 (Amphibious Jet)": 3,
}


def condition_monitor(vehicle: Vehicle) -> int:
    """A vehicle's Condition Monitor: `12 + ceil(Body / 2)`, or `6 + ceil(Body / 2)` for a drone
    (p. 199). `(body + 1) // 2` is `ceil(body / 2)` for the non-negative Body every catalog row has
    -- the same regime `chummer5.engine.derived._ceil_div` covers for the character-level monitors.
    """
    base = BASE_DRONE_CONDITION_MONITOR if vehicle.is_drone else BASE_VEHICLE_CONDITION_MONITOR
    return base + (vehicle.body + 1) // 2


def build_vehicle_catalog(vehicles: Iterable[Vehicle] = ()) -> tuple[Vehicle, ...]:
    """The 35 offerable rows: WP91's 42, minus the 5 over the Availability cap and the 2 unprinted
    ones, with the one printed-stat correction applied. See module docstring for all three.

    Sorted by `(category, name)` so the web layer can group rows by category directly off catalog
    order without re-sorting itself -- the same contract `build_starter_gear_catalog` already has.
    """
    offered = []
    for vehicle in vehicles:
        if vehicle.name in _UNPRINTED_VEHICLE_NAMES:
            continue
        if vehicle.availability > MAX_AVAILABILITY:
            continue
        handling = _PRINTED_HANDLING_CORRECTIONS.get(vehicle.name)
        offered.append(vehicle if handling is None else replace(vehicle, handling=handling))
    return tuple(sorted(offered, key=lambda vehicle: (vehicle.category, vehicle.name)))


# Parsed once at import time (Project Overview's "parsed once at startup" rule), like every other
# catalog constant in this package.
VEHICLE_CATALOG: tuple[Vehicle, ...] = build_vehicle_catalog(load_vehicles())


@dataclass(frozen=True)
class VehicleSelection:
    """A validated set of purchased stock vehicles/drones and their combined nuyen cost.

    `vehicles` may contain the same `Vehicle` more than once (four Fly-Spies is one rigger's normal
    loadout), so it is a tuple of rows in purchase order, not a set.
    """

    vehicles: tuple[Vehicle, ...]
    nuyen_budget: int
    nuyen_spent: int

    @property
    def vehicle_ids(self) -> tuple[str, ...]:
        """The persistable inverse of `create_vehicle_selection`'s input -- mirrors
        `BiowareSelection.to_requests`, in the simplest shape a purchase with no player choice
        attached to it can have."""
        return tuple(vehicle.id for vehicle in self.vehicles)


def create_vehicle_selection(
    vehicle_ids: Iterable[str],
    catalog: Iterable[Vehicle] = VEHICLE_CATALOG,
    nuyen_budget: int = 0,
) -> VehicleSelection:
    """Build a `VehicleSelection`, validating the spend against `nuyen_budget`.

    Validates: every id resolves against `catalog` (which is the *offerable* catalog, so an
    over-Availability or unprinted row is rejected here as an unknown id rather than needing a
    second check); the total cost doesn't exceed `nuyen_budget`. Repeats are allowed -- see module
    docstring. Does not require the full budget to be spent, mirroring every other `create_*`
    function in this engine.

    `nuyen_budget` is the caller's own responsibility to resolve, the same way
    `create_cyberware_tree_selection`/`create_bioware_selection` take theirs: this function has no
    idea what else already spent from the shared Step Six pool. `chummer5.io.save_format
    .build_character` passes what gear/Lifestyle/cyberware/bioware left.
    """
    by_id = {vehicle.id: vehicle for vehicle in catalog}
    ids = list(vehicle_ids)

    unknown = sorted({vehicle_id for vehicle_id in ids if vehicle_id not in by_id})
    if unknown:
        raise ValueError(f"not a vehicle catalog id: {unknown}")

    selected = tuple(by_id[vehicle_id] for vehicle_id in ids)
    nuyen_spent = sum(vehicle.cost for vehicle in selected)
    if nuyen_spent > nuyen_budget:
        raise ValueError(f"vehicle spend {nuyen_spent} exceeds the nuyen budget of {nuyen_budget}")

    return VehicleSelection(
        vehicles=selected,
        nuyen_budget=nuyen_budget,
        nuyen_spent=nuyen_spent,
    )
