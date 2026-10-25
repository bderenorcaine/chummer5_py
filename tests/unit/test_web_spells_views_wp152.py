"""WP152 (Phase Z, "Redesign 5"): the Spells sub-tab's Filtered and Known views and its narrow-width
dropdown, on WP150's view code made page-agnostic (`app.js`, keyed on `data-view-*` attributes).

The narrowing itself is client-side and on the worklog's manual browser checklist. These pin the
server contract the script reads: which sections render, what each row carries, where the filter
field sits, the dropdown, and the script and CSS hooks.
"""

from __future__ import annotations

import re

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

METATYPES = load_metatypes()
PRIORITIES = load_priorities()
SKILLS = load_skills()
SPELLS = load_spells()
HERMETIC = next(t for t in load_traditions() if t.name == "Hermetic")
SPELLCASTING = next(s for s in SKILLS if s.name == "Spellcasting")
COUNTERSPELLING = next(s for s in SKILLS if s.name == "Counterspelling")

HTMX = {"HX-Request": "true"}
CATEGORIES = ["Combat", "Detection", "Health", "Illusion", "Manipulation", "Rituals"]
ACID_STREAM = next(s for s in SPELLS if s.name == "Acid Stream")
HEAL = next(s for s in SPELLS if s.name == "Heal")


def _magician(client: TestClient) -> None:
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
            "talent_codename": "Magician",
            "tradition_id": HERMETIC.id,
            "granted_skill_id": [SPELLCASTING.id, COUNTERSPELLING.id],
        },
    )
    client.post("/ui/spells", data={"spell_id": [ACID_STREAM.id, HEAL.id]})


def _sections(html: str) -> dict[str, str]:
    """Each Spells panel's opening tag, by its slug."""
    found = re.findall(r'(<section class="spells-panel" data-spells-panel="([a-z]+)"[^>]*>)', html)
    return {slug: tag for tag, slug in found}


def _fragment(html: str) -> str:
    start = html.index('<div id="spell-selection"')
    messages = html.index('<div class="spells-messages">', start)
    return html[start : html.index("</div>", messages) + len("</div>")]


@pytest.mark.parametrize(("view", "mode"), [("filtered", "filter"), ("known", "fixed")])
def test_both_views_show_every_category_under_its_heading(view: str, mode: str) -> None:
    client = TestClient(create_app())
    _magician(client)

    html = _fragment(client.get(f"/ui/page/magic/spells/{view}", headers=HTMX).text)

    assert re.search(
        rf'<div id="spell-selection" class="spells-page" data-view-scope="spells" '
        rf'data-view-mode="{mode}">',
        html,
    )
    sections = _sections(html)
    assert list(sections) == [c.lower() for c in CATEGORIES]
    for tag in sections.values():
        assert "data-view-section" in tag and " hidden" not in tag
    headings = re.findall(r'<h2 class="view-heading">([^<]+)</h2>', html)
    assert headings == CATEGORIES
    assert f'name="spells_tab" value="{view}"' in html
    assert html.count('name="spell_id"') == len(SPELLS)


@pytest.mark.parametrize("view", ["combat", "rituals"])
def test_a_category_tab_is_no_view(view: str) -> None:
    client = TestClient(create_app())
    _magician(client)

    html = _fragment(client.get(f"/ui/page/magic/spells/{view}", headers=HTMX).text)

    assert 'data-view-scope="spells" data-view-mode="">' in html
    assert "data-view-section" not in html
    assert "view-heading" not in html


def test_rows_carry_what_the_script_narrows_by() -> None:
    client = TestClient(create_app())
    _magician(client)

    html = client.get("/ui/page/magic/spells/known", headers=HTMX).text

    assert (
        f'<tr data-view-key="{ACID_STREAM.id}" data-view-name="acid stream" data-view-kept="true">'
        in html
    )
    assert f'<tr data-view-key="{HEAL.id}" data-view-name="heal" data-view-kept="true">' in html
    rows = re.findall(
        r'<tr data-view-key="([^"]+)" data-view-name="[^"]*" data-view-kept="(\w+)">', html
    )
    assert len(rows) == len(SPELLS)
    assert {key for key, kept in rows if kept == "true"} == {ACID_STREAM.id, HEAL.id}


def test_unchecking_on_known_keeps_the_row_for_the_script() -> None:
    """The server renders every row on Known; the script keeps the set fixed on entry, so an
    unchecked spell stays listed until the player leaves the tab."""
    client = TestClient(create_app())
    _magician(client)

    html = client.post("/ui/spells", data={"spells_tab": "known", "spell_id": [HEAL.id]}).text

    assert 'data-view-mode="fixed"' in html
    assert (
        f'<tr data-view-key="{ACID_STREAM.id}" data-view-name="acid stream" data-view-kept="false">'
        in html
    )
    assert "data-view-section" in _sections(html)["combat"]


def test_the_filter_field_is_on_filtered_only_and_outside_the_form() -> None:
    client = TestClient(create_app())
    _magician(client)

    filtered = _fragment(client.get("/ui/page/magic/spells/filtered", headers=HTMX).text)

    field = re.search(r'<input\s[^>]*id="spell-filter"[^>]*>', filtered, re.S)
    assert field is not None
    assert "name=" not in field.group(0)  # never posted
    assert 'data-view-filter="spells"' in field.group(0)
    assert 'type="search"' in field.group(0)
    assert 'placeholder="Part of a spell&#39;s name"' in field.group(0)
    assert "Filter spells" in filtered
    # After the strip, before (outside) the form.
    assert filtered.index('id="spells-tabs"') < filtered.index('id="spell-filter"')
    assert filtered.index('id="spell-filter"') < filtered.index("<form")
    for view in ("combat", "known"):
        html = client.get(f"/ui/page/magic/spells/{view}", headers=HTMX).text
        assert 'id="spell-filter"' not in html


@pytest.mark.parametrize(("view", "mode"), [("filtered", "filter"), ("known", "fixed")])
def test_spells_tab_survives_an_autosave_on_both_views(view: str, mode: str) -> None:
    client = TestClient(create_app())
    _magician(client)

    html = client.post("/ui/spells", data={"spells_tab": view, "spell_id": [ACID_STREAM.id]}).text

    assert f'data-view-mode="{mode}"' in html
    assert f'name="spells_tab" value="{view}"' in html
    assert all("data-view-section" in tag for tag in _sections(html).values())
    assert ('id="spell-filter"' in html) == (view == "filtered")
    current = re.search(r"<a\s[^>]*view-tab--current[^>]*>", html)
    assert current is not None and f"/spells/{view}" in current.group(0)
    # An error re-render (more than the cap of 8) keeps the view too, messages at the bottom.
    html = client.post(
        "/ui/spells", data={"spells_tab": view, "spell_id": [s.id for s in SPELLS[:9]]}
    ).text
    assert f'data-view-mode="{mode}"' in html
    assert html.index("</form>") < html.index("Magic Rating x2 cap of 8")


@pytest.mark.parametrize("view", SPELL_VIEW_SLUGS)
def test_the_dropdown_lists_every_view_with_the_current_one_selected(view: str) -> None:
    client = TestClient(create_app())
    _magician(client)

    html = _fragment(client.get(f"/ui/page/magic/spells/{view}", headers=HTMX).text)

    select = re.search(r'<select\s[^>]*id="spells-tab-select"[^>]*>.*?</select>', html, re.S)
    assert select is not None
    assert 'class="view-tabs__select"' in select.group(0)
    assert 'aria-label="Spells sections"' in select.group(0)
    options = re.findall(r'<option\s+value="([^"]+)"([^>]*)>([^<]+)</option>', select.group(0))
    assert [value for value, _, _ in options] == [
        f"/ui/page/magic/spells/{slug}" for slug in SPELL_VIEW_SLUGS
    ]
    assert [label for _, _, label in options] == [*CATEGORIES, "Filtered", "Known"]
    assert [v.rsplit("/", 1)[1] for v, attrs, _ in options if "selected" in attrs] == [view]
    assert not any("disabled" in attrs for _, attrs, _ in options)
    # The narrow block is outside the form, so choosing a view never autosaves.
    assert html.index("</nav>") < html.index("<form")
    # The counters' narrow row repeats all three.
    row = re.search(r'<dl class="view-counters view-counters--row">.*?</dl>', html, re.S)
    assert row is not None
    assert re.findall(r"<abbr[^>]*>([^<]+)</abbr>", row.group(0)) == ["F", "C", "Ka"]


def test_a_view_url_requested_directly_renders_the_whole_shell() -> None:
    client = TestClient(create_app())
    _magician(client)

    response = client.get("/ui/page/magic/spells/known")

    assert response.status_code == 200
    assert 'id="app-shell"' in response.text
    assert 'data-view-mode="fixed"' in response.text


def test_the_script_and_css_have_the_hooks_the_markup_relies_on() -> None:
    client = TestClient(create_app())
    script = client.get("/static/app.js").text
    # Page-agnostic: keyed on the data attributes and shared classes, never on a page's ids.
    for hook in (
        "'[data-view-scope=\"' + scope + '\"]'",
        'getAttribute("data-view-mode")',
        "'input[data-view-filter=\"' + scope + '\"]'",
        'querySelectorAll("section[data-view-section]")',
        'querySelectorAll("tr[data-view-key]")',
        "row.dataset.viewName",
        "row.dataset.viewKept",
        'contains("view-tabs__select")',
        'closest(".view-tabs")',
    ):
        assert hook in script, hook
    for gone in ("spell-filter", "spells-tab-select", "skill-filter", "skills-tab-select"):
        assert gone not in script, gone
    css = client.get("/static/app.css").text
    spells = css[css.index("/* --- Spells page (WP151") :]
    assert "container-type: inline-size" in spells
    assert "@container (max-width: 32rem)" in spells
    assert ".spells-page .view-tabs__strip" in spells
    assert ".spells-page .view-tabs__narrow" in spells
    assert ".view-heading {" in css and ".view-filter {" in css
