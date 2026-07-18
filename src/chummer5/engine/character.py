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
from chummer5.engine.improvements import ImprovementIndex, ImprovementType

if TYPE_CHECKING:
    # Deferred to type-checking only: `chummer5.engine.{qualities,resources,skills}` each import
    # `Character` from this module, so importing them back here at runtime would be circular. Safe
    # under `from __future__ import annotations` (PEP 563) -- every annotation in this module,
    # including dataclass field types, is a lazily-evaluated string, so `dataclasses.dataclass`
    # never needs these names to actually resolve at import time.
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

    def attribute_range(self, code: str) -> AttributeRange:
        return self.metatype.attributes[code]

    def attribute_value(self, code: str) -> int:
        """`metatype minimum + points spent + Σ improvements`, capped at the metatype maximum."""
        attribute_range = self.attribute_range(code)
        points = self.attribute_points.get(code, 0)
        bonus = self.improvements.resolve(ImprovementType.ATTRIBUTE, code)
        return min(attribute_range.minimum + points + bonus, attribute_range.maximum)


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
