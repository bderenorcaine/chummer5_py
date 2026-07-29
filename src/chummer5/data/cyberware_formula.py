"""Resolver for the rating-scaled `<cost>`/`<ess>`/`<capacity>` formula shapes SR5-sourced
`cyberware.xml` entries actually use (WP36 -- Phase K's first WP, pure groundwork with no real
catalog data wired through it yet, mirroring WP5's/WP30's "prove the mechanism in isolation first"
precedent).

WP31's loader (`chummer5.data.cyberware`) keeps only the 60 of 87 SR5 entries whose `<cost>` and
`<ess>` are both bare literals; the other 27 carry a formula. This module is what evaluates those
formulas against a chosen rating, so WP37's widened loader can offer them. It is a **whitelist of
named, hand-verified shapes**, not a general arithmetic-expression parser -- the same
"classify known shapes, fail closed on anything else" posture `chummer5.data.qualities`'s bonus
classifier and `chummer5.data.gear.parse_rating_availability` already established. Nothing here
reflects, `eval`s, or interprets the legacy rules language generally.

## The shape survey, re-confirmed against all 87 SR5 entries (WP36)

The Implementation Plan's Phase K intro carried an exploratory survey of the *27 WP31-excluded*
entries and counted "6 distinct formula shapes." Re-derived here over the complete 87-entry SR5
set and over all three fields (`<cost>`, `<ess>`, `<capacity>`, not just the two WP31 filters on),
which turns up **8** resolvable shapes -- the intro's 6 plus a bare `Rating` (only ever seen
bracketed, in `<capacity>`) and `(Rating * A) + B`, the shared `<ess>` of Cybereyes Basic System and
Cyberears that the intro's own cost-focused pass classified as part of those two items' "one-off
named formulas" when it is in fact a shape they share. Each shape, with every SR5 item that uses it:

- `LITERAL` -- `1000`, `0.25`, `-0.5`, `0`: every flat `<cost>`/`<ess>` (the 60 items WP31 already
  loads) and every bare-integer `<capacity>` budget (the 16 Cyberlimb variants, plus the 19 items
  whose `<capacity>` is `0`, i.e. "holds nothing").
- `RATING` -- `Rating`: the `<capacity>` cost of Vision Enhancement, Audio Enhancement, Select
  Sound Filter, Armor and Hydraulic Jacks (written bracketed, `[Rating]`).
- `RATING_TIMES` -- `Rating * N`, N fractional or negative, optionally paren-wrapped: 19 `<cost>`
  (Data Lock's `Rating * 1000` through Muscle Replacement's `Rating * 25000`), 8 `<ess>` (Dermal
  Plating's `Rating * 0.5`, Essence Antihole's `Rating * -0.01`, ...), and 3 `<capacity>`
  (Cyberears' `Rating * 4`, Cybereyes Basic System's parenthesized `(Rating * 4)`, Enhanced
  Strength/Agility's `[Rating * 1]`).
- `RATING_TIMES_PLUS` -- `(Rating * A) + B`: the `<ess>` shared by Cybereyes Basic System and
  Cyberears (`(Rating * 0.1) + 0.1`).
- `FIXED_VALUES` -- `FixedValues(v1,v2,...)`: Wired Reflexes (both `<cost>` and `<ess>`) and
  Control Rig (`<cost>`).
- `RATING_ABOVE_MIN_TIMES` -- `(Rating - MinRating + A) * B`: the `<cost>` of Customized Strength
  and Customized Agility.
- `CYBEREYES_BASIC_SYSTEM_COST` -- `4000 * Rating - 2000 * number(Rating > 1)`: that item's
  `<cost>`, nothing else.
- `CYBEREARS_COST` -- `3000 + 500 * ((Rating - 1) * (Rating + 1) + number(Rating > 2))`: that
  item's `<cost>`, nothing else.

Every one of these is hand-checked against the printed rulebook tables (core rulebook pp. 453,
454, 456, 457) in `tests/unit/test_cyberware_formula.py`, not just against the XML it was read from
-- `spec/rulebooks/learnings/phase-k.md`'s WP36 entry has the transcribed tables, plus the verified
PDF page offset (physical page = book page + 2) and the reason an item's `<page>` tag often names
the page *before* the table its numbers live in.

## Decisions this module makes (each one a "decide & document" item in WP36's own plan entry)

- **The two one-off formulas are keyed by their verbatim formula string, not by item name.** WP36's
  entry suggested hardcoding them "by item name"; keying on the (whitespace-normalized) formula
  text is the same one-off-per-item outcome with two advantages: the resolver stays a pure function
  of the formula (no item identity to thread through WP37/38 call sites), and a future
  `cyberware.xml` update that changes either expression surfaces as an unsupported-formula failure
  instead of silently resolving with the old, now-wrong arithmetic.
- **Brackets are *not* this module's concern.** `[Rating]`, `[2]`, `[Rating * 1]` are rejected
  (`parse_cyberware_formula` returns `None`). A bracketed `<capacity>` means "this is a plugin's
  Capacity *cost*" and a bare one means "this is a parent's Capacity *budget*" -- semantics WP37/38
  own. Requiring the caller to strip brackets *before* resolving keeps this module agnostic to
  budget-vs-cost (WP36's explicit instruction) and makes the mistake of resolving a plugin cost as a
  budget impossible to make silently here.
- **`[*]` (Image Link, Sound Link) is not a formula at all** -- it is a marker meaning "bundled free
  with the parent, no Capacity charged" (core rulebook p. 454's own eyeware-table footnote,
  "* Included in the basic cybereyes system"). Rejected like any other bracketed value; WP37/38
  handle it as a `bundled_free` flag with nothing to resolve. This confirms the current read
  recorded in `spec/rulebooks/learnings/phase-k.md`'s pre-Phase-K entry.
- **`<rating>`/`<minrating>` bounds resolution is out of scope.** Two items' bounds are attribute
  placeholders (`<rating>{AGIMaximum}</rating>`, `<minrating>{AGIMinimum}+1</minrating>` on
  Customized Agility/Strength) -- character-state lookups, not arithmetic over a rating. The
  resolver takes already-resolved `rating`/`min_rating` ints from its caller.
- **`<avail>` is out of scope**, even though it carries the same shape family. The Availability-cap
  mechanic is ruled out project-wide (Project Overview, 2026-07-21), so nothing needs to resolve an
  availability formula per-rating.
- **Fail loud, never fail quiet.** `parse_cyberware_formula` returns `None` for an unrecognized
  string (so WP37 can use it as an inclusion filter), while `resolve_cyberware_formula` raises
  `UnsupportedCyberwareFormulaError`. `min_rating` defaults to `None`, not `0`, so resolving
  `RATING_ABOVE_MIN_TIMES` without supplying one raises rather than quietly overcharging by
  `MinRating * B` nuyen -- this project's stated primary risk is plausible-but-wrong numbers, not
  crashes.

## `FixedValues` indexing, confirmed against the legacy C#

`FixedValues(a,b,c)` is indexed **1-based by rating, clamped at both ends**: rating 1 -> `a`,
rating 3 -> `c`, rating 4+ -> `c` (the last entry), rating <= 1 -> `a`. Read directly from
`legacy/Chummer/Backend/Static/Extensions/StringExtensions.cs`'s
`ProcessFixedValuesStringCore` (`if (intRating <= 1) return` the first segment; the per-entry loop
`return`s the last segment once it runs out of commas), not assumed. The nested-parentheses and
multiple-`FixedValues()`-per-string cases that function also handles do not occur in any SR5
cyberware entry -- both real uses are a single flat comma list wrapping the entire field -- so only
that case is supported here.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum

# A numeric literal inside a formula: optionally negative, optionally fractional.
_NUMBER = r"-?\d+(?:\.\d+)?"

_LITERAL_RE = re.compile(rf"({_NUMBER})")
_RATING_RE = re.compile(r"Rating")
_RATING_TIMES_RE = re.compile(rf"Rating\s*\*\s*({_NUMBER})")
_RATING_TIMES_PLUS_RE = re.compile(rf"\(\s*Rating\s*\*\s*({_NUMBER})\s*\)\s*\+\s*({_NUMBER})")
_FIXED_VALUES_RE = re.compile(rf"FixedValues\(\s*({_NUMBER}(?:\s*,\s*{_NUMBER})*)\s*\)")
_RATING_ABOVE_MIN_TIMES_RE = re.compile(
    rf"\(\s*Rating\s*-\s*MinRating\s*\+\s*({_NUMBER})\s*\)\s*\*\s*({_NUMBER})"
)


class FormulaKind(Enum):
    """The named, hand-verified formula shapes this module resolves. See the module docstring's
    table for which real `cyberware.xml` fields use each one.
    """

    LITERAL = "literal"
    RATING = "rating"
    RATING_TIMES = "rating_times"
    RATING_TIMES_PLUS = "rating_times_plus"
    FIXED_VALUES = "fixed_values"
    RATING_ABOVE_MIN_TIMES = "rating_above_min_times"
    CYBEREYES_BASIC_SYSTEM_COST = "cybereyes_basic_system_cost"
    CYBEREARS_COST = "cyberears_cost"


class UnsupportedCyberwareFormulaError(ValueError):
    """Raised when a formula string doesn't match any shape in `FormulaKind`.

    WP37's loader is expected to call `parse_cyberware_formula` (which returns `None` instead) to
    decide whether an item is offerable at all; this error is for the case where a formula that was
    supposed to be resolvable isn't -- i.e. real data drift, not a routine filter miss.
    """


@dataclass(frozen=True)
class CyberwareFormula:
    """One parsed cyberware formula: a shape plus its numeric parameters, resolvable per rating.

    Parsed once (`parse_cyberware_formula`) and resolved many times, so WP37 can choose to keep
    parsed formulas on its catalog entries rather than re-parsing raw strings per purchase -- the
    "compile the condition once at construction" principle the Project Overview states for
    Improvements, applied to the one other rules-language string this engine reads.

    `params` is shape-specific and documented per `FormulaKind`:

    - `LITERAL`: `(value,)`
    - `RATING`: `()`
    - `RATING_TIMES`: `(multiplier,)`
    - `RATING_TIMES_PLUS`: `(multiplier, addend)`
    - `FIXED_VALUES`: one entry per rating step, in order
    - `RATING_ABOVE_MIN_TIMES`: `(offset, multiplier)`
    - `CYBEREYES_BASIC_SYSTEM_COST`, `CYBEREARS_COST`: `()` (the arithmetic is the shape)
    """

    kind: FormulaKind
    raw: str
    params: tuple[Decimal, ...]

    @property
    def scales_with_rating(self) -> bool:
        """True when the resolved value depends on the rating at all -- i.e. everything but a
        `LITERAL`. WP37/38 can use this to tell "needs a rating picker" from "single price."
        """
        return self.kind is not FormulaKind.LITERAL

    @property
    def requires_min_rating(self) -> bool:
        """True when `resolve` needs a `min_rating` (only `RATING_ABOVE_MIN_TIMES`, i.e. only
        Customized Strength/Agility).
        """
        return self.kind is FormulaKind.RATING_ABOVE_MIN_TIMES

    def resolve(self, *, rating: int, min_rating: int | None = None) -> Decimal:
        """Evaluate this formula at `rating`.

        `rating` must be >= 1 (SR5 has no rating-0 purchase; a flat item is resolved at rating 1).
        `min_rating` is required only when `requires_min_rating` is true, and is the item's *lowest
        purchasable* rating -- see this module's `resolve_cyberware_formula` docstring for the
        inclusive-count reading that makes `(Rating - MinRating + 1)` come out right.
        """
        if rating < 1:
            raise ValueError(f"rating must be >= 1, got {rating}")
        if self.requires_min_rating and min_rating is None:
            raise ValueError(
                f"formula {self.raw!r} needs a min_rating (its cost counts rating points above the "
                f"item's lowest purchasable rating)"
            )

        rating_dec = Decimal(rating)
        match self.kind:
            case FormulaKind.LITERAL:
                return self.params[0]
            case FormulaKind.RATING:
                return rating_dec
            case FormulaKind.RATING_TIMES:
                return rating_dec * self.params[0]
            case FormulaKind.RATING_TIMES_PLUS:
                return rating_dec * self.params[0] + self.params[1]
            case FormulaKind.FIXED_VALUES:
                # 1-based, clamped at both ends -- see module docstring's legacy-C# citation.
                index = min(rating, len(self.params)) - 1
                return self.params[index]
            case FormulaKind.RATING_ABOVE_MIN_TIMES:
                assert min_rating is not None  # guarded above; narrows the type for mypy
                offset, multiplier = self.params
                return (rating_dec - Decimal(min_rating) + offset) * multiplier
            case FormulaKind.CYBEREYES_BASIC_SYSTEM_COST:
                return Decimal(4000) * rating_dec - Decimal(2000 if rating > 1 else 0)
            case FormulaKind.CYBEREARS_COST:
                steps = (rating_dec - 1) * (rating_dec + 1) + Decimal(1 if rating > 2 else 0)
                return Decimal(3000) + Decimal(500) * steps


# The two items whose formula is unique to them: matched by verbatim (whitespace-normalized) text
# rather than generalized into a parser, per the module docstring's first decision.
_ONE_OFF_FORMULAS = {
    "4000 * Rating - 2000 * number(Rating > 1)": FormulaKind.CYBEREYES_BASIC_SYSTEM_COST,
    "3000 + 500 * ((Rating - 1) * (Rating + 1) + number(Rating > 2))": FormulaKind.CYBEREARS_COST,
}


def _normalize(text: str) -> str:
    """Collapse whitespace runs to single spaces and trim, so formatting differences in the XML
    don't change whether a formula is recognized.
    """
    return re.sub(r"\s+", " ", text.strip())


def _strip_outer_parentheses(text: str) -> str:
    """Remove one layer of parentheses wrapping the *entire* string (`"(Rating * 4)"` ->
    `"Rating * 4"`, Cybereyes Basic System's own `<capacity>`), leaving strings whose parentheses
    only wrap a part alone (`"(Rating * 0.1) + 0.1"` is returned unchanged).
    """
    if not (text.startswith("(") and text.endswith(")")):
        return text
    depth = 0
    for index, char in enumerate(text):
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                # The paren opened at 0 closes here: only a full wrap if that's the last character.
                return text[1:-1].strip() if index == len(text) - 1 else text
    return text


def parse_cyberware_formula(formula: str) -> CyberwareFormula | None:
    """Parse a `<cost>`/`<ess>`/`<capacity>` formula string, or return `None` if it isn't one of
    the whitelisted shapes (module docstring's table).

    Returns `None` -- deliberately, see the module docstring's bracket decision -- for any
    bracketed `<capacity>` value (`[2]`, `[Rating]`, `[Rating * 1]`, `[*]`): the caller strips
    brackets first, because whether a Capacity value is a parent's budget or a plugin's cost is
    WP37/38's semantics, not this resolver's.
    """
    text = _normalize(formula)
    if not text:
        return None

    one_off = _ONE_OFF_FORMULAS.get(text)
    if one_off is not None:
        return CyberwareFormula(kind=one_off, raw=text, params=())

    fixed_values = _FIXED_VALUES_RE.fullmatch(text)
    if fixed_values:
        values = tuple(Decimal(part.strip()) for part in fixed_values.group(1).split(","))
        return CyberwareFormula(kind=FormulaKind.FIXED_VALUES, raw=text, params=values)

    rating_times_plus = _RATING_TIMES_PLUS_RE.fullmatch(text)
    if rating_times_plus:
        return CyberwareFormula(
            kind=FormulaKind.RATING_TIMES_PLUS,
            raw=text,
            params=(Decimal(rating_times_plus.group(1)), Decimal(rating_times_plus.group(2))),
        )

    above_min = _RATING_ABOVE_MIN_TIMES_RE.fullmatch(text)
    if above_min:
        return CyberwareFormula(
            kind=FormulaKind.RATING_ABOVE_MIN_TIMES,
            raw=text,
            params=(Decimal(above_min.group(1)), Decimal(above_min.group(2))),
        )

    # Only the single-term shapes below may be wrapped in redundant parentheses in the real data
    # (Cybereyes Basic System's `(Rating * 4)` <capacity>); the multi-term shapes above match their
    # own parentheses exactly.
    unwrapped = _strip_outer_parentheses(text)

    rating_times = _RATING_TIMES_RE.fullmatch(unwrapped)
    if rating_times:
        return CyberwareFormula(
            kind=FormulaKind.RATING_TIMES, raw=text, params=(Decimal(rating_times.group(1)),)
        )

    if _RATING_RE.fullmatch(unwrapped):
        return CyberwareFormula(kind=FormulaKind.RATING, raw=text, params=())

    literal = _LITERAL_RE.fullmatch(unwrapped)
    if literal:
        return CyberwareFormula(
            kind=FormulaKind.LITERAL, raw=text, params=(Decimal(literal.group(1)),)
        )

    return None


def resolve_cyberware_formula(
    formula: str, *, rating: int, min_rating: int | None = None
) -> Decimal:
    """Resolve a cyberware `<cost>`/`<ess>`/`<capacity>` formula at `rating`, as a `Decimal`.

    One `Decimal` return type for all three fields, deliberately: `<cost>` and `<capacity>` are
    always integral in practice but `<ess>` is routinely fractional, and `Decimal` throughout keeps
    Essence arithmetic exact (`chummer5.engine.derived`'s Essence math is already `Decimal`-based,
    and float would reintroduce the rounding this engine avoids by construction). Callers wanting
    an `int` convert explicitly.

    `min_rating` is only consulted by the `(Rating - MinRating + 1) * N` shape (Customized
    Strength/Agility), where it means the item's **lowest purchasable rating**, making
    `Rating - MinRating + 1` an inclusive count of purchased points. Hand-checked against the
    printed table (core rulebook p. 457, "Each STR or AGI point above 3 ... +5,000¥"): a cyberlimb's
    base STR/AGI is 3, so the lowest purchasable point is 4, and buying up to rating 6 costs
    `(6 - 4 + 1) * 5000 = 15,000¥` for points 4/5/6. Omitting it for that shape raises rather than
    defaulting to 0.

    Raises `UnsupportedCyberwareFormulaError` if the formula isn't a whitelisted shape (including
    any bracketed `<capacity>` value -- strip brackets first, see the module docstring).
    """
    parsed = parse_cyberware_formula(formula)
    if parsed is None:
        raise UnsupportedCyberwareFormulaError(
            f"unsupported cyberware formula {formula!r} -- this resolver whitelists named shapes "
            f"only (see chummer5.data.cyberware_formula's docstring); bracketed <capacity> values "
            f"must have their brackets stripped by the caller first"
        )
    return parsed.resolve(rating=rating, min_rating=min_rating)
