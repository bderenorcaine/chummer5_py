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
"""

from __future__ import annotations

from tests.fixtures.mundane_chum5 import mundane_fixture_path

from chummer5.data.priorities import load_priorities
from chummer5.data.skills import load_skills
from chummer5.data.traditions import load_traditions
from chummer5.engine.magic import create_magic_selection
from chummer5.io.legacy_chum5 import load_chum5, priority_letter

PRIORITIES = load_priorities()
TRADITIONS = load_traditions()
SKILLS = load_skills()
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
