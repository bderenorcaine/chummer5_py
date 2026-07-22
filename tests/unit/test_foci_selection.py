"""Tests for `chummer5.engine.foci` (WP47). See that module's docstring for the two-cap (count +
chargen-specific total-Force), per-pick Availability, and shared nuyen/Karma budget reasoning this
file exercises.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from chummer5.data.foci import load_foci
from chummer5.data.metatypes import load_metatypes
from chummer5.data.priorities import load_priorities
from chummer5.data.skills import load_skills
from chummer5.data.traditions import load_traditions
from chummer5.engine.character import Character, create_character, metatype_choices
from chummer5.engine.foci import (
    CHARGEN_FORCE_CAP_MULTIPLIER,
    MAX_AVAILABILITY,
    FociSelection,
    FocusPick,
    apply_foci_improvements,
    create_foci_selection,
)
from chummer5.engine.improvements import ImprovementSource, ImprovementType
from chummer5.engine.magic import create_magic_selection

PRIORITIES = load_priorities()
TRADITIONS = load_traditions()
METATYPES = load_metatypes()
SKILLS = load_skills()
FOCI = load_foci()

# Letters A/B's Magician option grants 2 free Magical Active skills -- irrelevant noise for these
# Foci tests, satisfied here with 2 arbitrary eligible skill ids (mirrors chummer5.data.priorities'
# own "magic" skilltype filter: any Magical Active/Pseudo-Magical Active skill).
_MAGICAL_SKILL_IDS = [s.id for s in SKILLS if s.category == "Magical Active"][:2]

ALCHEMICAL = next(f for f in FOCI if f.name == "Alchemical Focus")
CENTERING = next(f for f in FOCI if f.name == "Centering Focus")


def _mundane_human() -> Character:
    heritage = PRIORITIES.heritage["D"]
    human = next(c for c in metatype_choices(heritage, METATYPES) if c.metatype.name == "Human")
    return create_character(
        metatype_choice=human,
        heritage_letter="D",
        attributes_letter="A",
        priorities=PRIORITIES,
        attribute_points={},
    )


def _magician(talent_letter: str = "A") -> Character:
    """A Human Magician at `talent_letter` (letter A grants Magic 6 -- see `chummer5.data.
    priorities` -- deliberately the highest available so the count/total-Force caps have real
    headroom to test against), Hermetic tradition. Letters A/B require the free-skill grant to be
    satisfied (`_MAGICAL_SKILL_IDS`); letter C/D need none."""
    character = _mundane_human()
    tradition = next(t for t in TRADITIONS if t.name == "Hermetic")
    grant_ids = _MAGICAL_SKILL_IDS if talent_letter in ("A", "B") else []
    selection = create_magic_selection(
        talent_letter, "Magician", tradition.id, grant_ids, PRIORITIES, TRADITIONS, SKILLS
    )
    return replace(
        character,
        magic_type=selection.magic_type,
        magic_rating=selection.magic_rating,
        tradition=selection.tradition,
    )


def _adept(talent_letter: str = "D") -> Character:
    """A Human Adept at `talent_letter` (letter D grants no free-skill grant, avoiding irrelevant
    picks noise -- see `chummer5.data.priorities`)."""
    character = _mundane_human()
    selection = create_magic_selection(talent_letter, "Adept", None, [], PRIORITIES, TRADITIONS, ())
    return replace(
        character, magic_type=selection.magic_type, magic_rating=selection.magic_rating
    )


# -- create_foci_selection ------------------------------------------------------------------------


def test_empty_picks_is_always_fine_even_for_a_mundane_character() -> None:
    mundane = _mundane_human()
    selection = create_foci_selection([], mundane, FOCI, nuyen_budget=0, karma_budget=0)
    assert selection == FociSelection(picks=(), nuyen_cost=0, karma_cost=0, nuyen_budget=0,
                                       karma_budget=0)


def test_rejects_any_pick_for_a_mundane_character() -> None:
    mundane = _mundane_human()
    with pytest.raises(ValueError, match="magically active"):
        create_foci_selection(
            [(ALCHEMICAL.id, 1)], mundane, FOCI, nuyen_budget=10**6, karma_budget=100
        )


def test_adept_can_bond_a_focus_not_just_magician() -> None:
    # Bonding only requires being Awakened at all (core rulebook p. 317), not specifically a
    # Magician -- see module docstring.
    adept = _adept()
    selection = create_foci_selection(
        [(ALCHEMICAL.id, 1)], adept, FOCI, nuyen_budget=10**6, karma_budget=100
    )
    assert selection.nuyen_cost == ALCHEMICAL.cost_per_force


def test_rejects_unknown_focus_id() -> None:
    character = _magician()
    with pytest.raises(ValueError, match="not a Foci catalog id"):
        create_foci_selection(
            [("not-a-real-id", 1)], character, FOCI, nuyen_budget=10**6, karma_budget=100
        )


def test_rejects_force_below_one() -> None:
    character = _magician()
    with pytest.raises(ValueError, match="Force must be between 1 and 18"):
        create_foci_selection(
            [(ALCHEMICAL.id, 0)], character, FOCI, nuyen_budget=10**6, karma_budget=100
        )


def test_rejects_force_above_the_catalog_max_rating() -> None:
    character = _magician()
    with pytest.raises(ValueError, match="Force must be between 1 and 18"):
        create_foci_selection(
            [(ALCHEMICAL.id, 19)], character, FOCI, nuyen_budget=10**8, karma_budget=10**4
        )


def test_binds_a_single_focus_within_budget_and_computes_costs() -> None:
    character = _magician()
    selection = create_foci_selection(
        [(ALCHEMICAL.id, 2)], character, FOCI, nuyen_budget=10**6, karma_budget=100
    )
    assert selection.picks == (FocusPick(focus=ALCHEMICAL, force=2),)
    assert selection.nuyen_cost == ALCHEMICAL.cost_per_force * 2
    assert selection.karma_cost == ALCHEMICAL.bonding_karma_per_force * 2


def test_allows_partial_spend() -> None:
    character = _magician()
    selection = create_foci_selection(
        [(ALCHEMICAL.id, 1)], character, FOCI, nuyen_budget=10**6, karma_budget=100
    )
    assert selection.nuyen_cost < selection.nuyen_budget
    assert selection.karma_cost < selection.karma_budget


def test_allows_binding_two_of_the_same_focus() -> None:
    character = _magician()
    selection = create_foci_selection(
        [(ALCHEMICAL.id, 1), (ALCHEMICAL.id, 1)], character, FOCI, nuyen_budget=10**6,
        karma_budget=100,
    )
    assert len(selection.picks) == 2


def test_rejects_count_exceeding_magic_rating() -> None:
    # Letter C Magician grants Magic 3 (lowest offered, no free-skill grant) -- easy to exceed with
    # 4 picks.
    character = _magician(talent_letter="C")
    assert character.attribute_value("MAG") == 3
    with pytest.raises(ValueError, match="exceeding the Magic limit of 3"):
        create_foci_selection(
            [(ALCHEMICAL.id, 1)] * 4,
            character,
            FOCI,
            nuyen_budget=10**6,
            karma_budget=1000,
        )


def test_rejects_total_force_exceeding_the_chargen_cap() -> None:
    # Magic 6 at letter A -> chargen cap = 6 * 2 = 12. 4 picks at Force 4 = 16 > 12, count 4 <= 6.
    character = _magician()
    assert character.attribute_value("MAG") == 6
    with pytest.raises(ValueError, match=r"exceeds the character-creation cap of 12"):
        create_foci_selection(
            [(ALCHEMICAL.id, 4)] * 4, character, FOCI, nuyen_budget=10**8, karma_budget=10**4
        )


def test_a_build_legal_under_general_x5_but_illegal_under_the_x2_chargen_rule_is_rejected() -> None:
    # Magic 6: general/lifetime rule caps total Force at 30 (Magic x 5, p. 317); the
    # chargen-specific rule (Step Seven's own table, p. 98) tightens this to 12 (Magic x 2). Total
    # Force 13, split across 4 picks so no single pick's own Availability (Force x 3, capped at 4
    # each) trips first, is comfortably under the general cap (13 < 30) and under the count cap
    # (4 <= 6) but still over the tighter chargen-specific one -- the exact trap the Implementation
    # Plan's WP47 intro warned a general-rule-only reading would miss.
    character = _magician()
    with pytest.raises(ValueError, match=r"exceeds the character-creation cap of 12"):
        create_foci_selection(
            [(CENTERING.id, 4), (CENTERING.id, 4), (CENTERING.id, 4), (CENTERING.id, 1)],
            character,
            FOCI,
            nuyen_budget=10**8,
            karma_budget=10**4,
        )
    # Total Force 12 fits the chargen cap exactly (== Magic x 2).
    selection = create_foci_selection(
        [(CENTERING.id, 4), (CENTERING.id, 4), (CENTERING.id, 4)],
        character,
        FOCI,
        nuyen_budget=10**8,
        karma_budget=10**4,
    )
    assert sum(pick.force for pick in selection.picks) == 12


def test_rejects_availability_exceeding_the_project_cap() -> None:
    # Alchemical Focus: availability_per_force == 3. Force 5 -> Availability 15 > 12.
    character = _magician()
    with pytest.raises(ValueError, match=f"exceeds {MAX_AVAILABILITY}"):
        create_foci_selection(
            [(ALCHEMICAL.id, 5)], character, FOCI, nuyen_budget=10**8, karma_budget=10**4
        )


def test_availability_at_exactly_the_cap_is_allowed() -> None:
    # Force 4 -> Availability 12 == MAX_AVAILABILITY, not over it.
    character = _magician()
    selection = create_foci_selection(
        [(ALCHEMICAL.id, 4)], character, FOCI, nuyen_budget=10**8, karma_budget=10**4
    )
    assert selection.picks[0].force == 4


def test_rejects_nuyen_cost_exceeding_budget() -> None:
    character = _magician()
    with pytest.raises(ValueError, match="nuyen cost .* exceeds the nuyen budget"):
        create_foci_selection(
            [(ALCHEMICAL.id, 1)], character, FOCI, nuyen_budget=100, karma_budget=100
        )


def test_rejects_karma_cost_exceeding_budget() -> None:
    character = _magician()
    with pytest.raises(ValueError, match="Karma cost .* exceeds the Karma budget"):
        create_foci_selection(
            [(ALCHEMICAL.id, 1)], character, FOCI, nuyen_budget=10**6, karma_budget=1
        )


def test_chargen_force_cap_uses_the_multiplier_constant() -> None:
    assert CHARGEN_FORCE_CAP_MULTIPLIER == 2


# -- apply_foci_improvements ----------------------------------------------------------------------


def test_flat_bonus_focus_applies_a_skill_improvement_scaled_to_force() -> None:
    character = _magician()
    selection = create_foci_selection(
        [(ALCHEMICAL.id, 3)], character, FOCI, nuyen_budget=10**6, karma_budget=100
    )
    apply_foci_improvements(character, selection)
    assert character.improvements.resolve(ImprovementType.SKILL, "Alchemy") == 3


def test_no_effect_focus_applies_no_improvement() -> None:
    character = _magician()
    selection = create_foci_selection(
        [(CENTERING.id, 2)], character, FOCI, nuyen_budget=10**6, karma_budget=100
    )
    apply_foci_improvements(character, selection)
    assert character.improvements.improvements == ()


def test_improvements_are_recorded_under_focus_source() -> None:
    character = _magician()
    selection = create_foci_selection(
        [(ALCHEMICAL.id, 2)], character, FOCI, nuyen_budget=10**6, karma_budget=100
    )
    apply_foci_improvements(character, selection)
    (imp,) = character.improvements.improvements
    assert imp.source_type == ImprovementSource.FOCUS
    assert imp.source_id == ALCHEMICAL.id
