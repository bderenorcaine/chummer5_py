"""Contacts & starting resources.

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
`spec/worklogs/WP4.md`). `STARTER_GEAR_CATALOG` is a deliberately small, hand-curated list of
flat-cost (non-`Rating`-scaled) SR5-sourced items cross-checked directly against
`legacy/Chummer/data/{gear,armor,weapons}.xml` — not a general gear-catalog loader, which the
Implementation Plan explicitly scopes out of MVP ("a deliberately minimal starter-gear purchase
... explicitly not the full gear catalog"). `create_resources_selection` only validates that every
selected item is in that small catalog and that the total cost doesn't exceed the Resources-letter
nuyen budget — there's no equivalent "real characters exceed this" escape hatch here, since nuyen
(unlike contact points) has no legacy provision for going over budget by paying with something
else at chargen.

**Lifestyle (WP20).** `chummer5.engine.lifestyle.LifestyleSelection` (the mandatory primary-
Lifestyle purchase, core rulebook p. 369) draws from this same nuyen budget rather than a separate
one — `create_resources_selection`'s `lifestyle_cost` parameter folds its already-computed total
cost into the one joint over-budget check, instead of `chummer5.engine.lifestyle` duplicating a
second budget validator of its own. See that module's docstring for why lifestyle cost validation
lives here and not there.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from chummer5.data.priorities import PriorityTable
from chummer5.engine.character import Character

# CharacterSettings.ContactPointsExpression (legacy default: `"{CHAUnaug} * 3"`) -- confirmed
# against the core rulebook ("Making Connections", p. 98: "This Karma is equal to a Character's
# Charisma rating x 3") and against every mundane fixture's <contactpoints> tag (see module
# docstring). MVP has no cyberware/gear that could make augmented CHA differ from unaugmented, so
# `Character.attribute_value("CHA")` is used directly rather than needing a separate "unaugmented"
# read.
FREE_CONTACT_POINTS_PER_CHARISMA = 3

# CharacterSettings.KarmaContact (legacy default: `_intKarmaContact = 1`) -- Karma cost per point of
# Connection/Loyalty spent beyond the free budget above.
KARMA_PER_EXCESS_CONTACT_POINT = 1

# Core rulebook, "Making Connections": "Any Contacts a player buys must have a minimum rating of 1
# in Connection and a minimum rating of 1 in Loyalty."
MIN_CONTACT_RATING = 1


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

    free_points = character.attribute_value("CHA") * FREE_CONTACT_POINTS_PER_CHARISMA
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
    name: str
    cost: int


# A small, deliberately minimal, hand-curated starter-gear list -- flat-cost SR5-sourced items
# cross-checked directly against legacy/Chummer/data/{gear,armor,weapons}.xml (none use a
# Rating-scaled cost formula), not a general gear-catalog loader. See module docstring.
STARTER_GEAR_CATALOG: tuple[StarterGearItem, ...] = (
    StarterGearItem("Meta Link", 100),
    StarterGearItem("Certified Credstick, Standard", 5),
    StarterGearItem("Armor Jacket", 1000),
    StarterGearItem("Ares Predator V", 725),
    StarterGearItem("Combat Knife", 300),
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
    """

    resources_letter: str
    nuyen_budget: int
    gear: tuple[StarterGearItem, ...]
    nuyen_spent: int
    nuyen_remaining: int
    lifestyle_cost: int = 0


def starting_nuyen(letter: str, priorities: PriorityTable) -> int:
    return priorities.resources[letter].nuyen


def create_resources_selection(
    letter: str,
    priorities: PriorityTable,
    gear_names: Iterable[str],
    catalog: Iterable[StarterGearItem] = STARTER_GEAR_CATALOG,
    *,
    lifestyle_cost: int = 0,
) -> ResourcesSelection:
    """Build a `ResourcesSelection`, validating the combined gear + lifestyle spend against the
    nuyen budget.

    Validates: every name in `gear_names` is a `catalog` item's name (repeats allowed -- buying two
    Certified Credsticks is a normal purchase, unlike a quality or skill that can't be picked
    twice); `gear` cost plus `lifestyle_cost` together don't exceed `letter`'s nuyen budget (WP20:
    a character's primary Lifestyle draws from this same pool, confirmed against every one of the
    11 curated mundane fixtures -- see `spec/rulebooks/learnings.md`'s WP20 entry). Does not
    require the full budget to be spent, mirroring WP6/WP7/WP8's identical choice. `lifestyle_cost`
    defaults to 0 so every pre-WP20 call site (gear-only, no lifestyle yet selected) is unaffected.
    """
    by_name = {item.name: item for item in catalog}
    names = list(gear_names)

    unknown = sorted({name for name in names if name not in by_name})
    if unknown:
        raise ValueError(f"not a starter-gear catalog item: {unknown}")

    selected = tuple(by_name[name] for name in names)
    budget = starting_nuyen(letter, priorities)
    spent = sum(item.cost for item in selected)
    total_spent = spent + lifestyle_cost
    if total_spent > budget:
        if lifestyle_cost:
            raise ValueError(
                f"gear ({spent}) + lifestyle ({lifestyle_cost}) spend {total_spent} exceeds "
                f"Resources priority {letter}'s nuyen budget of {budget}"
            )
        raise ValueError(
            f"gear spend {spent} exceeds Resources priority {letter}'s nuyen budget of {budget}"
        )

    return ResourcesSelection(
        resources_letter=letter,
        nuyen_budget=budget,
        gear=selected,
        nuyen_spent=spent,
        nuyen_remaining=budget - total_spent,
        lifestyle_cost=lifestyle_cost,
    )
