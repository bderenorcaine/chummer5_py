"""Lifestyle selection (WP20): SR5's mandatory "Step Six" primary-Lifestyle purchase (core
rulebook, p. 369: "A character must select one of the lifestyles below to be their primary
Lifestyle"), paid from the same Resources-priority nuyen budget `chummer5.engine.resources`
already draws from for starter gear -- see that module's `create_resources_selection` for the
joint-budget check this selection feeds into, and `spec/rulebooks/learnings.md`'s WP20 entry for
the rulebook/legacy-code research behind the numbers below.

**Deliberately not modeled here (out of MVP scope, per the Implementation Plan's WP20 entry):**
the 9-entry SR5 lifestyle-qualities catalog (extra comforts/security modifiers), roommate cost
splitting, and the "buy a lifestyle permanently" mechanic (100 months' upkeep) -- this selection is
exactly `tier.monthly_cost * months`, nothing more.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from chummer5.data.lifestyle import LifestyleTier

# Core rulebook, "Paying the Bills" (p. 370): "Prepayments can be made for any number of months."
# The legacy C#'s character-creation screen (`CharacterCreate.Designer.cs`'s `nudLifestyleMonths`)
# is the one place this project found an actual numeric floor/ceiling: Minimum = 1, Maximum = 100.
# The 100-month ceiling isn't arbitrary either -- it's the exact threshold "Buying a Lifestyle"
# (p. 370) uses to make a Lifestyle permanent ("a payment equal to 100 months' upkeep"), so the UI
# simply caps prepayment at that boundary rather than letting it run past a rule the rulebook
# itself treats as a distinct mechanic. See spec/rulebooks/learnings.md's WP20 entry.
MIN_LIFESTYLE_MONTHS = 1
MAX_LIFESTYLE_MONTHS = 100


@dataclass(frozen=True)
class LifestyleSelection:
    """A validated primary-Lifestyle choice: which tier, for how many months, and the resulting
    total nuyen cost (`tier.monthly_cost * months` -- confirmed directly against `Lifestyle.
    TotalCost` in the legacy C#, see module docstring)."""

    tier: LifestyleTier
    months: int
    total_cost: int


def create_lifestyle_selection(
    tier_name: str, months: int, catalog: Iterable[LifestyleTier]
) -> LifestyleSelection:
    """Build a `LifestyleSelection`, validating the tier is a known catalog entry and `months` is
    within the legacy UI's own 1-100 range (see `MIN_LIFESTYLE_MONTHS`/`MAX_LIFESTYLE_MONTHS`).

    Does not check the result against a nuyen budget -- that's a joint constraint shared with
    starter-gear spend, checked in one place by `chummer5.engine.resources
    .create_resources_selection`'s own `lifestyle_cost` parameter, not duplicated here.
    """
    by_name = {tier.name: tier for tier in catalog}
    tier = by_name.get(tier_name)
    if tier is None:
        raise ValueError(f"not a lifestyle-catalog tier: {tier_name!r}")
    if not (MIN_LIFESTYLE_MONTHS <= months <= MAX_LIFESTYLE_MONTHS):
        raise ValueError(
            f"months must be between {MIN_LIFESTYLE_MONTHS} and {MAX_LIFESTYLE_MONTHS}, "
            f"got {months}"
        )
    return LifestyleSelection(tier=tier, months=months, total_cost=tier.monthly_cost * months)
