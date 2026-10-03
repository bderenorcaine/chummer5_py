"""WP135: whole-character validation -- the engine's checks, the Export page's checklist, the nav
marker and the title bar status."""

from __future__ import annotations

import re
from dataclasses import replace
from types import MappingProxyType

from fastapi.testclient import TestClient
from tests.fixtures.mundane_chum5 import PRIORITY_BUILD_FIXTURE, mundane_fixture_path
from tests.fixtures.synthetic import build_synthetic
from tests.fixtures.synthetic_fixtures import RIGGER_FIXTURE

from chummer5.data.metatypes import load_metatypes
from chummer5.data.priorities import load_priorities
from chummer5.data.qualities import load_qualities
from chummer5.data.skills import load_skills
from chummer5.engine.character import PRIMARY_ATTRIBUTES, metatype_choices
from chummer5.engine.qualities import QualityPick, QualitySelection
from chummer5.engine.validation import SessionLetters, validate
from chummer5.web.app import create_app

PRIORITIES = load_priorities()
METATYPES = load_metatypes()
SKILLS = load_skills()

RIGGER = build_synthetic(RIGGER_FIXTURE)
RIGGER_LETTERS = SessionLetters(
    RIGGER_FIXTURE.heritage_letter,
    RIGGER_FIXTURE.talent_letter or "E",
    RIGGER_FIXTURE.attributes_letter,
    RIGGER_FIXTURE.skills_letter,
    RIGGER_FIXTURE.resources_letter,
    RIGGER_FIXTURE.build_method,
)


def _keys(character, letters=RIGGER_LETTERS):  # type: ignore[no-untyped-def]
    return [i.key for i in validate(character, letters, priorities=PRIORITIES, skills=SKILLS)]


def test_a_finished_character_validates_clean() -> None:
    # The plan named p. 96's James, a Technomancer -- ruled out of this project. The rigger fixture
    # is a complete, fully spent build of the same kind.
    assert _keys(RIGGER) == []


def test_each_check_fires() -> None:
    # No Lifestyle, no contacts: warnings.
    assert _keys(replace(RIGGER, lifestyle_selection=None)) == ["Web_Validation_NoLifestyle"]
    assert _keys(replace(RIGGER, contact_selection=None)) == ["Web_Validation_NoContacts"]
    # Priority rows used twice.
    doubled = replace(RIGGER_LETTERS, talent=RIGGER_LETTERS.resources)
    assert "Web_Validation_PriorityRows" in _keys(RIGGER, doubled)
    # A smaller Resources budget leaves the same purchases overspent.
    poorer = SessionLetters("A", "B", "C", "D", "E")
    issues = validate(RIGGER, poorer, priorities=PRIORITIES, skills=SKILLS)
    assert "Web_Validation_NuyenOver" in [i.key for i in issues]
    # Points: unspent is a warning; overspent names the pool.
    fewer = dict(RIGGER.attribute_points)
    spent = next(code for code in PRIMARY_ATTRIBUTES if fewer.get(code, 0) > 0)
    fewer[spent] -= 1
    unspent = validate(
        replace(RIGGER, attribute_points=MappingProxyType(fewer)),
        RIGGER_LETTERS,
        priorities=PRIORITIES,
        skills=SKILLS,
    )
    assert [(i.severity, i.key, dict(i.params)) for i in unspent] == [
        ("warning", "Web_Validation_AttributePoints", {"count": 1})
    ]


def test_two_attributes_at_natural_maximum() -> None:
    # An import or a stale state WP112 couldn't reject at the spend.
    maxed = dict(RIGGER.attribute_points)
    for code in ("BOD", "AGI"):
        maxed[code] = RIGGER.attribute_range(code).maximum - RIGGER.attribute_range(code).minimum
    issues = validate(
        replace(RIGGER, attribute_points=MappingProxyType(maxed)),
        RIGGER_LETTERS,
        priorities=PRIORITIES,
        skills=SKILLS,
    )
    natural = [i for i in issues if i.key == "Web_Validation_NaturalMaximum"]
    assert natural and natural[0].severity == "error"
    assert set(natural[0].params["attributes"].split(", ")) >= {"BOD", "AGI"}
    assert set(PRIMARY_ATTRIBUTES) >= set(natural[0].params["attributes"].split(", "))


def _new_character(client: TestClient) -> None:
    client.get("/")
    human = next(
        c
        for c in metatype_choices(PRIORITIES.heritage["B"], METATYPES)
        if c.metatype.name == "Human"
    )
    client.post(
        "/ui/priorities",
        data={
            "heritage_letter": "B",
            "attributes_letter": "C",
            "skills_letter": "D",
            "resources_letter": "A",
            "talent_letter": "E",
            "metatype_id": human.metatype.id,
        },
    )


def test_a_fresh_character_lists_its_unspent_points() -> None:
    # The plan's acceptance.
    client = TestClient(create_app())
    _new_character(client)
    sheet = re.sub(r"\s+", " ", client.get("/character/sheet").text)
    for text in (
        "16 attribute points are unspent.",  # Attributes C
        "special attribute points are unspent; they are lost",
        "22 skill points are unspent.",  # Skills D
        "free Knowledge points are unspent.",
        "No primary Lifestyle has been chosen.",
        "The character has no contacts.",
    ):
        assert text in sheet, text
    # Each links to its step.
    assert 'href="/ui/page/equipment/lifestyle"' in sheet
    # The title bar counts them, and the nav marks the steps they belong to.
    home = client.get("/").text
    assert re.search(r"\d+ issues", home)
    assert "step-nav__item--stale" in client.get("/ui/nav").text
    status = client.get("/ui/validation-status").text
    assert "issues" in status and "Complete" not in status


def test_yetis_over_cap_contact_is_not_an_issue() -> None:
    # The plan's acceptance: the per-contact 7-Karma cap stays unenforced (WP9).
    client = TestClient(create_app())
    client.get("/")
    raw = mundane_fixture_path(PRIORITY_BUILD_FIXTURE).read_bytes()
    client.post(
        "/characters/upload?open=true",
        files={"files": ("Yeti.chum5", raw, "application/octet-stream")},
    )
    sheet = re.sub(r"\s+", " ", client.get("/character/sheet").text)
    start = sheet.index('id="validation-panel"')
    panel = sheet[start : sheet.index("</section>", start)]
    assert "contact" not in panel.lower()
    # Yeti's Resonance Talent imports as Mundane (Technomancers are ruled out), which lands on E --
    # the letter its Resources already use. That one real finding is all the panel lists.
    assert panel.count("<li") == 1
    assert "Each priority row A-E must be used exactly once." in panel


def test_the_magic_checks_a_save_skips() -> None:
    # WP118: an Adept's free skill grant naming Assensing, without Astral Perception.
    assensing = next(s for s in SKILLS if s.name == "Assensing")
    adept = replace(RIGGER, magic_type="Adept", magic_granted_skill_ids=(assensing.id,))
    assert "Web_Validation_AdeptAssensing" in _keys(adept)

    # WP121: Incompetent in a group an Aspected Magician can never learn is no handicap.
    incompetent = next(q for q in load_qualities() if q.name == "Incompetent")
    selection = QualitySelection(
        qualities=(QualityPick(incompetent, choice="Sorcery"),),
        positive_karma=0,
        negative_karma=5,
        karma_cost=-5,
    )
    aspected = replace(
        RIGGER,
        magic_type="Aspected Magician",
        magic_aspect="Conjuring",
        quality_selection=selection,
    )
    assert "Web_Validation_AspectIncompetent" in _keys(aspected)
    assert "Web_Validation_AspectIncompetent" not in _keys(
        replace(aspected, magic_aspect="Sorcery")
    )
