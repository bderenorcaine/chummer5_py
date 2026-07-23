"""WP49: Knowledge/Language skill selection cross-checked against real `.chum5` corpus data.

`Yeti-#ffffff2.chum5` (the corpus's sole mundane `buildmethod == Priority` fixture) gets full
`import_chum5()` coverage in `tests/integration/test_legacy_import_fixtures.py` -- it's the only
fixture whose knowledge/language data round-trips through the real import path end to end. Miko
(Elf Magician) and Wesson (Human Adept), Phase I's own two real magic fixtures, both fail
`import_legacy_character` for reasons unrelated to Knowledge/Language (Miko: her non-SR5 tradition;
Wesson: a karma-bought EDG point -- see `spec/worklogs/WP28.md`), so their own Knowledge/Language
data is cross-checked directly here instead, the same "read the raw fixture, build a `Character` by
hand, verify the formula" pattern WP26/WP29 already established for spells/Magic rating.
"""

from __future__ import annotations

from tests.fixtures.mundane_chum5 import mundane_fixture_path

from chummer5.data.knowledge import KNOWLEDGE_CATEGORY_NAMES
from chummer5.data.metatypes import load_metatypes
from chummer5.data.priorities import load_priorities
from chummer5.engine.character import create_character, metatype_choices, sr5_metatypes
from chummer5.engine.knowledge import (
    KnowledgeSkillPick,
    LanguageSkillPick,
    create_knowledge_selection,
)
from chummer5.io.legacy_chum5 import load_chum5, priority_letter

METATYPES = load_metatypes()
PRIORITIES = load_priorities()


def _character_from_legacy_attributes(legacy):  # type: ignore[no-untyped-def]
    heritage_letter = priority_letter(legacy.priorities.heritage)
    attributes_letter = priority_letter(legacy.priorities.attributes)
    heritage = PRIORITIES.heritage[heritage_letter]
    choice = next(
        c for c in metatype_choices(heritage, METATYPES) if c.metatype.name == legacy.metatype
    )
    attribute_points = {
        code: legacy.attributes[code].base
        for code in ("BOD", "AGI", "REA", "STR", "CHA", "INT", "LOG", "WIL", "EDG")
        if code in legacy.attributes
    }
    return create_character(
        choice, heritage_letter, attributes_letter, PRIORITIES, attribute_points
    )


def _picks_from_legacy(legacy):  # type: ignore[no-untyped-def]
    knowledge_skills = []
    languages = []
    for entry in legacy.knowledge_skills:
        if entry.base <= 0:
            continue
        if entry.category in KNOWLEDGE_CATEGORY_NAMES:
            knowledge_skills.append(
                KnowledgeSkillPick(name=entry.name, category=entry.category, rating=entry.base)
            )
        else:
            languages.append(
                LanguageSkillPick(name=entry.name, rating=entry.base, native=entry.native)
            )
    return tuple(knowledge_skills), tuple(languages)


def test_sr5_metatypes_resolve_for_both_magic_fixtures() -> None:
    # Sanity check on the test helper itself: both Miko (Elf) and Wesson (Human) resolve against
    # the SR5-core metatype catalog under their own recorded Heritage letter.
    for name in ("Miko.chum5", "Wesson.chum5"):
        legacy = load_chum5(mundane_fixture_path(name))
        assert legacy.metatype in {m.name for m in sr5_metatypes(METATYPES)}


def test_miko_knowledge_selection_matches_her_recorded_int_log_budget() -> None:
    # Miko: INT 4 + LOG 3 -> 14-point budget (see spec/rulebooks/learnings.md's WP49 entry). Her
    # own <knoskills> spend 13 of it (Fashion 3 + Area Knowledge: Neo-Tokyo 2 + Japanese 1 +
    # Classical Music 2 + Magical Theory (Academic) 2 + English 3 = 13) -- one point short of full,
    # legal under this project's "doesn't require full spend" precedent. Neither Japanese nor
    # English is marked native (her file predates <isnativelanguage>, see LegacyKnowledgeSkill's
    # own docstring), so both are ordinary paid Language entries here.
    legacy = load_chum5(mundane_fixture_path("Miko.chum5"))
    character = _character_from_legacy_attributes(legacy)
    assert character.attribute_value("INT") == 4
    assert character.attribute_value("LOG") == 3

    knowledge_skills, languages = _picks_from_legacy(legacy)
    selection = create_knowledge_selection(character, knowledge_skills, languages)

    assert selection.free_points == 14
    assert selection.points_spent == 13
    assert {k.name: k.rating for k in selection.knowledge_skills} == {
        "Fashion": 3,
        "Area Knowledge: Neo-Tokyo": 2,
        "Classical Music": 2,
        "Magical Theory (Academic)": 2,
    }
    assert {la.name: la.rating for la in selection.languages} == {"Japanese": 1, "English": 3}
    assert all(not la.native for la in selection.languages)


def test_wesson_knowledge_selection_matches_his_recorded_int_log_budget_exactly() -> None:
    # Wesson: INT 4 + LOG 4 -> 16-point budget, spent in full (4 Professional entries at 3 each +
    # Spanish (Language, 1) + a Corporation Academic entry (3) = 16). The trailing placeholder-
    # empty <skill> entry (base 0) is excluded by the ordinary base<=0 skip.
    legacy = load_chum5(mundane_fixture_path("Wesson.chum5"))
    character = _character_from_legacy_attributes(legacy)
    assert character.attribute_value("INT") == 4
    assert character.attribute_value("LOG") == 4

    knowledge_skills, languages = _picks_from_legacy(legacy)
    selection = create_knowledge_selection(character, knowledge_skills, languages)

    assert selection.free_points == 16
    assert selection.points_spent == 16
    assert len(knowledge_skills) == 5
    assert {la.name: la.rating for la in selection.languages} == {"Spanish": 1}
    assert all(not la.native for la in selection.languages)
