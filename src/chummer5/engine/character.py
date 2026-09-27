"""`Character` aggregate: metatype selection and attribute point allocation.

First real slice of chargen. Composes WP2's static rules data (`chummer5.data.metatypes`,
`chummer5.data.priorities`) with WP5's Improvement engine into a buildable, mundane,
priority-created character. Mundane fields only — no magic/resonance, no metavariants, no
cyberware/gear; see `spec/Project Overview.md`'s MVP scope and `spec/worklogs/WP6.md` for the
rules research this was checked against.

Two separate point pools feed attribute allocation, confirmed by reading both the legacy source
(`SelectMetatypePriority.cs`, `Attribute.Core.cs`) and the `Yeti-#ffffff2.chum5` fixture:
- The **Attributes** priority letter (`chummer5.data.priorities.AttributesPriority.points`) funds
  the 8 primary attributes (BOD/AGI/REA/STR/CHA/INT/LOG/WIL).
- The **Heritage** priority letter, combined with the chosen metatype, funds a separate
  "special attribute points" pool (`HeritageMetatypeOption.special_attribute_points`) that pays
  for EDG (and, outside MVP's mundane scope, MAG/RES). These are not one merged budget — a
  Human at Heritage D gets 3 special-attribute points independent of which Attributes letter was
  picked, and that budget cannot be spent on a primary attribute or vice versa.

`Attribute.Value = metatype minimum + points spent + Σ improvements`, per the Project Overview.
No metatype/priority-derived Improvement instances actually exist yet for MVP's 5 core metatypes
(confirmed: none of Human/Elf/Dwarf/Ork/Troll's `<bonus>` nodes grant an attribute effect) — the
`improvements` index is threaded through from the start so WP8's quality bonuses have somewhere to
land without a later reshape, but it resolves to 0 for every attribute until then.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass, replace
from types import MappingProxyType
from typing import TYPE_CHECKING

from chummer5.data.metatypes import AttributeRange, Metatype
from chummer5.data.priorities import HeritagePriority, PriorityTable
from chummer5.data.qualities import Quality
from chummer5.engine.biography import Biography
from chummer5.engine.improvements import ImprovementIndex, ImprovementType

if TYPE_CHECKING:
    # Deferred to type-checking only: `chummer5.engine.{qualities,resources,skills,magic}` each
    # import `Character` from this module, so importing them back here at runtime would be
    # circular. Safe under `from __future__ import annotations` (PEP 563) -- every annotation in
    # this module, including dataclass field types, is a lazily-evaluated string, so
    # `dataclasses.dataclass` never needs these names to actually resolve at import time.
    from chummer5.data.traditions import Tradition
    from chummer5.engine.bioware import BiowareSelection
    from chummer5.engine.cyberware_subsystems import CyberwareTreeSelection
    from chummer5.engine.foci import FociSelection
    from chummer5.engine.knowledge import KarmaKnowledgeSelection, KnowledgeSelection
    from chummer5.engine.lifestyle import LifestyleSelection
    from chummer5.engine.magic import PowerSelection, SpellSelection
    from chummer5.engine.qualities import QualitySelection
    from chummer5.engine.resources import ContactSelection, ResourcesSelection
    from chummer5.engine.skills import KarmaSkillSelection, SkillAllocation
    from chummer5.engine.spirits import BoundSpiritSelection
    from chummer5.engine.vehicles import VehicleSelection

# MVP content-scope filter (see Project Overview's "Core rulebook only" note and WP2's worklog):
# every data-driven choice offered to the player is restricted to entries sourced from the SR5
# core rulebook. For metatypes.xml this happens to reduce to exactly the 5 Metahuman base types
# (Human/Elf/Dwarf/Ork/Troll) as a side effect, since every metavariant and every non-Metahuman
# metatype is sourced from a later book.
CORE_RULEBOOK_SOURCE = "SR5"

# The 8 attributes funded by the Attributes priority letter.
PRIMARY_ATTRIBUTES = ("BOD", "AGI", "REA", "STR", "CHA", "INT", "LOG", "WIL")
# Funded by the Heritage-priority/metatype "special attribute points" pool instead. MAG/RES are
# also special attributes in the legacy data, but mundane MVP characters never buy them (Talent is
# forced to E, "Mundane" — see Project Overview) so they're excluded here rather than modeled as
# an always-zero-budget option.
SPECIAL_ATTRIBUTES = ("EDG",)
ALLOCATABLE_ATTRIBUTES = PRIMARY_ATTRIBUTES + SPECIAL_ATTRIBUTES

# WP35: the resolution target `ImprovementType.ESSENCE` improvements are always attached at
# (chummer5.engine.cyberware.apply_cyberware_improvements) -- there is only one Essence pool per
# character, the same reasoning chummer5.engine.derived's own `_GLOBAL_TARGET` sentinel documents.
# Duplicated here (rather than imported from derived.py) to avoid a circular import: derived.py
# already imports `Character` from this module.
_ESSENCE_TARGET = ""

# WP51: core rulebook p. 64, "All characters in Shadowrun start with 25 Karma they will use to
# improve themselves" -- cross-checked against the Step Four worked example (James ends Step Four
# with 26 Karma, not 25, having spent 19 on Positive Qualities and gained 20 from Negative ones --
# i.e. the pool moves from this fixed starting point, it isn't itself variable). Formerly
# `chummer5.engine.spirits.STARTING_KARMA` (WP46); moved here as the unified ledger's one home --
# see `Character.karma_remaining`'s own docstring.
STARTING_KARMA = 25

# WP52: core rulebook p.106-107, "the cost to improve an attribute is new Rating x 5 Karma" (see
# the "KARMA ADVANCEMENT TABLE FOR ATTRIBUTES", reconstructed and confirmed exactly by WP51's own
# research pass -- spec/rulebooks/learnings.md's WP51 entry). Applies uniformly to every
# `ALLOCATABLE_ATTRIBUTES` code (the Training Rate Table lists "Improving an attribute (Mental,
# Physical, Magic, Resonance)" and "Improving Edge" as the same Karma-cost table, just different
# training time) -- WP52 itself only offers this on `ALLOCATABLE_ATTRIBUTES` (Mental/Physical/EDG),
# deliberately excluding MAG/RES as their own, not-yet-built follow-up (see
# `KarmaAttributeSelection`'s own docstring).
ATTRIBUTE_KARMA_PER_RATING = 5


def karma_advancement_cost(start_rating: int, points: int, karma_per_rating: int) -> int:
    """Cumulative Karma cost to raise a rating by `points` steps from `start_rating`, `new_rating
    x karma_per_rating` summed per step -- the shared shape behind every row of the core
    rulebook's Karma Advancement Tables (p.106-107): Attributes use `karma_per_rating=5`
    (`ATTRIBUTE_KARMA_PER_RATING` above); Active Skills/Skill Groups/Knowledge & Language Skills
    (WP53) use 2/5/1 respectively over the identical cumulative shape -- see
    `spec/rulebooks/learnings.md`'s WP51 entry for the table cross-check that confirmed all four.
    `points=0` costs `0` (no steps to sum).
    """
    return sum((start_rating + step) * karma_per_rating for step in range(1, points + 1))


def sr5_metatypes(metatypes: tuple[Metatype, ...]) -> tuple[Metatype, ...]:
    """Restrict a metatype catalog to `source == "SR5"` entries.

    WP2 deliberately left `load_metatypes()` unfiltered (it keeps every book's content, `source`
    field intact) and left this filter to whichever WP first offers metatypes as a player choice —
    that's this one. See `spec/worklogs/WP2.md`.
    """
    return tuple(m for m in metatypes if m.source == CORE_RULEBOOK_SOURCE)


@dataclass(frozen=True)
class MetatypeChoice:
    """One metatype selectable under a specific Heritage priority letter.

    `special_attribute_points` and `karma` are that Heritage letter's cost for *this* metatype
    specifically (both vary per metatype at a given letter) — not a property of the `Metatype`
    itself, which is why this is a distinct dataclass rather than reusing `Metatype` directly.
    """

    metatype: Metatype
    special_attribute_points: int
    karma: int


def metatype_choices(
    heritage: HeritagePriority, metatypes: tuple[Metatype, ...]
) -> tuple[MetatypeChoice, ...]:
    """Cross-reference one Heritage priority letter's metatype list against the SR5-scoped catalog.

    `priorities.xml`'s Heritage metatype lists include every book's metatypes (A.I., Centaur, every
    Shapeshifter, ...), matched here by name against `sr5_metatypes()` — entries with no match
    (anything not `source == "SR5"`) are silently dropped, the same "excluded, not erroring" MVP
    content-scope filter applied everywhere else (WP3's quality catalog, WP2's metatype/quality
    filters). Metavariants (both the metatype's own and the Heritage option's nested metavariant
    list) are out of MVP scope entirely and are not consulted here.
    """
    by_name = {m.name: m for m in sr5_metatypes(metatypes)}
    choices = []
    for option in heritage.metatypes:
        metatype = by_name.get(option.name)
        if metatype is None:
            continue
        choices.append(
            MetatypeChoice(
                metatype=metatype,
                special_attribute_points=option.special_attribute_points,
                karma=option.karma,
            )
        )
    return tuple(choices)


@dataclass(frozen=True)
class Character:
    """A mundane, priority-built character-in-progress: metatype, attribute points, plus whatever
    later chargen stages have been committed so far.

    `attribute_points` holds however many points were spent above the metatype minimum for each
    of `ALLOCATABLE_ATTRIBUTES` — the source of those points (Attributes-priority budget vs.
    special-attribute-points budget) is a construction-time concern (`create_character`'s
    validation), not part of the finished character's own state.

    **WP18's fold**: `skill_allocation`/`quality_selection`/`contact_selection`/
    `resources_selection` make `Character` the single aggregate for a character-in-progress,
    replacing the prior design where only metatype/attributes lived here and the other four
    selections were sibling fields independently threaded through `chummer5.web.session
    .ChargenSession` and reunited ad hoc in `chummer5.io.save_format`'s now-retired
    `BuiltCharacter`. Each defaults to `None` until that stage of chargen is committed — the same
    "unset until confirmed" shape `attribute_points`/`improvements` already had before any points
    were spent. `create_character` itself does not set any of the four; a caller building up a
    character stage by stage does so via `dataclasses.replace(character, skill_allocation=...)`
    etc. against its existing `Character`, not by calling `create_character` again (which would
    also hand back a fresh, empty `improvements` index -- see that function's own docstring).

    **WP20** adds a 5th selection, `lifestyle_selection`, the same "`None` until committed" shape.
    Unlike the other four, its nuyen cost is validated jointly with `resources_selection`'s gear
    spend against one shared Resources-priority budget (see `chummer5.engine.resources
    .create_resources_selection`'s `lifestyle_cost` parameter) rather than independently -- see
    `chummer5.engine.lifestyle`'s module docstring.

    **WP23** adds `metatype_qualities`, the qualities `metatype` grants for free (e.g. Elf -> Low-
    Light Vision) -- unlike every field above, this is never player-submitted; it's always exactly
    `chummer5.engine.qualities.resolve_metatype_qualities(metatype, catalog)`'s output, kept in sync
    with `metatype` by the same "(re)construct a `Character`" call sites that already carry
    `quality_selection`/etc. forward (see `chummer5.web.app._relink_metatype_qualities`).

    **WP25** adds `magic_type`/`magic_rating`/`tradition`/`magic_granted_skill_ids` -- Phase I's
    Magic-type, Magic-rating, tradition, and Talent-free-skill-grant selection. Deliberately **4
    flat fields, not one wrapping `MagicSelection` field** -- unlike `skill_allocation`/
    `quality_selection`/etc. (each a validated bundle a *later* WP reads back out as a whole),
    `magic_type`/`magic_rating`/`tradition` are each read individually and often (`attribute_value`
    below dispatches on `magic_type` for every MAG-linked skill's dice pool, not just once per
    render), so flattening them here avoids an `if character.magic_selection` unwrap at every call
    site. `chummer5.engine.magic.create_magic_selection` is still the single validated
    construction path (mirrors `MetatypeChoice`'s relationship to `metatype`/`heritage_letter`/etc.
    above) -- its `MagicSelection` return value is what a caller unpacks via
    `dataclasses.replace(character, magic_type=selection.magic_type, ...)`, not stored wholesale.
    `magic_type` is `None`/`magic_rating` is `0`/`tradition` is `None`/`magic_granted_skill_ids` is
    `()` for a Mundane character (including every pre-WP25 `Character`, via these fields'
    defaults) -- the same "unset means Mundane, not merely uncommitted" shape the Project
    Overview's "Talent forced to E" MVP scoping already established, just no longer hardcoded.

    **Post-WP29 correction, `magic_attribute_points`.** WP25 originally claimed MAG is deliberately
    *not* point-bought at all -- wrong, confirmed against both the rulebook (p.65: Special Attribute
    Points "may be split... between... Edge and Magic or Resonance") and the legacy engine (MAG uses
    the exact same `RawMetatypeMinimum + Base` formula as EDG, just with a Talent-sourced minimum
    instead of a metatype-sourced one; see `spec/rulebooks/learnings.md`'s "Post-WP29 correction"
    entry for the full citations). `magic_attribute_points` holds however many points beyond
    `magic_rating` were spent from the *same* Heritage-derived special-attribute-points pool EDG
    draws from -- validated jointly with EDG by
    `chummer5.engine.magic.create_magic_attribute_points` (mirroring `chummer5.engine.lifestyle`'s
    cross-selection shared-budget precedent for gear/Lifestyle), not folded into `attribute_points`/
    `SPECIAL_ATTRIBUTES` itself: MAG's allocatability
    is character-specific (only legal once `magic_type` is set), unlike EDG's, which `create_
    character` can validate unconditionally for every character. `0` for Mundane and for any
    `Character` that predates this correction (the same "unset means nothing spent" default every
    other WP18+ selection field has).

    Per the Implementation Plan's Phase I intro finding, **MAG still isn't added to
    `SPECIAL_ATTRIBUTES`/`ALLOCATABLE_ATTRIBUTES`** (`create_character`'s own validated set) --
    that finding about the *budget it's funded from* (not the Attributes-priority letter the
    primary 8 attributes use) was correct; only "cannot be raised with points at all" was wrong.
    `attribute_value` below still special-cases `"MAG"` (now adding `magic_attribute_points` too,
    not just returning `magic_rating` flat) rather than teaching `attribute_range`/the generic
    formula about a Talent-sourced minimum (WP35, later, changes this further to also account for
    Essence-driven Magic loss -- see that WP's own scope).

    **WP26** adds `spell_selection: SpellSelection | None` -- a Magician's chosen spells, the same
    "`None` until committed" shape every other selection field already has. Unlike `magic_type`/
    `magic_rating`/etc., nothing in this engine reads `spell_selection` to compute another value (a
    spell is a chargen-time roster entry, not a computed value -- see `chummer5.engine.magic`'s
    module docstring), so it stays a single wrapping field (mirrors `quality_selection`/
    `contact_selection`'s shape) rather than being flattened the way the Phase I magic fields were.

    **WP27** adds `power_selection: PowerSelection | None` -- an Adept's purchased Powers, the same
    "`None` until committed" wrapping-field shape as `spell_selection` (nothing reads it piecemeal
    either). Unlike a spell, a purchased Power's `FLAT_BONUS` effects *do* feed `improvements` (via
    `chummer5.engine.magic.apply_power_improvements`, mirroring `quality_selection`'s relationship
    to `apply_quality_improvements`) -- `power_selection` itself still just holds the validated
    roster + Power Point spend, the same "selection is a record, Improvements are a side effect of
    applying it" split every prior selection type already has.

    **WP32** adds `cyberware_selection` -- purchased cyberware, the same "`None` until committed"
    wrapping-field shape as `power_selection` (nothing reads it piecemeal; every effect -- Essence
    cost, and any `<bonus>` -- reaches `improvements` via an `apply_*_improvements` call, not via a
    field read directly). **WP41** retypes it from WP32's flat `CyberwareSelection` to Phase K's
    `chummer5.engine.cyberware_subsystems.CyberwareTreeSelection`: a purchase is a *tree* now (a
    cyberlimb/cybereye/cyberear holding plugins that charge its Capacity instead of the character's
    Essence), and a `Character` carries exactly one cyberware shape -- WP38 deliberately added no
    field for the tree so that "a character holding both, each charging Essence" could never arise
    while the two coexisted. A flat purchase is simply a zero-plugin tree.

    **WP45** adds `bioware_selection: BiowareSelection | None` -- purchased bioware, the identical
    "`None` until committed" wrapping-field shape as `cyberware_selection` (same reasons: nothing
    reads it piecemeal, every effect reaches `improvements` via `chummer5.engine.bioware
    .apply_bioware_improvements`). Bioware and cyberware are still two separate fields, not one
    merged "augmentation" list -- `chummer5.data`/`chummer5.engine` already keep the two catalogs
    and selection types separate (see `chummer5.engine.bioware`'s own module docstring for why),
    even though both draw from the same nuyen budget and reduce the same Essence pool.

    **WP46** adds `bound_spirit_selection: BoundSpiritSelection | None` -- a Magician's bound
    spirits, the same "`None` until committed" wrapping-field shape as `spell_selection` (a bound
    spirit is a pure roster entry with a Karma cost, no computed Improvement -- see
    `chummer5.engine.spirits`'s module docstring; nothing reads it piecemeal either). Deliberately
    a wrapping selection field, not the Implementation Plan's own initial sketch of a bare
    `bound_spirits: tuple[BoundSpirit, ...]` -- the wrapper also carries `karma_cost`/`karma_budget`
    so a render can show "N of budget Karma spent" without recomputing it, the same reason
    `SpellSelection` wraps `spells` with its own `budget` field instead of being a bare tuple.

    **WP47** adds `foci_selection: FociSelection | None` -- a magically active character's bonded
    foci, the same "`None` until committed" wrapping-field shape as `bound_spirit_selection` (wraps
    `picks` alongside `nuyen_cost`/`karma_cost`/both budgets for the same "avoid recomputing on
    every render" reason). Unlike Bound Spirits, `foci_selection` *does* feed `improvements` for
    any pick whose catalog item is `FLAT_BONUS` (`chummer5.engine.foci.apply_foci_improvements`),
    mirroring `power_selection`'s "selection is a record, Improvements are a side effect of
    applying it" split.

    **WP35** adds no new field -- it changes `attribute_value("MAG")`'s own formula to subtract
    `magic_essence_loss` (Σ `ESSENCE` improvements, ceiling-rounded per the rulebook's "per point or
    fraction thereof" wording), the cross-phase interaction between Phase I's Magic rating and
    Phase J's Essence tracking. `magic_rating_before_essence_loss`/`magic_essence_loss` are exposed
    as separate properties purely so the character sheet can show *why* a reduced rating is reduced
    (see those properties' own docstrings) -- `attribute_value("MAG")` remains the one real,
    Essence-reduced value every other computation (dice pools, `power_points`) reads.

    **WP51 adds no new field either -- `karma_spent`/`karma_remaining` are computed properties, not
    stored state.** Phase O's unified Karma ledger, replacing the several independent one-shot
    checks `quality_selection`/`contact_selection`/`bound_spirit_selection`/`foci_selection` each
    used to validate their own Karma cost against separately (the pre-WP51 pattern
    `chummer5.engine.spirits.provisional_karma_budget`, now retired, made explicit: every caller
    had to remember to sum each already-committed selection's `karma_cost` by hand). A computed
    property is the right shape here for the same reason the class docstring's opening paragraph
    already established for `Character` as a whole: every summand (`quality_selection.karma_cost`,
    etc.) is itself already a validated, frozen sub-object's own resolved cost, so there is nothing
    to incrementally track -- summing them fresh on every read is cheap (character-sized, not
    corpus-sized) and can never drift out of sync with whatever is actually committed, the same
    "reconstruct wholesale to validate" principle the Project Overview's Improvement-engine section
    applies to jointly-constrained values. `karma_remaining` naturally starts at
    `STARTING_KARMA - quality_selection.karma_cost` once qualities are committed and nothing else
    is -- which is already the rulebook's own "post-Step-Four total" (James/Rob/Kyra's 26/25/26, not
    a flat 25), with no separate "starting Karma" field needed, since `QualitySelection.karma_cost`
    is already signed (`positive_karma - negative_karma`) to produce exactly that net effect. Widens
    automatically as future Phase O WPs (attribute/skill/spell Karma spends, WP52-54) add their own
    fields -- each just needs one more `+ (self.x_selection.karma_cost if ... else 0)` term below,
    mirroring how `bound_spirit_selection`/`foci_selection` joined the sum in WP46/WP47 before this
    property existed to hold them.

    **WP52** adds `karma_attribute_selection: KarmaAttributeSelection | None` -- leftover-Karma-
    funded attribute increases (Step Seven), the same "`None` until committed" wrapping-selection
    shape as `bound_spirit_selection`/`foci_selection` (wraps `points` alongside its own resolved
    `karma_cost`, so a render can show "N Karma spent on attributes" without recomputing it).
    `attribute_value` reads `karma_attribute_selection.points` as one more additive term on top of
    `attribute_points`, and `karma_spent` gains a matching `karma_attribute_selection.karma_cost`
    term -- see `create_karma_attribute_points`'s own docstring for the validation (cost formula,
    metatype-maximum check, and the "only one Mental/Physical attribute at natural maximum" rule).

    **WP53** adds `karma_skill_selection: KarmaSkillSelection | None` and `karma_knowledge_
    selection: KarmaKnowledgeSelection | None` -- leftover-Karma-funded Active skill/skill-group/
    specialization spend and Knowledge/Language rating spend respectively, the identical
    "`None` until committed" wrapping-selection shape as `karma_attribute_selection` (each wraps its
    own resolved `karma_cost`). Two separate fields, not one -- see `chummer5.engine.skills`'
    module docstring's own WP53 paragraph for why (different catalogs, different web-layer routes).
    Neither is read by `attribute_value`; `chummer5.engine.skills.skill_rating`/`dice_pool` read
    `karma_skill_selection` directly off `character` (mirroring how `skill_rating` already reads
    `character.improvements` directly rather than taking it as a parameter), and nothing in this
    engine computes a Knowledge/Language "dice pool" for `karma_knowledge_selection` to feed --
    it's a pure roster-rating increase, the same reason `KnowledgeSelection` itself isn't read
    piecemeal by any formula. `karma_spent` gains matching terms for both.

    **WP92** adds `vehicle_selection: VehicleSelection | None` -- purchased stock vehicles and
    drones, the same "`None` until committed" wrapping-field shape as `bioware_selection`. The
    plainest selection field on this class: a vehicle purchase grants no Improvement of any kind
    (nothing about a vehicle changes a *character* number -- see `chummer5.engine.vehicles`'s
    module docstring), so unlike cyberware/bioware there is no `apply_*_improvements` counterpart,
    and unlike qualities/foci there is no Karma term for `karma_spent` to pick up. It spends only
    from the shared Step Six nuyen pool, via `ResourcesSelection.vehicle_cost`.

    **WP54** adds no new field -- it widens `spell_selection` itself (`SpellSelection.karma_
    spell_count`/`.karma_cost`, see `chummer5.engine.magic`'s own WP54 paragraph) so a Magician can
    spend leftover Karma on spells beyond the Talent-granted free budget, up to the rulebook's
    "Magic Rating x 2" known-spells cap. `karma_spent` gains a matching `spell_selection.karma_cost`
    term, the same "one more selection joins the sum" pattern WP52/WP53 already established.
    """

    metatype: Metatype
    heritage_letter: str
    attributes_letter: str
    special_attribute_points: int
    attribute_points: MappingProxyType[str, int]
    improvements: ImprovementIndex
    skill_allocation: SkillAllocation | None = None
    quality_selection: QualitySelection | None = None
    contact_selection: ContactSelection | None = None
    resources_selection: ResourcesSelection | None = None
    lifestyle_selection: LifestyleSelection | None = None
    metatype_qualities: tuple[Quality, ...] = ()
    magic_type: str | None = None  # Talent codename: "Magician"/"Adept"; None for Mundane (WP25)
    # WP121: an Aspected Magician's group ("Sorcery"/"Conjuring"/"Enchanting"); None otherwise.
    magic_aspect: str | None = None
    magic_rating: int = 0  # the Talent-granted starting MAG rating; 0 for Mundane (WP25)
    tradition: Tradition | None = None  # Magician only (WP25)
    magic_granted_skill_ids: tuple[str, ...] = ()  # the Talent free-skill grant's picks (WP25)
    spell_selection: SpellSelection | None = None  # Magician's chosen spells (WP26)
    power_selection: PowerSelection | None = None  # Adept's purchased Powers (WP27)
    # WP32, retyped to the WP38 purchase tree in WP41 -- see class docstring.
    cyberware_selection: CyberwareTreeSelection | None = None
    bioware_selection: BiowareSelection | None = None  # purchased bioware (WP45)
    # Special Attribute Points spent raising MAG beyond magic_rating (post-WP29 correction; see
    # class docstring's own paragraph and chummer5.engine.magic.create_magic_attribute_points).
    magic_attribute_points: int = 0
    bound_spirit_selection: BoundSpiritSelection | None = None  # Magician's bound spirits (WP46)
    foci_selection: FociSelection | None = None  # magic-active character's bonded foci (WP47)
    knowledge_selection: KnowledgeSelection | None = None  # Knowledge/Language skills (WP49)
    # Leftover-Karma-funded attribute increases beyond the priority budget (Step Seven, WP52).
    karma_attribute_selection: KarmaAttributeSelection | None = None
    # Leftover-Karma-funded Active skill/skill-group/specialization spend (Step Seven, WP53).
    karma_skill_selection: KarmaSkillSelection | None = None
    # Leftover-Karma-funded Knowledge/Language skill rating spend (Step Seven, WP53).
    karma_knowledge_selection: KarmaKnowledgeSelection | None = None
    # Purchased stock vehicles/drones (Phase P, WP92).
    vehicle_selection: VehicleSelection | None = None
    # WP109: names of purchased armor the player has marked as *not* worn. Everything bought is
    # worn by default, which for body armor means "the highest rating counts" (p. 169) -- see
    # `chummer5.engine.derived.armor_breakdown`. A plain name set, not part of
    # `resources_selection`, so none of the many sites that re-validate the nuyen budget has to
    # carry it along.
    unworn_armor: frozenset[str] = frozenset()
    # WP134: name, alias, concept and the rest of the Bio page. Feeds no rule.
    biography: Biography = Biography()

    @property
    def karma_spent(self) -> int:
        """Σ every committed Karma-spending (or, for net-negative Qualities, Karma-refunding)
        selection's own `karma_cost` -- see class docstring's WP51 paragraph. `0` for a selection
        that hasn't been committed yet (`None`), the same "unset means not yet spent" default every
        other selection field already has.
        """
        return (
            (self.quality_selection.karma_cost if self.quality_selection is not None else 0)
            + (self.contact_selection.karma_cost if self.contact_selection is not None else 0)
            + (
                self.bound_spirit_selection.karma_cost
                if self.bound_spirit_selection is not None
                else 0
            )
            + (self.foci_selection.karma_cost if self.foci_selection is not None else 0)
            + (
                self.karma_attribute_selection.karma_cost
                if self.karma_attribute_selection is not None
                else 0
            )
            + (
                self.karma_skill_selection.karma_cost
                if self.karma_skill_selection is not None
                else 0
            )
            + (
                self.karma_knowledge_selection.karma_cost
                if self.karma_knowledge_selection is not None
                else 0
            )
            + (self.spell_selection.karma_cost if self.spell_selection is not None else 0)
            # WP89: Step Six's Karma-to-Nuyen conversion is a Karma *spend*, not a free top-up --
            # core rulebook p. 94, "players can convert some of their Karma to nuyen if they need a
            # little more to spend. They may convert up to 10 Karma at a rate of 2,000 nuyen per
            # Karma point", and Step Seven is titled "Spending Your Left Over Karma", i.e. what
            # Step Six left. WP43 deliberately deferred wiring this because no unified ledger
            # existed to draw it down; WP51 built one, and this is the term that was waiting for it.
            # Note this is the one term that isn't a `karma_cost` field: `ResourcesSelection`
            # records how many Karma *points* were converted, and a point is worth a point.
            + (
                self.resources_selection.karma_converted
                if self.resources_selection is not None
                else 0
            )
        )

    @property
    def karma_remaining(self) -> int:
        """`STARTING_KARMA - karma_spent` -- Phase O's unified "Karma remaining" ledger. Can exceed
        `STARTING_KARMA` when net Negative-Quality Karma outweighs net Positive-Quality Karma spent
        (the rulebook's own James/Kyra worked examples both do -- see class docstring's WP51
        paragraph), and can go negative for an over-budget selection built without going through
        this property's own validation (nothing here rejects negative Karma; each `create_*`
        function still validates its own spend against a caller-supplied budget derived from this
        property, the same "validation lives in the create_* function, not the aggregate" split
        every other selection already has).
        """
        return STARTING_KARMA - self.karma_spent

    @property
    def nuyen_spent(self) -> int:
        """WP99: Σ every committed spender of Step Six's one shared nuyen pool -- gear, the primary
        Lifestyle, cyberware, bioware, foci, and vehicles/drones -- `karma_spent`'s nuyen
        counterpart. Until this, the only way to that total was to thread each of the six costs
        through a context builder's argument list (`chummer5.web.shell.chargen_context` does, six
        times over); this is the one place that sums them. The pool's *size* is not here, because it
        depends on the Resources priority letter, which lives on the web session, not on
        `Character` -- see `chummer5.engine.resources.available_nuyen`.

        `resources_selection.nuyen_spent` is gear only (WP9's meaning, unchanged); the Karma-to-
        Nuyen conversion it also records tops the pool up rather than spending from it.
        """
        return (
            (self.resources_selection.nuyen_spent if self.resources_selection is not None else 0)
            + (self.lifestyle_selection.total_cost if self.lifestyle_selection is not None else 0)
            + (self.cyberware_selection.nuyen_spent if self.cyberware_selection is not None else 0)
            + (self.bioware_selection.nuyen_spent if self.bioware_selection is not None else 0)
            + (self.foci_selection.nuyen_cost if self.foci_selection is not None else 0)
            + (self.vehicle_selection.nuyen_spent if self.vehicle_selection is not None else 0)
        )

    def attribute_range(self, code: str) -> AttributeRange:
        return self.metatype.attributes[code]

    def natural_attribute_value(self, code: str) -> int:
        """WP81: `metatype minimum + points spent + Karma points`, capped at the metatype
        (**natural**) maximum -- the rating the character actually *bought*, with no Improvement
        contribution at all. `attribute_value` is the augmented total that everything else reads;
        see that method's own docstring for the split and where each side belongs.

        Three callers want this one specifically, and each is a rules citation rather than a
        preference:
        - `create_karma_attribute_points`'s "only one Mental or Physical attribute may sit at its
          natural maximum" rule (p. 99/100 -- the word "natural" is the rulebook's own).
        - `chummer5.engine.resources`'s free contact points (`CHA x 3`) and
          `chummer5.engine.knowledge`'s free Knowledge points (`(INT + LOG) x 2`). Core rulebook
          p. 95: "Attributes boosted by cyberware or bioware do not affect the calculation for
          things such as points for Knowledge skills or Contacts. However, other in-game mechanics
          such as Initiative and Inherent Limits are modified by these augmentations" -- which is
          also why `chummer5.engine.derived` deliberately keeps reading `attribute_value`. Legacy
          agrees from the other direction: `CharacterSettings.ContactPointsExpression` /
          `KnowledgeSkillPointsExpression` default to `{CHAUnaug} * 3` /
          `({INTUnaug} + {LOGUnaug}) * 2`.

        **`"MAG"` returns `attribute_value("MAG")` unchanged**, i.e. Magic has no natural/augmented
        split in this engine -- and cannot have a meaningful one, because every SR5-core metatype's
        `magaug` equals its `magmax` (6 = 6, checked for all of Human/Elf/Dwarf/Ork/Troll), so no
        Improvement can push MAG past its natural maximum in the first place. The one rule that
        actually asks the question, p. 99's "only one at its natural maximum," explicitly excludes
        Magic/Edge/Resonance from itself anyway.
        """
        if code == "MAG":
            return self.attribute_value("MAG")
        attribute_range = self.attribute_range(code)
        points = self.attribute_points.get(code, 0)
        karma_points = (
            self.karma_attribute_selection.points.get(code, 0)
            if self.karma_attribute_selection is not None
            else 0
        )
        return min(attribute_range.minimum + points + karma_points, self.attribute_maximum(code))

    def attribute_maximum(self, code: str) -> int:
        """WP112: the attribute's **natural** maximum -- the metatype's, plus Σ `ATTRIBUTE_MAXIMUM`
        (Exceptional Attribute, Lucky: "+1 to [its] maximum", p. 72/75). Every rule that asks "is
        this attribute at its maximum" reads this, not `attribute_range(code).maximum`."""
        return self.attribute_range(code).maximum + self.improvements.resolve(
            ImprovementType.ATTRIBUTE_MAXIMUM, code
        )

    def attribute_maximum_bonuses(self) -> dict[str, int]:
        """WP112: every nonzero `ATTRIBUTE_MAXIMUM` raise, by attribute -- what `create_character`
        needs to re-validate an attribute spend against the raised maximums."""
        bonuses = {
            code: self.improvements.resolve(ImprovementType.ATTRIBUTE_MAXIMUM, code)
            for code in (*self.metatype.attributes, "MAG")
        }
        return {code: bonus for code, bonus in bonuses.items() if bonus}

    def attribute_augmented_maximum(self, code: str) -> int:
        """WP81: the highest this attribute may reach once Improvements are counted --
        `AttributeRange.augmented`, i.e. `metatypes.xml`'s own `<bodaug>`/`<agiaug>`/... field,
        loaded by `chummer5.data.metatypes` since WP2 and (until WP81) read nowhere.

        For every SR5-core metatype this is exactly `attribute_range(code).maximum + 4` on the 8
        primary attributes and exactly `maximum` on EDG/MAG/RES -- which is the rulebook's own rule
        without needing a hardcoded `+ 4` here: core rulebook p. 94, "each attribute rating (Mental
        and Physical) can only receive an augmentation bonus of up to +4. If the attribute being
        raised has not reached its natural maximum limit, the attribute can be raised naturally
        with Karma; but at no point can augmentations exceed the +4 bonus cap." Edge is not a
        Mental or Physical attribute and its data carries no headroom, so an EDG Improvement is
        clamped to zero by construction rather than by a special case.

        **WP112**: raised by Σ `ATTRIBUTE_MAXIMUM` too -- Exceptional Attribute and Lucky raise the
        natural *and* augmented maximum, keeping the `+4` headroom between them.
        """
        return self.attribute_range(code).augmented + self.improvements.resolve(
            ImprovementType.ATTRIBUTE_MAXIMUM, code
        )

    def attribute_value(self, code: str) -> int:
        """The **augmented** attribute total: `natural_attribute_value` plus Σ `ATTRIBUTE`
        improvements, with both halves of SR5's augmented cap applied (WP81).

        The two clamps, mirroring legacy `CharacterAttrib` exactly (`AttributeModifiers` then
        `CalculatedTotalValue`, read directly):
        1. Σ improvements is clamped to `attribute_augmented_maximum(code) - attribute_range(code)
           .maximum` -- the per-attribute augmentation headroom, `+4` on every Mental/Physical
           attribute and `0` on EDG/MAG/RES (see `attribute_augmented_maximum`'s citation). Legacy
           comments this line "The most that any attribute can be increased by is 4."
        2. The result is clamped to `attribute_augmented_maximum(code)` itself.
        Before WP81 there was only one clamp, at the *natural* maximum, which silently swallowed
        any augmentation bought for an attribute already at its metatype maximum -- see
        `spec/decisions-log.md`, 2026-07-31 (WP78's "Gap 1"), for the finding this closes.

        This is the value **everything except the three callers named in
        `natural_attribute_value`** wants: dice pools, Initiative, the three Limits, both condition
        monitors. Core rulebook p. 95 is explicit that Initiative and the Inherent Limits *are*
        modified by augmentations while Knowledge/Contact points are not.

        **WP25/post-WP29**: `"MAG"` is a special case, not this formula -- see the class docstring's
        Phase I paragraph and its post-WP29 correction. Dispatching here (rather than teaching every
        caller about MAG) matters because `chummer5.engine.skills.dice_pool` calls this for *every*
        skill's linked attribute, including Magical Active ones (Spellcasting, Counterspelling,
        ...), for any character -- without this branch, a Mundane character's `attribute_range
        ("MAG")` would silently resolve to the metatype's raw eligibility range (minimum 1 for every
        MVP metatype) instead of the correct "no Magic at all" 0, since metatype data alone doesn't
        encode "Talent forced to E". For a magically active character, MAG's own maximum is still
        the metatype's raw `attribute_range("MAG").maximum` (6 for every SR5-core metatype) -- only
        the *minimum* is Talent-sourced (`magic_rating`) rather than metatype-sourced.
        """
        if code == "MAG":
            if self.magic_type is None:
                return 0
            # WP35: Essence loss reduces both the current and maximum Magic rating by the same
            # amount (core rulebook p.278 -- see magic_essence_loss's own docstring for the exact
            # citation). Since magic_rating_before_essence_loss is already capped at the metatype's
            # raw MAG maximum, subtracting the same loss from both the current value and that
            # maximum can never make the (already-capped) current value exceed the reduced maximum
            # -- so no separate "reduced maximum" cap is needed here, only the floor at 0.
            return max(self.magic_rating_before_essence_loss - self.magic_essence_loss, 0)
        attribute_range = self.attribute_range(code)
        natural = self.natural_attribute_value(code)
        bonus = self.improvements.resolve(ImprovementType.ATTRIBUTE, code)
        headroom = max(attribute_range.augmented - attribute_range.maximum, 0)
        return min(natural + min(bonus, headroom), self.attribute_augmented_maximum(code))

    @property
    def power_points(self) -> int:
        """Adept Power Points: the character's *current* Magic attribute, 1:1, granted free at
        chargen -- no separate budget to derive (SR5 core rulebook p.278-279, "POWER POINTS": "At
        character creation, adepts receive Power Points equal to their Magic attribute, while
        mystic adepts have to buy Power Points with Karma" -- Mystic Adept's split doesn't apply
        here, since it's out of scope entirely, see Project Overview's 2026-07-19 magic-scoping
        entry). Reads `attribute_value("MAG")`, not the raw `magic_rating` field directly -- the
        rulebook's "their Magic attribute" means the finished rating, which post-WP29 can exceed
        `magic_rating` if Special Attribute Points were spent raising it further (see this class's
        own docstring correction). Computed, not stored -- there is nothing here `magic_type`/
        `attribute_value("MAG")` don't already determine, so a separate field would just be
        redundant, staleness-prone state (the same reasoning `BASE_ESSENCE`'s docstring and WP23's
        "don't persist `metatype_qualities`" decision already used elsewhere).
        """
        return self.attribute_value("MAG") if self.magic_type == "Adept" else 0

    @property
    def magic_rating_before_essence_loss(self) -> int:
        """The Magic rating `attribute_value("MAG")` computed through WP29, before WP35's
        Essence-driven reduction: Talent-granted `magic_rating` + `magic_attribute_points` + Σ
        `ATTRIBUTE` improvements, capped at the metatype's raw MAG maximum. Exposed only for the
        character sheet's "reduced from N by Essence loss" display (`chummer5.web.app
        ._character_sheet_context`) -- `attribute_value("MAG")` itself, and everything that reads
        it (dice pools, `power_points`), must see the real, Essence-reduced value, not this one.
        `0` for Mundane, mirroring `attribute_value`'s own early return.
        """
        if self.magic_type is None:
            return 0
        return min(
            self._magic_points_total() + self.karma_magic_points, self.attribute_maximum("MAG")
        )

    def _magic_points_total(self) -> int:
        """Talent rating + Special Attribute Points + Σ `ATTRIBUTE` improvements on MAG, uncapped
        and without Karma (WP123)."""
        bonus = self.improvements.resolve(ImprovementType.ATTRIBUTE, "MAG")
        return self.magic_rating + self.magic_attribute_points + bonus

    @property
    def karma_magic_points(self) -> int:
        """WP123: Magic raised with Step Seven Karma (`karma_attribute_selection`'s "MAG")."""
        selection = self.karma_attribute_selection
        return selection.points.get("MAG", 0) if selection is not None else 0

    def magic_before_karma(self) -> int:
        """WP123: the current Magic rating with no Karma spent on it -- Essence loss included, the
        rating a Karma raise starts from."""
        if self.magic_type is None:
            return 0
        capped = min(self._magic_points_total(), self.attribute_maximum("MAG"))
        return max(capped - self.magic_essence_loss, 0)

    @property
    def magic_essence_loss(self) -> int:
        """SR5 core rulebook p.278 (extracted ahead of this WP during WP25's own research --
        see `spec/rulebooks/learnings.md`'s WP25 entry): "Anything that reduces your Essence also
        reduces your Magic rating. For every point (or fraction thereof) of Essence lost, both
        your current Magic Attribute and your maximum Magic Rating are reduced by one."

        `math.ceil` of the total Essence lost -- `resolve_essence()` sums each `ESSENCE`
        improvement's `essence_value` directly (each already a *negative* delta off the metatype's
        Essence maximum, per `chummer5.engine.derived.essence`'s own `BASE_ESSENCE + Σ`
        formula), so the lost amount is that sum's negation, not a subtraction from
        `attribute_range("ESS").maximum` (there is nothing to subtract *from* here -- the maximum
        itself never changes, only how much has been lost off it). `0` for every character with no
        `ESSENCE` improvement -- every character before Phase J's cyberware catalog existed, and
        every Mundane character regardless of how much cyberware they bought (Mundane never reads
        this at all -- see `attribute_value`'s own `magic_type is None` early return).

        Deliberately not distinguished from a "maximum rating has burned out to 0" case: this
        project doesn't model Karma-based post-chargen advancement (career mode is out of scope),
        so the rulebook's separate "current 0 is recoverable, maximum 0 is permanent burnout"
        distinction has no observable effect here -- both a reduced-to-0 current rating and a
        reduced-to-0 maximum look identical (Magic rating 0) in a chargen-only engine.
        """
        essence_lost = -self.improvements.resolve_essence(_ESSENCE_TARGET)
        return math.ceil(essence_lost)


def create_character(
    metatype_choice: MetatypeChoice,
    heritage_letter: str,
    attributes_letter: str,
    priorities: PriorityTable,
    attribute_points: Mapping[str, int],
    *,
    maximum_bonus: Mapping[str, int] | None = None,
    previous_attribute_points: Mapping[str, int] | None = None,
    karma_points: Mapping[str, int] | None = None,
) -> Character:
    """Build a `Character`, validating the attribute-point spend against both budgets.

    Validates: every key in `attribute_points` is one of `ALLOCATABLE_ATTRIBUTES`; no negative
    spend; primary-attribute spend doesn't exceed the Attributes-priority-letter budget;
    special-attribute (EDG) spend doesn't exceed `metatype_choice`'s own special-attribute-points
    budget; and every resulting value stays within the metatype's min/max range. Does not require
    the full budget to be spent — SR5 doesn't mandate that, and this project treats "must spend
    everything" as a UI nudge, not an engine invariant.

    **WP112**: `maximum_bonus` is `{code: raise}` from Exceptional Attribute / Lucky (see
    `Character.attribute_maximum`), and the range check reads the raised maximum. The **one at
    natural maximum** rule (Step Two: "only one Physical or Mental attribute may be at its natural
    maximum") is checked here too, but only against a submission that *itself* puts a second
    attribute there: it needs `previous_attribute_points` (the committed spend before this edit),
    and runs only when a Mental/Physical attribute that was below its maximum before ends at it.
    That is WP52's scoping, for WP52's reason -- a character already in breach (a legacy import, a
    pre-WP112 save) must still be editable elsewhere; WP135 reports it instead. `karma_points`
    (Step Seven's committed spend) counts towards the natural rating, since the rule is about the
    finished number.
    """
    unknown = set(attribute_points) - set(ALLOCATABLE_ATTRIBUTES)
    if unknown:
        raise ValueError(f"not allocatable in MVP scope: {sorted(unknown)}")

    primary_budget = priorities.attributes[attributes_letter].points
    primary_spent = sum(attribute_points.get(code, 0) for code in PRIMARY_ATTRIBUTES)
    if primary_spent > primary_budget:
        raise ValueError(
            f"primary attribute spend {primary_spent} exceeds "
            f"Attributes priority {attributes_letter}'s budget of {primary_budget}"
        )

    special_budget = metatype_choice.special_attribute_points
    special_spent = sum(attribute_points.get(code, 0) for code in SPECIAL_ATTRIBUTES)
    if special_spent > special_budget:
        raise ValueError(
            f"special attribute spend {special_spent} exceeds "
            f"{metatype_choice.metatype.name}'s special-attribute-points budget of {special_budget}"
        )

    bonus = maximum_bonus or {}
    for code in ALLOCATABLE_ATTRIBUTES:
        points = attribute_points.get(code, 0)
        if points < 0:
            raise ValueError(f"{code}: points spent must not be negative, got {points}")
        attribute_range = metatype_choice.metatype.attributes[code]
        value = attribute_range.minimum + points
        maximum = attribute_range.maximum + bonus.get(code, 0)
        if value > maximum:
            raise ValueError(
                f"{code}: {value} exceeds {metatype_choice.metatype.name}'s maximum of {maximum}"
            )

    if previous_attribute_points is not None:
        _check_one_at_natural_maximum(
            metatype_choice.metatype,
            attribute_points,
            previous_attribute_points,
            karma_points or {},
            bonus,
        )

    return Character(
        metatype=metatype_choice.metatype,
        heritage_letter=heritage_letter,
        attributes_letter=attributes_letter,
        special_attribute_points=special_budget,
        attribute_points=MappingProxyType(dict(attribute_points)),
        improvements=ImprovementIndex(),
    )


def _check_one_at_natural_maximum(
    metatype: Metatype,
    attribute_points: Mapping[str, int],
    previous_attribute_points: Mapping[str, int],
    karma_points: Mapping[str, int],
    maximum_bonus: Mapping[str, int],
) -> None:
    """WP112: reject a priority spend that itself puts a second Mental/Physical attribute at its
    natural maximum. See `create_character`'s docstring for the scoping."""

    def at_maximum(points: Mapping[str, int], code: str) -> bool:
        attribute_range = metatype.attributes[code]
        natural = attribute_range.minimum + points.get(code, 0) + karma_points.get(code, 0)
        return natural >= attribute_range.maximum + maximum_bonus.get(code, 0)

    raised = [
        code
        for code in PRIMARY_ATTRIBUTES
        if at_maximum(attribute_points, code) and not at_maximum(previous_attribute_points, code)
    ]
    at_max_count = sum(1 for code in PRIMARY_ATTRIBUTES if at_maximum(attribute_points, code))
    if raised and at_max_count > 1:
        raise ValueError(
            "only one Mental or Physical attribute may sit at its natural maximum at character "
            f"creation -- raising {', '.join(raised)} would put {at_max_count} there"
        )


@dataclass(frozen=True)
class KarmaAttributeSelection:
    """Leftover-Karma-funded attribute increases beyond the priority-derived `attribute_points`/
    `special_attribute_points` budgets (Step Seven, WP52; see the Implementation Plan's Phase O
    intro and `create_karma_attribute_points`'s own docstring).

    `points` mirrors `attribute_points`'s own shape and meaning -- however many *additional*
    points, per `ALLOCATABLE_ATTRIBUTES` code, were bought with Karma on top of whatever
    priority-budget points that attribute already has. Always the *full* resulting map, not an
    incremental delta on top of a prior `KarmaAttributeSelection` -- the same "recompute wholesale,
    not incrementally" shape every other selection in this engine uses (`create_quality_selection`,
    `create_bound_spirit_selection`, ...): a resubmission is a complete re-declaration of every
    Karma-funded attribute point, not a diff against what was there before.

    **MAG since WP123** (RES stays out of scope). MAG also has its Karma-free Special Attribute
    Point mechanism (`create_magic_attribute_points`); on top of that, the Karma Advancement
    Table (p. 106) prices Magic like any attribute, `new Rating x 5`. A Karma raise starts from the
    *current* rating, after WP35's Essence loss, and stops at the reduced maximum (p. 278) -- see
    `_karma_magic_cost`.
    """

    points: MappingProxyType[str, int]
    karma_cost: int


def _karma_magic_cost(character: Character, points: int) -> int:
    """WP123: Karma for raising Magic by `points`. p. 278: Essence loss lowers "both your current
    Magic Attribute and your maximum Magic Rating [...] (but you can still raise the attribute with
    Karma [...])" -- so the raise starts from the *reduced* current rating, at new rating x 5, and
    stops at the reduced maximum. A reduced maximum of 0 is burnout ("You are mundane forever")."""
    maximum = character.attribute_maximum("MAG")
    reduced_maximum = maximum - character.magic_essence_loss
    if reduced_maximum <= 0:
        raise ValueError("MAG: Essence loss has burned out the character's Magic")
    start = character.magic_before_karma()
    if start + points > reduced_maximum:
        raise ValueError(
            f"MAG: {start + points} (current + Karma) exceeds the maximum of {reduced_maximum}"
            + (" after Essence loss" if character.magic_essence_loss else "")
        )
    return karma_advancement_cost(start, points, ATTRIBUTE_KARMA_PER_RATING)


def create_karma_attribute_points(
    character: Character, karma_points: Mapping[str, int], karma_budget: int
) -> KarmaAttributeSelection:
    """Validate and build a `KarmaAttributeSelection`.

    `karma_points` raises an `ALLOCATABLE_ATTRIBUTES` attribute beyond its priority-derived budget
    at `new Rating x 5` Karma per rating step, cumulative (core rulebook p.106-107, "KARMA
    ADVANCEMENT TABLE FOR ATTRIBUTES" -- see `karma_advancement_cost`/`ATTRIBUTE_KARMA_PER_RATING`
    and `spec/rulebooks/learnings.md`'s WP51 entry for the confirming research pass).

    Validates: every key is one of `ALLOCATABLE_ATTRIBUTES` (MAG/RES are never allocatable here --
    see `KarmaAttributeSelection`'s own docstring); no negative spend; the resulting value
    (metatype minimum + priority points + Karma points) does not exceed the metatype's maximum for
    that attribute; **at most one of `PRIMARY_ATTRIBUTES` may sit at its own natural maximum**
    after this spend (core rulebook p.100, Step Seven: "Only one attribute can be at the natural
    attribute limit... These rules still apply to when you are spending Karma" -- restating Step
    Two's own restriction, p.99, which explicitly excludes Magic/Edge/Resonance from this
    limitation, so `SPECIAL_ATTRIBUTES`/EDG is not checked against it here); and the total Karma
    cost does not exceed `karma_budget` (the caller's responsibility to derive -- typically
    `character.karma_remaining + <this selection's own currently-committed karma_cost>`, mirroring
    every other Karma-spending `create_*` function's `karma_budget` parameter; see WP51's worklog
    for this "add back this section's own current commitment" idiom).

    **Scope note**: the "only one at natural maximum" check only fires when `karma_points` actually
    raises a `PRIMARY_ATTRIBUTES` code -- an empty or EDG-only `karma_points` skips it entirely,
    *even if* `character` already has two-plus Mental/Physical attributes at their natural maximum
    from priority-point spend alone. This matters in practice, not just hypothetically: the web
    layer (`chummer5.web.app.submit_attributes`) calls this function on *every* attribute-form
    submission, including ones that spend no Karma at all, purely to re-validate whatever Karma
    spend is already committed -- if the check ran unconditionally, a perfectly legal pure-priority
    spend that happens to reach the metatype maximum on more than one Mental/Physical attribute
    (`create_character`, WP6, never itself validated that restriction for the pure-priority path)
    would be rejected the moment the player touched the attribute form again, with no Karma
    involved at all. Confirmed this is a real, reachable case, not just theoretical: caught by
    `tests/unit/test_web_attribute_skill_allocation.py`'s own WP19 reconfirmation test during this
    WP's own manual verification, which spends BOD/AGI/REA all up to Human's natural maximum (6) via
    priority points alone -- see this function's own tests for the synthetic regression case that
    pins this behavior down directly.
    """
    # WP123: Magic too, for a magic user (p. 106: "new Rating x 5", like every attribute).
    allowed = (
        (*ALLOCATABLE_ATTRIBUTES, "MAG")
        if character.magic_type is not None
        else (ALLOCATABLE_ATTRIBUTES)
    )
    unknown = set(karma_points) - set(allowed)
    if unknown:
        raise ValueError(f"not allocatable in MVP scope: {sorted(unknown)}")

    nonzero_points = MappingProxyType({code: pts for code, pts in karma_points.items() if pts})
    cost = 0
    for code, points in nonzero_points.items():
        if points < 0:
            raise ValueError(f"{code}: Karma-funded points must not be negative, got {points}")
        if code == "MAG":
            cost += _karma_magic_cost(character, points)
            continue
        attribute_range = character.attribute_range(code)
        start_rating = attribute_range.minimum + character.attribute_points.get(code, 0)
        total = start_rating + points
        maximum = character.attribute_maximum(code)  # WP112: raised by Exceptional Attribute
        if total > maximum:
            raise ValueError(
                f"{code}: {total} (priority + Karma) exceeds {character.metatype.name}'s "
                f"maximum of {maximum}"
            )
        cost += karma_advancement_cost(start_rating, points, ATTRIBUTE_KARMA_PER_RATING)

    if cost > karma_budget:
        raise ValueError(
            f"Karma-funded attribute spend {cost} exceeds the Karma budget of {karma_budget}"
        )

    selection = KarmaAttributeSelection(points=nonzero_points, karma_cost=cost)

    # The "only one at natural maximum" check only fires when *this* Karma spend actually raises a
    # PRIMARY_ATTRIBUTES code -- an empty `karma_points` (the common case: every ordinary attribute
    # -point submission on the web layer calls this function too, to keep any already-committed
    # Karma spend re-validated) or one that only touches EDG must never trip it, since neither
    # changes whether any Mental/Physical attribute sits at its maximum. This also means a character
    # that already has two-plus Mental/Physical attributes at maximum from priority-point spend
    # alone (a state `create_character` has never itself rejected -- see this function's own
    # docstring "Scope note") is left alone by a `karma_points={}` or EDG-only call; only a spend
    # that would touch a Mental/Physical rating is actually checked against the rule.
    if any(code in PRIMARY_ATTRIBUTES for code in nonzero_points):
        candidate = replace(character, karma_attribute_selection=selection)
        # WP81: `natural_attribute_value`, not `attribute_value`. The rulebook's word is "natural"
        # and this engine can now tell the two apart -- an augmented REA of 7 on a natural 5 must
        # not count against this rule, and before WP81 it silently would have (the augmented value
        # was clamped at the natural maximum, so `>= maximum` was true for both cases).
        at_natural_maximum = sum(
            1
            for code in PRIMARY_ATTRIBUTES
            if candidate.natural_attribute_value(code) >= candidate.attribute_maximum(code)
        )
        if at_natural_maximum > 1:
            raise ValueError(
                "only one Mental or Physical attribute may sit at its natural maximum at "
                f"character creation -- this Karma spend would put {at_natural_maximum} there"
            )

    return selection
