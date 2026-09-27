"""WP134: the Bio page -- the `Biography` model, the page, save round trip, legacy import, and the
sheet header."""

from __future__ import annotations

import json
import re

import pytest
from fastapi.testclient import TestClient
from tests.fixtures.mundane_chum5 import PRIORITY_BUILD_FIXTURE, mundane_fixture_path

from chummer5.data.metatypes import load_metatypes
from chummer5.data.priorities import load_priorities
from chummer5.engine.biography import MAX_FIELD_LENGTH, Biography, create_biography
from chummer5.engine.character import metatype_choices
from chummer5.io.legacy_chum5 import load_chum5
from chummer5.web.app import create_app

PRIORITIES = load_priorities()
METATYPES = load_metatypes()


def test_the_model() -> None:
    bio = create_biography({"name": "  Jane Doe ", "concept": "Face", "bogus": "ignored"})
    assert bio == Biography(name="Jane Doe", concept="Face")
    assert bio.display_name == "Jane Doe"
    assert Biography(name="Jane", street_name="Ghost").display_name == "Ghost"
    assert bio.to_dict() == {"name": "Jane Doe", "concept": "Face"}
    with pytest.raises(ValueError, match="at most"):
        create_biography({"notes": "x" * (MAX_FIELD_LENGTH + 1)})


def test_legacy_parse_fills_the_bio() -> None:
    legacy = load_chum5(mundane_fixture_path(PRIORITY_BUILD_FIXTURE))
    assert legacy.biography.street_name == "Yeti-#ffffff"


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


def test_the_bio_page_round_trips_through_a_save() -> None:
    client = TestClient(create_app())
    _new_character(client)
    page = client.get("/ui/page/bio").text
    assert 'name="street_name"' in page
    client.post(
        "/ui/bio",
        data={
            "name": "Jane Doe",
            "street_name": "Ghost",
            "concept": "Corporate infiltrator",
            "age": "27",
            "background": "Grew up in the Barrens.",
        },
    )
    sheet = re.sub(r"\s+", " ", client.get("/character/sheet").text)
    assert "<h2>Ghost</h2>" in sheet
    assert "Human — Corporate infiltrator" in sheet
    assert "Grew up in the Barrens." in sheet

    saved = client.get("/character/save").content
    assert json.loads(saved)["biography"] == {
        "name": "Jane Doe",
        "street_name": "Ghost",
        "concept": "Corporate infiltrator",
        "age": "27",
        "background": "Grew up in the Barrens.",
    }
    fresh = TestClient(create_app())
    fresh.get("/")
    fresh.post("/character/load", files={"save_file": ("c.json", saved, "application/json")})
    assert 'value="Ghost"' in fresh.get("/ui/page/bio").text
    assert json.loads(fresh.get("/character/save").content)["biography"]["name"] == "Jane Doe"


def test_a_priority_reconfirmation_keeps_the_bio() -> None:
    client = TestClient(create_app())
    _new_character(client)
    client.post("/ui/bio", data={"street_name": "Ghost"})
    _new_character(client)
    assert "<h2>Ghost</h2>" in client.get("/character/sheet").text


def test_a_legacy_alias_appears_on_the_sheet() -> None:
    # The plan's acceptance.
    client = TestClient(create_app())
    client.get("/")
    raw = mundane_fixture_path(PRIORITY_BUILD_FIXTURE).read_bytes()
    client.post(
        "/character/import-chum5",
        files={"chum5_file": ("Yeti.chum5", raw, "application/octet-stream")},
    )
    assert "<h2>Yeti-#ffffff</h2>" in client.get("/character/sheet").text
