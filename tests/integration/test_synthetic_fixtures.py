"""Regression tests over the synthetic whole-character fixtures (Phase S / WP72+).

These cover subsystem *interactions* the fixed `.chum5` corpus structurally can't (only one mundane
Priority fixture exists) — see `tests/fixtures/synthetic.py`'s module docstring. Each fixture is
built through the real engine and every hand-derived `expected` value asserted, with each asserted
metric required to carry a citation (`assert_fixture` enforces both).
"""

from __future__ import annotations

import pytest
from tests.fixtures.synthetic import assert_fixture, build_synthetic, resolve_metric
from tests.fixtures.synthetic_fixtures import REFERENCE_MUNDANE_FIXTURE, SYNTHETIC_FIXTURES


@pytest.mark.parametrize("fixture", SYNTHETIC_FIXTURES, ids=lambda f: f.name)
def test_synthetic_fixture_matches_hand_derived_values(fixture) -> None:  # type: ignore[no-untyped-def]
    assert_fixture(fixture)


def test_reference_fixture_builds_a_finalized_character() -> None:
    """The reference mundane-Priority build produces a `Character` carrying the committed
    skill/quality selections the harness fed it — a smoke check that `build_synthetic` wires the
    real engine's public API end to end, not just that the numbers happen to match.
    """
    character = build_synthetic(REFERENCE_MUNDANE_FIXTURE)
    assert character.metatype.name == "Human"
    assert character.skill_allocation is not None
    assert character.quality_selection is not None
    # Catlike's +2 Sneaking improvement actually landed in the ImprovementIndex.
    assert resolve_metric(character, "rating:Sneaking") == 5


def test_unrecognised_metric_key_raises() -> None:
    character = build_synthetic(REFERENCE_MUNDANE_FIXTURE)
    with pytest.raises(KeyError):
        resolve_metric(character, "not:a:metric")
