"""WP121: the Aspected Magician (p. 69)."""

from __future__ import annotations

import re
from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from chummer5.data.mentors import gated_choice, load_mentors
from chummer5.data.metatypes import load_metatypes
from chummer5.data.priorities import load_priorities
from chummer5.data.skills import load_skills
from chummer5.data.traditions import load_traditions
from chummer5.engine.character import Character, create_character, metatype_choices
from chummer5.engine.derived import astral_initiative, drain_resistance
from chummer5.engine.magic import (
    apply_magic_skill_grant_improvements,
    binds_spirits,
    casts_spells,
    create_magic_selection,
)
from chummer5.engine.skills import create_skill_allocation, skill_purchase_rules
from chummer5.web.app import create_app

METATYPES = load_metatypes()
PRIORITIES = load_priorities()
SKILLS = load_skills()
SKILL = {s.name: s for s in SKILLS}
TRADITIONS = load_traditions()
HERMETIC = next(t for t in TRADITIONS if t.name == "Hermetic")


def _select(letter: str = "B", aspect: str | None = "Conjuring", **kwargs: object):  # type: ignore[no-untyped-def]
    return create_magic_selection(
        letter,
        "Aspected Magician",
        kwargs.get("tradition_id", HERMETIC.id),  # type: ignore[arg-type]
        kwargs.get("granted", ()),  # type: ignore[arg-type]
        PRIORITIES,
        TRADITIONS,
        SKILLS,
        aspect=aspect,
    )


def _aspected(aspect: str) -> Character:
    choice = next(
        c
        for c in metatype_choices(PRIORITIES.heritage["A"], METATYPES)
        if c.metatype.name == "Human"
    )
    character = create_character(choice, "A", "A", PRIORITIES, {"LOG": 2, "WIL": 2})
    selection = _select(aspect=aspect)
    apply_magic_skill_grant_improvements(character, selection, SKILLS)
    return replace(
        character,
        magic_type=selection.magic_type,
        magic_aspect=selection.aspect,
        magic_rating=selection.magic_rating,
        tradition=selection.tradition,
        magic_granted_skill_ids=selection.granted_skill_ids,
    )


# --- the Talent option ----------------------------------------------------------------------


@pytest.mark.parametrize(("letter", "magic", "rating"), [("B", 5, 4), ("C", 3, 2), ("D", 2, 0)])
def test_the_aspect_group_is_granted_at_the_priority_tables_rating(
    letter: str, magic: int, rating: int
) -> None:
    selection = _select(letter)
    assert (selection.magic_rating, selection.granted_skill_rating) == (magic, rating)
    expected = {"Banishing", "Binding", "Summoning"} if rating else set()
    assert {s.name for s in SKILLS if s.id in selection.granted_skill_ids} == expected
    assert selection.aspect == "Conjuring"


def test_an_aspected_magician_needs_an_aspect_and_a_tradition_and_picks_no_skills() -> None:
    with pytest.raises(ValueError, match="needs an aspect"):
        _select(aspect=None)
    with pytest.raises(ValueError, match="needs an aspect"):
        _select(aspect="Tasking")
    with pytest.raises(ValueError, match="requires a tradition"):
        _select(tradition_id=None)
    with pytest.raises(ValueError, match="free grant is its aspect group"):
        _select(granted=(SKILL["Summoning"].id,))
    with pytest.raises(ValueError, match="has no aspect"):
        create_magic_selection(
            "B", "Magician", HERMETIC.id, (), PRIORITIES, TRADITIONS, SKILLS, aspect="Sorcery"
        )


# --- what each aspect may do -----------------------------------------------------------------


def test_spells_are_for_sorcery_and_spirits_for_conjuring() -> None:
    conjurer, sorcerer, enchanter = (_aspected(a) for a in ("Conjuring", "Sorcery", "Enchanting"))
    assert (casts_spells(conjurer), binds_spirits(conjurer)) == (False, True)
    assert (casts_spells(sorcerer), binds_spirits(sorcerer)) == (True, False)
    assert (casts_spells(enchanter), binds_spirits(enchanter)) == (False, False)


def test_the_other_two_groups_and_their_skills_are_banned_forever() -> None:
    conjurer = _aspected("Conjuring")
    rules = skill_purchase_rules(conjurer)
    for name in ("Spellcasting", "Counterspelling", "Alchemy"):
        with pytest.raises(ValueError, match="Conjuring-aspected magician can never learn"):
            create_skill_allocation("A", PRIORITIES, SKILLS, {SKILL[name].id: 1}, {}, rules=rules)
    create_skill_allocation(
        "A",
        PRIORITIES,
        SKILLS,
        {SKILL[n].id: 2 for n in ("Assensing", "Arcana", "Astral Combat")},
        {},
        rules=rules,
    )


def test_tradition_drain_the_magician_mentor_slot_and_no_astral_initiative() -> None:
    conjurer = _aspected("Conjuring")
    assert drain_resistance(conjurer) == conjurer.attribute_value("LOG") + conjurer.attribute_value(
        "WIL"
    )
    assert astral_initiative(conjurer) is None  # no astral projection (p. 69)
    bear = next(m for m in load_mentors() if m.name == "Bear")
    assert gated_choice(bear, "Aspected Magician") == bear.magician_choice


# --- the page --------------------------------------------------------------------------------


def _confirm(client: TestClient, aspect: str) -> None:
    client.get("/")
    human = next(
        c
        for c in metatype_choices(PRIORITIES.heritage["A"], METATYPES)
        if c.metatype.name == "Human"
    )
    client.post(
        "/ui/priorities",
        data={
            "heritage_letter": "A",
            "talent_letter": "B",
            "attributes_letter": "C",
            "skills_letter": "D",
            "resources_letter": "E",
            "metatype_id": human.metatype.id,
        },
    )
    client.post(
        "/ui/talent",
        data={
            "talent_letter": "B",
            "talent_codename": "Aspected Magician",
            "tradition_id": HERMETIC.id,
            "magic_aspect": aspect,
        },
    )


def test_a_priority_b_conjurer_gets_conjuring_4_binds_spirits_and_casts_nothing() -> None:
    """The plan's acceptance."""
    client = TestClient(create_app())
    _confirm(client, "Conjuring")
    client.post("/ui/skills", data={})  # the sheet lists skills once a spend is committed
    sheet = re.sub(r">\s+<", "><", client.get("/character/sheet").text)
    assert "Aspect: Conjuring" in sheet
    for name in ("Banishing", "Binding", "Summoning"):
        assert f"<td>{name}</td><td>0 (4)</td>" in sheet
    assert "<td>Spellcasting</td>" not in sheet

    spirits = client.post(
        "/ui/spirits", data={"spirit_type_0": "Spirit of Air", "spirit_services_0": "1"}
    ).text
    assert 'name="spirit_type_0"' in spirits
    assert "Spirit of Air" in client.get("/character/sheet").text

    spells = client.post("/ui/spells", data={}).text
    assert 'name="spell_id"' not in spells


def test_a_sorcerer_casts_with_karma_only_and_binds_nothing() -> None:
    client = TestClient(create_app())
    _confirm(client, "Sorcery")
    spells = client.post("/ui/spells", data={}).text
    assert 'name="spell_id"' in spells
    assert 'name="spirit_type_0"' not in client.post("/ui/spirits", data={}).text


def test_the_aspect_survives_a_save() -> None:
    client = TestClient(create_app())
    _confirm(client, "Enchanting")
    saved = client.get("/character/save").content
    assert b'"magic_aspect": "Enchanting"' in saved
    fresh = TestClient(create_app())
    fresh.get("/")
    loaded = fresh.post(
        "/characters/upload?open=true", files={"files": ("c.json", saved, "application/json")}
    )
    assert "Character loaded." in loaded.text
    assert "Aspect: Enchanting" in fresh.get("/character/sheet").text


def test_a_magician_turned_conjurer_flags_the_sorcery_skills() -> None:
    """The stale-selection matrix for Magician -> Aspected: spells reset with any Talent change
    (WP29), and a bought Sorcery skill stays with the skills page's WP19 warning."""
    client = TestClient(create_app())
    _confirm(client, "Conjuring")
    client.post(
        "/ui/talent",
        data={
            "talent_letter": "B",
            "talent_codename": "Magician",
            "tradition_id": HERMETIC.id,
            "granted_skill_id": [SKILL["Spellcasting"].id, SKILL["Counterspelling"].id],
        },
    )
    client.post("/ui/skills", data={f"skill_{SKILL['Ritual Spellcasting'].id}": "2"})
    client.post(
        "/ui/talent",
        data={
            "talent_letter": "B",
            "talent_codename": "Aspected Magician",
            "tradition_id": HERMETIC.id,
            "magic_aspect": "Conjuring",
        },
    )
    assert "Conjuring-aspected magician can never learn" in client.get("/ui/page/skills").text


def test_legacy_import_reports_an_aspected_magician_as_blocking() -> None:
    from tests.fixtures.mundane_chum5 import mundane_fixture_path

    from chummer5.io.legacy_chum5 import load_chum5
    from chummer5.io.legacy_import import _blocking_reasons

    legacy = load_chum5(mundane_fixture_path("Miko.chum5"))
    legacy = replace(
        legacy, priorities=replace(legacy.priorities, talent_codename="Aspected Magician")
    )
    reasons = _blocking_reasons(legacy, TRADITIONS, (), (), SKILLS)
    assert any("Aspected Magician' can't be imported yet" in r for r in reasons)
