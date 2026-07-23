"""WP50: skill specialization cross-checked against real `.chum5` corpus data.

`Yeti-#ffffff2.chum5` (the corpus's sole mundane `buildmethod == Priority` fixture) gets full
`import_chum5()` coverage in `tests/integration/test_legacy_import_fixtures.py`, including her 6
recorded specializations (5 import cleanly, 1 is dropped -- see that test's own comment). Miko (Elf
Magician), Phase I's own fixture, fails `import_legacy_character` for a reason unrelated to skills
(her non-SR5 tradition -- see `spec/worklogs/WP28.md`), so her own specialization data is
cross-checked directly here instead, the same "read the raw fixture, build a `SkillAllocation` by
hand, verify the formula" pattern `test_knowledge_fixtures.py` already established for Knowledge/
Language skills.
"""

from __future__ import annotations

from tests.fixtures.mundane_chum5 import mundane_fixture_path

from chummer5.data.priorities import load_priorities
from chummer5.data.skills import load_skills
from chummer5.engine.skills import create_skill_allocation
from chummer5.io.legacy_chum5 import load_chum5, priority_letter

PRIORITIES = load_priorities()
SKILLS = load_skills()
SKILLS_BY_ID = {s.id: s for s in SKILLS}


def test_miko_specializations_exactly_exhaust_her_skills_c_budget() -> None:
    # Miko: 3 real specializations (Etiquette/Tea Ceremonies, Spellcasting/Manipulation,
    # Summoning/Plant Spirit), all on individually-purchased skills (none belong to a group with
    # points spent -- her only bought group, Stealth, contains none of the 3). 25 individual skill
    # points + 3 specialization points = 28, exactly her Skills-C budget (28 skills / 2 groups) --
    # and her one bought group, Stealth at 2, exactly fills the group budget too.
    legacy = load_chum5(mundane_fixture_path("Miko.chum5"))
    letter = priority_letter(legacy.priorities.skills)
    assert letter == "C"

    bought_groups = {g.name: g.base for g in legacy.skill_groups if g.base > 0}
    skill_points: dict[str, int] = {}
    for legacy_skill in legacy.skills:
        if legacy_skill.base <= 0:
            continue
        skill = SKILLS_BY_ID.get(legacy_skill.suid)
        if skill is None:
            continue
        if skill.skill_group is not None and skill.skill_group in bought_groups:
            continue
        skill_points[skill.id] = legacy_skill.base

    specializations: dict[str, str] = {}
    for legacy_skill in legacy.skills:
        if not legacy_skill.specializations:
            continue
        skill = SKILLS_BY_ID.get(legacy_skill.suid)
        if skill is None or skill.id not in skill_points:
            continue
        specializations[skill.id] = legacy_skill.specializations[0]

    assert {SKILLS_BY_ID[sid].name: name for sid, name in specializations.items()} == {
        "Etiquette": "Tea Ceremonies",
        "Spellcasting": "Manipulation",
        "Summoning": "Plant Spirit",
    }
    assert sum(skill_points.values()) == 25

    allocation = create_skill_allocation(
        letter, PRIORITIES, SKILLS, skill_points, bought_groups, specializations
    )
    assert allocation.specializations == specializations
    budget = PRIORITIES.skills[letter]
    assert sum(allocation.skill_points.values()) + len(allocation.specializations) == budget.skills
    assert sum(allocation.group_points.values()) == budget.skill_groups
