"""Cross-checks `chummer5.engine.magic` against the corpus's 2 real magic-capable, `buildmethod ==
Priority` fixtures — Miko (Elf Magician) and Wesson (Human Adept). See `tests/fixtures
/mundane_chum5.py`'s `MAGIC_PRIORITY_BUILD_FIXTURES` and the Implementation Plan's Phase I intro for
why these are the only 2 in the 34-file corpus, and `spec/worklogs/WP25.md` for the full research
this was checked against — including a correction to the Implementation Plan's own claim that
Wesson's Talent letter (Adept, C) "grants no free skill at all": it does, confirmed both against
`priorities.xml` directly and against Wesson's own `<priorityskills>` free-skill-name record.

Neither fixture's own tradition (Miko: Shinto, `SG`; Wesson: Christian Theurgy, `FA`) is one of the
2 SR5-sourced traditions this phase offers (Hermetic/Shamanic) — expected and unrelated to what
these tests check (Magic rating + free-skill-grant mechanism), not a gap; see the phase intro for
why tradition-specific mechanics are hand-verified against Hermetic/Shamanic directly instead.

**WP26's spell test reads Miko's `<spells>` block with a bare `xml.etree.ElementTree` read**, not
via `chummer5.io.legacy_chum5` — that module has never parsed spells at all until WP28, which adds
a real `LegacyCharacter.spells` field (see the end-to-end import tests at the bottom of this file).

**WP28** adds `drain_resistance`/magic-aware save-load coverage, plus the real end-to-end import
attempts this phase's engine work made possible for both real fixtures -- neither actually
succeeds, but each is rejected for a specific, itemized, honest reason instead of a blanket "Magic
is enabled" one: Miko (Magician) for her own non-SR5 tradition (Shinto) -- see `tests/integration
/test_legacy_import_fixtures.py::test_rejects_miko_for_her_own_unresolvable_tradition`; Wesson
(Adept, needing no tradition at all) for an unrelated, previously-latent gap this WP's own research
found -- a Karma-bought attribute point beyond his priority budget, which this engine has never
modeled -- see `test_wesson_also_blocked_for_an_unrelated_karma_bought_attribute_point` below and
`spec/worklogs/WP28.md` for the full research, including why this corrects the Implementation
Plan's own more optimistic "Wesson imports end to end" acceptance text.
`test_wesson_adept_magic_and_drain_via_direct_engine_construction` below proves WP28's actual
deliverables (Drain Resistance, save/load round-trip) against Wesson's real data anyway, composing
the same engine functions `import_legacy_character` would have, independent of that import gap.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import replace
from decimal import Decimal

import pytest
from tests.fixtures.mundane_chum5 import mundane_fixture_path

from chummer5.data.lifestyle import load_lifestyles
from chummer5.data.metatypes import load_metatypes
from chummer5.data.powers import BonusSupport as PowerBonusSupport
from chummer5.data.powers import load_powers
from chummer5.data.priorities import load_priorities
from chummer5.data.qualities import load_qualities
from chummer5.data.skills import load_skills
from chummer5.data.spells import load_spells
from chummer5.data.traditions import load_traditions
from chummer5.engine.character import ALLOCATABLE_ATTRIBUTES, create_character, metatype_choices
from chummer5.engine.derived import drain_resistance
from chummer5.engine.magic import (
    apply_magic_skill_grant_improvements,
    create_magic_selection,
    create_power_selection,
    create_spell_selection,
)
from chummer5.io.legacy_chum5 import load_chum5, priority_letter
from chummer5.io.legacy_import import UnsupportedLegacyCharacterError, import_chum5
from chummer5.io.save_format import build_character, create_character_save

METATYPES = load_metatypes()
PRIORITIES = load_priorities()
TRADITIONS = load_traditions()
SKILLS = load_skills()
QUALITIES = load_qualities()
LIFESTYLES = load_lifestyles()
SPELLS = load_spells()
POWERS = load_powers()
HERMETIC_ID = next(t.id for t in TRADITIONS if t.name == "Hermetic")

_SKILL_ID_BY_NAME = {s.name: s.id for s in SKILLS}


def test_miko_magician_magic_rating_and_free_skill_grant() -> None:
    legacy = load_chum5(mundane_fixture_path("Miko.chum5"))
    assert legacy.build_method == "Priority"
    assert legacy.metatype == "Elf"
    assert legacy.priorities.talent_codename == "Magician"

    talent_letter = priority_letter(legacy.priorities.talent)
    assert talent_letter == "A"

    granted_ids = [_SKILL_ID_BY_NAME[name] for name in legacy.priorities.talent_bonus_skills]
    assert set(legacy.priorities.talent_bonus_skills) == {"Counterspelling", "Spellcasting"}

    selection = create_magic_selection(
        talent_letter, "Magician", HERMETIC_ID, granted_ids, PRIORITIES, TRADITIONS, SKILLS
    )

    assert selection.magic_type == "Magician"
    assert selection.magic_rating == legacy.attributes["MAG"].total_value == 6
    assert selection.granted_skill_rating == 5
    assert set(selection.granted_skill_ids) == set(granted_ids)


def test_wesson_adept_magic_rating_and_free_skill_grant() -> None:
    legacy = load_chum5(mundane_fixture_path("Wesson.chum5"))
    assert legacy.build_method == "Priority"
    assert legacy.metatype == "Human"
    assert legacy.priorities.talent_codename == "Adept"

    talent_letter = priority_letter(legacy.priorities.talent)
    assert talent_letter == "C"

    # This is the fact the Implementation Plan's Phase I/WP25 text got wrong: it claims "Wesson's
    # Talent letter, C, grants no free skill at all" (only Adept letter B does). Wesson's own save
    # data says otherwise.
    assert legacy.priorities.talent_bonus_skills == ("Pistols",)
    granted_ids = [_SKILL_ID_BY_NAME["Pistols"]]

    selection = create_magic_selection(
        talent_letter, "Adept", None, granted_ids, PRIORITIES, TRADITIONS, SKILLS
    )

    assert selection.magic_type == "Adept"
    assert selection.magic_rating == legacy.attributes["MAG"].total_value == 4
    assert selection.tradition is None
    assert selection.granted_skill_ids == tuple(granted_ids)
    assert selection.granted_skill_rating == 2


def test_miko_spell_selection_resolves_her_sr5_spells_and_flags_the_rest() -> None:
    # Miko's letter-A Magician option grants a 10-spell budget (matches "6 Magic/10 Spells" in
    # priorities.xml); her own <spells> block has exactly 10 entries, but only 6 are SR5-sourced --
    # the other 4 are Shinto (SG)-sourced, the same non-core-tradition situation her own <tradition>
    # choice is in (see module docstring). This engine's spell catalog is SR5-scoped only (WP26), so
    # only the 6 can resolve -- asserted explicitly here, not silently dropped.
    root = ET.parse(mundane_fixture_path("Miko.chum5")).getroot()
    spells_elem = root.find(".//spells")
    assert spells_elem is not None
    raw_spells = [
        (s.findtext("name", ""), s.findtext("source", "")) for s in spells_elem.findall("spell")
    ]
    assert len(raw_spells) == 10

    sr5_names = {name for name, source in raw_spells if source == "SR5"}
    non_sr5_names = {name for name, source in raw_spells if source != "SR5"}
    assert sr5_names == {
        "Manabolt",
        "Stunbolt",
        "Clout",
        "Improved Invisibility",
        "Cure Disease",
        "Heal",
    }
    assert non_sr5_names == {"Calm Animal", "Animal Sense", "Mindnet Extended", "Fashion"}

    catalog_names = {s.name for s in SPELLS}
    assert sr5_names <= catalog_names
    assert non_sr5_names.isdisjoint(catalog_names)

    miko = load_chum5(mundane_fixture_path("Miko.chum5"))
    talent_letter = priority_letter(miko.priorities.talent)
    magician_option = next(
        o for o in PRIORITIES.talent[talent_letter].options if o.codename == "Magician"
    )
    assert magician_option.spells == 10

    spell_ids = [next(s.id for s in SPELLS if s.name == name) for name in sr5_names]
    selection = create_spell_selection(spell_ids, SPELLS, budget=magician_option.spells)
    assert {s.name for s in selection.spells} == sr5_names


def test_wesson_adept_powers_hand_verified_against_the_raw_fixture_and_catalog() -> None:
    """Wesson's own `<powers>` block has 6 real entries. Only 4 are `source == "SR5"` (Motion Sense
    and Rapid Draw are both `SG`-sourced, like his own tradition -- see this module's docstring for
    the same non-core-content situation) -- so, contrary to the Implementation Plan's WP27
    acceptance text ("his 6 real powers resolve against the catalog"), only 4 of 6 do; the other 2
    don't resolve at all. This is the same "aspirational plan text corrected by this WP's own
    research" pattern WP25/WP26 already established for Wesson's free-skill grant and Miko's spell
    catalog respectively.

    Of those 4 SR5-sourced powers, **all 4** turn out NOT_YET_SUPPORTED under this WP's classifier
    -- Attribute Boost (the documented trap, see `chummer5.data.powers`'s module docstring), Combat
    Sense (a `dodge` bonus, combat-only), Enhanced Accuracy (skill) (weapon accuracy, combat-only),
    and Improved Ability (skill) (deliberately deferred). This is a stronger, more honest finding
    than the plan's own acceptance text anticipated ("two powers this WP cannot fully support") --
    it's actually all of them, asserted explicitly here rather than glossed over, mirroring WP8/
    WP22's "excluded... rather than skipped quietly" acceptance pattern.

    The Power Point *budget* math still checks out exactly, using every one of his 6 real powers'
    raw points/levels/rating (hand-read from the fixture, cross-checked against the source catalog
    for the 4 that resolve): 0.25 (Attribute Boost, 0.25/level x rating 1) + 2.0 (Combat Sense,
    0.5/level x rating 4) + 0.25 (Enhanced Accuracy (skill), levels=False) + 0.5 (Improved Ability
    (skill), 0.5/level x rating 1) + 0.5 (Motion Sense, levels=False) + 0.5 (Rapid Draw,
    levels=False) = 4.0, exactly his MAG-4 Power Point budget.
    """
    root = ET.parse(mundane_fixture_path("Wesson.chum5")).getroot()
    powers_elem = root.find(".//powers")
    assert powers_elem is not None
    raw_powers = [
        (
            p.findtext("name", ""),
            int(p.findtext("rating", "1")),
            p.findtext("levels", "False") == "True",
        )
        for p in powers_elem.findall("power")
    ]
    assert {name for name, _, _ in raw_powers} == {
        "Attribute Boost",
        "Combat Sense",
        "Enhanced Accuracy (skill)",
        "Improved Ability (skill)",
        "Motion Sense",
        "Rapid Draw",
    }

    catalog_names = {p.name for p in POWERS}
    sr5_names = {name for name, _, _ in raw_powers if name in catalog_names}
    non_sr5_names = {name for name, _, _ in raw_powers if name not in catalog_names}
    assert sr5_names == {
        "Attribute Boost",
        "Combat Sense",
        "Enhanced Accuracy (skill)",
        "Improved Ability (skill)",
    }
    assert non_sr5_names == {"Motion Sense", "Rapid Draw"}

    for name in sr5_names:
        power = next(p for p in POWERS if p.name == name)
        assert power.bonus_support == PowerBonusSupport.NOT_YET_SUPPORTED

    # Hand-verified PP-budget cross-check using every real power's raw points/levels/rating --
    # Motion Sense/Rapid Draw's own <points> (0.5 each, levels=False) are read directly from
    # legacy/Chummer/data/powers.xml (SG-sourced, so absent from the SR5-scoped POWERS catalog).
    points_by_name = {p.name: p.points for p in POWERS}
    points_by_name["Motion Sense"] = Decimal("0.5")
    points_by_name["Rapid Draw"] = Decimal("0.5")
    total_pp = sum(
        (points_by_name[name] * rating if levels else points_by_name[name])
        for name, rating, levels in raw_powers
    )
    assert total_pp == Decimal("4.0")

    wesson = load_chum5(mundane_fixture_path("Wesson.chum5"))
    assert wesson.attributes["MAG"].total_value == 4


def test_wesson_also_blocked_for_an_unrelated_karma_bought_attribute_point() -> None:
    """A real, previously-latent gap this WP's own Wesson research surfaced -- unrelated to magic
    at all. Wesson's tradition needs no resolution (he's an Adept), so he was expected to be this
    phase's real "imports end to end" success case per the Implementation Plan's own WP28
    acceptance text. He is not: his real `<attributes><attribute name="EDG">` carries `<base>1</
    base><karma>1</karma>` against Heritage E's 1-point special-attribute-points budget for Human --
    i.e. he spent 1 Karma-bought EDG point *beyond* his priority budget, a real, valid, standard SR5
    chargen rule (a Karma-for-attribute-points purchase) this engine's `create_character` has never
    modeled at all (it only validates priority-derived points against the priority budget). This
    was always true of `import_legacy_character`'s pre-existing `base + karma` attribute-points
    formula (written in WP12, long before this phase existed) -- it just never actually executed
    with a nonzero `karma` value before, since Yeti (the only Priority-built fixture among the
    curated mundane 11) happens to have `karma == 0` on every allocatable attribute. Fixed by
    rejecting any nonzero-karma allocatable attribute as a new, itemized blocking reason (mirroring
    cyberware/metavariant's existing treatment) rather than silently mis-validating or
    under-reporting EDG by 1 -- see `spec/worklogs/WP28.md` for the full research and the "neither
    of Phase I's 2 real fixtures can achieve a full round-trip import" finding this test and
    `tests/integration/test_legacy_import_fixtures.py::test_rejects_miko_for_her_own_unresolvable_
    tradition` establish together.
    """
    legacy = load_chum5(mundane_fixture_path("Wesson.chum5"))
    assert legacy.attributes["EDG"].base == 1
    assert legacy.attributes["EDG"].karma == 1

    with pytest.raises(UnsupportedLegacyCharacterError) as exc_info:
        import_chum5(
            mundane_fixture_path("Wesson.chum5"),
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
        "character has Karma-bought attribute points beyond the priority budget on EDG; MVP's "
        "engine only models priority-derived attribute points, not chargen-time Karma spend on "
        "attributes",
    )


def test_wesson_adept_magic_and_drain_via_direct_engine_construction() -> None:
    """Since `import_chum5` can't reach a successful build for Wesson (see the rejection test
    above), this proves WP28's own actual deliverables -- Adept Drain Resistance, `power_points`,
    the free-skill grant, dropped-power reporting -- directly, composing the same engine functions
    `import_legacy_character` would have called, using Wesson's real data by hand. Mirrors this
    file's own established "verify by hand where the fixture can't reach" precedent (WP26's spell
    test, WP27's power-budget test) one level up, at the whole-`Character` scope.
    """
    legacy = load_chum5(mundane_fixture_path("Wesson.chum5"))
    heritage_letter = priority_letter(legacy.priorities.heritage)
    attributes_letter = priority_letter(legacy.priorities.attributes)
    heritage = PRIORITIES.heritage[heritage_letter]
    human_choice = next(
        c for c in metatype_choices(heritage, METATYPES) if c.metatype.name == "Human"
    )
    # `.base` only -- see the rejection test above for why `.karma` is never added in this engine.
    attribute_points = {
        code: legacy.attributes[code].base
        for code in ALLOCATABLE_ATTRIBUTES
        if code in legacy.attributes
    }
    character = create_character(
        metatype_choice=human_choice,
        heritage_letter=heritage_letter,
        attributes_letter=attributes_letter,
        priorities=PRIORITIES,
        attribute_points=attribute_points,
    )

    talent_letter = priority_letter(legacy.priorities.talent)
    assert talent_letter == "C"
    granted_ids = [_SKILL_ID_BY_NAME["Pistols"]]
    selection = create_magic_selection(
        talent_letter, "Adept", None, granted_ids, PRIORITIES, TRADITIONS, SKILLS
    )
    character = replace(
        character,
        magic_type=selection.magic_type,
        magic_rating=selection.magic_rating,
        tradition=selection.tradition,
        magic_granted_skill_ids=selection.granted_skill_ids,
    )
    apply_magic_skill_grant_improvements(character, selection, SKILLS)

    assert character.magic_type == "Adept"
    assert character.magic_rating == 4
    assert character.tradition is None
    assert character.power_points == 4
    assert drain_resistance(character) == character.attribute_value(
        "BOD"
    ) + character.attribute_value("WIL")

    # All 6 of Wesson's real powers are unrepresentable in this WP's offered catalog -- see
    # test_wesson_adept_powers_hand_verified_against_the_raw_fixture_and_catalog above for the full
    # per-power accounting (2 non-SR5, 4 SR5-sourced but NOT_YET_SUPPORTED).
    power_selection = create_power_selection((), POWERS, power_point_budget=character.power_points)
    assert power_selection.picks == ()

    # Native save/load round-trips this hand-built magic character exactly (WP28's own "magic-aware
    # save/load" deliverable, demonstrated independently of the legacy-import gap above).
    save = create_character_save(
        metatype_name="Human",
        heritage_letter=heritage_letter,
        attributes_letter=attributes_letter,
        attribute_points=attribute_points,
        skills_letter="B",
        skill_points={},
        group_points={},
        quality_ids=(),
        contacts=(),
        resources_letter="D",
        gear_names=(),
        lifestyle_tier_name="Medium",
        lifestyle_months=1,
        talent_letter=talent_letter,
        talent_codename="Adept",
        granted_skill_ids=tuple(granted_ids),
        spell_ids=(),
        power_picks=(),
    )
    reloaded = build_character(
        save,
        metatypes=METATYPES,
        priorities=PRIORITIES,
        skills=SKILLS,
        qualities=QUALITIES,
        lifestyles=LIFESTYLES,
        traditions=TRADITIONS,
        spells=SPELLS,
        powers=POWERS,
    )
    assert reloaded.magic_type == "Adept"
    assert reloaded.magic_rating == 4
    assert reloaded.tradition is None
    assert reloaded.magic_granted_skill_ids == tuple(granted_ids)
    assert reloaded.power_selection is not None
    assert reloaded.power_selection.picks == ()
    assert reloaded.spell_selection is not None
    assert reloaded.spell_selection.spells == ()
    assert drain_resistance(reloaded) == drain_resistance(character)
