"""Priority-letter build methods (WP44): `Priority` (WP14's bijection -- 5 categories, 5 distinct
letters) and `SumtoTen`, an alternate letter-assignment rule that reuses `priorities.xml`/
`chummer5.data.priorities` completely unchanged, just with a different validity check on the same
5 letters.

**Not a rulebook mechanic.** Confirmed via `pdftotext -layout` over the full core rulebook PDF:
zero hits for "sum to ten"/"sum-to-ten"/"sumtoten". This is legacy-Chummer/errata content --
`Chummer.Backend.Enums.CharacterBuildMethod.SumtoTen` -- not a page citation. See
`spec/rulebooks/learnings.md`'s WP44 entry for the full research.

**The rule is exact equality, not a ceiling.** Each of the 5 categories (Heritage, Talent,
Attributes, Skills, Resources) gets a letter A-E; letters may repeat (unlike Priority's bijection);
each letter has a fixed point value (`SUM_TO_TEN_POINT_VALUES`, `SelectMetatypePriority.cs`'s
hardcoded `_dicSumtoTenValues` fallback); the 5 letters' point values must sum to *exactly*
`SUM_TO_TEN_TARGET` (10) -- confirmed via `SelectMetatypePriority.cs`'s own `!=` comparison and its
`Message_SumtoTen` string ("Your Priority selection must equal {0}."), and independently via 5 real
curated `.chum5` fixtures (4 `SumtoTen`-built, 1 `Priority`-built) whose full 5-letter assignment
always totals exactly 10, including cases with repeated letters. `SUM_TO_TEN_TARGET` is hardcoded
rather than exposed as a setting, mirroring `QUALITY_KARMA_LIMIT`'s "hardcode the one supported
default, don't build a settings system that doesn't otherwise exist" precedent -- the legacy engine
itself lets `CharacterSettings._intSumtoTen` vary per settings block, but every shipped block uses
10.
"""

from __future__ import annotations

from collections.abc import Iterable
from types import MappingProxyType

# `<buildmethod>` literal values (chummer5.io.legacy_chum5.LegacyCharacter.build_method) -- matched
# verbatim so no translation layer is needed between this module and legacy_import.py.
PRIORITY_BUILD_METHOD = "Priority"
SUM_TO_TEN_BUILD_METHOD = "SumtoTen"
SUPPORTED_BUILD_METHODS = (PRIORITY_BUILD_METHOD, SUM_TO_TEN_BUILD_METHOD)

# SelectMetatypePriority.cs's hardcoded fallback point table (A highest, E lowest -- the same rank
# order every priority letter already has everywhere else in this project).
SUM_TO_TEN_POINT_VALUES: MappingProxyType[str, int] = MappingProxyType(
    {"A": 4, "B": 3, "C": 2, "D": 1, "E": 0}
)
SUM_TO_TEN_TARGET = 10


def sum_to_ten_total(letters: Iterable[str]) -> int:
    """Sum of `SUM_TO_TEN_POINT_VALUES` for the given letters, repeats counted per occurrence (the
    legacy `GetSumToTenValue()` call is made once per category, independently, with no dedup).

    Raises `ValueError` for a letter outside A-E -- never for a total that doesn't hit
    `SUM_TO_TEN_TARGET`, so callers can use this for a live "current total" display even on an
    as-yet-invalid combination; use `validate_sum_to_ten_total` to enforce the target itself.
    """
    unknown = sorted({letter for letter in letters if letter not in SUM_TO_TEN_POINT_VALUES})
    if unknown:
        raise ValueError(f"not a Sum-to-Ten priority letter (must be A-E): {unknown}")
    return sum(SUM_TO_TEN_POINT_VALUES[letter] for letter in letters)


def validate_sum_to_ten_total(letters: Iterable[str]) -> int:
    """Validate that `letters` (one per category, repeats allowed) sums to exactly
    `SUM_TO_TEN_TARGET`, returning that total on success.

    Confirmed exact equality, not "at most" -- see this module's own docstring and
    `spec/rulebooks/learnings.md`'s WP44 entry for why the Implementation Plan's original "must not
    exceed" phrasing was wrong.
    """
    letters = tuple(letters)
    total = sum_to_ten_total(letters)
    if total != SUM_TO_TEN_TARGET:
        raise ValueError(
            f"Sum-to-Ten priority selection must total exactly {SUM_TO_TEN_TARGET}; "
            f"{'+'.join(letters)} totals {total}"
        )
    return total
