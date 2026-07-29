"""Capacity/subsystem-aware loader for `legacy/Chummer/data/cyberware.xml` (WP37 -- Phase K's data
WP, following WP36's formula resolver and preceding WP38's purchase tree).

**This module is additive to `chummer5.data.cyberware`, not a replacement for it.** WP31's
`load_cyberware()` keeps its exact contract -- 60 flat-cost/flat-Essence `Cyberware` rows, unchanged
fields, unchanged call sites (WP32's selection engine, WP33's legacy import, WP34's UI, WP35's
fixtures all still consume it). `load_cyberware_entries()` here is the *second, explicitly-named
loading path* WP37's plan entry asked for: the **complete 87-entry SR5 set**, including the 27
rating-scaled items WP31 filters out, with `<capacity>`, `<allowsubsystems>`, `<subsystems>` and
`<requireparent>` captured so WP38 can build a real purchase tree. Nothing in this module changes
what any already-shipped code sees.

## Why a sibling type (`CyberwareEntry`) rather than widening `Cyberware`

WP37's entry left this open ("widen `Cyberware` (or a new sibling type -- decide and document)").
Widening in place is impossible without breaking WP31's contract: `Cyberware.cost` is an `int` and
`Cyberware.essence_cost` a `Decimal`, and a rating-scaled row (Cybereyes Basic System's
`4000 * Rating - 2000 * number(Rating > 1)`) has no single value for either until a rating is
chosen. `CyberwareEntry` therefore carries **parsed `CyberwareFormula` objects** for `cost`,
`essence_cost`, `capacity_budget` and `capacity_cost` -- one uniform shape for flat and
rating-scaled rows alike, since WP36's `LITERAL` kind resolves a flat value at any rating.

**Parsed at load, resolved per purchase** -- the other choice WP37's entry left open. Parsing is
where data drift should surface (an unrecognized formula raises `UnsupportedCyberwareFormulaError`
at load, not deep inside a purchase), and resolving cannot happen at load time anyway because the
rating isn't known yet. This is exactly what WP36's two-function API (`parse_cyberware_formula` for
the compile step, `CyberwareFormula.resolve` for the evaluate step) was shaped for.

Placing it in its own module, rather than appending to `chummer5.data.cyberware`, follows WP36's own
precedent and reasoning: that module is dense WP31-era filter/classifier documentation whose every
sentence is about the flat-only catalog, and interleaving a second, wider catalog's rules into it
would make both harder to read. `BonusSupport`, `CyberwareFlatBonus` and `classify_bonus` are
imported from there rather than re-implemented -- the `<bonus>` grammar is identical (same file,
same rows), so `chummer5.data.bioware`'s "reuse `BonusSupport`, re-implement the classifier"
split does not apply here; there is nothing to re-implement.

## `<capacity>`: budget vs. cost vs. bundled-free, confirmed against the legacy C#

The rulebook rule (`spec/rulebooks/learnings/phase-k.md`, pre-Phase-K entry, p. 29100-29106): a
bare Capacity value is the item's **budget** as a parent; a bracketed one is its **cost** as a
plugin. `Cyberware.CapacityRemaining` in `legacy/Chummer/Backend/Equipment/Cyberware.cs` confirms
the exact edge behaviour this module encodes, rather than leaving it inferred:

- A purely bracketed `<capacity>` gives the item **zero** budget of its own -- that method's two
  branches are `Capacity.Contains("/[")` and `!Capacity.Contains('[')`, and a `[N]`-only value
  matches neither, so it falls through and returns `0`. This is what makes the Cyber Implant Weapon
  layer a genuine problem rather than a third nesting level for free -- see below.
- A child whose Capacity is `*` contributes `0` to its parent's spend ("`if (strCapacity == "*")
  strCapacity = "0"`") -- the `bundled_free` case.
- The combined `budget/[cost]` form the legacy engine also parses **does not occur in any SR5
  entry** (checked across all 87: no `<capacity>` contains `/`). `_parse_capacity` raises on it
  rather than guessing, so a data update that introduces one fails loudly.

Every SR5 entry has a `<capacity>` tag (87 of 87), so "absent" is not a case this data set
exercises; the loader still handles it as "no budget, no cost."

## The parent/plugin split, re-verified against the full data set (WP37's own re-confirmation duty)

The Phase K intro's exploratory survey said "**29 of the 87 SR5 entries carry
`<allowsubsystems>`**: 16 Cyberlimb variants / 2 Cybereyes+Cyberears / 11 Cyber Implant Weapon."
Re-derived here over the complete file: **exact, all three numbers**. 50 entries carry a bracketed
`<capacity>` (i.e. are installable as plugins); 11 of those are the Cyber Implant Weapons, which are
both. The 19 remaining entries are standalone-only (bare `<capacity>0</capacity>`, no
`<allowsubsystems>`) -- Bone Lacing, Datajack, Wired Reflexes, Muscle Replacement and friends.

**The Cyber Implant Weapon -> Cyber Implant Weapon Accessory two-level case: no fixture exercises
it, and the data gives it no budget.** WP37's entry asks for this to be settled before WP38 decides
whether to support a third nesting level. Both halves check out against a third level being cut:

1. *No fixture uses it.* Walking `<children>` recursively across all 34 `.chum5` fixtures finds 135
   depth-1, 9 depth-2 and 2 depth-3 nested items. Every depth-2/3 chain is a Chrome Flesh (`CF`)
   modular-limb chain (`Modular Connector, Wrist` -> `Obvious Hand, Modular` -> `Armor`, and
   `Modular Connector, Shoulder` -> `Obvious Full Arm, Modular` -> ...), all out of SR5 scope. The
   two cyber implant weapons that do appear (`Spurs` in `Ghile Mear.chum5`, `Custom Submachine Gun`
   in `SCSi.chum5`) are childless depth-1 plugins into a limb.
2. *The data gives a cyber implant weapon nothing to spend.* Its `<capacity>` is bracketed
   (`Hand Blade` `[2]`, `Grenade Launcher` `[15]`), so per the legacy behaviour above its own
   Capacity budget is zero -- there is no budget for an accessory to be charged against. The
   accessories resolve this in the legacy engine via `<addtoparentcapacity>`/`<addtoparentess>`
   (empty flag tags carried by exactly the 3 SR5 `Cyber Implant Weapon Accessory` rows: External
   Clip Port, Laser Sight, Silencer/Suppressor), meaning their cost is folded into the *parent
   weapon's* cost against the *grandparent limb*. That is a distinct mechanic, not one more level of
   the same one.

Both flags are captured here anyway (`adds_to_parent_capacity`, `adds_to_parent_essence`) so WP38
can make that call from data rather than from this docstring, but the recommendation this WP records
is: **cut the third level explicitly in WP38**, exactly as WP31 cut rating-scaled items rather than
half-supporting them.

## `<subsystems>`: bundled-free is two signals, not one

The pre-Phase-K research entry identified `[*]` (Image Link, Sound Link) as the bundled-free marker
and flagged the reading as needing confirmation. It is correct but **incomplete**: the actual
auto-inclusion list is a parent's `<subsystems>` element, and there are **3** of them in the SR5
set, not 2 -- `Cybereyes Basic System` -> `Image Link`, `Cyberears` -> `Sound Link`, and
**`Control Rig` -> `Datajack`**. The third one is real fixture content (`Mittens Chargen.chum5`
carries `Control Rig` with a nested `Datajack`), and it breaks the `[*]`-only reading twice over:
`Control Rig` has no `<allowsubsystems>` at all (so it is not a "parent" by the category test) and
`Datajack`'s own `<capacity>` is a bare `0`, not `[*]`. So:

- `bundled_free` (from `[*]`) means "*this row*, when installed as a plugin, costs no Capacity."
- `bundled_subsystem_names` (from a parent's `<subsystems>`) means "*these rows* come with this one
  automatically, whether or not they are plugins in their own right."

WP38 needs both; conflating them would have silently dropped the Control Rig case.

## What this loader deliberately does *not* capture

Faithful-but-narrow, per WP31's own precedent of recording exclusions rather than half-supporting
them. Present in the SR5 rows and knowingly skipped: `<limbslot>`/`<blocksmounts>`/`<limit>` (how
many limbs of each slot a body has, and which mounts a limb blocks -- a limb-count mechanic, not a
Capacity one), `<allowgear>` (25 rows can hold *gear* children, e.g. a Commlink's programs -- a
gear-in-cyberware mechanic no phase has scoped), `<selectside>`, `<pairbonus>`/`<pairinclude>`
(bonuses that only apply to a matched pair), `<required>`/`<forbidden>` (prerequisite trees),
`<addweapon>`/`<addvehicle>`, and `<avail>` (Availability-cap mechanic ruled out project-wide,
2026-07-21). `<forcegrade>`/`<bannedgrades>` are moot while Phase J's Standard-grade-only scope
holds.

`<rating>`/`<minrating>` bounds are captured **both raw and parsed**, because two rows
(`Customized Agility`, `Customized Strength`) express them as attribute placeholders
(`{AGIMaximum}`, `{AGIMinimum}+1`) that resolve against *character* state, not arithmetic -- out of
scope for a data loader, and explicitly out of scope for WP36's resolver too. Those two get
`max_rating is None` / `min_rating is None` alongside their verbatim strings, so WP38 can resolve
them against a real character without this module inventing a placeholder vocabulary. Note the
legacy engine treats an absent `<minrating>` as 0 (`Cyberware.GetMinRating` parses the empty string
to 0); this loader stores `None` for absent instead of 0, keeping "not stated" and "stated as zero"
distinguishable -- no SR5 row states zero, so nothing is lost.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

from chummer5.data.cyberware import (
    CORE_RULEBOOK_SOURCE,
    DEFAULT_CYBERWARE_PATH,
    BonusSupport,
    CyberwareFlatBonus,
    classify_bonus,
)
from chummer5.data.cyberware_formula import (
    CyberwareFormula,
    UnsupportedCyberwareFormulaError,
    parse_cyberware_formula,
)

# A <capacity> value wrapped entirely in brackets -- a plugin's Capacity *cost*, per the module
# docstring. The inner text is handed to WP36's resolver, which deliberately rejects brackets
# itself so that stripping them stays an explicit, single-place decision.
_BRACKETED_RE = re.compile(r"\[(.*)\]")

# The bundled-free marker: <capacity>[*]</capacity> (Image Link, Sound Link). Not a formula --
# see WP36's module docstring and this one's "<subsystems>" section.
_BUNDLED_FREE_CAPACITY = "*"

# A bare integer <rating>/<minrating>. Anything else (`{AGIMaximum}`, `{AGIMinimum}+1`) is an
# attribute placeholder resolved against character state -- kept raw, see module docstring.
_FLAT_INT_RE = re.compile(r"\d+")


@dataclass(frozen=True)
class CyberwareEntry:
    """One SR5 `cyberware.xml` row, with its formulas parsed and its Capacity/subsystem structure
    captured -- the Phase K view of the catalog, alongside (not replacing)
    `chummer5.data.cyberware.Cyberware`'s WP31 flat view.

    Cost/Essence/Capacity are `CyberwareFormula`s (WP36), not resolved numbers: a rating-scaled row
    has no value until a rating is chosen, and a flat row resolves to the same value at every
    rating. See the module docstring for why parsing (not resolving) happens at load time.
    """

    id: str
    name: str
    category: str
    source: str
    page: int

    cost: CyberwareFormula
    essence_cost: CyberwareFormula

    # Verbatim <rating>/<minrating>, or None when the tag is absent. Kept alongside the parsed ints
    # because two rows express these as attribute placeholders -- see module docstring.
    raw_max_rating: str | None
    raw_min_rating: str | None
    max_rating: int | None  # None when absent *or* attribute-derived
    min_rating: int | None  # None when absent *or* attribute-derived

    # Exactly one of these is set for any row with a <capacity> tag (both are None only for the
    # `[*]` bundled-free rows): a bare value is the row's budget as a parent, a bracketed one its
    # cost as a plugin. Never both -- the legacy `budget/[cost]` combined form does not occur in
    # SR5 data and is rejected at load.
    capacity_budget: CyberwareFormula | None
    capacity_cost: CyberwareFormula | None
    bundled_free: bool

    allowed_subsystem_categories: tuple[str, ...]  # <allowsubsystems>: what this parent may hold
    bundled_subsystem_names: tuple[str, ...]  # <subsystems>: what comes with it automatically
    requires_parent: bool  # <requireparent>: installable only as a plugin, never standalone
    adds_to_parent_essence: bool  # <addtoparentess>
    adds_to_parent_capacity: bool  # <addtoparentcapacity>

    bonus_support: BonusSupport
    flat_bonuses: tuple[CyberwareFlatBonus, ...]  # populated only when bonus_support is FLAT_BONUS
    raw_bonus: str | None  # serialized <bonus> element; None if absent

    @property
    def is_rated(self) -> bool:
        """True when the row carries a `<rating>` tag, i.e. the player picks a rating. Equivalently
        (verified in WP36): true for exactly the 27 rows WP31's flat-only filter excludes.
        """
        return self.raw_max_rating is not None

    @property
    def has_resolvable_rating_bounds(self) -> bool:
        """False for the two attribute-placeholder rows (Customized Agility/Strength), whose bounds
        need a character's attribute min/max -- see module docstring.
        """
        return (self.raw_max_rating is None or self.max_rating is not None) and (
            self.raw_min_rating is None or self.min_rating is not None
        )

    @property
    def is_subsystem_parent(self) -> bool:
        """True when this row may hold plugins of its own (`<allowsubsystems>`). Note a parent may
        still have a zero budget -- the 11 Cyber Implant Weapons do; see module docstring.
        """
        return bool(self.allowed_subsystem_categories)

    @property
    def is_plugin(self) -> bool:
        """True when this row is installable into a parent, i.e. its `<capacity>` is bracketed
        (a cost) or `[*]` (bundled-free). Independent of `is_subsystem_parent`: the Cyber Implant
        Weapons are both.
        """
        return self.capacity_cost is not None or self.bundled_free


def _parse_bound(text: str | None) -> int | None:
    if text is None or _FLAT_INT_RE.fullmatch(text) is None:
        return None
    return int(text)


def _require_formula(text: str, *, item_name: str, field: str) -> CyberwareFormula:
    parsed = parse_cyberware_formula(text)
    if parsed is None:
        raise UnsupportedCyberwareFormulaError(
            f"{item_name}: <{field}> {text!r} is not a shape chummer5.data.cyberware_formula "
            f"recognizes"
        )
    return parsed


def _parse_capacity(
    text: str | None, *, item_name: str
) -> tuple[CyberwareFormula | None, CyberwareFormula | None, bool]:
    """Split a `<capacity>` value into `(budget, cost, bundled_free)` -- see module docstring for
    the bare/bracketed/`[*]` distinction and the legacy citation behind it.
    """
    if text is None:
        return None, None, False

    stripped = text.strip()
    if "/" in stripped:
        # The legacy `budget/[cost]` combined form: an item that is both a parent and a plugin, with
        # two different numbers. No SR5 row uses it; refuse to guess which half is which.
        raise UnsupportedCyberwareFormulaError(
            f"{item_name}: combined budget/[cost] <capacity> {text!r} is not supported (no SR5 "
            f"entry uses this form -- see chummer5.data.cyberware_subsystems' docstring)"
        )

    bracketed = _BRACKETED_RE.fullmatch(stripped)
    if bracketed is None:
        return _require_formula(stripped, item_name=item_name, field="capacity"), None, False

    inner = bracketed.group(1).strip()
    if inner == _BUNDLED_FREE_CAPACITY:
        return None, None, True
    return None, _require_formula(inner, item_name=item_name, field="capacity"), False


def _child_names(elem: ET.Element, container: str, child: str) -> tuple[str, ...]:
    container_elem = elem.find(container)
    if container_elem is None:
        return ()
    return tuple(
        node.text.strip() for node in container_elem.findall(child) if node.text is not None
    )


def _parse_entry(elem: ET.Element) -> CyberwareEntry:
    name = elem.findtext("name", "")
    bonus_elem = elem.find("bonus")
    support, flat_bonuses = classify_bonus(bonus_elem)
    raw_max_rating = elem.findtext("rating")
    raw_min_rating = elem.findtext("minrating")
    capacity_budget, capacity_cost, bundled_free = _parse_capacity(
        elem.findtext("capacity"), item_name=name
    )
    return CyberwareEntry(
        id=elem.findtext("id", ""),
        name=name,
        category=elem.findtext("category", ""),
        source=elem.findtext("source", ""),
        page=int(elem.findtext("page", "0")),
        cost=_require_formula(elem.findtext("cost", "0"), item_name=name, field="cost"),
        essence_cost=_require_formula(elem.findtext("ess", "0"), item_name=name, field="ess"),
        raw_max_rating=raw_max_rating,
        raw_min_rating=raw_min_rating,
        max_rating=_parse_bound(raw_max_rating),
        min_rating=_parse_bound(raw_min_rating),
        capacity_budget=capacity_budget,
        capacity_cost=capacity_cost,
        bundled_free=bundled_free,
        allowed_subsystem_categories=_child_names(elem, "allowsubsystems", "category"),
        bundled_subsystem_names=tuple(
            sub.findtext("name", "")
            for sub in elem.findall("subsystems/cyberware")
            if sub.findtext("name")
        ),
        requires_parent=elem.find("requireparent") is not None,
        adds_to_parent_essence=elem.find("addtoparentess") is not None,
        adds_to_parent_capacity=elem.find("addtoparentcapacity") is not None,
        bonus_support=support,
        flat_bonuses=flat_bonuses,
        raw_bonus=(
            ET.tostring(bonus_elem, encoding="unicode").strip() if bonus_elem is not None else None
        ),
    )


def load_cyberware_entries(xml_path: Path = DEFAULT_CYBERWARE_PATH) -> tuple[CyberwareEntry, ...]:
    """Parse every `source == "SR5"` row of `cyberware.xml` (87 of 362), formulas parsed and
    Capacity/subsystem structure captured.

    Unlike `chummer5.data.cyberware.load_cyberware()` (60 rows, flat cost/Essence only, WP31's
    frozen contract), this applies **no** formula-flatness filter -- resolving rating-scaled rows is
    the whole point of Phase K. Raises `UnsupportedCyberwareFormulaError` if any row's
    `<cost>`/`<ess>`/`<capacity>` is not a shape `chummer5.data.cyberware_formula` whitelists: an
    unrecognized formula is data drift, and this loader fails loudly rather than dropping the row.
    """
    root = ET.parse(xml_path).getroot()
    cyberwares_elem = root.find("cyberwares")
    if cyberwares_elem is None:
        return ()
    return tuple(
        _parse_entry(c)
        for c in cyberwares_elem.findall("cyberware")
        if c.findtext("source") == CORE_RULEBOOK_SOURCE
    )
