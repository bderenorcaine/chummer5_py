"""Round-trips known raw fields from the 11 curated mundane `.chum5` fixtures (WP4).

Every hand-checked value below was independently cross-checked against the raw XML with a bare
`xml.etree.ElementTree` read, not derived from `chummer5.io.legacy_chum5` itself — see
`tests/fixtures/README.md` for the corpus and `spec/worklogs/WP4.md` for the reconnaissance this is
built on.
"""

from __future__ import annotations

import pytest
from tests.fixtures.mundane_chum5 import (
    MUNDANE_FIXTURES,
    PRIORITY_BUILD_FIXTURE,
    mundane_fixture_path,
)

from chummer5.data.priorities import load_priorities
from chummer5.engine.build_method import validate_sum_to_ten_total
from chummer5.io.legacy_chum5 import load_chum5, priority_letter

# name -> (metatype, karma_remaining, build_karma, nuyen_remaining, starting_nuyen, quality_count)
# Hand-checked directly against each file's <karma>/<buildkarma>/<nuyen>/<startingnuyen>/<qualities>
# elements.
_KNOWN_RAW_FIELDS = {
    "BLUE.chum5": ("Ork", 0, 25, 756.333333333333, 450000, 6),
    "Barrett.chum5": ("Human", 3, 25, 617.50, 450000, 10),
    "Bastion.chum5": ("Human", 0, 25, 0.00, 450000, 11),
    "Blindfire.chum5": ("Elf", 3, 25, 300.00, 450000, 10),
    "Fuzzy-chargen.chum5": ("Human", 0, 25, 610.00, 275000, 11),
    "Gentle Earthquake.chum5": ("Troll", 1, 25, 90.0000, 140000, 11),
    "Monomax (approved) 3.chum5": ("Troll", 3, 25, 64.00, 140000, 11),
    "Rez0luti0n2.0.chum5": ("Dwarf", 0, 25, 400.00, 6000, 12),
    "SCSi.chum5": ("Human", 0, 25, 55.00, 450000, 6),
    "Serpent.chum5": ("Human", 0, 25, 15420.0, 275000, 8),
    "Yeti-#ffffff2.chum5": ("Human", 1, 25, 1145.0, 6000, 6),
}

# name -> <nuyenbp> (Karma actually converted to nuyen at Step Six, core rulebook p. 94). Hand-
# checked directly against each file's <nuyenbp> element (WP43) -- 6 of the 11 curated mundane
# fixtures actually used this mechanic, the best real coverage of any Phase L candidate.
_KNOWN_KARMA_CONVERTED_TO_NUYEN = {
    "BLUE.chum5": 9,
    "Barrett.chum5": 10,
    "Bastion.chum5": 10,
    "Blindfire.chum5": 2,
    "Fuzzy-chargen.chum5": 0,
    "Gentle Earthquake.chum5": 10,
    "Monomax (approved) 3.chum5": 0,
    "Rez0luti0n2.0.chum5": 10,
    "SCSi.chum5": 0,
    "Serpent.chum5": 0,
    "Yeti-#ffffff2.chum5": 0,
}

# name -> <contactpoints> (the save format's cached CHA*3 free-contact-point budget). Hand-checked
# directly against each file's <contactpoints> element (WP9).
_KNOWN_CONTACT_POINTS_BUDGET = {
    "BLUE.chum5": 15,
    "Barrett.chum5": 12,
    "Bastion.chum5": 12,
    "Blindfire.chum5": 18,
    "Fuzzy-chargen.chum5": 6,
    "Gentle Earthquake.chum5": 6,
    "Monomax (approved) 3.chum5": 6,
    "Rez0luti0n2.0.chum5": 9,
    "SCSi.chum5": 6,
    "Serpent.chum5": 9,
    "Yeti-#ffffff2.chum5": 15,
}


def test_known_raw_fields_registry_covers_every_curated_fixture() -> None:
    assert set(_KNOWN_RAW_FIELDS) == set(MUNDANE_FIXTURES)


@pytest.mark.parametrize("name", MUNDANE_FIXTURES)
def test_round_trips_known_raw_fields(name: str) -> None:
    metatype, karma_remaining, build_karma, nuyen_remaining, starting_nuyen, quality_count = (
        _KNOWN_RAW_FIELDS[name]
    )
    character = load_chum5(mundane_fixture_path(name))

    assert character.metatype == metatype
    assert character.metatype_category == "Metahuman"  # every mundane fixture, per WP2's note
    assert character.magic_enabled is False  # the definition of "mundane" used throughout this WP
    assert character.karma_remaining == karma_remaining
    assert character.build_karma == build_karma
    assert character.nuyen_remaining == pytest.approx(nuyen_remaining)
    assert character.starting_nuyen == starting_nuyen
    assert len(character.qualities) == quality_count


def test_known_karma_converted_to_nuyen_registry_covers_every_curated_fixture() -> None:
    assert set(_KNOWN_KARMA_CONVERTED_TO_NUYEN) == set(MUNDANE_FIXTURES)


@pytest.mark.parametrize("name", MUNDANE_FIXTURES)
def test_karma_converted_to_nuyen_matches_raw_tag(name: str) -> None:
    character = load_chum5(mundane_fixture_path(name))
    assert character.karma_converted_to_nuyen == _KNOWN_KARMA_CONVERTED_TO_NUYEN[name]


@pytest.mark.parametrize("name", MUNDANE_FIXTURES)
def test_starting_nuyen_matches_resources_priority_letter(name: str) -> None:
    # Cross-checks the parser against WP2's independently-loaded priorities.xml data: whatever
    # Resources priority letter a fixture's raw <priorityresources> encodes should grant exactly
    # the nuyen the fixture's own <startingnuyen> records, for both build methods in the corpus.
    priorities = load_priorities()
    character = load_chum5(mundane_fixture_path(name))
    letter = priority_letter(character.priorities.resources)
    assert priorities.resources[letter].nuyen == character.starting_nuyen


def test_known_contact_points_budget_registry_covers_every_curated_fixture() -> None:
    assert set(_KNOWN_CONTACT_POINTS_BUDGET) == set(MUNDANE_FIXTURES)


@pytest.mark.parametrize("name", MUNDANE_FIXTURES)
def test_contact_points_budget_matches_raw_tag(name: str) -> None:
    character = load_chum5(mundane_fixture_path(name))
    assert character.contact_points_budget == _KNOWN_CONTACT_POINTS_BUDGET[name]


def test_yeti_contacts() -> None:
    # Hand-checked against Yeti-#ffffff2.chum5's <contacts><contact>...
    character = load_chum5(mundane_fixture_path(PRIORITY_BUILD_FIXTURE))
    assert len(character.contacts) == 2
    contacts_by_name = {c.name: c for c in character.contacts}
    assert contacts_by_name["JoJo"].connection == 3
    assert contacts_by_name["JoJo"].loyalty == 3
    assert contacts_by_name["JoJo"].free is False
    assert contacts_by_name["Ralph, Just Ralph"].connection == 5
    assert contacts_by_name["Ralph, Just Ralph"].loyalty == 4
    assert contacts_by_name["Ralph, Just Ralph"].free is False


def test_monomax_has_one_free_contact() -> None:
    # Hand-checked: Monomax (approved) 3.chum5 has a <free>True</free> contact -- the only one
    # across the 11 curated mundane fixtures (WP9's own reconnaissance).
    character = load_chum5(mundane_fixture_path("Monomax (approved) 3.chum5"))
    free_contacts = [c for c in character.contacts if c.free]
    assert len(free_contacts) == 1
    assert free_contacts[0].connection == 2
    assert free_contacts[0].loyalty == 1


def test_yeti_is_the_priority_build_fixture() -> None:
    assert PRIORITY_BUILD_FIXTURE == "Yeti-#ffffff2.chum5"
    character = load_chum5(mundane_fixture_path(PRIORITY_BUILD_FIXTURE))
    assert character.build_method == "Priority"


def test_yeti_priority_selections() -> None:
    # Hand-checked against Yeti-#ffffff2.chum5's raw <priority*> elements. Yeti is a Technomancer
    # (<resenabled>True</resenabled>) despite being "mundane" in this project's magenabled-only
    # sense — see tests/fixtures/README.md.
    character = load_chum5(mundane_fixture_path(PRIORITY_BUILD_FIXTURE))
    priorities = character.priorities

    assert priority_letter(priorities.heritage) == "D"
    assert priority_letter(priorities.attributes) == "A"
    assert priority_letter(priorities.talent) == "B"
    assert priority_letter(priorities.skills) == "C"
    assert priority_letter(priorities.resources) == "E"
    assert priorities.talent_codename == "Technomancer"
    assert priorities.talent_bonus_skills == ("Compiling", "Hacking", "Cybercombat")


# WP44: hand-verified against a direct read of each fixture's raw <priority*> fields -- the only 5
# of the 11 curated mundane fixtures with a real letter recorded for all 5 categories (the other 6
# have a blank Skills field -- a genuine Mundane-Talent-SumtoTen save-format gap, see
# spec/rulebooks/learnings.md's WP44 entry, not exercised here). Confirms
# `validate_sum_to_ten_total` against real fixture data, including two cases with repeated letters,
# not just hand-picked ones -- real, independent corroboration of both "the rule is exact equality"
# and "repeats are legal", beyond the legacy C#/language-string research alone.
_FIXTURES_WITH_ALL_FIVE_PRIORITY_LETTERS = (
    "Bastion.chum5",
    "Rez0luti0n2.0.chum5",
    "SCSi.chum5",
    "Serpent.chum5",
    "Yeti-#ffffff2.chum5",
)


@pytest.mark.parametrize("name", _FIXTURES_WITH_ALL_FIVE_PRIORITY_LETTERS)
def test_every_complete_priority_letter_assignment_sums_to_exactly_ten(name: str) -> None:
    character = load_chum5(mundane_fixture_path(name))
    priorities = character.priorities
    letters = (
        priority_letter(priorities.heritage),
        priority_letter(priorities.talent),
        priority_letter(priorities.attributes),
        priority_letter(priorities.skills),
        priority_letter(priorities.resources),
    )
    assert validate_sum_to_ten_total(letters) == 10


def test_yeti_attributes() -> None:
    # Hand-checked against Yeti-#ffffff2.chum5's <attributes><attribute><name>BOD</name>...
    character = load_chum5(mundane_fixture_path(PRIORITY_BUILD_FIXTURE))
    bod = character.attributes["BOD"]
    assert bod.metatype_min == 1
    assert bod.metatype_max == 6
    assert bod.metatype_aug_max == 10
    assert bod.base == 3
    assert bod.karma == 0
    assert bod.total_value == 4
    # No priority-spendable Initiative attribute in a saved character, matching WP2's metatypes.xml
    # finding (INI is derived, not priority-bought).
    assert "INI" not in character.attributes


def test_yeti_technomancer_quality() -> None:
    # Hand-checked against Yeti-#ffffff2.chum5's <qualities><quality><name>Technomancer</name>.
    character = load_chum5(mundane_fixture_path(PRIORITY_BUILD_FIXTURE))
    technomancer = next(q for q in character.qualities if q.name == "Technomancer")
    assert technomancer.karma == 15
    assert technomancer.quality_type == "Positive"
    assert technomancer.source == "SR5"
    # WP23: <qualitysource>Metatype</qualitysource> here despite Yeti being Human -- confirms this
    # tag isn't exclusively "this metatype's real racial quality" (see spec/worklogs/WP23.md and
    # chummer5.io.legacy_import's own handling of this case).
    assert technomancer.quality_source == "Metatype"


def test_blindfire_low_light_vision_quality_source_is_metatype() -> None:
    # WP23: Blindfire is an Elf; Low-Light Vision is Elf's real free racial quality, also tagged
    # qualitysource=Metatype -- the "genuinely metatype-granted" case test_yeti_technomancer_quality
    # above is deliberately not.
    character = load_chum5(mundane_fixture_path("Blindfire.chum5"))
    low_light = next(q for q in character.qualities if q.name == "Low-Light Vision")
    assert low_light.quality_source == "Metatype"
    # <bp>4</bp> -- the catalog's flat karma value, recorded even though a Metatype-sourced quality
    # was never actually paid for; the legacy engine excludes it from the karma total by checking
    # OriginSource elsewhere (Character.cs), not by zeroing <bp> in the save. Confirms
    # chummer5.io.legacy_import must exclude it by quality_source, not by a bp==0 shortcut.
    assert low_light.karma == 4


def test_yeti_skill_groups_include_stealth_and_firearms() -> None:
    # Hand-checked against Yeti-#ffffff2.chum5's <newskills><groups>.
    character = load_chum5(mundane_fixture_path(PRIORITY_BUILD_FIXTURE))
    groups_by_name = {g.name: g for g in character.skill_groups}
    assert groups_by_name["Stealth"].base == 1
    assert groups_by_name["Tasking"].base == 0
    assert groups_by_name["Firearms"].base == 1


def test_barrett_attributes_and_qualities() -> None:
    # Hand-checked against Barrett.chum5's <attributes> and <qualities> (SumtoTen build method,
    # for coverage of a fixture other than the Priority-built Yeti).
    character = load_chum5(mundane_fixture_path("Barrett.chum5"))

    bod = character.attributes["BOD"]
    assert bod.metatype_min == 1
    assert bod.metatype_max == 6
    assert bod.base == 4
    assert bod.karma == 0
    assert bod.total_value == 5

    qualities_by_name = {q.name: q for q in character.qualities}
    assert qualities_by_name["Prototype Transhuman"].karma == 10
    assert qualities_by_name["Prototype Transhuman"].quality_type == "Positive"
    assert qualities_by_name["SINner (Corporate)"].karma == -25
    assert qualities_by_name["SINner (Corporate)"].quality_type == "Negative"


def test_no_knowledge_skills_are_parsed() -> None:
    # WP3 precedent: knowledge skills are out of MVP scope, so <newskills><knoskills> is never
    # touched. Yeti's file has 5 knowledge skills (English Language, Japanese Language, ...); none
    # should leak into `.skills`.
    character = load_chum5(mundane_fixture_path(PRIORITY_BUILD_FIXTURE))
    assert len(character.skills) == 62
    assert all(skill.category != "Language" for skill in character.skills)
