"""Tests for `chummer5.data.lifestyle` (WP20's loader) and `chummer5.engine.lifestyle` (the
`LifestyleSelection` builder) -- synthetic/hand-checked values first, mirroring WP5's "prove the
mechanism in isolation" pattern before any real fixture touches it. Fixture cross-checks live in
`tests/integration/test_character_fixtures.py`.
"""

from __future__ import annotations

import pytest

from chummer5.data.lifestyle import STARTING_TIER_NAMES, LifestyleTier, load_lifestyles
from chummer5.engine.lifestyle import (
    MAX_LIFESTYLE_MONTHS,
    MIN_LIFESTYLE_MONTHS,
    LifestyleSelection,
    create_lifestyle_selection,
)

LIFESTYLES = load_lifestyles()


# --- Data loader --------------------------------------------------------------------------------


def test_loads_exactly_the_6_real_starting_tiers() -> None:
    assert {tier.name for tier in LIFESTYLES} == set(STARTING_TIER_NAMES)
    assert len(LIFESTYLES) == 6


def test_excludes_id_error_placeholder() -> None:
    assert "ID ERROR. Re-add life style to fix" not in {t.name for t in LIFESTYLES}


def test_excludes_hospitalized_entries() -> None:
    names = {t.name for t in LIFESTYLES}
    assert "Hospitalized, Basic" not in names
    assert "Hospitalized, Intensive" not in names


def test_excludes_non_sr5_sourced_entries() -> None:
    # Bolt Hole/Commercial/Traveler are all RF-sourced -- confirmed directly against
    # legacy/Chummer/data/lifestyles.xml (see spec/rulebooks/learnings.md's WP20 entry).
    names = {t.name for t in LIFESTYLES}
    assert "Bolt Hole" not in names
    assert "Commercial" not in names
    assert "Traveler" not in names


def test_hand_checked_monthly_costs_match_core_rulebook_lifestyle_costs_table() -> None:
    # Core rulebook, "Lifestyle Costs Table" (p. 94) -- see learnings.md's WP20 entry.
    by_name = {tier.name: tier for tier in LIFESTYLES}
    assert by_name["Street"].monthly_cost == 0
    assert by_name["Squatter"].monthly_cost == 500
    assert by_name["Low"].monthly_cost == 2000
    assert by_name["Medium"].monthly_cost == 5000
    assert by_name["High"].monthly_cost == 10000
    assert by_name["Luxury"].monthly_cost == 100000


# --- Engine selection ----------------------------------------------------------------------------


def test_create_lifestyle_selection_computes_monthly_rate_times_months() -> None:
    selection = create_lifestyle_selection("Low", 3, LIFESTYLES)
    assert isinstance(selection, LifestyleSelection)
    assert selection.tier.name == "Low"
    assert selection.months == 3
    assert selection.total_cost == 6000


def test_create_lifestyle_selection_default_1_month() -> None:
    selection = create_lifestyle_selection("Street", MIN_LIFESTYLE_MONTHS, LIFESTYLES)
    assert selection.total_cost == 0  # Street is the rulebook's own free tier


def test_create_lifestyle_selection_rejects_unknown_tier() -> None:
    with pytest.raises(ValueError, match="not a lifestyle-catalog tier"):
        create_lifestyle_selection("Penthouse", 1, LIFESTYLES)


def test_create_lifestyle_selection_rejects_months_below_minimum() -> None:
    with pytest.raises(ValueError, match="months must be between"):
        create_lifestyle_selection("Low", 0, LIFESTYLES)


def test_create_lifestyle_selection_rejects_months_above_maximum() -> None:
    with pytest.raises(ValueError, match="months must be between"):
        create_lifestyle_selection("Low", MAX_LIFESTYLE_MONTHS + 1, LIFESTYLES)


def test_create_lifestyle_selection_accepts_boundary_months() -> None:
    low_boundary = create_lifestyle_selection("Low", MIN_LIFESTYLE_MONTHS, LIFESTYLES)
    high_boundary = create_lifestyle_selection("Low", MAX_LIFESTYLE_MONTHS, LIFESTYLES)
    assert low_boundary.months == MIN_LIFESTYLE_MONTHS
    assert high_boundary.months == MAX_LIFESTYLE_MONTHS


def test_synthetic_catalog_ignores_out_of_scope_tiers() -> None:
    # A hand-built catalog to prove create_lifestyle_selection doesn't special-case the real
    # catalog's shape -- any tier not present simply isn't selectable.
    catalog = (LifestyleTier(name="Custom", monthly_cost=42, source="Homebrew", page=0),)
    selection = create_lifestyle_selection("Custom", 2, catalog)
    assert selection.total_cost == 84
    with pytest.raises(ValueError, match="not a lifestyle-catalog tier"):
        create_lifestyle_selection("Low", 1, catalog)
