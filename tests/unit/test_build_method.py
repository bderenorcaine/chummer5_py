"""Tests for `chummer5.engine.build_method` (WP44's Sum-to-Ten letter-assignment rule).

Synthetic/hand-checked values first, mirroring WP5's "prove the mechanism in isolation" pattern --
the real-fixture cross-check (5 curated `.chum5` files whose full 5-letter assignment sums to
exactly 10) lives in `tests/integration/test_legacy_chum5.py`, alongside the research recorded in
`spec/rulebooks/learnings.md`'s WP44 entry.
"""

from __future__ import annotations

import pytest

from chummer5.engine.build_method import (
    PRIORITY_BUILD_METHOD,
    SUM_TO_TEN_BUILD_METHOD,
    SUM_TO_TEN_POINT_VALUES,
    SUM_TO_TEN_TARGET,
    SUPPORTED_BUILD_METHODS,
    sum_to_ten_total,
    validate_sum_to_ten_total,
)


def test_point_table_matches_legacy_hardcoded_fallback() -> None:
    # SelectMetatypePriority.cs's _dicSumtoTenValues fallback: A=4, B=3, C=2, D=1, E=0.
    assert dict(SUM_TO_TEN_POINT_VALUES) == {"A": 4, "B": 3, "C": 2, "D": 1, "E": 0}


def test_target_defaults_to_10() -> None:
    assert SUM_TO_TEN_TARGET == 10


def test_supported_build_methods_are_priority_and_sum_to_ten() -> None:
    assert SUPPORTED_BUILD_METHODS == (PRIORITY_BUILD_METHOD, SUM_TO_TEN_BUILD_METHOD)
    assert PRIORITY_BUILD_METHOD == "Priority"
    assert SUM_TO_TEN_BUILD_METHOD == "SumtoTen"


def test_sum_to_ten_total_sums_point_values() -> None:
    assert sum_to_ten_total(["A", "B", "C", "D", "E"]) == 4 + 3 + 2 + 1 + 0


def test_sum_to_ten_total_counts_repeats_per_occurrence() -> None:
    # Bastion.chum5's real letters (Heritage/Talent/Attributes/Skills/Resources): E, C, A, E, A.
    assert sum_to_ten_total(["E", "C", "A", "E", "A"]) == 0 + 2 + 4 + 0 + 4


def test_sum_to_ten_total_rejects_unknown_letter() -> None:
    with pytest.raises(ValueError, match="not a Sum-to-Ten priority letter"):
        sum_to_ten_total(["A", "F", "C", "D", "E"])


def test_validate_sum_to_ten_total_accepts_exact_10_with_repeats() -> None:
    # Serpent.chum5's real letters -- repeats both C and B, still totals exactly 10.
    assert validate_sum_to_ten_total(["E", "C", "C", "B", "B"]) == 10


def test_validate_sum_to_ten_total_accepts_distinct_letters_illegal_under_priority() -> None:
    # A distinct A-E permutation is legal under Priority too, but this proves Sum-to-Ten doesn't
    # require distinctness -- Yeti's own letters (Priority-built) happen to be a permutation and
    # still total exactly 10 under this rule.
    assert validate_sum_to_ten_total(["D", "A", "B", "C", "E"]) == 10


def test_validate_sum_to_ten_total_rejects_under_target() -> None:
    with pytest.raises(ValueError, match="must total exactly 10"):
        validate_sum_to_ten_total(["E", "E", "E", "E", "E"])  # 0+0+0+0+0 = 0


def test_validate_sum_to_ten_total_rejects_over_target() -> None:
    # Confirmed against the legacy C#'s own `!=` comparison (not `>`): exceeding 10 is just as
    # invalid as falling short, not merely "wasteful."
    with pytest.raises(ValueError, match="must total exactly 10"):
        validate_sum_to_ten_total(["A", "A", "A", "A", "A"])  # 4*5 = 20
