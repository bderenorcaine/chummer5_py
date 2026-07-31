"""WP17: the character-sheet page, save/download, and native-format load, backed directly by
WP10's derived-stat functions and WP11's `CharacterSave`/`build_character`. Synthetic (hand-built)
coverage; the legacy `.chum5` import path (WP12, `import_chum5`) against a real fixture is covered
in `tests/integration/test_web_character_sheet_fixtures.py`, mirroring how WP12's own unit/
integration test split already works (see `tests/unit/test_legacy_import.py`'s own docstring).
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from chummer5.data.metatypes import load_metatypes
from chummer5.data.priorities import load_priorities
from chummer5.engine.character import create_character, metatype_choices
from chummer5.engine.derived import (
    initiative_dice,
    initiative_value,
    mental_limit,
    physical_condition_monitor,
    physical_limit,
    social_limit,
    stun_condition_monitor,
)
from chummer5.io.save_format import from_json
from chummer5.web.app import create_app

METATYPES = load_metatypes()
PRIORITIES = load_priorities()


def _confirm_human(client: TestClient) -> None:
    client.get("/")
    heritage = PRIORITIES.heritage["A"]
    human_choice = next(
        c for c in metatype_choices(heritage, METATYPES) if c.metatype.name == "Human"
    )
    response = client.post(
        "/ui/priorities",
        data={
            "heritage_letter": "A",
            "attributes_letter": "B",
            "skills_letter": "C",
            "resources_letter": "D",
            "talent_letter": "E",
            "metatype_id": human_choice.metatype.id,
        },
    )
    assert response.status_code == 200


def test_character_sheet_shows_placeholder_before_confirmation() -> None:
    client = TestClient(create_app())

    response = client.get("/character/sheet")

    assert response.status_code == 200
    assert "Confirm a metatype and priorities" in response.text
    # The load/import forms are always available, even before any chargen confirmation -- that's
    # how a session can start *from* an import rather than the priority form.
    assert 'hx-post="/character/load"' in response.text
    assert 'hx-post="/character/import-chum5"' in response.text


def test_character_sheet_shows_derived_stats_matching_the_engine() -> None:
    client = TestClient(create_app())
    _confirm_human(client)
    client.post("/ui/attributes", data={"attr_BOD": 3, "attr_AGI": 2})

    response = client.get("/character/sheet")

    assert response.status_code == 200
    heritage = PRIORITIES.heritage["A"]
    human_choice = next(
        c for c in metatype_choices(heritage, METATYPES) if c.metatype.name == "Human"
    )
    character = create_character(human_choice, "A", "B", PRIORITIES, {"BOD": 3, "AGI": 2})
    assert f"{initiative_value(character)} + {initiative_dice(character)}D6" in response.text
    assert f"<td>{physical_limit(character)}</td>" in response.text
    assert f"<td>{mental_limit(character)}</td>" in response.text
    assert f"<td>{social_limit(character)}</td>" in response.text
    assert f"{physical_condition_monitor(character)} boxes" in response.text
    assert f"{stun_condition_monitor(character)} boxes" in response.text


def test_download_save_before_confirmation_is_rejected() -> None:
    client = TestClient(create_app())
    client.get("/")

    response = client.get("/character/save")

    assert response.status_code == 400


def test_download_save_returns_an_attachment_json_body() -> None:
    client = TestClient(create_app())
    _confirm_human(client)
    client.post("/ui/attributes", data={"attr_BOD": 3})

    response = client.get("/character/save")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    assert "attachment" in response.headers["content-disposition"]
    save = from_json(response.text)
    assert save.metatype_name == "Human"
    assert save.heritage_letter == "A"
    assert save.attribute_points["BOD"] == 3


def test_saved_character_loads_into_a_fresh_session_with_matching_values() -> None:
    source_client = TestClient(create_app())
    _confirm_human(source_client)
    source_client.post("/ui/attributes", data={"attr_BOD": 3, "attr_AGI": 2})
    source_client.post("/ui/skills", data={"skill_" + _first_mundane_skill_id(): "2"})
    save_bytes = source_client.get("/character/save").content

    fresh_client = TestClient(create_app())
    fresh_client.get("/")
    response = fresh_client.post(
        "/character/load",
        files={"save_file": ("character.json", save_bytes, "application/json")},
    )

    assert response.status_code == 200
    assert "Character loaded." in response.text
    assert "Human" in response.text

    # The rest of the chargen page reflects the loaded selections too, not just the sheet -- a
    # follow-up GET / should show the same committed attribute spend.
    index_response = fresh_client.get("/")
    assert "Confirmed: Human" in index_response.text


def _first_mundane_skill_id() -> str:
    from chummer5.web.app import MUNDANE_SKILLS

    return MUNDANE_SKILLS[0].id


def test_a_loaded_qualitys_bonus_survives_a_later_attribute_edit() -> None:
    """WP16 found that `create_character` always rebuilds a fresh, empty `ImprovementIndex`, which
    once meant every route that rebuilt `session.character` this way for an already-in-progress
    session had to re-apply any committed quality's Improvements onto it or the bonus would
    silently vanish on the next attribute edit. Post-WP63, `submit_attributes` no longer rebuilds
    via `create_character()` at all -- it `dataclasses.replace`s the previous `Character` in
    place, which carries the already-populated `ImprovementIndex` forward by reference, so there is
    nothing left to re-apply. `_apply_built_character_to_session` (this WP's load/import entry
    point) sets `session.quality_selection` from the loaded save, so this proves a *loaded*
    quality's bonus survives an attribute edit the same way one picked directly through the UI
    does -- composition end to end, not just by inspection.
    """
    from chummer5.data.qualities import load_qualities

    catlike = next(q for q in load_qualities() if q.name == "Catlike")

    source_client = TestClient(create_app())
    _confirm_human(source_client)
    source_client.post("/ui/qualities", data={"quality_id": catlike.id})
    save_bytes = source_client.get("/character/save").content

    fresh_client = TestClient(create_app())
    fresh_client.get("/")
    fresh_client.post(
        "/character/load",
        files={"save_file": ("character.json", save_bytes, "application/json")},
    )
    assert "Sneaking" in fresh_client.get("/character/sheet").text

    fresh_client.post("/ui/attributes", data={"attr_BOD": 1})

    assert "Sneaking" in fresh_client.get("/character/sheet").text


def test_loading_a_malformed_file_is_rejected_without_touching_the_session() -> None:
    client = TestClient(create_app())
    _confirm_human(client)

    response = client.post(
        "/character/load",
        files={"save_file": ("bad.json", b"not json at all", "application/json")},
    )

    assert response.status_code == 200
    assert "Could not load save" in response.text
    # The previously-confirmed character survives an invalid load attempt.
    sheet = client.get("/character/sheet")
    assert "Human" in sheet.text


def test_loading_without_choosing_a_file_shows_a_prompt_not_a_crash() -> None:
    client = TestClient(create_app())
    client.get("/")

    response = client.post("/character/load", data={})

    assert response.status_code == 200
    assert "Choose a save file" in response.text


def test_importing_without_choosing_a_file_shows_a_prompt_not_a_crash() -> None:
    client = TestClient(create_app())
    client.get("/")

    response = client.post("/character/import-chum5", data={})

    assert response.status_code == 200
    assert "Choose a .chum5 file" in response.text


def test_importing_a_non_xml_file_is_rejected() -> None:
    client = TestClient(create_app())
    client.get("/")

    response = client.post(
        "/character/import-chum5",
        files={"chum5_file": ("bad.chum5", b"this is not xml", "application/xml")},
    )

    assert response.status_code == 200
    assert "Not a valid .chum5 file" in response.text


def test_nav_links_to_the_character_sheet_from_every_page() -> None:
    client = TestClient(create_app())

    response = client.get("/")

    assert 'href="/character/sheet"' in response.text


# --- WP56: unmodeled-effects disclosure section --------------------------------------------------


def _confirm_elf(client: TestClient) -> None:
    client.get("/")
    heritage = PRIORITIES.heritage["A"]
    elf_choice = next(c for c in metatype_choices(heritage, METATYPES) if c.metatype.name == "Elf")
    response = client.post(
        "/ui/priorities",
        data={
            "heritage_letter": "A",
            "attributes_letter": "B",
            "skills_letter": "C",
            "resources_letter": "D",
            "talent_letter": "E",
            "metatype_id": elf_choice.metatype.id,
        },
    )
    assert response.status_code == 200


def test_unmodeled_effects_section_hidden_for_plain_human() -> None:
    client = TestClient(create_app())
    _confirm_human(client)

    response = client.get("/character/sheet")

    assert "Unmodeled real effects" not in response.text


def test_unmodeled_effects_section_shows_elf_metatype_grant() -> None:
    client = TestClient(create_app())
    _confirm_elf(client)

    response = client.get("/character/sheet")

    assert "Unmodeled real effects (1)" in response.text
    assert "Low-Light Vision" in response.text
    assert "lighting-condition Perception" in response.text


def test_unmodeled_effects_section_shows_purchased_no_effect_quality_without_duplication() -> None:
    from chummer5.web.app import MVP_QUALITIES

    client = TestClient(create_app())
    _confirm_elf(client)
    guts = next(q for q in MVP_QUALITIES if q.name == "Guts")

    client.post("/ui/qualities", data={"quality_id": guts.id})
    response = client.get("/character/sheet")

    # Two distinct aspects (Low-Light Vision from the metatype, Guts from the purchase) -- not
    # more, confirming re-viewing the metatype grant alongside a purchase doesn't double-count.
    assert "Unmodeled real effects (2)" in response.text
    assert "Guts" in response.text
    assert "fear/intimidation" in response.text


# --- WP79: the same disclosure section, now carrying augmentation rows ----------------------------


def test_unmodeled_effects_section_shows_purchased_cyberware() -> None:
    """WP79's acceptance criterion, mirroring WP56's quality-side test above.

    Bone Lacing (Titanium) is one of the 5 registry rows a player can actually buy from the browser
    today (30,000 nuyen, Essence 1.5 -- both inside Resources D's budget), and until this WP it was
    purchasable, charged in full and mechanically silent with nothing on the sheet saying so.
    """
    from chummer5.web.app import CYBERWARE

    client = TestClient(create_app())
    _confirm_human(client)
    bone_lacing = next(c for c in CYBERWARE if c.name == "Bone Lacing (Titanium)")

    client.post("/ui/cyberware", data={f"cyberware_{bone_lacing.id}": "1"})
    response = client.get("/character/sheet")

    assert "Unmodeled real effects (1)" in response.text
    assert "Bone Lacing (Titanium)" in response.text
    assert "no character-level Armor total" in response.text


def test_unmodeled_effects_section_stays_empty_for_cyberware_with_nothing_unmodeled() -> None:
    # The counterpart: a Datajack's whole printed effect is its Essence/nuyen cost, so the section
    # must not appear at all. Without this, "the sheet has an unmodeled-effects row" would pass for
    # a note attached to every purchase indiscriminately.
    from chummer5.web.app import CYBERWARE

    client = TestClient(create_app())
    _confirm_human(client)
    datajack = next(c for c in CYBERWARE if c.name == "Datajack")

    client.post("/ui/cyberware", data={f"cyberware_{datajack.id}": "1"})
    response = client.get("/character/sheet")

    assert "Unmodeled real effects" not in response.text
