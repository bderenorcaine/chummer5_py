"""Loader for `legacy/Chummer/data/vehicles.xml`, restricted to `source == "SR5"` (WP91).

A literal XML->frozen-dataclass pass in the shape `chummer5.data.gear` established: this module
translates one file and knows nothing about policy. The two policy filters Phase P's research pass
(WP90) settled -- **Availability <= 12** (Project Overview's 2026-07-21 ruling) and the **2 rows
that are not printed in any book** -- live one layer up in `chummer5.engine.vehicles`, exactly as
`chummer5.data.gear` splits loader-vs-policy today. `load_vehicles()` therefore returns all **42**
SR5 rows (29 vehicles + 13 drones), so the count stays literal and testable.

**There are no formulas in this file's SR5 set.** WP90 checked every SR5-sourced row: `<cost>`,
`<avail>`, `<body>`, `<armor>`, `<pilot>`, `<sensor>`, `<accel>` and `<seats>` are bare integers,
and `<handling>`/`<speed>` are either a bare integer or the printed `on-road/off-road` pair (`4/3`,
`3/4`). No `Rating * N`, no `FixedValues(...)`, no `Variable(...)` anywhere -- so this phase needs
nothing like `chummer5.data.cyberware_formula`. Accordingly every field parser here **fails closed**
(raises `ValueError` naming the row and tag) rather than guessing: if a future data drop introduces
a formula, that is a change upstream wants a human to look at, not something to silently coerce.

**The `on-road/off-road` pair is split in the loader, not propagated as a string.** `vehicles.xml`
writes it as one `<handling>4/3</handling>`; `.chum5` writes it as two elements
(`<handling>4</handling><offroadhandling>3</offroadhandling>`). `handling_offroad`/`speed_offroad`
are `None` for the rows that print a single number, which is what the printed tables show (only the
Yamaha Growler prints a `speed` pair at all) -- the legacy engine's own save shape instead repeats
the on-road value, e.g. `Wesson.chum5`'s Scorpion carries `<speed>4</speed><offroadspeed>4</offroad
speed>` for an XML `<speed>4</speed>`. Treat `None` as "same as on-road".

**What this loader deliberately does not read.**

- **`<mods>`.** The 2026-07-21 ruling excludes vehicle/drone modifications from Phase P entirely,
  and WP90 sized what that costs precisely: the whole SR5-core modification system is a four-row
  table (p. 461), of which only 2 rows are purchasable modifications. The one consequence worth
  knowing is already derivable from `is_drone`: every SR5 drone ships with a Rigger Interface built
  in and no SR5 vehicle does (p. 265, and `vehicles.xml` agrees row-for-row), so under the ruling a
  bought *vehicle* is one no rigger can jump into. That gap is recorded in Project Overview's
  unmodeled-effects registry (WP95), not worked around here.
- **`<gears>`** (every row carries a bundled `Sensor Array`), **`<weaponmounts>`**, and the
  `R5`-sourced `*modslots` counts -- all modification-system surface, same ruling.
- **Matrix/Device Rating.** No SR5 `<vehicle>` row carries `<devicerating>` at all (the legacy
  engine defaults it to 1 when saving, cf. `Wesson.chum5`), and nothing downstream would read it.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

_DATA_DIR = Path(__file__).resolve().parents[3] / "legacy" / "Chummer" / "data"
DEFAULT_VEHICLES_PATH = _DATA_DIR / "vehicles.xml"

# MVP content scope: only entries carrying this <source> tag are loaded. See "MVP content scope" in
# Implementation Plan.md.
CORE_RULEBOOK_SOURCE = "SR5"

# `vehicles.xml` splits drones from vehicles by category alone: "Drones: Micro", "Drones: Mini",
# "Drones: Small", "Drones: Medium", "Drones: Large", "Drones: Anthro" (13 SR5 rows across the six),
# against 8 vehicle categories. The distinction is load-bearing downstream -- drones get a different
# Condition Monitor constant (6 vs 12, p. 199) and print no Seating (p. 466).
_DRONE_CATEGORY_PREFIX = "Drones:"

# An <avail> is a bare magnitude plus an optional R (Restricted) / F (Forbidden) legality marker --
# `0`, `8`, `5R`, `12F`. Same shape `chummer5.data.gear._AVAIL_RESTRICTION_RE` strips, kept as one
# fullmatch here because this file has no Rating-scaled availability to fall back on.
_AVAIL_RE = re.compile(r"(\d+)([RF]?)")

# A stat is a bare integer, or an `on-road/off-road` pair of them (<handling>, <speed> only).
_INT_RE = re.compile(r"\d+")
_PAIR_RE = re.compile(r"(\d+)/(\d+)")


@dataclass(frozen=True)
class Vehicle:
    """One SR5-sourced `<vehicle>` row -- a vehicle or a drone, per `is_drone`.

    `availability` is the numeric magnitude and `availability_restriction` the `R`/`F` legality
    marker (`""` when unrestricted), split the way `chummer5.data.gear` already treats the same
    field: only the magnitude matters for the Availability <= 12 cap, but the marker is what the
    printed table shows (`5R`, `12F`), so it survives for display.

    `handling_offroad`/`speed_offroad` are `None` for rows printing a single number; `seats` is
    `None` for drones, which print no Seating at all.
    """

    id: str
    name: str
    category: str
    cost: int
    availability: int
    availability_restriction: str
    handling: int
    handling_offroad: int | None
    speed: int
    speed_offroad: int | None
    acceleration: int
    body: int
    armor: int
    pilot: int
    sensor: int
    seats: int | None
    is_drone: bool
    hidden: bool
    source: str
    page: int


def _fail(name: str, tag: str, text: str | None) -> ValueError:
    return ValueError(
        f"vehicles.xml: {name!r} has an unparseable <{tag}> of {text!r}. Every SR5-sourced row was "
        "flat literals when this loader was written (WP90); a formula here means the data changed "
        "and needs a human, not a guess."
    )


def _int_field(elem: ET.Element, tag: str, name: str) -> int:
    text = elem.findtext(tag)
    if text is None or not _INT_RE.fullmatch(text.strip()):
        raise _fail(name, tag, text)
    return int(text.strip())


def _optional_int_field(elem: ET.Element, tag: str, name: str) -> int | None:
    """An absent tag is `None` (drones carry no `<seats>`); a present-but-unparseable one raises."""
    if elem.findtext(tag) is None:
        return None
    return _int_field(elem, tag, name)


def _pair_field(elem: ET.Element, tag: str, name: str) -> tuple[int, int | None]:
    """`<handling>4/3</handling>` -> `(4, 3)`; `<speed>4</speed>` -> `(4, None)`."""
    text = elem.findtext(tag)
    if text is None:
        raise _fail(name, tag, text)
    stripped = text.strip()
    pair = _PAIR_RE.fullmatch(stripped)
    if pair:
        return int(pair.group(1)), int(pair.group(2))
    if _INT_RE.fullmatch(stripped):
        return int(stripped), None
    raise _fail(name, tag, text)


def _availability(elem: ET.Element, name: str) -> tuple[int, str]:
    text = elem.findtext("avail")
    if text is None:
        raise _fail(name, "avail", text)
    match = _AVAIL_RE.fullmatch(text.strip())
    if not match:
        raise _fail(name, "avail", text)
    return int(match.group(1)), match.group(2)


def load_vehicles(xml_path: Path = DEFAULT_VEHICLES_PATH) -> tuple[Vehicle, ...]:
    """Parse `vehicles.xml`, restricted to `source == "SR5"` -- all 42 rows, no policy filtering.

    The Availability <= 12 cap and the 2 unprinted rows (`Ocular Drone`, the `Horizon Flying Eye
    w/Flash-Pak and Grenade` bundle) are `chummer5.engine.vehicles`' job, not this loader's; see the
    module docstring.
    """
    root = ET.parse(xml_path).getroot()
    vehicles_elem = root.find("vehicles")
    if vehicles_elem is None:
        return ()
    items = []
    for elem in vehicles_elem.findall("vehicle"):
        if elem.findtext("source") != CORE_RULEBOOK_SOURCE:
            continue
        name = elem.findtext("name", "")
        category = elem.findtext("category", "")
        availability, restriction = _availability(elem, name)
        handling, handling_offroad = _pair_field(elem, "handling", name)
        speed, speed_offroad = _pair_field(elem, "speed", name)
        items.append(
            Vehicle(
                id=elem.findtext("id", ""),
                name=name,
                category=category,
                cost=_int_field(elem, "cost", name),
                availability=availability,
                availability_restriction=restriction,
                handling=handling,
                handling_offroad=handling_offroad,
                speed=speed,
                speed_offroad=speed_offroad,
                acceleration=_int_field(elem, "accel", name),
                body=_int_field(elem, "body", name),
                armor=_int_field(elem, "armor", name),
                pilot=_int_field(elem, "pilot", name),
                sensor=_int_field(elem, "sensor", name),
                seats=_optional_int_field(elem, "seats", name),
                is_drone=category.startswith(_DRONE_CATEGORY_PREFIX),
                hidden=elem.find("hide") is not None,
                source=elem.findtext("source", ""),
                page=int(elem.findtext("page", "0")),
            )
        )
    return tuple(items)
