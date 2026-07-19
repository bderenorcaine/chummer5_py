"""WP17's acceptance bar against the real corpus: "import Yeti-#ffffff2.chum5" through the web
layer specifically, not just `chummer5.io.legacy_import` directly (already covered by
`tests/integration/test_legacy_import_fixtures.py`). Cross-checks the imported character's sheet
values against the same `import_chum5` call made directly, so this test proves the web route is a
thin, faithful wrapper -- the same "UI is a thin layer over an already-correct engine" precedent
every prior WP in Phase F established.
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from tests.fixtures.mundane_chum5 import PRIORITY_BUILD_FIXTURE, mundane_fixture_path

from chummer5.data.lifestyle import load_lifestyles
from chummer5.data.metatypes import load_metatypes
from chummer5.data.priorities import load_priorities
from chummer5.data.qualities import load_qualities
from chummer5.data.skills import load_skills
from chummer5.engine.derived import (
    initiative_dice,
    initiative_value,
    mental_limit,
    physical_condition_monitor,
    physical_limit,
    social_limit,
    stun_condition_monitor,
)
from chummer5.io.legacy_import import import_chum5
from chummer5.web.app import create_app

METATYPES = load_metatypes()
PRIORITIES = load_priorities()
SKILLS = load_skills()
QUALITIES = load_qualities()
LIFESTYLES = load_lifestyles()


def test_importing_yeti_through_the_web_layer_matches_the_engine_directly() -> None:
    expected = import_chum5(
        mundane_fixture_path(PRIORITY_BUILD_FIXTURE),
        metatypes=METATYPES,
        priorities=PRIORITIES,
        skills=SKILLS,
        qualities=QUALITIES,
        lifestyles=LIFESTYLES,
    )
    expected_character = expected.built

    client = TestClient(create_app())
    client.get("/")
    with open(mundane_fixture_path(PRIORITY_BUILD_FIXTURE), "rb") as f:
        raw = f.read()

    response = client.post(
        "/character/import-chum5",
        files={"chum5_file": ("Yeti.chum5", raw, "application/octet-stream")},
    )

    assert response.status_code == 200
    assert "Character imported." in response.text
    for name in expected.dropped_qualities:
        assert name in response.text

    sheet = client.get("/character/sheet")
    assert "Human" in sheet.text
    assert f"{initiative_value(expected_character)} + " in sheet.text
    assert f"<td>{physical_limit(expected_character)}</td>" in sheet.text
    assert f"<td>{mental_limit(expected_character)}</td>" in sheet.text
    assert f"<td>{social_limit(expected_character)}</td>" in sheet.text
    assert f"{physical_condition_monitor(expected_character)} boxes" in sheet.text
    assert f"{stun_condition_monitor(expected_character)} boxes" in sheet.text
    assert f"{initiative_dice(expected_character)}D6" in sheet.text

    # The imported contacts/gear/lifestyle/nuyen also show up on the sheet, matching the
    # direct-import path.
    for contact in expected.built.contact_selection.contacts:
        assert contact.name in sheet.text
    assert expected.built.lifestyle_selection.tier.name in sheet.text
    assert (
        f"Nuyen remaining: {expected.built.resources_selection.nuyen_remaining} / "
        f"{expected.built.resources_selection.nuyen_budget}."
    ) in sheet.text


def test_importing_a_blocked_legacy_character_through_the_web_layer_reports_every_reason() -> None:
    """`Miko.chum5` (Magic enabled, otherwise clean except for her own non-SR5 tradition) is already
    used by `tests/integration/test_legacy_import_fixtures.py::test_rejects_miko_for_her_own_
    unresolvable_tradition` to isolate that blocking reason against real data (WP28 replaced the
    older blanket "Magic is enabled" rejection this test used to check for); this test confirms the
    same rejection surfaces correctly through the web route, not just the underlying `import_chum5`
    call. **WP29** wires `chummer5.web.app`'s import route up to the real `TRADITIONS`/`SPELLS`/
    `POWERS` catalogs (previously all defaulted to `()`, since no web feature consumed them before
    this WP) -- the assertion here is unchanged either way, since Miko's tradition (Shinto, `SG`-
    sourced) still isn't one of the real 2-entry SR5 catalog's names any more than it was resolvable
    against an empty one.
    """
    from tests.fixtures.mundane_chum5 import LEGACY_TESTFILES_DIR

    client = TestClient(create_app())
    client.get("/")
    with open(LEGACY_TESTFILES_DIR / "Miko.chum5", "rb") as f:
        raw = f.read()

    response = client.post(
        "/character/import-chum5",
        files={"chum5_file": ("Miko.chum5", raw, "application/octet-stream")},
    )

    assert response.status_code == 200
    assert "Cannot import" in response.text
    # Jinja2 autoescapes the quotes around 'Shinto' as HTML entities -- match the substring either
    # side of them instead of the literal apostrophes.
    assert "tradition" in response.text
    assert "Shinto" in response.text
    assert "is not one of the SR5-core traditions" in response.text
    # A blocked import must not leave a half-applied character behind.
    sheet = client.get("/character/sheet")
    assert "Confirm a metatype and priorities" in sheet.text
