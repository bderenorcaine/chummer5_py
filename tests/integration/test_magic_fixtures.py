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
via `chummer5.io.legacy_chum5` — that module has never parsed spells at all (WP28 is where a real
`LegacyCharacter.spells` field is added, per the Implementation Plan's Phase I intro), and adding
one early here would preempt that WP's own scope. Mirrors `tests/integration/test_legacy_chum5.py`'s
own "independently cross-checked against the raw XML" precedent.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from decimal import Decimal

from tests.fixtures.mundane_chum5 import mundane_fixture_path

from chummer5.data.powers import BonusSupport as PowerBonusSupport
from chummer5.data.powers import load_powers
from chummer5.data.priorities import load_priorities
from chummer5.data.skills import load_skills
from chummer5.data.spells import load_spells
from chummer5.data.traditions import load_traditions
from chummer5.engine.magic import create_magic_selection, create_spell_selection
from chummer5.io.legacy_chum5 import load_chum5, priority_letter

PRIORITIES = load_priorities()
TRADITIONS = load_traditions()
SKILLS = load_skills()
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
