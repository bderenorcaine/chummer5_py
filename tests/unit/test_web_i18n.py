"""WP101: the i18n key layer -- catalogs (`chummer5.data.lang`), lookup and fallback
(`chummer5.web.i18n`), the `_()` template global, the session locale, and the language picker.
No page string is converted here (that is WP102); the title bar's own picker labels are the only
`_()` calls, and they are enough to prove a page renders through the layer.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from chummer5.data.lang import (
    LEGACY_LANG_DIR,
    PROJECT_LANG_DIR,
    load_locale_strings,
    load_string_file,
    normalise_winforms_text,
)
from chummer5.web import i18n, prefs
from chummer5.web.app import create_app
from chummer5.web.catalogs import TEMPLATES_DIR

STUB_LOCALE = prefs.Locale("xx-test", "x-test", "Testisch")
STUB_CATALOG = {"Web_Prefs_Theme": "Thema", "Web_Prefs_Language": "Sprache"}


@pytest.fixture
def stub_locale(monkeypatch: pytest.MonkeyPatch) -> None:
    """Offer a made-up locale whose two-entry catalog covers only the picker labels."""
    monkeypatch.setitem(i18n.CATALOGS, STUB_LOCALE.tag, STUB_CATALOG)
    monkeypatch.setattr(prefs, "LOCALES", (*prefs.LOCALES, STUB_LOCALE))
    monkeypatch.setitem(prefs.LOCALES_BY_TAG, STUB_LOCALE.tag, STUB_LOCALE)


def test_a_page_renders_through_a_non_english_catalog(stub_locale: None) -> None:
    client = TestClient(create_app())
    assert "Theme" in client.get("/").text

    response = client.post("/ui/prefs/locale", data={"locale": STUB_LOCALE.tag})
    html = client.get("/").text

    assert response.headers["HX-Refresh"] == "true"
    assert "HX-Trigger" not in response.headers  # not a chargen change
    assert '<html lang="x-test">' in html
    assert re.search(r"\s+Thema\s+<select name=\"theme\"", html)
    assert re.search(r"\s+Sprache\s+<select name=\"locale\"", html)
    assert re.search(r'<option value="xx-test" lang="x-test"\s+selected>Testisch</option>', html)


def test_a_key_missing_from_the_locale_falls_back_to_english(stub_locale: None) -> None:
    # The stub has no theme names: those render in English, silently.
    assert i18n.translate(STUB_LOCALE.tag, "Web_Theme_Sketch") == "Sketch"
    assert i18n.translate(STUB_LOCALE.tag, "Web_Prefs_Theme") == "Thema"


def test_an_unknown_key_renders_a_visible_marker_and_logs(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING, logger="chummer5.web.i18n"):
        text = i18n.translate("en-us", "Web_No_Such_Key")

    assert text == "⟦Web_No_Such_Key⟧"
    assert "Web_No_Such_Key" in caplog.text


def test_placeholders_named_and_positional(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(
        i18n.CATALOGS,
        "xx-test",
        {"Named": "{remaining} of {budget} left", "Positional": "{1} before {0}"},
    )

    assert i18n.translate("xx-test", "Named", remaining=3, budget=7) == "3 of 7 left"
    assert i18n.translate("xx-test", "Positional", "a", "b") == "b before a"


def test_a_mismatched_placeholder_shows_the_raw_text_rather_than_crashing(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setitem(i18n.CATALOGS, "xx-test", {"Named": "{remaining} left"})

    with caplog.at_level(logging.WARNING, logger="chummer5.web.i18n"):
        assert i18n.translate("xx-test", "Named", other=1) == "{remaining} left"
    assert "cannot format" in caplog.text


def test_translated_text_is_html_escaped_in_a_template(monkeypatch: pytest.MonkeyPatch) -> None:
    """Rule 4 of src/chummer5/lang/README.md: a catalog text is plain text, never markup."""
    monkeypatch.setitem(i18n.CATALOGS, "en-us", {**i18n.catalog("en-us")})
    monkeypatch.setitem(i18n.CATALOGS["en-us"], "Web_Prefs_Theme", "<b>Theme</b>")  # type: ignore[index]

    html = TestClient(create_app()).get("/").text

    assert "&lt;b&gt;Theme&lt;/b&gt;" in html
    assert "<b>Theme</b>" not in html


def test_winforms_mnemonics_are_stripped_from_legacy_text() -> None:
    assert normalise_winforms_text("&Add && More") == "Add & More"
    assert normalise_winforms_text("Report a &Bug") == "Report a Bug"
    assert normalise_winforms_text("Rock & Roll") == "Rock & Roll"  # a spaced & is literal
    english = load_locale_strings("en-us")
    assert english["Tab_Vehicles"] == "Vehicles & Drones"
    assert "&" not in english["Tab_Gear"]


def test_the_legacy_layer_brings_real_translations() -> None:
    english = load_locale_strings("en-us")
    german = load_locale_strings("de-de")

    assert english["String_Karma"] == "Karma"
    assert german["Tab_Gear"] and german["Tab_Gear"] != english["Tab_Gear"]
    # A locale with no files at all is empty, not an error -- the fallback handles it.
    assert load_locale_strings("xx-none") == {}


def test_the_project_layer_overrides_the_legacy_one(tmp_path: Path) -> None:
    legacy, project = tmp_path / "legacy", tmp_path / "project"
    legacy.mkdir()
    project.mkdir()
    entry = "<string><key>{k}</key><text>{t}</text></string>"
    (legacy / "xx.xml").write_text(
        "<chummer><strings>"
        + entry.format(k="A", t="&amp;legacy")
        + entry.format(k="B", t="only legacy")
        + "</strings></chummer>"
    )
    (project / "xx.xml").write_text(
        "<chummer><strings>" + entry.format(k="A", t="Rock &amp;Roll") + "</strings></chummer>"
    )

    strings = load_locale_strings("xx", legacy, project)

    # The project text wins, and is literal: no mnemonic stripping on this layer.
    assert strings == {"A": "Rock &Roll", "B": "only legacy"}


def test_every_project_catalog_parses_and_owns_only_web_keys() -> None:
    catalogs = sorted(PROJECT_LANG_DIR.glob("*.xml"))
    assert [path.stem for path in catalogs] == ["en-us"]
    legacy_keys = set(load_string_file(LEGACY_LANG_DIR / "en-us.xml"))
    for path in catalogs:
        keys = load_string_file(path)  # raises on malformed XML
        assert all(key.startswith("Web_") for key in keys), path.name
        assert not set(keys) & legacy_keys, path.name


def test_every_literal_key_a_template_uses_exists_in_english() -> None:
    english = load_locale_strings("en-us")
    used = {
        key
        for path in Path(TEMPLATES_DIR).glob("*.html")
        for key in re.findall(r"""_\(\s*["']([A-Za-z0-9_]+)["']""", path.read_text())
    }
    assert used, "no _() call found -- the regex is stale"
    assert used - set(english) == set()


def test_every_offered_theme_label_has_a_key() -> None:
    english = load_locale_strings("en-us")
    for theme in prefs.THEMES:
        assert theme.label_key in english


def test_an_unknown_locale_is_rejected() -> None:
    client = TestClient(create_app())
    client.get("/")

    assert client.post("/ui/prefs/locale", data={"locale": "de-de"}).status_code == 422
    assert '<html lang="en-US">' in client.get("/").text
