"""Regression tests over the synthetic whole-character fixtures (Phase S / WP72+).

These cover subsystem *interactions* the fixed `.chum5` corpus structurally can't (only one mundane
Priority fixture exists) — see `tests/fixtures/synthetic.py`'s module docstring. Each fixture is
built through the real engine and every hand-derived `expected` value asserted, with each asserted
metric required to carry a citation (`assert_fixture` enforces both).
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from tests.fixtures.synthetic import assert_fixture, build_synthetic, resolve_metric
from tests.fixtures.synthetic_fixtures import (
    COMBAT_MAGE_FIXTURE,
    REFERENCE_MUNDANE_FIXTURE,
    SHAMAN_FACE_FIXTURE,
    STREET_SAMURAI_FIXTURE,
    SYNTHETIC_FIXTURES,
)


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


def test_street_samurai_stacks_cyberware_and_bioware_essence() -> None:
    """The WP73 samurai commits both a cyberware and a bioware selection, and the two Essence costs
    stack against the one shared pool — the interaction (G1/G2) no `.chum5` fixture exercises. A
    smoke check that `build_synthetic` wires both selection functions through the real engine in the
    documented cyberware-first/bioware-second order, not just that the derived numbers happen to
    match.
    """
    character = build_synthetic(STREET_SAMURAI_FIXTURE)
    assert character.metatype.name == "Ork"
    assert character.cyberware_selection is not None
    assert character.bioware_selection is not None
    # Both sources contribute to one Essence pool: 6 - 3.1 - 0.5 = 2.4.
    assert character.cyberware_selection.essence_spent == Decimal("3.1")
    assert character.bioware_selection.essence_spent == Decimal("0.5")
    assert resolve_metric(character, "essence") == Decimal("2.4")
    # The Enhanced Articulation bioware bonus reached the Escape Artist rating (1 bought + 1 bio).
    assert resolve_metric(character, "rating:Escape Artist") == 2


def test_combat_mage_essence_loss_reduces_magic_and_carries_foci_and_mentor() -> None:
    """The WP74 combat mage is a magician whose cyberware Essence loss drops her Magic rating, who
    also carries a bonded focus and a mentor spirit — the interactions (G3/G6) no `.chum5` fixture
    exercises (the corpus's two magic Priority builds carry zero cyberware). A smoke check that
    `build_synthetic` wires the magic/cyberware/foci/mentor paths through the real engine, and that
    the Essence→Magic loss actually flows into the downstream caps and MAG-linked dice pools, not
    just the headline rating.
    """
    character = build_synthetic(COMBAT_MAGE_FIXTURE)
    assert character.metatype.name == "Human"
    assert character.magic_type == "Magician"
    assert character.cyberware_selection is not None
    assert character.foci_selection is not None
    assert character.quality_selection is not None
    assert character.quality_selection.mentor_spirit is not None

    # G3: a 0.3 Essence loss (< 1 point) still costs a full Magic point (6 -> 5).
    assert character.magic_rating_before_essence_loss == 6
    assert character.magic_essence_loss == 1
    assert resolve_metric(character, "essence") == Decimal("5.7")
    assert character.attribute_value("MAG") == 5
    # The reduced MAG flows into a MAG-linked skill's dice pool, not just the raw rating.
    assert resolve_metric(character, "pool:Spellcasting") == 10  # rating 5 + reduced MAG 5

    # G6: the mentor's General (+2 Survival) and Magician (+2 Counterspelling) FLAT_BONUS slots
    # both landed as Improvements; Counterspelling's grant (5) + mentor (2) caps at 6.
    assert resolve_metric(character, "rating:Survival") == 4  # 2 bought + 2 Mountain General
    assert resolve_metric(character, "rating:Counterspelling") == 6  # grant 5 + mentor 2, capped
    # The bonded Power Focus committed its nuyen/Karma cost.
    assert character.foci_selection.karma_cost == 12


def test_shaman_face_spends_leftover_karma_breaking_a_group_and_buying_a_spell() -> None:
    """The WP75 shaman face spends every point of her Step Seven leftover Karma — on an attribute,
    on an individual skill raise that *breaks* a purchased skill group, on a Karma-funded
    specialization, on raising a second group as a group, and on a spell beyond her free Talent
    budget — the interactions (G4/G5) no `.chum5` fixture exercises at all (`learnings/phase-o.md`'s
    WP53/WP54 entries both record "no fixture ... hand-verified"). A smoke check that
    `build_synthetic` drives the real Step Seven selection functions in the documented
    attributes→skills→spells order, and that the group-breaking split reaches the affected ratings
    rather than only the Karma ledger.
    """
    character = build_synthetic(SHAMAN_FACE_FIXTURE)
    assert character.metatype.name == "Elf"
    assert character.magic_type == "Magician"
    assert character.karma_attribute_selection is not None
    assert character.karma_skill_selection is not None
    assert character.spell_selection is not None

    # G4: only Influence broke, and only Negotiation left it — its siblings keep the group rating.
    assert character.karma_skill_selection.broken_groups == frozenset({"Influence"})
    assert resolve_metric(character, "rating:Negotiation") == 5
    assert resolve_metric(character, "rating:Etiquette") == 4
    # The Karma-funded specialization reaches the dice pool (+2), on top of the broken-out rating.
    assert resolve_metric(character, "pool:Negotiation") == 15  # 5 + CHA 8 + 2 spec
    # Conjuring was raised *as a group* with Karma instead — 1 priority point + 1 Karma point.
    assert resolve_metric(character, "rating:Binding") == 2

    # G5: the 6th spell is Karma-funded, at exactly the Magic 3 x 2 known-spells cap.
    assert len(character.spell_selection.spells) == 6
    assert character.spell_selection.budget == 5
    assert character.spell_selection.karma_spell_count == 1

    # The whole 25-Karma pool (widened to 42 by net-negative qualities) is spent to the point.
    assert character.karma_spent == 25
    assert character.karma_remaining == 0


def test_unrecognised_metric_key_raises() -> None:
    character = build_synthetic(REFERENCE_MUNDANE_FIXTURE)
    with pytest.raises(KeyError):
        resolve_metric(character, "not:a:metric")
