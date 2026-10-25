"""WP151 (Phase Z, "Redesign 5"): the Magic page's Spells sub-tab in the Skills page's style -- the
shared view-tab strip with one tab per spell category, the F/C/Ka counters, one panel per
category, and the third URL level (`/ui/page/magic/spells/<view>`) the tabs link to.

`spec/plan/phase-z-page-redesigns.md`, "Redesign 5", has the rulings and defaults these pin.
"""

from __future__ import annotations

import re
from collections import Counter

import pytest
from fastapi.testclient import TestClient

from chummer5.data.metatypes import load_metatypes
from chummer5.data.priorities import load_priorities
from chummer5.data.skills import load_skills
from chummer5.data.spells import load_spells
from chummer5.data.traditions import load_traditions
from chummer5.engine.character import metatype_choices
from chummer5.web.app import create_app
from chummer5.web.routes.spells import SPELL_VIEW_SLUGS
from chummer5.web.shell import STEP_PAGES_BY_SLUG

METATYPES = load_metatypes()
PRIORITIES = load_priorities()
SKILLS = load_skills()
SPELLS = load_spells()
HERMETIC = next(t for t in load_traditions() if t.name == "Hermetic")
SPELLCASTING = next(s for s in SKILLS if s.name == "Spellcasting")
COUNTERSPELLING = next(s for s in SKILLS if s.name == "Counterspelling")

HTMX = {"HX-Request": "true"}
CATEGORIES = ("Combat", "Detection", "Health", "Illusion", "Manipulation", "Rituals")
CATEGORY_SLUGS = tuple(c.lower() for c in CATEGORIES)


def _confirm(client: TestClient, codename: str = "Magician", aspect: str | None = None) -> None:
    """A Human with Talent B (Magician: Magic 4, 7 free spells, so a known cap of 8)."""
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
    data: dict[str, str | list[str]] = {
        "talent_letter": "B",
        "talent_codename": codename,
        "tradition_id": HERMETIC.id,
    }
    if aspect is not None:
        data["magic_aspect"] = aspect
    else:
        data["granted_skill_id"] = [SPELLCASTING.id, COUNTERSPELLING.id]
    client.post("/ui/talent", data=data)


def _fragment(html: str) -> str:
    """The Spells fragment alone, out of a whole Magic page."""
    start = html.index('<div id="spell-selection"')
    messages = html.index('<div class="spells-messages">', start)
    return html[start : html.index("</div>", messages) + len("</div>")]


def _form(html: str) -> str:
    start = html.index('hx-post="/ui/spells"')
    return html[start : html.index("</form>", start)]


def _shown_panels(html: str) -> list[str]:
    return re.findall(r'<section class="spells-panel" data-spells-panel="([a-z]+)">', html)


def _counter(html: str, label: str) -> tuple[str, bool]:
    """A counter's `remaining/of`, and whether it carries the overspent modifier."""
    found = re.search(
        r'<div class="view-counter( view-counter--over)?">\s*'
        rf'<dt class="view-counter__label"><abbr title="[^"]*">{label}</abbr></dt>\s*'
        r'<dd class="view-counter__value">([^<]+)</dd>',
        html,
    )
    assert found is not None, label
    return found.group(2), found.group(1) is not None


def _strip(html: str) -> str:
    start = html.index('id="spells-tabs"')
    return html[start : html.index("</nav>", start)]


def test_the_views_are_the_spell_categories_in_catalog_order() -> None:
    assert SPELL_VIEW_SLUGS == (*CATEGORY_SLUGS, "filtered", "known")  # WP152 added the last two
    assert tuple(dict.fromkeys(s.category for s in SPELLS)) == CATEGORIES
    section = STEP_PAGES_BY_SLUG["magic"].section("spells")
    assert section is not None
    assert section.views == SPELL_VIEW_SLUGS
    assert section.view_key == "spells_tab"


def test_the_strip_lists_every_category_with_its_counters() -> None:
    client = TestClient(create_app())
    _confirm(client)

    strip = _strip(client.get("/ui/page/magic/spells", headers=HTMX).text)

    links = re.findall(r'<a\s[^>]*href="(/ui/page/magic/spells/[a-z]+)"[^>]*>', strip)
    assert links == [f"/ui/page/magic/spells/{slug}" for slug in SPELL_VIEW_SLUGS]
    labels = re.findall(r'<span class="view-tab__label">([^<]+)</span>', strip)
    assert labels == [*CATEGORIES, "Filtered", "Known"]
    for link in re.findall(r"<a\s[^>]*>", strip):
        assert 'hx-target="#page"' in link and 'hx-push-url="true"' in link
    # The counters sit in the strip: F and C at its start, Ka at its end. No re-fetch: the strip
    # is inside the fragment, so every autosave re-renders it.
    start = re.search(r'<dl class="view-counters view-counters--start">.*?</dl>', strip, re.S)
    end = re.search(r'<dl class="view-counters view-counters--end">.*?</dl>', strip, re.S)
    assert start is not None and end is not None
    assert re.findall(r"<abbr[^>]*>(\w+)</abbr>", start.group(0)) == ["F", "C"]
    assert re.findall(r"<abbr[^>]*>(\w+)</abbr>", end.group(0)) == ["Ka"]
    assert 'title="Free Spells"' in start.group(0) and 'title="Spell Limit"' in start.group(0)
    assert "hx-get" not in strip[: strip.index(">")]


@pytest.mark.parametrize("slug", CATEGORY_SLUGS)
def test_each_category_tab_shows_exactly_its_panel_with_every_checkbox_in_the_form(
    slug: str,
) -> None:
    client = TestClient(create_app())
    _confirm(client)

    html = client.get(f"/ui/page/magic/spells/{slug}", headers=HTMX).text

    assert _shown_panels(html) == [slug]
    current = re.search(r"<a\s[^>]*view-tab--current[^>]*>", html)
    assert current is not None and f'href="/ui/page/magic/spells/{slug}"' in current.group(0)
    assert 'aria-current="page"' in current.group(0)
    # The Magic page's own sub-tab strip still marks Spells.
    sub = re.search(r"<a\s[^>]*page-tabs__item--current[^>]*>", html)
    assert sub is not None and 'href="/ui/page/magic/spells"' in sub.group(0)
    form = _form(html)
    assert form.count('name="spell_id"') == len(SPELLS)
    assert re.search(rf'name="spells_tab" value="{slug}"', form)
    panel = re.search(rf'data-spells-panel="{slug}">(.*?)</section>', form, re.S)
    assert panel is not None
    category = CATEGORIES[CATEGORY_SLUGS.index(slug)]
    assert panel.group(1).count('name="spell_id"') == sum(s.category == category for s in SPELLS)


def test_the_bare_sub_tab_opens_on_combat() -> None:
    client = TestClient(create_app())
    _confirm(client)

    assert _shown_panels(client.get("/ui/page/magic/spells", headers=HTMX).text) == ["combat"]
    # Nothing remembers the view: the sub-tab opens on Combat again after visiting another.
    client.get("/ui/page/magic/spells/rituals", headers=HTMX)
    assert _shown_panels(client.get("/ui/page/magic/spells", headers=HTMX).text) == ["combat"]
    assert _shown_panels(client.get("/ui/page/magic", headers=HTMX).text) == ["combat"]


def test_a_view_url_requested_directly_renders_the_whole_shell() -> None:
    client = TestClient(create_app())
    _confirm(client)

    response = client.get("/ui/page/magic/spells/illusion")

    assert response.status_code == 200
    assert response.text.lstrip().lower().startswith("<!doctype html>")
    assert 'id="app-shell"' in response.text
    assert _shown_panels(response.text) == ["illusion"]
    assert response.headers["Vary"] == "HX-Request"


@pytest.mark.parametrize(
    "url",
    [
        "/ui/page/magic/spells/nosuch",
        "/ui/page/magic/talent/combat",  # a section with no views
        "/ui/page/magic/nosuch/combat",
        "/ui/page/skills/combat/combat",  # a view-tab page has no third level
        "/ui/page/attributes/attributes/combat",
    ],
)
def test_an_unknown_view_is_a_404(url: str) -> None:
    client = TestClient(create_app())
    _confirm(client)

    assert client.get(url, headers=HTMX).status_code == 404


def test_counters_follow_an_autosave() -> None:
    client = TestClient(create_app())
    _confirm(client)
    html = client.get("/ui/page/magic/spells", headers=HTMX).text
    assert _counter(html, "F") == ("7/7", False)
    assert _counter(html, "C") == ("8/8", False)
    assert _counter(html, "Ka") == ("25/25", False)

    html = client.post("/ui/spells", data={"spell_id": [s.id for s in SPELLS[:3]]}).text
    assert _counter(html, "F") == ("4/7", False)
    assert _counter(html, "C") == ("5/8", False)
    assert _counter(html, "Ka") == ("25/25", False)

    # Past the free spells, F stays at 0 (those are bought with Karma, not overspent) and Ka pays.
    html = client.post("/ui/spells", data={"spell_id": [s.id for s in SPELLS[:8]]}).text
    assert _counter(html, "F") == ("0/7", False)
    assert _counter(html, "C") == ("0/8", False)
    assert _counter(html, "Ka") == ("20/25", False)


def test_more_spells_than_the_cap_overspends_c_and_shows_the_error_at_the_bottom() -> None:
    client = TestClient(create_app())
    _confirm(client)

    html = client.post("/ui/spells", data={"spell_id": [s.id for s in SPELLS[:9]]}).text

    assert _counter(html, "C") == ("-1/8", True)
    assert _counter(html, "F") == ("0/7", False)
    error = html.index("Magic Rating x2 cap of 8")
    assert error > html.index("</form>")
    assert html.index('<div class="spells-messages">') < error
    # Nothing was committed, so Ka still shows the committed figure.
    assert _counter(html, "Ka") == ("25/25", False)


def test_a_sorcery_aspected_magician_has_no_free_spells() -> None:
    client = TestClient(create_app())
    _confirm(client, "Aspected Magician", aspect="Sorcery")

    html = client.get("/ui/page/magic/spells", headers=HTMX).text

    assert _counter(html, "F") == ("0/0", False)
    c_value, _over = _counter(html, "C")
    assert c_value.split("/")[0] == c_value.split("/")[1]  # nothing known yet
    html = client.post("/ui/spells", data={"spell_id": [SPELLS[0].id]}).text
    assert _counter(html, "F") == ("0/0", False)
    assert _counter(html, "Ka") == ("20/25", False)


@pytest.mark.parametrize("slug", ["detection", "rituals"])
def test_spells_tab_survives_an_autosave(slug: str) -> None:
    client = TestClient(create_app())
    _confirm(client)

    html = client.post("/ui/spells", data={"spells_tab": slug, "spell_id": [SPELLS[0].id]}).text

    assert _shown_panels(html) == [slug]
    assert f'name="spells_tab" value="{slug}"' in html
    current = re.search(r"<a\s[^>]*view-tab--current[^>]*>", html)
    assert current is not None and f"/spells/{slug}" in current.group(0)
    # An error re-render keeps the view too.
    html = client.post(
        "/ui/spells", data={"spells_tab": slug, "spell_id": [s.id for s in SPELLS[:9]]}
    ).text
    assert _shown_panels(html) == [slug]


@pytest.mark.parametrize("posted", ["", "nosuch", "rated"])  # Rated is a Skills view
def test_an_unknown_spells_tab_falls_back_to_combat(posted: str) -> None:
    client = TestClient(create_app())
    _confirm(client)

    html = client.post("/ui/spells", data={"spells_tab": posted}).text

    assert _shown_panels(html) == ["combat"]


def test_posting_the_same_spell_ids_commits_the_same_selection() -> None:
    client = TestClient(create_app())
    _confirm(client)
    chosen = [SPELLS[0].id, SPELLS[40].id, SPELLS[-1].id]  # three different categories

    html = client.post("/ui/spells", data={"spells_tab": "health", "spell_id": chosen}).text

    for spell in SPELLS:
        box = re.search(rf'<input[^>]*id="spell-{spell.id}"[^>]*>', html, re.S)
        assert box is not None
        assert ("checked" in box.group(0)) == (spell.id in chosen)
    sheet = client.get("/character/sheet").text
    for spell in SPELLS:
        if spell.id in chosen:
            assert spell.name in sheet
    # A page render shows the committed selection checked.
    page = client.get("/ui/page/magic/spells/combat", headers=HTMX).text
    assert re.search(rf'id="spell-{SPELLS[0].id}"[^>]*checked', page, re.S)


def test_no_details_no_submit_button_and_messages_after_the_form() -> None:
    client = TestClient(create_app())
    _confirm(client)

    for html in (
        _fragment(client.get("/ui/page/magic/spells", headers=HTMX).text),
        client.post("/ui/spells", data={"spell_id": [s.id for s in SPELLS[:9]]}).text,
    ):
        assert "<details" not in html
        assert "<summary" not in html
        assert "<button" not in html
        assert 'type="submit"' not in html
        assert "spell-known-filter" not in html
        assert html.index("</form>") < html.index('<div class="spells-messages">')
        # The strip comes before the form, outside it.
        assert html.index('id="spells-tabs"') < html.index('hx-post="/ui/spells"')


def test_ids_are_stable_and_unique() -> None:
    client = TestClient(create_app())
    _confirm(client)

    html = client.get("/ui/page/magic/spells", headers=HTMX).text

    ids = re.findall(r'\sid="([^"]+)"', html)
    duplicates = [i for i, n in Counter(ids).items() if n > 1]
    assert duplicates == []
    for spell in SPELLS:
        assert f'id="spell-{spell.id}"' in html


def test_the_fragment_stays_empty_for_a_character_who_casts_nothing() -> None:
    client = TestClient(create_app())
    _confirm(client, "Adept")

    html = client.get("/ui/page/magic/spells", headers=HTMX).text

    assert 'id="spells-tabs"' not in html
    assert 'name="spell_id"' not in html
    assert "Spells need a confirmed Magician Talent." in html


def test_the_old_spells_keys_and_filter_are_retired() -> None:
    from pathlib import Path

    import chummer5.web

    web = Path(chummer5.web.__file__).parent
    lang = (web.parent / "lang" / "en-us.xml").read_text()
    for key in (
        "Web_Spells_Chosen",
        "Web_Spells_KarmaCost",
        "Web_Spells_KarmaRemaining",
        "Web_Spells_Update",
        "Web_Spells_Show",
    ):
        assert f"<key>{key}" not in lang
    script = (web / "static" / "app.js").read_text()
    assert "applySpellFilter" not in script and "spell-known-filter" not in script
    assert "spellcat:" not in (web / "templates" / "_spell_selection.html").read_text()
