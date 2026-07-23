"""Cross-checks `chummer5.io.legacy_import` against the legacy `.chum5` corpus: the acceptance bar
from the Implementation Plan's WP12 entry, verbatim -- "successfully imports Yeti-#ffffff2.chum5;
imports of saves with out-of-scope content (magic, cyberware, etc.) fail with a specific, itemized
error rather than silently dropping data."

`Yeti-#ffffff2.chum5` is the only fixture in the curated 11-fixture mundane corpus that's
`buildmethod == Priority` -- every other mundane fixture is `SumtoTen`-built, tested below via
`Barrett.chum5`. The "magic content fails" side is demonstrated with `Miko.chum5`, a *non*-mundane
(`magenabled == True`) fixture from the wider 34-file corpus, picked specifically because it's
Priority-built and otherwise clean (Standard gameplay option, no cyberware, no metavariant) -- so it
exercises exactly one blocking reason rather than several at once. See `spec/worklogs/WP12.md`.

**WP28 update**: Miko still fails to import (see `test_rejects_miko_for_her_own_unresolvable_
tradition` below) -- but no longer for a blanket "Magic is enabled" reason, since real Magician/
Adept import support now exists. Her own real gap (a non-SR5 tradition) just happens to be a
different blocking reason. `Wesson.chum5` (an Adept, needing no tradition) is this phase's real
magic-import success case -- see `tests/integration/test_magic_fixtures.py`.

**WP44 update**: `SumtoTen` is no longer rejected on build-method grounds alone (see
`chummer5.io.legacy_import`'s own docstring) -- `Barrett.chum5` (below) is still rejected, but now
for two *other* real reasons this widening newly makes reachable: a missing Skills priority letter
(a genuine Mundane-Talent-`SumtoTen` save-format gap, see `spec/rulebooks/learnings.md`'s WP44
entry) and her own real cyberware/Bioware content (WP33's itemized checks).
"""

from __future__ import annotations

import pytest
from tests.fixtures.mundane_chum5 import (
    LEGACY_TESTFILES_DIR,
    PRIORITY_BUILD_FIXTURE,
    mundane_fixture_path,
)

from chummer5.data.lifestyle import load_lifestyles
from chummer5.data.metatypes import load_metatypes
from chummer5.data.powers import load_powers
from chummer5.data.priorities import load_priorities
from chummer5.data.qualities import load_qualities
from chummer5.data.skills import load_skills
from chummer5.data.spells import load_spells
from chummer5.data.traditions import load_traditions
from chummer5.engine.character import ALLOCATABLE_ATTRIBUTES
from chummer5.io.legacy_chum5 import load_chum5
from chummer5.io.legacy_import import UnsupportedLegacyCharacterError, import_chum5

METATYPES = load_metatypes()
PRIORITIES = load_priorities()
SKILLS = load_skills()
QUALITIES = load_qualities()
LIFESTYLES = load_lifestyles()
TRADITIONS = load_traditions()
SPELLS = load_spells()
POWERS = load_powers()


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
        lifestyles=LIFESTYLES,
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

    # Specializations (WP50): Yeti's own recorded 6 <specs> entries -- 5 individually-purchased
    # skills import cleanly, and Computer's own "Matrix Perception" is dropped (her Computer skill
    # is karma-only, base<=0, so it never reaches skill_points -- see chummer5.io.legacy_import's
    # own module docstring). Adding 5 specialization points to her existing 23 individual skill
    # points exactly fills her 28-point Skills-C budget.
    skills_by_name = {s.name: s for s in SKILLS}
    assert {
        skills_by_name["Compiling"].id: "Machine Sprite",
        skills_by_name["Cybercombat"].id: "Sprites",
        skills_by_name["Hacking"].id: "Hosts",
        skills_by_name["Registering"].id: "Machine Sprite",
        skills_by_name["Software"].id: "Puppeteer",
    }.items() <= result.save.specializations.items()
    assert len(result.save.specializations) == 5
    assert result.dropped_specializations == ("Computer: Matrix Perception",)
    assert result.built.skill_allocation is not None
    assert (
        sum(result.built.skill_allocation.skill_points.values())
        + len(result.built.skill_allocation.specializations)
        == 28
    )

    # Contacts and starting resources.
    assert len(result.save.contacts) == 2
    assert result.built.contact_selection.points_spent == 15
    assert result.built.contact_selection.karma_cost == 0
    assert result.built.resources_selection.nuyen_budget == legacy.starting_nuyen

    # Lifestyle (WP20): Yeti's own recorded primary Lifestyle -- Low, 1 month.
    assert len(legacy.lifestyles) == 1
    assert legacy.lifestyles[0].base_lifestyle == "Low"
    assert result.built.lifestyle_selection is not None
    assert result.built.lifestyle_selection.tier.name == "Low"
    assert result.built.lifestyle_selection.months == 1
    assert result.built.lifestyle_selection.total_cost == 2000

    # Knowledge/Language (WP49): Yeti's own recorded <knoskills> -- 4 real entries once "English"
    # (base 0, no native marker in this pre-5.212.72 fixture -- see spec/rulebooks/learnings.md's
    # WP49 entry) is excluded by the ordinary base<=0 skip. INT 5 + LOG 6 gives a 22-point budget,
    # spent in full: Matrix (Professional, 4) + Host Design/Host Networking/Japanese (Language, 6
    # each) = 22.
    knowledge_selection = result.built.knowledge_selection
    assert knowledge_selection is not None
    assert knowledge_selection.free_points == 22
    assert knowledge_selection.points_spent == 22
    assert {k.name: k.rating for k in knowledge_selection.knowledge_skills} == {"Matrix": 4}
    assert {la.name: la.rating for la in knowledge_selection.languages} == {
        "Host Design": 6,
        "Host Networking": 6,
        "Japanese": 6,
    }
    assert all(not la.native for la in knowledge_selection.languages)


def test_rejects_sumtoten_mundane_fixture() -> None:
    """Barrett is `SumtoTen`-built, which WP44 accepts on its own -- but she's still rejected, for
    two real reasons WP44's widening newly makes reachable: her Skills priority letter is blank (a
    genuine Mundane-Talent-`SumtoTen` save-format gap -- see `spec/rulebooks/learnings.md`'s WP44
    entry) and she carries real cyberware/Bioware content WP31/33's catalog can't represent.
    """
    with pytest.raises(UnsupportedLegacyCharacterError) as exc_info:
        import_chum5(
            mundane_fixture_path("Barrett.chum5"),
            metatypes=METATYPES,
            priorities=PRIORITIES,
            skills=SKILLS,
            qualities=QUALITIES,
            lifestyles=LIFESTYLES,
        )
    reasons = exc_info.value.reasons
    assert any("no priority letter recorded for Skills" in r for r in reasons)
    assert any("is Bioware" in r or "out of scope" in r for r in reasons)


def test_rejects_miko_for_her_own_unresolvable_tradition() -> None:
    """`Miko.chum5` (outside the mundane 11, from the wider legacy corpus) is Priority-built,
    Standard, cyberware-free, and non-metavariant -- clean on every axis WP12 already checked.
    Before WP28, she hit a blanket "Magic is enabled" rejection; after WP28 she is **still
    rejected**, but for a real, more specific reason this WP's own research found: her tradition,
    Shinto, is `SG`-sourced, not one of the 2 SR5-core traditions (Hermetic/Shamanic) this project
    offers -- and there is no sensible "import without a tradition" fallback for a Magician (see
    `chummer5.io.legacy_import`'s module docstring). This corrects the Implementation Plan's own
    WP28 acceptance text, which expected Miko to import end to end -- see `spec/worklogs/WP28.md`
    for the full research. `Wesson.chum5` (an Adept, needing no tradition at all) was hoped to be
    this phase's real success case instead, but WP52's own research found he *also* can't reach a
    full end-to-end import (an unrelated Karma-budget gap, not a magic-scoping one) -- see
    `tests/integration/test_magic_fixtures.py`'s
    `test_wesson_still_blocked_after_wp52_by_the_excluded_sinner_qualitys_lost_karma_credit` and
    `test_wesson_karma_funded_edg_increase_via_direct_engine_construction` for the full detail and
    for WP52's actual deliverable proven directly against his real numbers instead.
    """
    legacy = load_chum5(LEGACY_TESTFILES_DIR / "Miko.chum5")
    assert legacy.tradition_name == "Shinto"

    with pytest.raises(UnsupportedLegacyCharacterError) as exc_info:
        import_chum5(
            LEGACY_TESTFILES_DIR / "Miko.chum5",
            metatypes=METATYPES,
            priorities=PRIORITIES,
            skills=SKILLS,
            qualities=QUALITIES,
            lifestyles=LIFESTYLES,
            traditions=TRADITIONS,
            spells=SPELLS,
            powers=POWERS,
        )
    assert exc_info.value.reasons == (
        "tradition 'Shinto' is not one of the SR5-core traditions MVP offers (Hermetic, Shamanic)",
    )
