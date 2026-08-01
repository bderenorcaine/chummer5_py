"""Regression guard over the on-disk native-save corpus (Phase S / WP85).

`tests/integration/test_save_format_fixtures.py` already round-trips `save_format` by building a
`CharacterSave` in code, writing it, and reading it back. That proves the writer and the reader
agree with *each other* — it cannot catch a change that leaves both self-consistent while breaking
a file an older build already wrote. This module closes that hole with the opposite direction of
test: a real `format_version: 1` file, produced by a player through this project's own web UI and
checked in unmodified, must keep loading and keep computing the same character.

The asserted values are the six headline results `spec/plan/phase-s-test-fixtures.md` §6 states
about this build, chosen because each one is a *different* mechanism's output rather than six
readings of the same number: the Essence floor, an augmentation-driven attribute/Initiative-dice
raise, an Improvement pushing a skill past the chargen maximum, the nuyen ledger's bottom line, and
both Capacity budgets landing exactly full. WP88 authors the full hand-derived `expected`/
`citations` treatment as a `SyntheticCharacter`; this file deliberately stays at "the save format
still reads this file the same way", which is the regression it exists to catch.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from tests.fixtures.native_saves import (
    NATIVE_SAVE_FIXTURES,
    RAZORBOY_SAVE,
    native_save_path,
)

from chummer5.data.bioware import load_bioware
from chummer5.data.cyberware_subsystems import load_cyberware_entries
from chummer5.data.foci import load_foci
from chummer5.data.lifestyle import load_lifestyles
from chummer5.data.mentors import load_mentors
from chummer5.data.metatypes import load_metatypes
from chummer5.data.powers import load_powers
from chummer5.data.priorities import load_priorities
from chummer5.data.qualities import load_qualities
from chummer5.data.skills import load_skills
from chummer5.data.spells import load_spells
from chummer5.data.traditions import load_traditions
from chummer5.engine.character import Character
from chummer5.engine.derived import essence, initiative_dice
from chummer5.engine.skills import MAX_SKILL_RATING_CREATE, skill_rating
from chummer5.io.save_format import CharacterSave, build_character, from_json, to_json

METATYPES = load_metatypes()
PRIORITIES = load_priorities()
SKILLS = load_skills()
QUALITIES = load_qualities()
LIFESTYLES = load_lifestyles()
TRADITIONS = load_traditions()
SPELLS = load_spells()
POWERS = load_powers()
CYBERWARE = load_cyberware_entries()
BIOWARE = load_bioware()
FOCI = load_foci()
MENTORS = load_mentors()

SKILLS_BY_NAME = {s.name: s for s in SKILLS}


def _load(name: str) -> CharacterSave:
    """Read one native save off disk.

    `Path.read_text` raising `FileNotFoundError` is the intended behaviour if the fixture is
    missing -- a loud failure, never a skip. WP85's acceptance criteria call for exactly that: a
    silently-skipped save-format regression test is indistinguishable from a passing one.
    """
    return from_json(native_save_path(name).read_text(encoding="utf-8"))


def _build(save: CharacterSave) -> Character:
    """Rebuild through the same catalogs `chummer5.web.routes.character.load_save` passes, so this
    test exercises the real load path rather than a reduced one that might accept less."""
    return build_character(
        save,
        metatypes=METATYPES,
        priorities=PRIORITIES,
        skills=SKILLS,
        qualities=QUALITIES,
        lifestyles=LIFESTYLES,
        traditions=TRADITIONS,
        spells=SPELLS,
        powers=POWERS,
        cyberware=CYBERWARE,
        bioware=BIOWARE,
        foci=FOCI,
        mentors=MENTORS,
    )


@pytest.mark.parametrize("name", NATIVE_SAVE_FIXTURES)
def test_native_save_still_loads_and_builds(name: str) -> None:
    """Every checked-in native save must still parse and rebuild into a `Character`.

    The broadest possible statement of the regression this corpus guards: a `format_version: 1`
    file written by an earlier build keeps loading. Anything that made this fail would mean the
    format regressed, which WP85's acceptance criteria say to stop and log rather than work around.
    """
    character = _build(_load(name))
    assert character.skill_allocation is not None
    assert character.resources_selection is not None


@pytest.mark.parametrize("name", NATIVE_SAVE_FIXTURES)
def test_native_save_round_trips_through_json(name: str) -> None:
    """`from_json → to_json → from_json` is stable, and the rebuilt characters agree.

    Not `to_json(save) == original_text`: the on-disk file is whatever the UI wrote, and equality
    with it would pin down key *order* and whitespace, which this format has never promised. What
    it does promise is that reading a file loses nothing -- so re-serializing and re-reading yields
    an identical `CharacterSave`, and building either one yields the same Essence/nuyen bottom line.
    """
    save = _load(name)
    reloaded = from_json(to_json(save))
    assert reloaded == save
    assert essence(_build(reloaded)) == essence(_build(save))


def test_razorboy_headline_values() -> None:
    """The six §6 headline results, each a different mechanism's output.

    Hand-derivation for each figure is WP88's job (with citations); what's pinned here is only that
    *this file* keeps producing them, which is what makes it a save-format regression guard rather
    than a second rules test.
    """
    character = _build(_load(RAZORBOY_SAVE))

    # G9: 5.90 of 6.00 spent, the tightest legal margin against `create_cyberware_tree_selection`'s
    # `>= BASE_ESSENCE` reject. Load-bearing downstream, not just a big number -- Social Limit reads
    # `ceil(Essence)`, so 0.10 rounds to 1 rather than 0.
    assert essence(character) == Decimal("0.10")

    # G10: Wired Reflexes 2 raises REA (natural 4 -> augmented 6) and adds Initiative Dice. Both
    # sides are asserted, since a fixture that only checked the augmented total would pass equally
    # well if the bonus had been folded into the natural value.
    assert character.natural_attribute_value("REA") == 4
    assert character.attribute_value("REA") == 6
    assert initiative_dice(character) == 3

    # G13: Stealth group 5 + Catlike's +2 puts Sneaking above the chargen skill maximum -- legal,
    # because the cap bounds what may be *bought*, not what an Improvement may add on top.
    assert character.skill_allocation is not None
    sneaking = skill_rating(character, character.skill_allocation, SKILLS_BY_NAME["Sneaking"])
    assert sneaking == 7
    assert sneaking > MAX_SKILL_RATING_CREATE

    # G12: the spend side balances to ¥580 left of a ¥283,000 pool (¥275,000 from Resources B plus
    # ¥8,000 from converting 4 Karma) across gear, Rating-priced gear, Lifestyle and cyberware.
    assert character.resources_selection is not None
    assert character.resources_selection.nuyen_remaining == 580


def test_razorboy_capacity_budgets_are_exactly_full() -> None:
    """G8: both Rating-3 parents' Capacity comes out exactly full at 12/12 (`Rating * 4`).

    Asserted as `capacity_remaining == 0` *and* the explicit 12/12 split, so the test distinguishes
    "the plugins fit" (which `create_cyberware_tree_selection` already enforces, and which a much
    emptier limb would also satisfy) from "they fill it to the pin" -- the boundary case §6 says
    this build is here to exercise.
    """
    character = _build(_load(RAZORBOY_SAVE))
    assert character.cyberware_selection is not None
    by_name = {p.item.name: p for p in character.cyberware_selection.purchases}

    for parent_name in ("Cyberears", "Cybereyes Basic System"):
        parent = by_name[parent_name]
        assert parent.rating == 3
        assert parent.capacity_budget == Decimal(12)
        assert parent.capacity_spent == Decimal(12)
        assert parent.capacity_remaining == Decimal(0)
