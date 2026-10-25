"""WP103: game-data term translation at display time (`chummer5.data.lang.load_data_terms`,
`chummer5.web.i18n.data_term`/`data_text`, the `| dterm` and `| dtext` filters).

The rule every test here serves: **translate for display only, never for identity.** A translated
name may reach the page's visible text; it must never reach a form value, a field name, an id, a
save, or a lookup key. The real legacy German catalog (`legacy/Chummer/lang/de-de_data.xml`) is
used throughout, offered to the session by monkeypatching `prefs` -- the UI itself still offers
English only (see `prefs.LOCALES`).
"""

from __future__ import annotations

import json
import logging
import re

import pytest
from fastapi.testclient import TestClient

from chummer5.data.lang import EMPTY_DATA_TERMS, load_data_terms
from chummer5.data.mentors import load_mentors
from chummer5.data.metatypes import load_metatypes
from chummer5.data.priorities import load_priorities
from chummer5.data.skills import load_skills
from chummer5.engine.character import metatype_choices
from chummer5.web import prefs
from chummer5.web.app import MVP_QUALITIES, create_app
from chummer5.web.i18n import data_term, data_text

GERMAN = prefs.Locale("de-de", "de-DE", "Deutsch")
PRIORITIES = load_priorities()
SKILLS = load_skills()
PISTOLS = next(s for s in SKILLS if s.name == "Pistols")
CATLIKE = next(q for q in MVP_QUALITIES if q.name == "Catlike")


@pytest.fixture
def german(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(prefs, "LOCALES", (*prefs.LOCALES, GERMAN))
    monkeypatch.setitem(prefs.LOCALES_BY_TAG, GERMAN.tag, GERMAN)


def _human_id() -> str:
    return next(
        c
        for c in metatype_choices(PRIORITIES.heritage["A"], load_metatypes())
        if c.metatype.name == "Human"
    ).metatype.id


def _build(client: TestClient) -> None:
    """A Human with a quality, a skill, a lifestyle and some gear -- one of each kind of key: GUID
    (skill, quality), priority-row name, lifestyle-tier name, and name-keyed starter gear."""
    client.post(
        "/ui/priorities",
        data={
            "heritage_letter": "A",
            "talent_letter": "E",
            "attributes_letter": "B",
            "skills_letter": "C",
            "resources_letter": "D",
            "metatype_id": _human_id(),
        },
    )
    client.post("/ui/qualities", data={"quality_id": CATLIKE.id})
    client.post("/ui/skills", data={f"skill_{PISTOLS.id}": "3"})
    client.post("/ui/lifestyle", data={"lifestyle_tier": "Low", "lifestyle_months": "1"})
    client.post("/ui/resources", data={"gear_Medkit": "1"})


# --- The loader ---------------------------------------------------------------------------------


def test_the_german_catalog_indexes_ids_file_terms_and_text_fields() -> None:
    terms = load_data_terms("de-de")
    bear = next(m for m in load_mentors() if m.name == "Bear")

    # The Pistols GUID also names "Handguns" in this file (a reused id): keyed by name, too.
    assert terms.by_id[PISTOLS.id.lower()] == {"Pistols": "Pistolen", "Handguns": "Handfeuerwaffen"}
    assert terms.by_file["skills.xml"]["Combat Active"] == "Kampf-Aktionsfertigkeiten"
    assert terms.by_file["skills.xml"]["Firearms"] == "Feuerwaffen"  # a skill group
    assert terms.by_file["lifestyles.xml"]["Low"] == "Unterschicht"
    assert terms.fields[(bear.id.lower(), "advantage")].startswith("Allgemein:")
    assert (bear.id.lower(), "page") not in terms.fields  # <altpage> is not a text field


def test_english_has_no_data_catalog_because_english_is_the_data() -> None:
    assert load_data_terms("en-us") == EMPTY_DATA_TERMS


def test_an_untranslated_term_falls_back_to_english_silently(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.DEBUG, logger="chummer5.web.i18n"):
        assert data_term("de-de", "Not A Real Item", "gear.xml") == "Not A Real Item"
        assert data_term("de-de", {"id": "0" * 32, "name": "Nameless"}) == "Nameless"
        assert data_term("xx-none", PISTOLS, "skills.xml") == "Pistols"
        assert data_text("de-de", {"id": None, "advantage": "Plain"}, "advantage") == "Plain"
    assert caplog.text == ""


def test_lookup_is_by_guid_checked_against_the_name() -> None:
    # The Pistols id is reused for "Handguns"; the object's own English name picks the entry.
    assert data_term("de-de", PISTOLS) == "Pistolen"
    assert data_term("de-de", {"id": PISTOLS.id, "name": "Handguns"}) == "Handfeuerwaffen"
    # An id with two entries and a name matching neither is ambiguous: English, not a guess.
    assert data_term("de-de", {"id": PISTOLS.id, "name": "Something Else"}) == "Something Else"
    # A plain string has no id, so it needs the file(s) it can come from.
    assert data_term("de-de", "Pistols") == "Pistols"
    assert data_term("de-de", "Pistols", "skills.xml") == "Pistolen"


# --- Display only -------------------------------------------------------------------------------


def test_german_names_reach_the_page_but_never_its_form_fields(german: None) -> None:
    client = TestClient(create_app())
    client.get("/")
    client.post("/ui/prefs/locale", data={"locale": "de-de"})
    _build(client)

    skills = client.get("/ui/page/skills").text
    assert "<td>Pistolen</td>" in skills
    assert f'name="skill_{PISTOLS.id}"' in skills  # identity: the GUID, unchanged
    # The filter matches what the player types against what the player *sees*.
    assert 'data-view-name="pistolen"' in skills
    # WP148: the categories became tabs with project labels; a group name is still a data term.
    assert "Feuerwaffen" in client.get("/ui/page/skills/group").text

    gear = client.get("/ui/page/equipment/gear").text
    assert 'name="gear_Medkit"' in gear  # name-keyed gear: the English key, unchanged
    lifestyle = client.get("/ui/page/equipment/lifestyle").text
    assert 'value="Low"' in lifestyle  # the tier's key stays English ...
    assert "Unterschicht" in lifestyle  # ... while its label is German
    priorities = client.get("/ui/page/priorities").text
    # WP143: the summary names what Talent's letter offers, from priorities.xml's rows.
    assert "E — Mundan" in priorities
    assert 'name="talent_letter" value="E"' in priorities  # the letter itself stays a letter
    assert "Mensch" in priorities


def test_a_german_session_saves_english_ids_and_reloads_identically(german: None) -> None:
    client = TestClient(create_app())
    client.get("/")
    client.post("/ui/prefs/locale", data={"locale": "de-de"})
    _build(client)

    save_text = client.get("/character/save").text
    save = json.loads(save_text)

    # Nothing the German display produced may have leaked into the save.
    for german_term in ("Pistolen", "Unterschicht", "Mensch", "Katzenhaft", "Medkit"):
        if german_term == "Medkit":
            continue  # the same word in both languages; checked positively below
        assert german_term not in save_text, german_term
    assert PISTOLS.id in save_text
    assert CATLIKE.id in save_text
    assert "Low" in save_text
    assert "Medkit" in save_text

    # Loaded into a fresh English session: the same character, in English.
    english = TestClient(create_app())
    english.get("/")
    loaded = english.post(
        "/characters/upload?open=true",
        files={"files": ("character.json", json.dumps(save), "application/json")},
    ).text
    assert "Character loaded." in loaded
    sheet = english.get("/character/sheet").text
    assert "<td>Pistols</td>" in sheet
    assert "Catlike" in sheet
    # And its own save is identical: locale never touched the saved data.
    assert json.loads(english.get("/character/save").text) == save


def test_the_german_sheet_translates_every_kind_of_name(german: None) -> None:
    client = TestClient(create_app())
    client.get("/")
    client.post("/ui/prefs/locale", data={"locale": "de-de"})
    _build(client)

    sheet = client.get("/character/sheet").text

    assert re.search(r"<h2>\s*Mensch\s*</h2>", sheet)
    assert "<td>Pistolen</td>" in sheet
    assert "Unterschicht" in sheet
    assert "A - Jeder Metatyp" in sheet
