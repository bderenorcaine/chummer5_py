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
from dataclasses import dataclass, replace

from chummer5.data.lifestyle import LifestyleOption, LifestyleTier
from chummer5.engine.character import Character
from chummer5.engine.improvements import ImprovementType

# Core rulebook, "Paying the Bills" (p. 370): "Prepayments can be made for any number of months."
# The legacy C#'s character-creation screen (`CharacterCreate.Designer.cs`'s `nudLifestyleMonths`)
# is the one place this project found an actual numeric floor/ceiling: Minimum = 1, Maximum = 100.
# The 100-month ceiling isn't arbitrary either -- it's the exact threshold "Buying a Lifestyle"
# (p. 370) uses to make a Lifestyle permanent ("a payment equal to 100 months' upkeep"), so the UI
# simply caps prepayment at that boundary rather than letting it run past a rule the rulebook
# itself treats as a distinct mechanic. See spec/rulebooks/learnings.md's WP20 entry.
MIN_LIFESTYLE_MONTHS = 1
MAX_LIFESTYLE_MONTHS = 100

# WP132, p. 370, "Buying a Lifestyle": "A character can permanently buy a given lifestyle by
# making a payment equal to 100 months' upkeep."
PERMANENT_LIFESTYLE_MONTHS = 100

# WP132, p. 370: the options "can be selected for any of the lifestyles except Streets or
# Hospitalized" (Hospitalized is never a starting tier).
NO_OPTIONS_TIER_NAMES = frozenset({"Street", "Hospitalized"})


@dataclass(frozen=True)
class LifestyleOptionPick:
    """One Lifestyle Option on the primary Lifestyle (WP132); `text` says what a repeatable one
    is ("garage", "lab")."""

    option: LifestyleOption
    text: str | None = None


@dataclass(frozen=True)
class LifestyleSelection:
    """A validated primary-Lifestyle choice: which tier, for how many months, and the resulting
    total nuyen cost (`tier.monthly_cost * months` -- confirmed directly against `Lifestyle.
    TotalCost` in the legacy C#, see module docstring).

    **WP113**: `cost_percent` is the character's Σ `LIFESTYLE_COST` surcharge (Dwarf +20%, Troll
    +100% -- "the troll tax", p. 420), and `monthly_cost` is the tier's price with it applied.
    `total_cost` is `monthly_cost * months`.
    """

    tier: LifestyleTier
    months: int
    total_cost: int
    cost_percent: int = 0
    # WP132: Lifestyle Options, and "bought permanently" (100 months' upkeep, p. 370).
    options: tuple[LifestyleOptionPick, ...] = ()
    permanent: bool = False

    @property
    def monthly_cost(self) -> int:
        return lifestyle_monthly_cost(self.tier, self.options, self.cost_percent)


def lifestyle_monthly_cost(
    tier: LifestyleTier, options: Iterable[LifestyleOptionPick], cost_percent: int = 0
) -> int:
    """A month's upkeep (WP132): the tier's price, moved by each option's percent "of the
    lifestyle" (p. 370) -- summed, each taken against the tier's price -- plus each option's flat
    monthly amount; then WP113's metatype/Dependents surcharge on the whole, as the plan rules."""
    picks = tuple(options)
    percent = sum(pick.option.cost_percent for pick in picks)
    flat = sum(pick.option.flat_cost for pick in picks)
    adjusted = -(-tier.monthly_cost * (100 + percent) // 100) + flat
    return surcharged_monthly_cost(adjusted, cost_percent)


def reprice_lifestyle(selection: LifestyleSelection, cost_percent: int) -> LifestyleSelection:
    """`selection` at a new Σ `LIFESTYLE_COST` surcharge (WP113; WP132 keeps its options)."""
    repriced = replace(selection, cost_percent=cost_percent)
    return replace(repriced, total_cost=repriced.monthly_cost * repriced.months)


def surcharged_monthly_cost(base: int, cost_percent: int) -> int:
    """WP113: a monthly price with a percent surcharge, rounded up to the nuyen. Every core tier
    and every core surcharge divide exactly (500 x 1.2 = 600), so the rounding never bites today."""
    return -(-base * (100 + cost_percent) // 100)


def lifestyle_cost_percent(character: Character) -> int:
    """The character's Σ `LIFESTYLE_COST` surcharge, in percent (WP113)."""
    return character.improvements.resolve(ImprovementType.LIFESTYLE_COST, "")


def create_lifestyle_selection(
    tier_name: str,
    months: int,
    catalog: Iterable[LifestyleTier],
    *,
    cost_percent: int = 0,
    options: Iterable[tuple[str, str | None]] = (),
    option_catalog: Iterable[LifestyleOption] = (),
    permanent: bool = False,
) -> LifestyleSelection:
    """Build a `LifestyleSelection`, validating the tier is a known catalog entry and `months` is
    within the legacy UI's own 1-100 range (see `MIN_LIFESTYLE_MONTHS`/`MAX_LIFESTYLE_MONTHS`).

    Does not check the result against a nuyen budget -- that's a joint constraint shared with
    starter-gear spend, checked in one place by `chummer5.engine.resources
    .create_resources_selection`'s own `lifestyle_cost` parameter, not duplicated here.

    **WP132**: `options` are `(option name, text)` pairs resolved against `option_catalog`. They are
    rejected on Streets (p. 370). A non-repeatable one may be taken once; a repeatable one (Special
    Work Area) needs its text, and each text once. `permanent` buys the Lifestyle for 100 months'
    upkeep, and the selection's `months` becomes 100.
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
    picks = _option_picks(tier, options, option_catalog)
    if permanent:
        months = PERMANENT_LIFESTYLE_MONTHS
    monthly = lifestyle_monthly_cost(tier, picks, cost_percent)
    return LifestyleSelection(
        tier=tier,
        months=months,
        total_cost=monthly * months,
        cost_percent=cost_percent,
        options=picks,
        permanent=permanent,
    )


def _option_picks(
    tier: LifestyleTier,
    options: Iterable[tuple[str, str | None]],
    option_catalog: Iterable[LifestyleOption],
) -> tuple[LifestyleOptionPick, ...]:
    requested = tuple(options)
    if not requested:
        return ()
    if tier.name in NO_OPTIONS_TIER_NAMES:
        raise ValueError(f"{tier.name}: Lifestyle Options can't be taken with this lifestyle")
    by_name = {option.name: option for option in option_catalog}
    picks: list[LifestyleOptionPick] = []
    seen: set[tuple[str, str | None]] = set()
    for name, raw_text in requested:
        option = by_name.get(name)
        if option is None:
            raise ValueError(f"not a Lifestyle Option: {name!r}")
        text = (raw_text or "").strip() or None
        if option.repeatable and text is None:
            raise ValueError(f"{name}: say what the work area is")
        key = (name, text if option.repeatable else None)
        if key in seen:
            raise ValueError(f"{name} is already on this Lifestyle")
        seen.add(key)
        picks.append(LifestyleOptionPick(option, text if option.repeatable else None))
    return tuple(picks)
