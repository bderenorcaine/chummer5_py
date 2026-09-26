"""Cyberware purchase *tree* + Capacity budget validation (WP38 -- Phase K's third primitive,
consuming WP36's formula resolver and WP37's Capacity/subsystem catalog).

WP31/32 model a cyberware purchase as a flat list of items, each charging Essence and nuyen. Real
SR5 lets a parent item (a cyberlimb, a cybereye, a cyberear) *hold* plugins, which charge the
parent's **Capacity** instead of the character's Essence. This module is that mechanic: a nested
purchase request in, a validated, fully-costed purchase tree out.

## This replaced `chummer5.engine.cyberware`'s flat selection in WP41

WP38's plan entry left the question open ("decide & document whether this replaces
`CyberwareSelection.items`'s current flat `tuple[Cyberware, ...]` outright ... or sits alongside
it"), and WP38 answered "alongside, for now": retyping `chummer5.io.save_format`,
`chummer5.io.legacy_import`, `chummer5.web.routes.cyberware` and five test modules *and*
introducing the tree mechanic in one WP would have bundled a mechanical migration into a rules
change. **WP41 performed that migration**, since it had to touch save/load and legacy import
anyway -- which is exactly where the flat-vs-tree shape becomes visible outside the engine.

So as of WP41: `Character.cyberware_selection` is a `CyberwareTreeSelection`, every purchase path
(the web route, `build_character`, `import_legacy_character`) resolves against WP37's
`CyberwareEntry` catalog, and WP32's `CyberwareSelection`/`create_cyberware_selection`/
`apply_cyberware_improvements` are **retired** rather than left as a second, unattachable builder
(see `chummer5.engine.cyberware`'s own docstring). A flat purchase is a zero-plugin tree; nothing
was lost in the swap, because this module's validation is a strict superset of what the flat one
did. `CyberwareTreeSelection` still carries `CyberwareSelection`'s `nuyen_budget`/`nuyen_spent`/
`essence_spent` field names, which is what made that swap mechanical.

**WP42 finished the job at the UI layer.** `chummer5.web.routes.cyberware`'s picker used to offer
WP31's 60 flat rows at rating 1, so every tree the browser built was a set of zero-plugin leaves; it
now offers the full SR5 set (bar two engine-bookkeeping rows), a rating control per purchased unit,
and a plugin checklist per purchased parent with its Capacity spend shown live. Two pieces of this
module are public for that: `cyberware_rating_bounds` (the picker's rating range must be the one
`_build_purchase` validates against) and `PAIRED_BONUS_ITEM_NAMES` (the sheet must say a Hydraulic
Jack's bonus needs a matched pair).

## Essence-vs-Capacity dual costing: the same catalog row, two prices

The core mechanic, and it is confirmed from three independent directions rather than assumed:

- **Rulebook, p. 456 (Bodyware narrative):** "Bodyware cannot be installed into cyberlimbs unless
  it has a Capacity cost [in brackets]. Bodyware with a Capacity cost can be installed in
  cyberlimbs, **costing capacity rather than Essence**."
- **Rulebook, equipment-table legend (p. 29100-29106, quoted in `spec/rulebooks/learnings/
  phase-k.md`'s pre-Phase-K entry):** "Some cyberware items with a Capacity cost can also be
  installed as standalone items (taking up Essence) rather than subsystems (taking up Capacity);
  if both costs are listed, only one applies, depending on whether you installed it in another
  item or in yourself."
- **The legacy engine, `Cyberware.cs`'s `GetCalculatedESSPrototypeInvariantCoreAsync`:** its very
  first line is `if (Parent != null && !AddToParentESS) return 0;` -- an installed child
  contributes **zero** Essence, full stop, unless it carries `<addtoparentess>`.

So: `Installation.STANDALONE` charges the item's own Essence and no Capacity;
`Installation.SUBSYSTEM` charges the parent's Capacity and **zero** Essence. Nuyen is charged
either way -- the same legacy `CalculatedTotalCostWithoutModifiers` that zeroes a child's Essence
explicitly does "Add in the cost of all child components," and Barrett's real `Enhanced Agility`
plugins are paid for in nuyen like anything else.

## Bundled subsystems: always auto-attached, and free

WP38's entry asked to "confirm via real fixture data whether any curated Cybereyes/Cyberears
purchase ever appears *without* its bundled item before deciding whether to model it as
always-auto-attached (simpler) or a skippable choice." Checked across all 34 `.chum5` fixtures:
there are **8** purchases of a parent with a `<subsystems>` list (5 Cybereyes Basic System, 2
Cyberears, 1 Control Rig) and **all 8** carry their bundled child. None is ever skipped, so this
models them as always-auto-attached: `create_cyberware_tree_selection` adds any missing bundled
name itself, flagged `PurchasedCyberware.bundled`.

Bundled means **free in all three currencies**: 0 nuyen (legacy `Cyberware.Create` sets
`objSubsystem.Cost = "0"` when auto-adding from `<subsystems>`, and every fixture's stored
`<cost>` for a bundled `Image Link`/`Sound Link`/`Datajack` is literally `0`), 0 Essence (it is a
child -- see above), 0 Capacity (`[*]`, and p. 454's table footnote "* Included in the basic
cybereyes system"). An explicit request for a bundled name is *not* an error and is *not* charged
either -- it resolves to the same free node, so WP41's legacy import (where `<children>` does list
`Image Link` explicitly) needs no special case.

Note `bundled_free` (`[*]`) and `bundled_subsystem_names` (`<subsystems>`) are two different
signals, per WP37's own correction: `Control Rig` -> `Datajack` is bundled without either item
carrying `[*]`. This module keys "free" off the parent's `<subsystems>` list, and treats `[*]`
as a zero Capacity cost independently.

## Three nesting levels: cut, per the 2026-07-29 ruling

A plugin may not itself hold plugins. This is the explicit cut the decisions log records for WP38
(the 11 SR5 `Cyber Implant Weapon` rows carry `<allowsubsystems>Cyber Implant Weapon Accessory
</allowsubsystems>` yet have a purely-bracketed `<capacity>`, i.e. **zero budget** to spend; their
3 accessories work by `<addtoparentcapacity>`/`<addtoparentess>`, folding into the weapon's cost
against the grandparent limb -- a different mechanic, and one no fixture exercises). Requesting a
plugin on a plugin raises, naming the reason, rather than silently accepting a purchase whose
Capacity charge would land nowhere.

## `{AGIMinimum}+1` / `{AGIMaximum}`: the one input that needs *character* state

WP37 left this as "the one thing WP38 will still have to solve." Exactly two SR5 rows have
attribute-placeholder rating bounds -- `Customized Agility` and `Customized Strength`,
`<minrating>{AGIMinimum}+1</minrating>` / `<rating>{AGIMaximum}</rating>`. Both halves are settled
from the rulebook and cross-checked against the legacy resolution path:

- `{AGIMinimum}` / `{STRMinimum}` is the **limb's** attribute floor, not the character's:
  p. 456, "All standard cyberlimbs come with Strength and Agility attributes of 3." The legacy
  engine agrees literally -- `Cyberware.ProcessAttributesInXPath` overrides `AGIMinimum`/
  `STRMinimum` with the parent cyberlimb's `MinAgility`/`MinStrength`, whose backing field is
  initialised to `3` and which no SR5 cyberlimb row overrides. So `{AGIMinimum}+1` is 4 --
  "the lowest *purchasable* point," matching the `(Rating - MinRating + 1) * 5000` inclusive-count
  reading WP36 already pinned down (p. 457's "Each STR or AGI point above 3 ... +5,000¥").
- `{AGIMaximum}` / `{STRMaximum}` is the **character's** natural maximum: p. 456, "If either of
  your limb's attributes are increased beyond your natural maximum for that attribute, you can't
  use the cyberlimb (so don't overdo it)." Legacy falls through to
  `AttributeSection.ProcessAttributesInXPath`, which substitutes the character attribute's
  `TotalMaximum` -- the same number `Character.attribute_range(code).maximum` gives here.

`create_cyberware_tree_selection` takes those maximums as a plain `Mapping[str, int]`
(`cyberlimb_attribute_maximums(character)` builds one) rather than a `Character`, keeping this
module's validation testable with synthetic data. It defaults to `None` and **raises** if a
purchase actually needs a bound it wasn't given -- mirroring WP36's `min_rating=None` decision, for
the same reason: silently defaulting would produce a plausible-but-wrong rating cap.

## One enhancement of each type per limb

p. 456: "Each limb can have only one enhancement of each type (you can't stack two Strength 3
enhancements in the same cyberarm), but you can replace one you have with one you want." Enforced
narrowly, for exactly the `Cyberlimb Enhancement` category the sentence is about -- two plugins of
the same catalog row in the same parent are rejected there. No *general* one-per-parent rule is
modeled: nothing in SR5 forbids, say, two Vision Enhancements in one cybereye, and the Capacity
budget already bounds that case. Note `Customized Agility`/`Customized Strength` sit in the same
XML category despite being "Customization" rather than an "Enhancement" in the printed tables, so
they are covered by the same check -- harmless, since stacking two customizations of one attribute
in one limb is meaningless under the "each point above 3" pricing either way.

## Improvements (WP40): `apply_cyberware_tree_improvements`

WP38 left this module computing money, Essence and Capacity only; WP40 adds the Improvement half,
mirroring `chummer5.engine.cyberware.apply_cyberware_improvements` node-for-node. Every node in
every tree grants its Essence cost (already dual-costed, so a plugin's is 0) plus whatever its
`<bonus>` classified to, translated by `chummer5.engine.cyberware.cyberware_bonus_improvements` --
imported rather than duplicated, matching the data layer's own single shared `classify_bonus`.

Three of the four real conditional bonuses in the SR5 set are rating-scaled and therefore reachable
*only* through this catalog: `Vision Enhancement` and `Audio Enhancement` (+Rating Mental limit, on
visual/hearing Perception tests respectively) and `Hydraulic Jacks` (+Rating Physical limit). The
fourth, `Spatial Recognizer`, is flat and so reaches a character through either module.

**Hydraulic Jacks is a matched *pair*, which the data does not say and a per-item application gets
wrong.** p. 457: "This implant requires you to have two cyberlegs with a hydraulic jack of
identical Ratings in each leg. Each Rating point adds a +1 to your Physical limit for jumping and
sprinting." So a lone jack grants nothing at all, and a pair grants `+Rating` **once**, not twice.
`cyberware.xml` carries no `<pairbonus>`/`<pairinclude>` on this row to signal any of that (WP37
deliberately captures neither tag), and the legacy engine never evaluates a conditional limit
modifier anyway -- so applying this row the same way as every other one would silently produce
`+2 x Rating` for a real, ordinary build (`Barrett.chum5` owns exactly two). Modeled here as a
named rule (`PAIRED_BONUS_ITEM_NAMES`): its bonus is granted once per Rating for which at least
two jacks sit in **distinct** parents, carrying a `unique_name` so that two qualifying Ratings --
impossible with two legs, but not something this engine counts -- collapse to the highest under
SR5's existing "highest bonus wins" rule rather than stacking. The `<required><parentdetails>`
"parent must be a leg" restriction is *not* enforced: WP37 captures no `<required>` data, so
"distinct parents" is what this engine can actually check.

## What this module deliberately does not do

- **No cyberlimb attribute model.** `Customized Agility`/`Enhanced Agility`/`Enhanced Strength`
  carry no `<bonus>` at all -- the legacy engine gives a *limb* its own STR/AGI (p. 456,
  "Physical attribute enhancements add their Rating to the appropriate attribute of the limb"),
  a per-limb attribute system this engine has no representation of. Purchasable and correctly
  priced here; mechanically inert. Recorded in the Project Overview's "Unmodeled real effects"
  registry rather than silently dropped.
- **No grades, no Availability, no limb-slot counting** -- Phase J's Standard-grade-only scope, the
  project-wide Availability ruling (2026-07-21), and WP37's own list of uncaptured tags all still
  hold.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, replace
from decimal import Decimal
from enum import Enum

from chummer5.data.cyberware_subsystems import CyberwareEntry
from chummer5.engine.character import Character
from chummer5.engine.cyberware import cyberware_bonus_improvements
from chummer5.engine.derived import BASE_ESSENCE
from chummer5.engine.improvements import Improvement, ImprovementSource, ImprovementType

# p. 456, "All standard cyberlimbs come with Strength and Agility attributes of 3" -- the value
# `{AGIMinimum}`/`{STRMinimum}` resolves to for a cyberlimb enhancement (legacy `Cyberware
# ._intMinAgility`/`_intMinStrength`, both initialised to 3 and overridden by no SR5 row).
CYBERLIMB_BASE_ATTRIBUTE = 3

# The category p. 456's "only one enhancement of each type" sentence is about. See module docstring
# for why the rule is applied to this category only rather than generalized.
_ONE_PER_PARENT_CATEGORY = "Cyberlimb Enhancement"

# Items whose <bonus> is granted by a matched *pair*, not per purchase -- p. 457's "requires you to
# have two cyberlegs with a hydraulic jack of identical Ratings in each leg." See the module
# docstring's WP40 section; this is a rulebook rule with no signal in the data at all.
#
# **Public since WP42**: the character sheet has to say "granted once for a matched pair" beside
# such an item's bonus, or a player looking at two jacks would read the printed +Rating twice.
PAIRED_BONUS_ITEM_NAMES = frozenset({"Hydraulic Jacks"})

# Every ImprovementType this module produces is a single character-wide total (one Essence pool,
# one Physical Limit) -- the same sentinel target chummer5.engine.derived resolves them against.
_GLOBAL_TARGET = ""

# `{AGIMinimum}+1`, `{STRMaximum}`, ... -- the only two rating-bound placeholder shapes in the SR5
# set, both on Customized Agility/Strength. A whitelist of named shapes, not an expression parser,
# mirroring `chummer5.data.cyberware_formula`'s own posture.
_ATTRIBUTE_BOUND_RE = re.compile(
    r"\{(?P<code>AGI|STR)(?P<bound>Minimum|Maximum)\}(?:\+(?P<plus>\d+))?"
)


class Installation(Enum):
    """How a purchase is installed, which is what decides whether it costs Essence or Capacity.

    See the module docstring's dual-costing section for the rulebook/legacy citations behind the
    split.
    """

    STANDALONE = "standalone"  # installed in the character: costs Essence, charges no Capacity
    SUBSYSTEM = "subsystem"  # installed in a parent item: charges Capacity, costs zero Essence


@dataclass(frozen=True)
class CyberwarePurchaseRequest:
    """What a caller *asks* to buy: a catalog id, a rating, and nested plugin requests.

    Deliberately separate from `PurchasedCyberware` (the validated, costed result): a request is
    plain data a UI/save file can hold with no catalog resolved, which is the shape WP41/WP42 need.
    `rating` defaults to 1 -- the only legal value for an unrated row, and the lowest for a rated
    one.
    """

    item_id: str
    rating: int = 1
    plugins: tuple[CyberwarePurchaseRequest, ...] = ()


@dataclass(frozen=True)
class PurchasedCyberware:
    """One validated node of a purchase tree, with every cost already resolved at its rating.

    `nuyen_cost`/`essence_cost`/`capacity_cost` are this node's *own* charges, excluding plugins --
    use `total_nuyen_cost`/`total_essence_cost` for the subtree. `capacity_cost` is what this node
    charges its **parent** (0 for a standalone purchase and for a bundled one); `capacity_budget`
    is what it offers **its own** plugins (0 for anything installed as a subsystem, per the legacy
    `CapacityRemaining` behaviour WP37 documented).
    """

    item: CyberwareEntry
    rating: int
    installation: Installation
    plugins: tuple[PurchasedCyberware, ...] = ()
    nuyen_cost: int = 0
    essence_cost: Decimal = Decimal(0)
    capacity_cost: Decimal = Decimal(0)
    capacity_budget: Decimal = Decimal(0)
    bundled: bool = False  # auto-included with the parent (its <subsystems> list): free, not a pick

    @property
    def total_nuyen_cost(self) -> int:
        """This node plus every plugin installed in it."""
        return self.nuyen_cost + sum(plugin.total_nuyen_cost for plugin in self.plugins)

    @property
    def total_essence_cost(self) -> Decimal:
        """This node plus every plugin -- in practice this node's own cost, since a subsystem
        always contributes zero Essence (module docstring's dual-costing section). Summed anyway so
        the shape stays honest if a later WP models `<addtoparentess>`.
        """
        return self.essence_cost + sum(
            (plugin.total_essence_cost for plugin in self.plugins), Decimal(0)
        )

    @property
    def capacity_spent(self) -> Decimal:
        """Capacity charged by the plugins installed in this node."""
        return sum((plugin.capacity_cost for plugin in self.plugins), Decimal(0))

    @property
    def capacity_remaining(self) -> Decimal:
        """Unspent Capacity -- what a further plugin could still be installed into."""
        return self.capacity_budget - self.capacity_spent


@dataclass(frozen=True)
class CyberwareTreeSelection:
    """A validated set of cyberware purchase trees and their combined nuyen/Essence cost.

    Field names mirror WP32's retired `CyberwareSelection`'s deliberately -- see the module
    docstring for the WP41 migration that shape made mechanical. `purchases` holds only the
    top-level (standalone) purchases; plugins hang off their parents.
    """

    purchases: tuple[PurchasedCyberware, ...]
    nuyen_budget: int
    nuyen_spent: int
    essence_spent: Decimal

    def walk(self) -> tuple[PurchasedCyberware, ...]:
        """Every node in every tree, parents before their own plugins."""

        def _walk(node: PurchasedCyberware) -> list[PurchasedCyberware]:
            nodes = [node]
            for plugin in node.plugins:
                nodes.extend(_walk(plugin))
            return nodes

        return tuple(node for purchase in self.purchases for node in _walk(purchase))

    def to_requests(self) -> tuple[CyberwarePurchaseRequest, ...]:
        """The `CyberwarePurchaseRequest` tree this selection was built from (WP41).

        The inverse of `create_cyberware_tree_selection`'s input, and what
        `chummer5.io.save_format.CharacterSave.cyberware_purchases` persists: a validated selection
        holds resolved catalog objects and prices, none of which a save file should carry (this
        project's "selections, not derived values" rule).

        **Bundled nodes are omitted**, because they are not picks -- `create_cyberware_tree_
        selection` re-attaches them itself on the way back in (see the module docstring's bundled-
        subsystem section), so persisting them would either duplicate them or rely on the
        explicit-request-resolves-to-the-same-free-node behaviour to paper over it. Round-tripping
        `to_requests()` through `create_cyberware_tree_selection` reproduces this selection exactly.
        """

        def _request(node: PurchasedCyberware) -> CyberwarePurchaseRequest:
            return CyberwarePurchaseRequest(
                item_id=node.item.id,
                rating=node.rating,
                plugins=tuple(_request(plugin) for plugin in node.plugins if not plugin.bundled),
            )

        return tuple(_request(purchase) for purchase in self.purchases if not purchase.bundled)


def cyberlimb_attribute_maximums(character: Character) -> Mapping[str, int]:
    """The `{AGIMaximum}`/`{STRMaximum}` bounds for `create_cyberware_tree_selection`.

    A cyberlimb customized past the character's natural maximum for that attribute is unusable
    (p. 456) -- so the cap is the metatype's own maximum, which is what the legacy engine
    substitutes too (`AttributeSection.ProcessAttributesInXPath` -> the attribute's `TotalMaximum`).
    """
    # WP112: `attribute_maximum` (legacy `TotalMaximum` includes maximum modifiers).
    return {code: character.attribute_maximum(code) for code in ("AGI", "STR")}


def _resolve_bound(
    raw: str | None,
    parsed: int | None,
    *,
    attribute_maximums: Mapping[str, int] | None,
    item_name: str,
    field_name: str,
    absent_default: int,
) -> int:
    """Resolve one `<rating>`/`<minrating>` bound, including the two attribute-placeholder rows.

    `absent_default` is what an entirely absent tag means (1 for both bounds: an unrated row is
    bought at rating 1 and no lower/higher).
    """
    if raw is None:
        return absent_default
    if parsed is not None:
        return parsed

    match = _ATTRIBUTE_BOUND_RE.fullmatch(raw.strip())
    if match is None:
        raise ValueError(
            f"{item_name}: <{field_name}> {raw!r} is not a rating bound this engine resolves "
            f"(only a bare integer or an {{AGI|STR}}{{Minimum|Maximum}} placeholder)"
        )

    code = match.group("code")
    plus = int(match.group("plus") or 0)
    if match.group("bound") == "Minimum":
        # The *limb's* floor, not the character's -- see module docstring.
        return CYBERLIMB_BASE_ATTRIBUTE + plus
    if attribute_maximums is None or code not in attribute_maximums:
        raise ValueError(
            f"{item_name}: <{field_name}> {raw!r} needs the character's natural {code} maximum "
            f"(pass attribute_maximums=cyberlimb_attribute_maximums(character))"
        )
    return attribute_maximums[code] + plus


def cyberware_rating_bounds(
    item: CyberwareEntry, *, attribute_maximums: Mapping[str, int] | None = None
) -> tuple[int, int]:
    """The `(minimum, maximum)` rating this item may be purchased at, placeholders resolved.

    `(1, 1)` for an unrated row (no `<rating>`/`<minrating>` tag), which is the only value such a
    row has. Raises when a bound needs an attribute maximum that `attribute_maximums` doesn't carry
    -- see `_resolve_bound` and the module docstring's `{AGIMaximum}` section.

    **Public since WP42**, which needs exactly this to build the picker's per-purchase rating
    dropdown: an offered range the engine would then reject is the one thing a rating control must
    not produce. `_build_purchase` calls it for the validation half, so the two cannot disagree.
    """
    minimum = _resolve_bound(
        item.raw_min_rating,
        item.min_rating,
        attribute_maximums=attribute_maximums,
        item_name=item.name,
        field_name="minrating",
        absent_default=1,
    )
    maximum = _resolve_bound(
        item.raw_max_rating,
        item.max_rating,
        attribute_maximums=attribute_maximums,
        item_name=item.name,
        field_name="rating",
        absent_default=1,
    )
    return minimum, maximum


def _as_nuyen(value: Decimal, *, item_name: str) -> int:
    """Cyberware prices are whole nuyen in every SR5 row; refuse to round one that isn't."""
    if value != value.to_integral_value():
        raise ValueError(f"{item_name}: resolved nuyen cost {value} is not a whole number")
    return int(value)


def _build_purchase(
    request: CyberwarePurchaseRequest,
    by_id: Mapping[str, CyberwareEntry],
    by_name: Mapping[str, CyberwareEntry],
    *,
    parent: CyberwareEntry | None,
    attribute_maximums: Mapping[str, int] | None,
    bundled: bool = False,
) -> PurchasedCyberware:
    item = by_id.get(request.item_id)
    if item is None:
        raise ValueError(f"not a cyberware catalog id: {request.item_id!r}")

    installation = Installation.STANDALONE if parent is None else Installation.SUBSYSTEM

    if parent is None:
        if item.requires_parent:
            raise ValueError(
                f"{item.name} can only be installed as a subsystem of another item "
                f"(<requireparent>), not on its own"
            )
    else:
        # A bundled subsystem bypasses every eligibility check below: it is named directly by its
        # parent's own `<subsystems>` list, which is the parent saying "this one comes with me."
        # Not a formality -- `Control Rig` -> `Datajack` satisfies *none* of the three (Control Rig
        # has no `<allowsubsystems>`, Datajack is `Headware` rather than a listed category, and
        # Datajack's `<capacity>` is a bare `0` rather than a bracketed cost), yet it is real
        # fixture content (`Mittens Chargen.chum5`). See WP37's learnings entry.
        if not bundled:
            if not parent.is_subsystem_parent:
                raise ValueError(f"{parent.name} cannot hold subsystems (no <allowsubsystems>)")
            if item.category not in parent.allowed_subsystem_categories:
                raise ValueError(
                    f"{parent.name} cannot hold a {item.category} subsystem "
                    f"({item.name}); it allows {list(parent.allowed_subsystem_categories)}"
                )
            if not item.is_plugin:
                # p. 456: "Cyberlimbs cannot hold ... any cyber-implants that take up Essence
                # rather than Capacity." A row with no bracketed <capacity> has no Capacity price.
                raise ValueError(
                    f"{item.name} has no Capacity cost, so it can only be installed standalone "
                    f"(taking Essence), not as a subsystem of {parent.name}"
                )
        if request.plugins:
            # The explicit third-level cut -- see module docstring and the 2026-07-29 ruling.
            raise ValueError(
                f"{item.name} is itself a subsystem of {parent.name}; nesting a further subsystem "
                f"inside it is out of scope (the Cyber Implant Weapon Accessory layer folds into "
                f"its parent's cost instead -- see spec/decisions-log.md, 2026-07-29)"
            )

    minimum, maximum = cyberware_rating_bounds(item, attribute_maximums=attribute_maximums)
    if not minimum <= request.rating <= maximum:
        raise ValueError(
            f"{item.name}: rating {request.rating} is outside its purchasable range "
            f"{minimum}-{maximum}"
        )

    if bundled:
        # Free in all three currencies -- see the module docstring's bundled-subsystem section.
        nuyen_cost = 0
        essence_cost = Decimal(0)
        capacity_cost = Decimal(0)
    else:
        nuyen_cost = _as_nuyen(
            item.cost.resolve(rating=request.rating, min_rating=minimum), item_name=item.name
        )
        essence_cost = (
            item.essence_cost.resolve(rating=request.rating, min_rating=minimum)
            if installation is Installation.STANDALONE
            else Decimal(0)
        )
        capacity_cost = (
            item.capacity_cost.resolve(rating=request.rating, min_rating=minimum)
            if installation is Installation.SUBSYSTEM and item.capacity_cost is not None
            else Decimal(0)
        )

    capacity_budget = (
        item.capacity_budget.resolve(rating=request.rating, min_rating=minimum)
        if installation is Installation.STANDALONE and item.capacity_budget is not None
        else Decimal(0)
    )

    plugins = _build_plugins(request, item, by_id, by_name, attribute_maximums=attribute_maximums)

    if plugins:
        spent = sum((plugin.capacity_cost for plugin in plugins), Decimal(0))
        if spent > capacity_budget:
            raise ValueError(
                f"{item.name}: subsystems cost {spent} Capacity, exceeding its Capacity budget "
                f"of {capacity_budget}"
            )

    return PurchasedCyberware(
        item=item,
        rating=request.rating,
        installation=installation,
        plugins=plugins,
        nuyen_cost=nuyen_cost,
        essence_cost=essence_cost,
        capacity_cost=capacity_cost,
        capacity_budget=capacity_budget,
        bundled=bundled,
    )


def _build_plugins(
    request: CyberwarePurchaseRequest,
    item: CyberwareEntry,
    by_id: Mapping[str, CyberwareEntry],
    by_name: Mapping[str, CyberwareEntry],
    *,
    attribute_maximums: Mapping[str, int] | None,
) -> tuple[PurchasedCyberware, ...]:
    """Build `request`'s explicit plugins, then auto-attach any missing bundled subsystem."""
    bundled_names = set(item.bundled_subsystem_names)
    plugins = [
        _build_purchase(
            plugin_request,
            by_id,
            by_name,
            parent=item,
            attribute_maximums=attribute_maximums,
            bundled=_plugin_item(plugin_request, by_id).name in bundled_names,
        )
        for plugin_request in request.plugins
    ]
    _reject_stacked_enhancements(item, plugins)

    already_present = {plugin.item.name for plugin in plugins}
    for name in item.bundled_subsystem_names:
        if name in already_present:
            continue
        bundled_item = by_name.get(name)
        if bundled_item is None:
            raise ValueError(
                f"{item.name} bundles {name!r}, which is not in this catalog -- "
                f"pass the full catalog from chummer5.data.cyberware_subsystems"
                f".load_cyberware_entries()"
            )
        plugins.append(
            _build_purchase(
                CyberwarePurchaseRequest(item_id=bundled_item.id),
                by_id,
                by_name,
                parent=item,
                attribute_maximums=attribute_maximums,
                bundled=True,
            )
        )
    return tuple(plugins)


def _plugin_item(
    request: CyberwarePurchaseRequest, by_id: Mapping[str, CyberwareEntry]
) -> CyberwareEntry:
    item = by_id.get(request.item_id)
    if item is None:
        raise ValueError(f"not a cyberware catalog id: {request.item_id!r}")
    return item


def _reject_stacked_enhancements(
    parent: CyberwareEntry, plugins: Sequence[PurchasedCyberware]
) -> None:
    """p. 456: "Each limb can have only one enhancement of each type." See module docstring for why
    this is applied to the `Cyberlimb Enhancement` category only.
    """
    seen: set[str] = set()
    for plugin in plugins:
        if plugin.item.category != _ONE_PER_PARENT_CATEGORY:
            continue
        if plugin.item.id in seen:
            raise ValueError(
                f"{parent.name} already has a {plugin.item.name}; a limb may hold only one "
                f"enhancement of each type"
            )
        seen.add(plugin.item.id)


def create_cyberware_tree_selection(
    requests: Iterable[CyberwarePurchaseRequest],
    catalog: Iterable[CyberwareEntry],
    nuyen_budget: int,
    *,
    attribute_maximums: Mapping[str, int] | None = None,
    other_essence_spent: Decimal = Decimal(0),
) -> CyberwareTreeSelection:
    """Build a validated `CyberwareTreeSelection` from nested purchase requests.

    Validates, in addition to everything `chummer5.engine.cyberware.create_cyberware_selection`
    already does (unknown ids, the nuyen budget, the strictly-positive Essence floor shared with
    `other_essence_spent`):

    - a `<requireparent>` item is not bought standalone, and a plugin's category is one its
      parent's `<allowsubsystems>` accepts;
    - a plugin actually has a Capacity price (p. 456: a parent "cannot hold ... cyber-implants that
      take up Essence rather than Capacity");
    - each parent's plugins fit its resolved Capacity budget;
    - each purchase's rating is inside the item's own bounds, resolving `{AGIMinimum}+1`/
      `{AGIMaximum}`-style placeholders (see module docstring; `attribute_maximums` is required
      only when a purchase actually uses one);
    - a limb holds at most one `Cyberlimb Enhancement` of each type (p. 456);
    - no third nesting level (2026-07-29 ruling).

    Missing bundled subsystems are auto-attached, free. Duplicate purchases of the same item are
    allowed, exactly as in `create_cyberware_selection` -- a matched pair of cyberlimbs is an
    ordinary build.
    """
    entries = tuple(catalog)
    by_id = {entry.id: entry for entry in entries}
    by_name = {entry.name: entry for entry in entries}

    purchases = tuple(
        _build_purchase(request, by_id, by_name, parent=None, attribute_maximums=attribute_maximums)
        for request in requests
    )

    nuyen_spent = sum(purchase.total_nuyen_cost for purchase in purchases)
    if nuyen_spent > nuyen_budget:
        raise ValueError(
            f"cyberware spend {nuyen_spent} exceeds the nuyen budget of {nuyen_budget}"
        )

    essence_spent = sum((purchase.total_essence_cost for purchase in purchases), Decimal(0))
    if essence_spent + other_essence_spent >= BASE_ESSENCE:
        raise ValueError(
            f"cyberware Essence cost {essence_spent} would leave no Essence remaining "
            f"(total Essence cost, including {other_essence_spent} already spent elsewhere, must "
            f"stay below {BASE_ESSENCE})"
        )

    return CyberwareTreeSelection(
        purchases=purchases,
        nuyen_budget=nuyen_budget,
        nuyen_spent=nuyen_spent,
        essence_spent=essence_spent,
    )


def _paired_bonus_nodes(
    selection: CyberwareTreeSelection,
) -> dict[tuple[str, int], list[tuple[int, PurchasedCyberware]]]:
    """Group every `PAIRED_BONUS_ITEM_NAMES` plugin by `(item name, rating)`, tagged with the
    index of the top-level purchase it is installed in.

    The index is what makes "two jacks in *distinct* legs" checkable: two matching plugins in the
    same limb are one leg's worth, not a pair. A paired item bought standalone (not installed in
    anything) is deliberately not collected -- p. 457's rule is about jacks *in cyberlegs*.
    """
    grouped: dict[tuple[str, int], list[tuple[int, PurchasedCyberware]]] = {}
    for parent_index, purchase in enumerate(selection.purchases):
        for plugin in purchase.plugins:
            if plugin.item.name in PAIRED_BONUS_ITEM_NAMES:
                grouped.setdefault((plugin.item.name, plugin.rating), []).append(
                    (parent_index, plugin)
                )
    return grouped


def apply_cyberware_tree_improvements(
    character: Character, selection: CyberwareTreeSelection
) -> None:
    """Add every purchased node's Essence cost and `<bonus>` to `character.improvements` (WP40).

    The tree-shaped counterpart of `chummer5.engine.cyberware.apply_cyberware_improvements`, and
    deliberately the same shape: every node grants an `ESSENCE` Improvement unconditionally --
    which for a plugin is `0`, since dual costing already zeroed its `essence_cost` -- plus the
    Improvements its `<bonus>` classified to, resolved at that node's own purchased rating.

    `source_id` is the item's catalog id, not per-purchase, exactly as in the flat function: a
    matched pair of limbs is an ordinary build, and this project has no "retract one of a pair"
    use case.

    Hydraulic Jacks is the one item not applied per node -- see the module docstring's WP40
    section for p. 457's matched-pair rule and why a per-node application would silently double it.
    """
    paired = _paired_bonus_nodes(selection)

    for node in selection.walk():
        character.improvements.add(
            Improvement(
                improvement_type=ImprovementType.ESSENCE,
                target=_GLOBAL_TARGET,
                value=0,
                source_type=ImprovementSource.CYBERWARE,
                source_id=node.item.id,
                essence_value=-node.essence_cost,
            )
        )
        if node.item.name in PAIRED_BONUS_ITEM_NAMES:
            continue
        for improvement in cyberware_bonus_improvements(
            item_id=node.item.id,
            item_name=node.item.name,
            flat_bonuses=node.item.flat_bonuses,
            conditional_bonuses=node.item.conditional_bonuses,
            rating=node.rating,
        ):
            character.improvements.add(improvement)

    for (name, rating), installations in sorted(paired.items()):
        if len({parent_index for parent_index, _ in installations}) < 2:
            continue
        node = installations[0][1]
        for improvement in cyberware_bonus_improvements(
            item_id=node.item.id,
            item_name=node.item.name,
            flat_bonuses=node.item.flat_bonuses,
            conditional_bonuses=node.item.conditional_bonuses,
            rating=rating,
        ):
            # `unique_name` so two qualifying Ratings would collapse to the highest under SR5's
            # own "highest bonus wins" rule rather than stacking -- see module docstring.
            character.improvements.add(replace(improvement, unique_name=name))
