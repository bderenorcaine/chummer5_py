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
        # A literal key is the whole first argument; `_("Web_X_" ~ value)` is a computed one.
        for key in re.findall(r"""_\(\s*["']([A-Za-z0-9_]+)["']\s*[,)]""", path.read_text())
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


# --- WP102: keys built at render time, and the Python-side message types -------------------------


def test_every_computed_key_family_is_complete() -> None:
    """Templates build some keys from a value (`"Web_MagicType_" ~ character.magic_type`), which
    the literal-key test above cannot see; each family is checked against its value set here."""
    from chummer5.data.knowledge import KNOWLEDGE_CATEGORIES
    from chummer5.data.skills import load_skills
    from chummer5.data.traditions import load_traditions
    from chummer5.engine.build_method import PRIORITY_BUILD_METHOD, SUM_TO_TEN_BUILD_METHOD
    from chummer5.engine.character import ALLOCATABLE_ATTRIBUTES
    from chummer5.engine.magic import OFFERED_TALENT_CODENAMES
    from chummer5.web.catalogs import MVP_POWERS

    english = load_locale_strings("en-us")
    keys = {f"Web_BuildMethod_{m}" for m in (PRIORITY_BUILD_METHOD, SUM_TO_TEN_BUILD_METHOD)}
    keys |= {f"Web_MagicType_{c}" for c in OFFERED_TALENT_CODENAMES if c != "Mundane"}
    codes = set(ALLOCATABLE_ATTRIBUTES) | {"MAG"}
    codes |= {skill.attribute for skill in load_skills()}
    codes |= {code for t in load_traditions() for code in t.drain_attributes}
    codes |= {category.linked_attribute for category in KNOWLEDGE_CATEGORIES}
    codes |= {
        code
        for power in MVP_POWERS
        for bonus in power.flat_bonuses
        for code in getattr(bonus, "attribute_options", ())
    }
    keys |= {f"String_Attribute{code}Short" for code in codes}
    assert keys - set(english) == set()


def test_every_key_the_shell_tables_hold_exists() -> None:
    from chummer5.web.shell import STEP_PAGES

    english = load_locale_strings("en-us")
    keys = set()
    for page in STEP_PAGES:
        keys |= {page.label_key, page.disabled_reason_key, page.heading_key, page.locked_note_key}
        for section in page.sections:
            keys |= {section.label_key, section.unavailable_reason_key}
    keys.discard(None)
    assert keys - set(english) == set()


def test_a_message_renders_its_params_and_nested_joins() -> None:
    message = i18n.Message.of(
        "Web_Stale_Lifestyle",
        breakdown=i18n.MessageJoin(
            (
                i18n.Message.of("Web_Stale_SpendGear", amount=100),
                i18n.Message.of("Web_Stale_SpendLifestyle", amount=200),
            ),
            "Web_List_Plus",
        ),
        total=300,
        letter="E",
        budget=250,
    )

    text = str(i18n.render_message("en-us", message))

    assert text.startswith("No longer fits since priorities were last confirmed: ")
    assert "gear (100) + lifestyle (200) spend 300" in text
    assert "priority E&#39;s nuyen budget of 250." in text  # escaped like any template value


def test_an_engine_string_passes_through_escaped() -> None:
    assert str(i18n.render_message("en-us", "a <b> & c")) == "a &lt;b&gt; &amp; c"


def test_markup_arguments_survive_but_plain_ones_are_escaped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from markupsafe import Markup

    monkeypatch.setitem(i18n.CATALOGS, "xx-test", {"K": "<{word}> costs {cost}"})

    rendered = i18n._markup_format(
        "K",
        i18n._lookup("xx-test", "K"),
        (),
        {"word": Markup("<strong>Capacity</strong>"), "cost": "<1>"},
    )

    assert str(rendered) == "&lt;<strong>Capacity</strong>&gt; costs &lt;1&gt;"


def test_plurals_pick_the_form_by_count() -> None:
    assert i18n.translate_plural("en-us", "Web_Sheet_Boxes", 1) == "1 box"
    assert i18n.translate_plural("en-us", "Web_Sheet_Boxes", 0) == "0 boxes"
    assert i18n.translate_plural("en-us", "Web_Sheet_Boxes", 10) == "10 boxes"


def test_every_plural_key_has_both_forms() -> None:
    english = set(load_locale_strings("en-us"))
    for key in english:
        for form, other in (("_One", "_Other"), ("_Other", "_One")):
            if key.endswith(form):
                assert key[: -len(form)] + other in english, key


def test_money_goes_through_one_formatter() -> None:
    assert i18n.format_nuyen("en-us", 50000) == "50000¥"
    for path in Path(TEMPLATES_DIR).glob("*.html"):
        # Every ¥ a template shows comes from the `nuyen` filter, never a literal.
        assert "¥" not in path.read_text(), path.name


@pytest.mark.parametrize("talent", ["Mundane", "Magician", "Adept"])
def test_no_page_renders_a_missing_key_marker(
    talent: str, caplog: pytest.LogCaptureFixture
) -> None:
    """Every page and tab, for each archetype, with a little of everything bought: nothing renders
    `⟦Key⟧` and nothing logs an i18n warning -- the end-to-end check behind the static ones."""
    from chummer5.data.metatypes import load_metatypes
    from chummer5.data.priorities import load_priorities
    from chummer5.data.skills import load_skills
    from chummer5.data.traditions import load_traditions
    from chummer5.engine.character import metatype_choices
    from chummer5.web.shell import STEP_PAGES

    priorities = load_priorities()
    human = next(
        c
        for c in metatype_choices(priorities.heritage["A"], load_metatypes())
        if c.metatype.name == "Human"
    ).metatype.id
    skills = {s.name: s.id for s in load_skills()}
    client = TestClient(create_app())
    with caplog.at_level(logging.WARNING, logger="chummer5.web.i18n"):
        pages = [client.get("/").text]  # before any character: every placeholder
        client.post(
            "/ui/priorities",
            data={
                "heritage_letter": "A",
                "talent_letter": "B",
                "attributes_letter": "C",
                "skills_letter": "D",
                "resources_letter": "E",
                "metatype_id": human,
            },
        )
        talent_data: dict[str, object] = {"talent_letter": "B", "talent_codename": talent}
        if talent == "Magician":
            hermetic = next(t for t in load_traditions() if t.name == "Hermetic")
            talent_data |= {
                "tradition_id": hermetic.id,
                "granted_skill_id": [skills["Spellcasting"], skills["Counterspelling"]],
            }
        elif talent == "Adept":
            talent_data |= {"granted_skill_id": [skills["Pistols"]]}
        client.post("/ui/talent", data=talent_data)
        client.post("/ui/lifestyle", data={"lifestyle_tier": "Low", "lifestyle_months": "30"})
        client.post("/ui/attributes", data={"attr_BOD": "99"})  # an error message, too
        for page in STEP_PAGES:
            if not page.enabled:
                continue
            pages.append(client.get(f"/ui/page/{page.slug}").text)
            for section in page.sections if page.tabbed else ():
                pages.append(client.get(f"/ui/page/{page.slug}/{section.slug}").text)
        pages.append(client.get("/ui/resource-panel").text)

    for html in pages:
        assert "⟦" not in html
    assert "i18n" not in caplog.text


def test_no_project_key_is_an_orphan() -> None:
    """Every `Web_*` key is used by some template or web module -- literally, as the base of an
    `_n()` pair, or through one of the computed families -- so dead keys cannot pile up for
    translators to translate for nothing."""
    # WP114: Home Ground's bonus names are `"Web_HomeGround_" ~ code` (_quality_choice_label.html).
    # WP115: Scorched's effects are `"Web_Scorched_" ~ code`, likewise.
    computed_prefixes = ("Web_BuildMethod_", "Web_MagicType_", "Web_HomeGround_", "Web_Scorched_")
    sources = "\n".join(
        path.read_text()
        for path in [
            *Path(TEMPLATES_DIR).glob("*.html"),
            *Path(TEMPLATES_DIR).parent.rglob("*.py"),
        ]
    )
    orphans = []
    for key in load_string_file(PROJECT_LANG_DIR / "en-us.xml"):
        base = re.sub(r"_(One|Other)$", "", key)
        if key.startswith(computed_prefixes) or f'"{base}"' in sources or f"'{base}'" in sources:
            continue
        orphans.append(key)
    assert orphans == []
