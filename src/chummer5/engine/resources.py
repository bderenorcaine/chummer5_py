"""Contacts & starting resources.

**Cyberware (WP34).** `chummer5.engine.cyberware.CyberwareSelection` (Phase J) draws from this same
nuyen budget too -- `create_resources_selection`'s `cyberware_cost` parameter folds its already-
computed total cost into the same joint over-budget check `lifestyle_cost` already established,
rather than `chummer5.engine.cyberware` duplicating a second budget validator of its own. Mirrors
`lifestyle_cost`'s own relationship to this function exactly, extended from a two-way to a
three-way shared check. See `chummer5.engine.cyberware`'s module docstring for the confirmed
"same Step Six pool" citation.

**Bioware (WP45).** `chummer5.engine.bioware.BiowareSelection` draws from the identical pool --
`bioware_cost` extends the same joint check from three terms to four, mirroring `cyberware_cost`'s
own shape exactly (see `chummer5.engine.bioware`'s module docstring for the confirmed "same Step
Six pool, same Essence pool" citations).

Composes WP2's Resources-priority data (`chummer5.data.priorities`) with WP6's `Character` into
the last two mundane MVP chargen inputs: contacts and a starting-nuyen spend. Mundane MVP scope
only — see `spec/Project Overview.md`.

**Contacts.** Checked directly against `legacy/Chummer/Backend/Characters/Contact.cs`
(`ContactPoints`) and `Character.cs` (`ContactPoints`, the character-level CHA*3 free budget),
cross-referenced against the core rulebook ("Making Connections", p. 98 — see
`spec/rulebooks/learnings.md`'s WP9 entry) and every mundane fixture's `<contactpoints>` tag (all
11 equal `CHA_total_value * 3` exactly — see `spec/worklogs/WP9.md`):

- One `Contact.points` = `Connection + Loyalty`, floored at 2 (redundant given both ratings' own
  1-minimum, kept for parity with the legacy formula) — 0 if the contact is `free` (a GM-granted/
  plot contact that doesn't draw from the point budget at all).
- A character's free contact-point budget is `Charisma * 3`.
- Any point spent beyond that free budget costs 1 Karma each (`CharacterSettings.KarmaContact`,
  legacy default `1`) — `create_contact_selection` computes this as data (`karma_cost`), it does
  **not** reject an over-budget selection. A real character routinely exceeds the free budget and
  pays the karma difference; rejecting it outright would be modeling a rule that doesn't exist.
- **Deliberately not enforced: "a single contact may not have more than 7 Karma spent on it at
  character creation"** (core rulebook, "Additional Purchases & Restrictions" table, p. 98; also
  checked in legacy `CharacterCreate.cs`'s character-validity pass, absent the Friends in High
  Places quality). `Yeti-#ffffff2.chum5` — this project's own priority-build golden fixture,
  already load-bearing for WP6/WP7 — has a contact at Connection 5/Loyalty 4 (9 points, no Friends
  in High Places quality present) that violates this rule outright. Since real, accepted ground
  truth breaks it, MVP does not enforce it as a construction-time `ValueError` (it would make the
  engine unable to reproduce its own reference fixture); flagged here rather than silently
  omitted, the same "don't hide a real rules gap" precedent WP8 set for the negative-quality catalog
  gap. See `spec/worklogs/WP9.md` for the full fixture check.

**Starting resources.** `starting_nuyen()` is a thin lookup over WP2's `PriorityTable.resources`
(already cross-validated against all 11 mundane `.chum5` fixtures' `<startingnuyen>` in WP4 — see
`spec/worklogs/WP4.md`). `STARTER_GEAR_CATALOG` was, through WP20, a deliberately small,
hand-curated list of 5 flat-cost SR5-sourced items — WP21 replaced it with `build_starter_gear_
catalog()`, built from `chummer5.data.gear`'s real loaders over the full SR5-core, flat-cost
equipment set (411 items across gear/armor/weapons; see that module's docstring for exactly what
"flat-cost" excludes and how a handful of real cross-file name collisions are resolved). **WP66**
adds the Rating-priced gear this originally excluded (Fake SINs, AR glasses/goggles/contacts,
earbuds/headphones, and the rest of the `Rating * N`-cost SR5 catalog) via
`chummer5.data.gear.load_rating_gear`, each purchasable at a chosen rating (`cost = rating *
cost_per_rating`) with its selectable range clamped to Availability<=12 -- see
`build_starter_gear_catalog`'s own docstring for the cap and the Foci/Formulae exclusion.
`create_resources_selection` only validates that every
selected item is in the catalog and that the total cost doesn't exceed the Resources-letter nuyen
budget — there's no equivalent "real characters exceed this" escape hatch here, since nuyen
(unlike contact points) has no legacy provision for going over budget by paying with something
else at chargen.

**Lifestyle (WP20).** `chummer5.engine.lifestyle.LifestyleSelection` (the mandatory primary-
Lifestyle purchase, core rulebook p. 369) draws from this same nuyen budget rather than a separate
one — `create_resources_selection`'s `lifestyle_cost` parameter folds its already-computed total
cost into the one joint over-budget check, instead of `chummer5.engine.lifestyle` duplicating a
second budget validator of its own. See that module's docstring for why lifestyle cost validation
lives here and not there.

**Karma-to-Nuyen conversion (WP43).** Core rulebook p. 94 (Step Six): "Nuyen from this step cannot
convert to Karma, but a player can convert Karma into nuyen if needed: up to 10 Karma at 2,000 nuyen
per Karma point (up to 20,000 nuyen extra)." Confirmed against the legacy engine directly
(`Character.cs`'s `CalculateStartingNuyenFromKarma`,
`CharacterSettings.ChargenKarmaToNuyenExpression` -- default `"{Karma} * 2000 + {PriorityNuyen}"`,
i.e. the converted amount is *added* to the
Resources-priority nuyen budget, not drawn from some separate pool) and against the `.chum5` corpus
(`<nuyenbp>`, the per-character amount actually converted -- nonzero on 6 of the 11 curated mundane
fixtures; `<nuyenmaxbp>`, the *setting's* cap, always `10` for every `Standard`-gameplay-option
settings block in `settings.xml`, matching the rulebook's "experienced runner" default this project
implements -- see `spec/rulebooks/learnings.md`'s WP43 entry for the full citations). Modeled as a
`create_resources_selection` parameter (`karma_converted`) rather than a separate selection type,
the same "fold into the one joint budget check" shape `lifestyle_cost`/`cyberware_cost` already
have -- except karma conversion *enlarges* the budget rather than spending from it.

**Where the double-spend check lives (WP89): the ledger, not this function.** WP43 left converted
Karma outside the Karma accounting entirely, because no unified "leftover Karma" ledger existed for
it to draw down; WP51 built one, and `chummer5.engine.character.Character.karma_spent` now carries
`resources_selection.karma_converted` as one of its terms. So converting Karma shrinks
`karma_remaining` by exactly the amount converted, and every Step Seven spend -- each of which
derives its own `karma_budget` from that property -- sees a smaller budget automatically.

The alternative considered and rejected was giving `create_resources_selection` a `karma_budget`
parameter like its Karma-spending siblings have. It doesn't fit this particular spender: unlike a
quality or a skill rank, this function is **re-called several times within a single build** (once up
front, again once cyberware/bioware are known, again once foci are -- see `chummer5.io.save_format
.build_character`), each time with the *same* conversion but a differently-populated Karma ledger,
since Step Seven's spends are resolved in between. Passing it a budget would mean passing a
different budget each call for one unchanged choice, which is exactly the double-counting trap
WP51's "add this section's own committed cost back in" idiom exists to avoid. The consequence
accepted with that ruling: an over-conversion is not rejected at its own commit point -- it drives
`karma_remaining` negative, and surfaces as every later Step Seven spend being refused, which is
the same "validity is re-derived rather than enforced at construction" shape the Project Overview's
"Character as the single aggregate" section already describes. `karma_to_nuyen` still enforces the
flat 0-10 rulebook cap here, since that one *is* a property of the conversion alone.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, replace

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
from chummer5.data.priorities import PriorityTable
from chummer5.engine.character import Character

# CharacterSettings.ContactPointsExpression (legacy default: `"{CHAUnaug} * 3"`) -- confirmed
# against the core rulebook ("Making Connections", p. 98: "This Karma is equal to a Character's
# Charisma rating x 3") and against every mundane fixture's <contactpoints> tag (see module
# docstring).
#
# **WP81**: the `Unaug` in that legacy expression is now honoured -- `create_contact_selection`
# reads `Character.natural_attribute_value("CHA")`, not `attribute_value("CHA")`. Through WP80 the
# two were the same number by construction (nothing this engine offers augments CHA), and this
# constant's own comment said so; WP81 makes the distinction real for every attribute at once, and
# the core rulebook states this specific exclusion outright (p. 95: "Attributes boosted by
# cyberware or bioware do not affect the calculation for things such as points for Knowledge skills
# or Contacts"). Still a no-op for every character this engine can build today -- no SR5 quality,
# power, cyberware or bioware row in any loaded catalog grants a CHA `ImprovementType.ATTRIBUTE`
# bonus -- but correct by construction rather than by that coincidence holding.
FREE_CONTACT_POINTS_PER_CHARISMA = 3

# CharacterSettings.KarmaContact (legacy default: `_intKarmaContact = 1`) -- Karma cost per point of
# Connection/Loyalty spent beyond the free budget above.
KARMA_PER_EXCESS_CONTACT_POINT = 1

# Core rulebook, "Making Connections": "Any Contacts a player buys must have a minimum rating of 1
# in Connection and a minimum rating of 1 in Loyalty."
MIN_CONTACT_RATING = 1

# Core rulebook p. 94 / CharacterSettings.ChargenKarmaToNuyenExpression's default "{Karma} * 2000 +
# {PriorityNuyen}" -- nuyen gained per Karma point converted at Step Six.
KARMA_TO_NUYEN_RATE = 2000

# Core rulebook p. 94: "up to 10 Karma"; cross-checked against every Standard-gameplay-option
# settings block in legacy/Chummer/data/settings.xml (`<nuyenmaxbp>10</nuyenmaxbp>` uniformly) and
# Miko.chum5's own <nuyenmaxbp>10</nuyenmaxbp>. Hardcoded rather than modeled as a settings knob,
# the same QUALITY_KARMA_LIMIT precedent chummer5.engine.qualities already established.
MAX_KARMA_TO_NUYEN = 10

# Project Overview's 2026-07-21 Availability ruling: new catalogs exclude items with Availability
# > 12 rather than tracking an Availability budget. WP66 is the first place the gear catalog
# enforces this -- scoped to the Rating-priced items it introduces (see build_starter_gear_catalog),
# not retroactively to WP21's flat-cost catalog.
MAX_AVAILABILITY = 12

# WP66: the two Rating-priced gear.xml categories owned by the dedicated Foci bonding system
# (chummer5.data.foci / chummer5.engine.foci), which models them with real Force/Karma-bonding
# semantics. Offering them as plain rating-priced gear would duplicate and misrepresent them (a
# focus must be bonded with Karma to function), so they are excluded from the starter-gear catalog.
_FOCI_GEAR_CATEGORIES = frozenset({"Foci", "Formulae"})

# WP94: the three flat-cost gear categories the Availability<=12 ruling is applied to. Deliberately
# **not** every flat-cost category. Phase P needed the rigger-adjacent slice of the gear catalog to
# stop offering over-cap items (a starting character could buy a Triox UberMensch at 18R); the
# general flat-gear backfill -- every other category here, plus the flat and rating-scaled halves of
# the cyberware catalog -- is a separate, still-unscheduled job, sized in `spec/decisions-log.md`'s
# 2026-08-01 entry. Widening this set is the right way to do that backfill when it is scheduled.
_AVAILABILITY_CAPPED_GEAR_CATEGORIES = frozenset(
    {"Commlinks", "Cyberdecks", "Rigger Command Consoles"}
)


def karma_to_nuyen(karma_spent: int) -> int:
    """`karma_spent * KARMA_TO_NUYEN_RATE`, validated against the 0-10 Karma cap.

    Raises `ValueError` outside `[0, MAX_KARMA_TO_NUYEN]` -- this is a hard rulebook cap (p. 94),
    not a soft nudge the way "must spend the full budget" isn't enforced elsewhere in this engine.
    """
    if not 0 <= karma_spent <= MAX_KARMA_TO_NUYEN:
        raise ValueError(
            f"karma converted to nuyen must be between 0 and {MAX_KARMA_TO_NUYEN}, "
            f"got {karma_spent}"
        )
    return karma_spent * KARMA_TO_NUYEN_RATE


@dataclass(frozen=True)
class Contact:
    """A player-authored contact -- no catalog to pick from (unlike metatypes/qualities/skills),
    since a contact's name/role/connection/loyalty are the player's own invention, not rules data.
    """

    name: str
    connection: int
    loyalty: int
    free: bool = False

    @property
    def points(self) -> int:
        """`Contact.ContactPoints`: `Connection + Loyalty`, floored at 2, or 0 if `free`."""
        if self.free:
            return 0
        return max(self.connection + self.loyalty, 2)


@dataclass(frozen=True)
class ContactSelection:
    """A validated set of contacts and their net effect on the free contact-point budget."""

    contacts: tuple[Contact, ...]
    free_points: int
    points_spent: int
    karma_cost: int


def create_contact_selection(character: Character, contacts: Iterable[Contact]) -> ContactSelection:
    """Build a `ContactSelection`.

    Validates only that every contact's Connection and Loyalty meet the core rulebook's 1-minimum
    each. Does **not** cap total spend at the free budget or at 7 points per contact -- see the
    module docstring for why both would reject this project's own `Yeti-#ffffff2.chum5` golden
    fixture (the first is a real, legacy-supported "pay the karma difference" case; the second is a
    rule the fixture itself violates).
    """
    contacts_t = tuple(contacts)
    for contact in contacts_t:
        if contact.connection < MIN_CONTACT_RATING or contact.loyalty < MIN_CONTACT_RATING:
            raise ValueError(
                f"{contact.name}: Connection and Loyalty must each be at least "
                f"{MIN_CONTACT_RATING}, got Connection={contact.connection} "
                f"Loyalty={contact.loyalty}"
            )

    free_points = character.natural_attribute_value("CHA") * FREE_CONTACT_POINTS_PER_CHARISMA
    points_spent = sum(contact.points for contact in contacts_t)
    karma_cost = max(0, points_spent - free_points) * KARMA_PER_EXCESS_CONTACT_POINT

    return ContactSelection(
        contacts=contacts_t,
        free_points=free_points,
        points_spent=points_spent,
        karma_cost=karma_cost,
    )


@dataclass(frozen=True)
class StarterGearItem:
    """One purchasable item in the starter-gear catalog.

    **WP21**: `category` and `armor_rating` are new, both optional so every pre-WP21 caller/test
    constructing a bare `StarterGearItem(name, cost)` keeps working unchanged. `category` is `None`
    only for hand-authored items in tests, never for anything `build_starter_gear_catalog` produces
    (every real `chummer5.data.gear` entry carries one). `armor_rating` is set only for armor items;
    gear/weapons have no analogous "rating" concept.

    **WP66 (Rating-priced gear).** A `StarterGearItem` now plays two roles for rating-priced items:
    - As a *catalog entry*, `cost_per_rating` (nuyen per rating point) and `max_rating` (the highest
      selectable rating, already clamped to Availability<=12 by `build_starter_gear_catalog`) are
      set, `rating` is None, and `cost` is 0 (the price isn't known until a rating is chosen).
    - As a *purchased item* (inside a `ResourcesSelection.gear`), `rating` is the chosen rating and
      `cost` is the computed `rating * cost_per_rating`; `cost_per_rating`/`max_rating` are carried
      through so the value round-trips.
    All three default to None, so a flat item (`cost_per_rating is None`) is unchanged and every
    pre-WP66 caller keeps working.

    **WP94 (the Matrix stat block).** The six `chummer5.data.gear.Gear` Matrix fields are carried
    through verbatim so the character sheet can render what a Commlink/Cyberdeck/Rigger Command
    Console actually *is*, not just what it cost. All default to None -- most gear is not a Matrix
    device -- and nothing in the engine derives anything from them: no Matrix rules exist here, so
    this is record-and-display only, the discipline WP27 applied to out-of-scope Adept Powers.
    `attribute_array` stays one descending tuple rather than four named attributes, because p. 439
    leaves the Attack/Sleaze/Data Processing/Firewall assignment to the decker.
    """

    name: str
    cost: int
    category: str | None = None
    armor_rating: int | None = None
    cost_per_rating: int | None = None
    max_rating: int | None = None
    rating: int | None = None
    device_rating: int | None = None
    attack: int | None = None
    sleaze: int | None = None
    data_processing: int | None = None
    firewall: int | None = None
    programs: int | None = None
    attribute_array: tuple[int, ...] | None = None


def _availability_capped_max_rating(rating_gear: RatingGear) -> int:
    """The highest rating in `1..max_rating` whose computed `<avail>` stays <= MAX_AVAILABILITY, or
    0 if the item is excluded entirely (a `+`-modifier/unparseable avail, or an avail already over
    the cap at rating 1). Availability is monotonic non-decreasing in rating for every SR5 form, so
    the first rating that breaks the cap ends the range.
    """
    parsed = parse_rating_availability(rating_gear.availability)
    if parsed is None:
        return 0
    slope, intercept = parsed
    offered = 0
    for rating in range(1, rating_gear.max_rating + 1):
        if slope * rating + intercept <= MAX_AVAILABILITY:
            offered = rating
        else:
            break
    return offered


def _flat_availability_over_cap(item: Gear) -> bool:
    """True if a flat-cost gear entry in an Availability-capped category (WP94) prints an
    availability above MAX_AVAILABILITY, or one this parser can't read.

    Reuses `parse_rating_availability`, which returns `(0, N)` for the bare `N`/`NR`/`NF` form
    every SR5 entry in these three categories actually uses. An unreadable `<avail>` excludes the
    row (fail-closed), the same posture `_availability_capped_max_rating` already takes for
    rating-priced gear.
    """
    parsed = parse_rating_availability(item.availability)
    if parsed is None:
        return True
    slope, intercept = parsed
    if slope != 0:
        return True  # a Rating-scaled avail on a flat-cost item: not a shape SR5 produces here
    return intercept > MAX_AVAILABILITY


def build_starter_gear_catalog(
    gear: Iterable[Gear] = (),
    armor: Iterable[Armor] = (),
    weapons: Iterable[Weapon] = (),
    rating_gear: Iterable[RatingGear] = (),
) -> tuple[StarterGearItem, ...]:
    """Build the purchasable starter-gear catalog from WP21's `chummer5.data.gear` loaders.

    Two exclusions beyond a plain conversion, both documented in `chummer5.data.gear`'s module
    docstring:

    - **Drops `hidden` gear/weapon entries outright.** `<hide/>` marks an auto-granted weapon
      *profile* (e.g. buying the real, 1200-cost `Armor`-category "Ballistic Shield" auto-grants a
      same-named, 0-cost `Exotic Melee Weapons` weapon purely so its melee-attack stats exist
      somewhere) -- never something the player picks directly, so it's excluded unconditionally
      rather than only when it happens to collide with another entry's name.
    - **Drops `armor_stacks` items** (Helmet, Ballistic Shield, Riot Shield) -- their `+N` additive
      armor bonus is different math from every other item's single rating, out of scope for this WP.

    Even after both exclusions, one real name collision remains (`Vision Magnification`: a 250-cost
    standalone accessory vs. a 0-cost, `<required>`-gated sensor-housing component -- neither
    `hidden` nor `armor_stacks`), plus ~30 harmless same-cost duplicates (e.g. `Grenade: Flash-Bang`
    priced identically as both `Ammunition` gear and a throwable weapon). Both are resolved the same
    way: **keep the higher-cost entry** -- correct for the genuine collision (0 is never a real
    standalone price once the two exclusions above have already run) and a no-op for the harmless
    ones (equal cost either way).

    **WP66 (Rating-priced gear).** `rating_gear` (from `chummer5.data.gear.load_rating_gear`) adds
    the `Rating * N`-cost items WP21 excluded. Three policy filters live here, not in the loader:
    - **Foci/Formulae categories are dropped** -- they're owned by the dedicated Foci bonding system
      (`chummer5.engine.foci`); offering them as plain gear would duplicate/misrepresent them.
    - **Availability<=12** (`_availability_capped_max_rating`): each item's selectable rating range
      is clamped to where its `<avail>` stays <= 12; an item over the cap even at rating 1 (e.g.
      Plastic Explosive, flat `16F`) is dropped outright. This is the first place the gear catalog
      enforces the 2026-07-21 Availability ruling at all.
    - A rating-priced catalog entry carries `cost_per_rating`/`max_rating` with `cost = 0` (the
      price isn't known until a rating is picked -- see `StarterGearItem`).

    **WP94 (Availability<=12 for the three Matrix-device categories).** Commlinks, Cyberdecks and
    Rigger Command Consoles are flat-cost, so WP66's cap never touched them -- this catalog offered
    a Triox UberMensch (18R) and a Fairlight Excalibur (18R) to a starting character. Those three
    categories are now capped (`_AVAILABILITY_CAPPED_GEAR_CATEGORIES`), dropping 6 rows: Fairlight
    Caliban (14); Shiawase Cyber-5 (15R) and Fairlight Excalibur (18R); Lone Star Remote Commander
    (14R), MCT Drone Web (16R) and Triox UberMensch (18R). Every *other* flat-cost category is
    still uncapped -- deliberately, see `_AVAILABILITY_CAPPED_GEAR_CATEGORIES`' own comment and
    Project Overview's note that the general backfill has no WP scheduled. Each surviving row also
    carries its printed Matrix stat block through to `StarterGearItem` now, for display only.

    One flat/rating name collision exists (`Camera`: a 0-cost `Sensor Functions` component vs. the
    real `Rating * 100` `Vision Devices` item). A rating-priced item displaces a same-named *0-cost*
    flat entry -- the same "0 is never a real standalone price" tie-break the flat collision
    handling already uses -- so the purchasable Camera wins.

    Sorted by `(category, name)` so the web layer can group rows by category directly off catalog
    order, without re-sorting itself.
    """
    by_name: dict[str, StarterGearItem] = {}

    def _consider(item: StarterGearItem) -> None:
        existing = by_name.get(item.name)
        if existing is None or item.cost > existing.cost:
            by_name[item.name] = item

    def _consider_rating(item: StarterGearItem) -> None:
        # A rating-priced item is a real standalone price at rating>=1; it displaces a 0-cost flat
        # component sharing its name (the Camera collision above), but a genuine flat price wins.
        existing = by_name.get(item.name)
        if existing is None or (existing.cost_per_rating is None and existing.cost == 0):
            by_name[item.name] = item

    for g in gear:
        if g.hidden:
            continue
        if g.category in _AVAILABILITY_CAPPED_GEAR_CATEGORIES and _flat_availability_over_cap(g):
            continue
        _consider(
            StarterGearItem(
                name=g.name,
                cost=g.cost,
                category=g.category,
                device_rating=g.device_rating,
                attack=g.attack,
                sleaze=g.sleaze,
                data_processing=g.data_processing,
                firewall=g.firewall,
                programs=g.programs,
                attribute_array=g.attribute_array,
            )
        )
    for a in armor:
        if a.armor_stacks:
            continue
        _consider(
            StarterGearItem(
                name=a.name, cost=a.cost, category=a.category, armor_rating=a.armor_rating
            )
        )
    for w in weapons:
        if w.hidden:
            continue
        _consider(StarterGearItem(name=w.name, cost=w.cost, category=w.category))
    for rg in rating_gear:
        if rg.hidden or rg.category in _FOCI_GEAR_CATEGORIES:
            continue
        offered_max = _availability_capped_max_rating(rg)
        if offered_max < 1:
            continue
        _consider_rating(
            StarterGearItem(
                name=rg.name,
                cost=0,
                category=rg.category,
                cost_per_rating=rg.cost_per_rating,
                max_rating=offered_max,
            )
        )

    return tuple(sorted(by_name.values(), key=lambda item: (item.category or "", item.name)))


# The full SR5-core, flat-cost equipment set (WP21) -- see chummer5.data.gear's module docstring for
# exactly what "flat-cost" excludes (Rating/FixedValues/Variable-cost items, the 3 additive-stacking
# armor items) and how the 5 real cross-file name collisions are resolved. Parsed once at import
# time (Project Overview's "parsed once at startup" rule), not a hand-curated stand-in anymore.
STARTER_GEAR_CATALOG: tuple[StarterGearItem, ...] = build_starter_gear_catalog(
    load_gear(), load_armor(), load_weapons(), load_rating_gear()
)


@dataclass(frozen=True)
class ResourcesSelection:
    """A Resources-priority-letter's nuyen budget plus a validated starter-gear spend.

    **WP20**: `lifestyle_cost` (default 0) is the character's separately-selected
    `chummer5.engine.lifestyle.LifestyleSelection.total_cost`, folded into `nuyen_remaining` here
    rather than in a second, independent check -- see `create_resources_selection`'s docstring and
    `chummer5.engine.lifestyle`'s module docstring for why the two selections share one budget.
    `nuyen_spent` itself stays gear-only (unchanged meaning from WP9), so existing callers reading
    "how much was spent on gear" don't need to account for lifestyle separately.

    **WP34**: `cyberware_cost` (default 0) is the character's separately-selected
    `chummer5.engine.cyberware.CyberwareSelection.nuyen_spent`, folded into `nuyen_remaining` the
    same way `lifestyle_cost` already is -- see `create_resources_selection`'s docstring.

    **WP45**: `bioware_cost` (default 0) is the character's separately-selected `chummer5.engine
    .bioware.BiowareSelection.nuyen_spent`, folded in the same way `cyberware_cost` already is.

    **WP43**: `karma_converted` (default 0) is however much Karma the player converted to nuyen at
    2,000 nuyen/point (core rulebook p. 94) -- unlike `lifestyle_cost`/`cyberware_cost`/
    `bioware_cost`, this *enlarges* the available budget rather than spending from it.
    `nuyen_budget` itself stays the pure priority-derived number (unchanged meaning, still
    `== legacy.starting_nuyen` for every fixture); `nuyen_remaining` is the one field that reflects
    the karma-derived top-up.

    **WP47**: `foci_cost` (default 0) is the character's separately-selected `chummer5.engine.foci
    .FociSelection.nuyen_cost`, folded in the same way `cyberware_cost`/`bioware_cost` already are.

    **WP92**: `vehicle_cost` (default 0) is the character's separately-selected
    `chummer5.engine.vehicles.VehicleSelection.nuyen_spent`, folded in the same way again. p. 94's
    Step Six Gear Checklist names "Vehicle(s), p. 461 / Drones..., p. 461" alongside gear and
    cyberware, so it is the same single Resources-priority pool, not a second budget.
    """

    resources_letter: str
    nuyen_budget: int
    gear: tuple[StarterGearItem, ...]
    nuyen_spent: int
    nuyen_remaining: int
    lifestyle_cost: int = 0
    cyberware_cost: int = 0
    bioware_cost: int = 0
    karma_converted: int = 0
    foci_cost: int = 0
    vehicle_cost: int = 0


def starting_nuyen(letter: str, priorities: PriorityTable) -> int:
    return priorities.resources[letter].nuyen


def available_nuyen(letter: str, priorities: PriorityTable, karma_converted: int = 0) -> int:
    """`starting_nuyen` plus whatever `karma_converted` Karma points convert to (WP43) -- the real
    total budget gear/lifestyle/cyberware purchases draw against. A thin composition, factored out
    since every one of `chummer5.web.app`'s several independent budget-display sites needs exactly
    this sum, not just the priority-derived half of it.
    """
    return starting_nuyen(letter, priorities) + karma_to_nuyen(karma_converted)


def resources_gear_args(
    selection: ResourcesSelection,
) -> tuple[tuple[str, ...], tuple[tuple[str, int], ...]]:
    """Split a committed selection's purchased items back into the `(gear_names, rating_gear)`
    argument pair `create_resources_selection` takes (WP66).

    Every carry-forward site (a priority reconfirm, a Lifestyle/cyberware edit re-validating the
    shared budget) reconstructs the resources arguments from the already-committed
    `character.resources_selection` rather than the raw form. Before rating-priced gear this was a
    bare `tuple(item.name for item in selection.gear)`; that would collapse a rating item to a name
    with no rating, losing the choice (and failing re-validation, since a rating item isn't a valid
    flat `gear_names` entry). This helper preserves each rating item's chosen rating instead.
    """
    flat: list[str] = []
    rated: list[tuple[str, int]] = []
    for item in selection.gear:
        if item.rating is not None:
            rated.append((item.name, item.rating))
        else:
            flat.append(item.name)
    return tuple(flat), tuple(rated)


def create_resources_selection(
    letter: str,
    priorities: PriorityTable,
    gear_names: Iterable[str],
    catalog: Iterable[StarterGearItem] = STARTER_GEAR_CATALOG,
    *,
    rating_gear: Iterable[tuple[str, int]] = (),
    lifestyle_cost: int = 0,
    cyberware_cost: int = 0,
    bioware_cost: int = 0,
    karma_converted: int = 0,
    foci_cost: int = 0,
    vehicle_cost: int = 0,
) -> ResourcesSelection:
    """Build a `ResourcesSelection`, validating the combined gear + lifestyle + cyberware + bioware
    + foci spend against the nuyen budget (priority-derived, plus whatever Karma-to-Nuyen conversion
    adds).

    Validates: every name in `gear_names` is a `catalog` item's name (repeats allowed -- buying two
    Certified Credsticks is a normal purchase, unlike a quality or skill that can't be picked
    twice); every `(name, rating)` in `rating_gear` (WP66) names a Rating-priced catalog item and
    has `1 <= rating <= max_rating` (its cost is `rating * cost_per_rating`, repeats allowed for
    quantity); `karma_converted` is 0-10 (see `karma_to_nuyen`); `gear` cost plus `lifestyle_cost`
    plus `cyberware_cost` plus `bioware_cost` plus `foci_cost` together don't exceed `letter`'s
    nuyen budget plus the converted amount (WP20: a character's primary Lifestyle draws from this
    same pool, confirmed against every one of the 11 curated mundane fixtures -- see
    `spec/rulebooks/learnings.md`'s WP20 entry; WP34: cyberware draws from it too, see
    `chummer5.engine.cyberware`'s own module docstring; WP45: bioware draws from it too, see
    `chummer5.engine.bioware`'s own module docstring; WP47: Foci draws from it too, see
    `chummer5.engine.foci`'s own module docstring; WP43: Karma-to-Nuyen tops up the same pool, see
    this module's own docstring; WP92: vehicles/drones draw from it too, see
    `chummer5.engine.vehicles`'s own module docstring). Does not require the full budget to be
    spent, mirroring WP6/WP7/WP8's identical choice. `lifestyle_cost`/`cyberware_cost`/
    `bioware_cost`/`karma_converted`/`foci_cost`/`vehicle_cost` each default to 0 so every
    pre-WP20/pre-WP34/pre-WP45/pre-WP43/pre-WP47/pre-WP92 call site is unaffected.
    """
    by_name = {item.name: item for item in catalog}
    names = list(gear_names)

    unknown = sorted({name for name in names if name not in by_name})
    if unknown:
        raise ValueError(f"not a starter-gear catalog item: {unknown}")

    flat_selected = tuple(by_name[name] for name in names)

    # WP66: rating-priced picks -- each (name, rating) becomes a purchased StarterGearItem carrying
    # its chosen rating and the computed cost = rating * cost_per_rating. Repeats are allowed for
    # quantity, exactly like flat gear_names.
    rating_selected: list[StarterGearItem] = []
    for name, rating in rating_gear:
        item = by_name.get(name)
        if item is None or item.cost_per_rating is None or item.max_rating is None:
            raise ValueError(f"not a Rating-priced starter-gear catalog item: {name!r}")
        if not 1 <= rating <= item.max_rating:
            raise ValueError(
                f"{name}: rating must be between 1 and {item.max_rating}, got {rating}"
            )
        rating_selected.append(replace(item, cost=rating * item.cost_per_rating, rating=rating))

    selected = flat_selected + tuple(rating_selected)
    budget = starting_nuyen(letter, priorities)
    available = budget + karma_to_nuyen(karma_converted)
    spent = sum(item.cost for item in selected)
    total_spent = spent + lifestyle_cost + cyberware_cost + bioware_cost + foci_cost + vehicle_cost
    if total_spent > available:
        parts = [f"gear ({spent})"]
        if lifestyle_cost:
            parts.append(f"lifestyle ({lifestyle_cost})")
        if cyberware_cost:
            parts.append(f"cyberware ({cyberware_cost})")
        if bioware_cost:
            parts.append(f"bioware ({bioware_cost})")
        if foci_cost:
            parts.append(f"foci ({foci_cost})")
        if vehicle_cost:
            parts.append(f"vehicles ({vehicle_cost})")
        if len(parts) == 1:
            raise ValueError(
                f"gear spend {spent} exceeds Resources priority {letter}'s nuyen budget of "
                f"{available}"
            )
        raise ValueError(
            f"{' + '.join(parts)} spend {total_spent} exceeds Resources priority {letter}'s "
            f"nuyen budget of {available}"
        )

    return ResourcesSelection(
        resources_letter=letter,
        nuyen_budget=budget,
        gear=selected,
        nuyen_spent=spent,
        nuyen_remaining=available - total_spent,
        lifestyle_cost=lifestyle_cost,
        cyberware_cost=cyberware_cost,
        bioware_cost=bioware_cost,
        karma_converted=karma_converted,
        foci_cost=foci_cost,
        vehicle_cost=vehicle_cost,
    )
