"""Cross-checks `chummer5.io.legacy_import` against the legacy `.chum5` corpus: the acceptance bar
from the Implementation Plan's WP12 entry, verbatim -- "successfully imports Yeti-#ffffff2.chum5;
imports of saves with out-of-scope content (magic, cyberware, etc.) fail with a specific, itemized
error rather than silently dropping data."

`Yeti-#ffffff2.chum5` is the only fixture in the curated 11-fixture mundane corpus that can even
reach the import path (it's the corpus's sole `buildmethod == Priority` fixture -- every other
mundane fixture is `SumtoTen`-built and is rejected on that basis alone, tested below via
`Barrett.chum5`). The "magic content fails" side is demonstrated with `Miko.chum5`, a *non*-mundane
(`magenabled == True`) fixture from the wider 34-file corpus, picked specifically because it's
Priority-built and otherwise clean (Standard gameplay option, no cyberware, no metavariant) -- so it
exercises exactly one blocking reason rather than several at once. See `spec/worklogs/WP12.md`.
"""

from __future__ import annotations

import pytest
from tests.fixtures.mundane_chum5 import (
    LEGACY_TESTFILES_DIR,
    PRIORITY_BUILD_FIXTURE,
    mundane_fixture_path,
)

from chummer5.data.metatypes import load_metatypes
from chummer5.data.priorities import load_priorities
from chummer5.data.qualities import load_qualities
from chummer5.data.skills import load_skills
from chummer5.engine.character import ALLOCATABLE_ATTRIBUTES
from chummer5.io.legacy_chum5 import load_chum5
from chummer5.io.legacy_import import UnsupportedLegacyCharacterError, import_chum5

METATYPES = load_metatypes()
PRIORITIES = load_priorities()
SKILLS = load_skills()
QUALITIES = load_qualities()


def test_imports_yeti_end_to_end() -> None:
    """The WP12 headline acceptance case: Yeti's own recorded attribute totals, skill rating, and
    contact/resource budgets must match what the import path reconstructs -- the same values
    WP6/WP7/WP9/WP10's fixture tests already independently confirmed by hand-assembling the same
    build from `LegacyCharacter` fields; this test proves `import_chum5` reproduces it through the
    real import path instead.
    """
    legacy = load_chum5(mundane_fixture_path(PRIORITY_BUILD_FIXTURE))
    result = import_chum5(
        mundane_fixture_path(PRIORITY_BUILD_FIXTURE),
        metatypes=METATYPES,
        priorities=PRIORITIES,
        skills=SKILLS,
        qualities=QUALITIES,
    )

    character = result.built
    for code in ALLOCATABLE_ATTRIBUTES:
        assert character.attribute_value(code) == legacy.attributes[code].total_value, code

    # Yeti's own real quality list (Technomancer, Infirm, Impassive, Paranoia, Faceless, Data
    # Anomaly -- see spec/worklogs/WP9.md) has zero overlap with WP8's 3 MVP-offered qualities, so
    # every one of them is excluded and reported, none silently vanish with no trace.
    assert set(result.dropped_qualities) == {
        "Technomancer",
        "Infirm",
        "Impassive",
        "Paranoia",
        "Faceless",
        "Data Anomaly",
    }
    assert result.save.quality_ids == ()

    # Skills: the Firearms group was bought, so Automatics (a Firearms-group skill) picks up the
    # group rating -- same cross-check WP7's fixture test makes directly against `SkillAllocation`.
    automatics_id = next(s.id for s in SKILLS if s.name == "Automatics")
    bought_groups = {g.name: g.base for g in legacy.skill_groups if g.base > 0}
    assert automatics_id not in result.save.skill_points  # rating comes from the group, not itself
    assert result.save.group_points.get("Firearms") == bought_groups["Firearms"]

    # Contacts and starting resources.
    assert len(result.save.contacts) == 2
    assert result.built.contact_selection.points_spent == 15
    assert result.built.contact_selection.karma_cost == 0
    assert result.built.resources_selection.nuyen_budget == legacy.starting_nuyen


def test_rejects_sumtoten_mundane_fixture() -> None:
    """Every mundane fixture except Yeti is SumToTen-built -- out of MVP's priority-chargen scope
    (see the Implementation Plan's corpus note), so the import path must reject it, not silently
    guess at a priority-letter budget the file never really encodes (WP4 found the `<priority*>`
    fields are mostly empty for SumToTen saves).
    """
    with pytest.raises(UnsupportedLegacyCharacterError, match="not Priority-built"):
        import_chum5(
            mundane_fixture_path("Barrett.chum5"),
            metatypes=METATYPES,
            priorities=PRIORITIES,
            skills=SKILLS,
            qualities=QUALITIES,
        )


def test_rejects_magic_enabled_priority_character() -> None:
    """`Miko.chum5` (outside the mundane 11, from the wider legacy corpus) is Priority-built,
    Standard, cyberware-free, and non-metavariant -- clean on every axis except Magic, so this
    isolates the "Magic is enabled" rejection reason specifically, against a real save file rather
    than only a synthetic one (see `tests/unit/test_legacy_import.py` for the synthetic coverage of
    every other blocking reason and their combinations).
    """
    with pytest.raises(UnsupportedLegacyCharacterError) as exc_info:
        import_chum5(
            LEGACY_TESTFILES_DIR / "Miko.chum5",
            metatypes=METATYPES,
            priorities=PRIORITIES,
            skills=SKILLS,
            qualities=QUALITIES,
        )
    assert exc_info.value.reasons == ("Magic is enabled; MVP does not support magic chargen",)
