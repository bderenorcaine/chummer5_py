"""Round-trip regression for `chummer5.io.save_format`, using `Yeti-#ffffff2.chum5` -- the same
priority-build fixture WP6/WP7/WP9/WP10 already lean on -- to prove `build → save → load → equal`
against real data, not just synthetic values.

Mirrors `tests/integration/test_character_fixtures.py`'s extraction pattern (metatype/priority
letters, attribute points, skill allocation, contacts, resources) to first construct a
`CharacterSave` describing Yeti, then exercises the save format's own contract: serialize that
save to JSON text, deserialize it back, rebuild the engine artifacts from the reloaded copy, and
check the rebuilt values against both the original build and Yeti's own legacy-computed ground
truth.
"""

from __future__ import annotations

from tests.fixtures.mundane_chum5 import PRIORITY_BUILD_FIXTURE, mundane_fixture_path

from chummer5.data.metatypes import load_metatypes
from chummer5.data.priorities import load_priorities
from chummer5.data.qualities import load_qualities
from chummer5.data.skills import load_skills
from chummer5.engine.character import ALLOCATABLE_ATTRIBUTES, metatype_choices
from chummer5.engine.resources import Contact
from chummer5.io.legacy_chum5 import load_chum5, priority_letter
from chummer5.io.save_format import (
    CharacterSave,
    build_character,
    create_character_save,
    from_json,
    to_json,
)

METATYPES = load_metatypes()
PRIORITIES = load_priorities()
SKILLS = load_skills()
QUALITIES = load_qualities()


def _yeti_save() -> CharacterSave:
    legacy = load_chum5(mundane_fixture_path(PRIORITY_BUILD_FIXTURE))
    heritage_letter = priority_letter(legacy.priorities.heritage)
    attributes_letter = priority_letter(legacy.priorities.attributes)
    skills_letter = priority_letter(legacy.priorities.skills)
    resources_letter = priority_letter(legacy.priorities.resources)

    heritage = PRIORITIES.heritage[heritage_letter]
    human_choice = next(
        c for c in metatype_choices(heritage, METATYPES) if c.metatype.name == "Human"
    )
    assert human_choice  # sanity: Yeti is a plain Human, per prior WPs' fixture research

    skills_by_id = {s.id: s for s in SKILLS}
    bought_groups = {g.name: g.base for g in legacy.skill_groups if g.base > 0}
    skill_points = {
        skill.id: legacy_skill.base
        for legacy_skill in legacy.skills
        if legacy_skill.base > 0
        for skill in [skills_by_id.get(legacy_skill.suid)]
        if skill is not None
        and not (skill.skill_group is not None and skill.skill_group in bought_groups)
    }

    contacts = tuple(
        Contact(name=c.name, connection=c.connection, loyalty=c.loyalty, free=c.free)
        for c in legacy.contacts
    )

    # Yeti's own qualities/gear aren't reconstructable from MVP's minimal catalogs (see
    # spec/worklogs/WP9.md/WP10.md) -- same "nothing to build there" gap the WP10 end-to-end
    # regression test already documents, so this save deliberately carries none of either.
    return create_character_save(
        metatype_name="Human",
        heritage_letter=heritage_letter,
        attributes_letter=attributes_letter,
        attribute_points={
            code: legacy.attributes[code].base + legacy.attributes[code].karma
            for code in ALLOCATABLE_ATTRIBUTES
        },
        skills_letter=skills_letter,
        skill_points=skill_points,
        group_points=bought_groups,
        quality_ids=(),
        contacts=contacts,
        resources_letter=resources_letter,
        gear_names=(),
    )


def test_yeti_save_round_trips_through_json_unchanged() -> None:
    save = _yeti_save()
    reloaded = from_json(to_json(save))
    assert reloaded == save


def test_yeti_build_save_load_produces_an_equal_reconstruction() -> None:
    """The `build → save → load → equal` acceptance criterion itself: build once, round-trip the
    save through JSON, build again from the reloaded copy, and confirm every artifact that can be
    compared by value matches -- plus the two artifacts that can't (`Character`, whose
    `ImprovementIndex` has no `__eq__`; see `BuiltCharacter`'s docstring) are cross-checked via
    `attribute_value()` instead, against both each other and Yeti's own legacy-computed totals.
    """
    save = _yeti_save()
    reloaded_save = from_json(to_json(save))

    built_before = build_character(
        save, metatypes=METATYPES, priorities=PRIORITIES, skills=SKILLS, qualities=QUALITIES
    )
    built_after = build_character(
        reloaded_save,
        metatypes=METATYPES,
        priorities=PRIORITIES,
        skills=SKILLS,
        qualities=QUALITIES,
    )

    legacy = load_chum5(mundane_fixture_path(PRIORITY_BUILD_FIXTURE))
    for code in ALLOCATABLE_ATTRIBUTES:
        before_value = built_before.character.attribute_value(code)
        after_value = built_after.character.attribute_value(code)
        assert before_value == after_value == legacy.attributes[code].total_value, code

    assert built_before.skill_allocation == built_after.skill_allocation
    assert built_before.quality_selection == built_after.quality_selection
    assert built_before.contact_selection == built_after.contact_selection
    assert built_before.resources_selection == built_after.resources_selection

    # Cross-check against Yeti's own recorded ground truth too, not just internal self-consistency.
    assert built_after.contact_selection.free_points == legacy.contact_points_budget
    assert built_after.contact_selection.points_spent == 15
    assert built_after.resources_selection.nuyen_budget == legacy.starting_nuyen
