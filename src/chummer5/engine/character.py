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

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import TYPE_CHECKING

from chummer5.data.metatypes import AttributeRange, Metatype
from chummer5.data.priorities import HeritagePriority, PriorityTable
from chummer5.data.qualities import Quality
from chummer5.engine.improvements import ImprovementIndex, ImprovementType

if TYPE_CHECKING:
    # Deferred to type-checking only: `chummer5.engine.{qualities,resources,skills,magic}` each
    # import `Character` from this module, so importing them back here at runtime would be
    # circular. Safe under `from __future__ import annotations` (PEP 563) -- every annotation in
    # this module, including dataclass field types, is a lazily-evaluated string, so
    # `dataclasses.dataclass` never needs these names to actually resolve at import time.
    from chummer5.data.traditions import Tradition
    from chummer5.engine.lifestyle import LifestyleSelection
    from chummer5.engine.qualities import QualitySelection
    from chummer5.engine.resources import ContactSelection, ResourcesSelection
    from chummer5.engine.skills import SkillAllocation

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
    Per the Implementation Plan's Phase I intro finding, **MAG is deliberately not added to
    `SPECIAL_ATTRIBUTES`/`ALLOCATABLE_ATTRIBUTES`** -- it isn't point-bought the way EDG is; the
    chosen Talent option's `magic` field *is* the finished rating outright. `attribute_value` below
    special-cases `"MAG"` instead (documented decision, not a default): every other attribute is a
    formula over `attribute_points`/`improvements`, but nothing about MAG's *value* varies per
    character beyond `magic_rating` itself (WP35, later, changes this to also account for
    Essence-driven Magic loss -- see that WP's own scope). Power Points, which Phase I's Adept
    archetype needs, aren't a stored field at all -- see `power_points` below.
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
    magic_rating: int = 0  # the finished MAG rating; 0 for Mundane (WP25)
    tradition: Tradition | None = None  # Magician only (WP25)
    magic_granted_skill_ids: tuple[str, ...] = ()  # the Talent free-skill grant's picks (WP25)

    def attribute_range(self, code: str) -> AttributeRange:
        return self.metatype.attributes[code]

    def attribute_value(self, code: str) -> int:
        """`metatype minimum + points spent + Σ improvements`, capped at the metatype maximum.

        **WP25**: `"MAG"` is a special case, not this formula -- see the class docstring's Phase I
        paragraph. Dispatching here (rather than teaching every caller about MAG) matters because
        `chummer5.engine.skills.dice_pool` calls this for *every* skill's linked attribute,
        including Magical Active ones (Spellcasting, Counterspelling, ...), for any character --
        without this branch, a Mundane character's `attribute_range("MAG")` would silently resolve
        to the metatype's raw eligibility range (minimum 1 for every MVP metatype) instead of the
        correct "no Magic at all" 0, since metatype data alone doesn't encode "Talent forced to E".
        """
        if code == "MAG":
            return self.magic_rating
        attribute_range = self.attribute_range(code)
        points = self.attribute_points.get(code, 0)
        bonus = self.improvements.resolve(ImprovementType.ATTRIBUTE, code)
        return min(attribute_range.minimum + points + bonus, attribute_range.maximum)

    @property
    def power_points(self) -> int:
        """Adept Power Points: the Magic rating, 1:1, granted free at chargen -- no separate budget
        to derive (SR5 core rulebook p.278-279, "POWER POINTS": "At character creation, adepts
        receive Power Points equal to their Magic attribute, while mystic adepts have to buy Power
        Points with Karma" -- Mystic Adept's split doesn't apply here, since it's out of scope
        entirely, see Project Overview's 2026-07-19 magic-scoping entry). Computed, not stored --
        there is nothing here `magic_type`/`magic_rating` don't already determine, so a separate
        field would just be redundant, staleness-prone state (the same reasoning `BASE_ESSENCE`'s
        docstring and WP23's "don't persist `metatype_qualities`" decision already used elsewhere).
        """
        return self.magic_rating if self.magic_type == "Adept" else 0


def create_character(
    metatype_choice: MetatypeChoice,
    heritage_letter: str,
    attributes_letter: str,
    priorities: PriorityTable,
    attribute_points: Mapping[str, int],
) -> Character:
    """Build a `Character`, validating the attribute-point spend against both budgets.

    Validates: every key in `attribute_points` is one of `ALLOCATABLE_ATTRIBUTES`; no negative
    spend; primary-attribute spend doesn't exceed the Attributes-priority-letter budget;
    special-attribute (EDG) spend doesn't exceed `metatype_choice`'s own special-attribute-points
    budget; and every resulting value stays within the metatype's min/max range. Does not require
    the full budget to be spent — SR5 doesn't mandate that, and this project treats "must spend
    everything" as a UI nudge, not an engine invariant.
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

    for code in ALLOCATABLE_ATTRIBUTES:
        points = attribute_points.get(code, 0)
        if points < 0:
            raise ValueError(f"{code}: points spent must not be negative, got {points}")
        attribute_range = metatype_choice.metatype.attributes[code]
        value = attribute_range.minimum + points
        if value > attribute_range.maximum:
            raise ValueError(
                f"{code}: {value} exceeds {metatype_choice.metatype.name}'s maximum of "
                f"{attribute_range.maximum}"
            )

    return Character(
        metatype=metatype_choice.metatype,
        heritage_letter=heritage_letter,
        attributes_letter=attributes_letter,
        special_attribute_points=special_budget,
        attribute_points=MappingProxyType(dict(attribute_points)),
        improvements=ImprovementIndex(),
    )
