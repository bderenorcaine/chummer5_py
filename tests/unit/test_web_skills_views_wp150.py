"""WP150 (Phase Z): the Skills page's Filtered and Rated views and its narrow-width dropdown. The
narrowing itself is client-side (`static/app.js`, see the WP150 worklog's browser checklist); this
pins what the script relies on. See `spec/plan/phase-z-page-redesigns.md`, "Redesign 4"."""

from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient

from chummer5.data.metatypes import load_metatypes
from chummer5.data.priorities import load_priorities
from chummer5.data.skills import load_skills
from chummer5.engine.character import metatype_choices
from chummer5.engine.skills import exotic_skill_key
from chummer5.web.app import create_app
from chummer5.web.shell import SKILLS_TABS

METATYPES = load_metatypes()
PRIORITIES = load_priorities()
SKILLS = load_skills()
BY_NAME = {s.name: s for s in SKILLS}
PISTOLS = BY_NAME["Pistols"]
EXOTIC_RANGED = BY_NAME["Exotic Ranged Weapon"]
HTMX = {"HX-Request": "true"}


def _confirm(client: TestClient) -> None:
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
            "attributes_letter": "B",
            "skills_letter": "C",
            "resources_letter": "D",
            "talent_letter": "E",
            "metatype_id": human.metatype.id,
        },
    )


def _sections(html: str) -> dict[str, str]:
    """Each panel's opening tag, by slug, in document order."""
    found = re.findall(r'(<section\s[^>]*data-skills-panel="([a-z]+)"[^>]*>)', html)
    return {slug: tag for tag, slug in found}


def _with_picks(client: TestClient) -> None:
    client.post(
        "/ui/skills",
        data={
            f"skill_{PISTOLS.id}": "2",
            "exotic_new_skill": EXOTIC_RANGED.id,
            "exotic_new_specific": "Flamethrower",
            "exotic_new_points": "1",
        },
    )
    client.post(
        "/ui/knowledge",
        data={
            "knowledge_name_0": "Corporations",
            "knowledge_category_0": "Street",
            "knowledge_rating_0": "1",
        },
    )


@pytest.mark.parametrize("tab", ["filtered", "rated"])
def test_the_views_show_every_section_but_group_under_its_heading(tab: str) -> None:
    client = TestClient(create_app())
    _confirm(client)
    _with_picks(client)
    html = client.get(f"/ui/page/skills/{tab}", headers=HTMX).text

    sections = _sections(html)
    in_view = [slug for slug, opening in sections.items() if "data-skills-view" in opening]
    assert in_view == [
        "combat",
        "physical",
        "social",
        "technical",
        "vehicle",
        "magical",
        "special",
        "knowledge",
    ]
    assert all(" hidden" not in sections[slug] for slug in in_view)
    assert " hidden" in sections["group"] and "data-skills-view" not in sections["group"]
    assert " hidden" in sections["resonance"]  # no rows to show
    headings = re.findall(r'<h2 class="skills-panel__heading">([^<]+)</h2>', html)
    assert headings == [
        "Combat",
        "Physical",
        "Social",
        "Technical",
        "Vehicle",
        "Magical",
        "Special",
        "Knowledge",
    ]
    assert re.search(r'<div id="knowledge-skills"[^>]*data-skills-tab="' + tab + '">', html)


def test_rows_carry_what_the_script_narrows_by() -> None:
    client = TestClient(create_app())
    _confirm(client)
    _with_picks(client)
    html = client.get("/ui/page/skills/rated", headers=HTMX).text

    assert f'data-skill-key="{PISTOLS.id}" data-skill-name="pistols" data-skill-rating="2"' in html
    flamethrower = exotic_skill_key(EXOTIC_RANGED.id, "Flamethrower")
    exotic = re.search(rf'<tr data-skill-key="x{flamethrower.encode().hex()}"[^>]*>', html)
    assert exotic is not None
    assert 'data-skill-name="exotic ranged weapon flamethrower"' in exotic.group(0)
    assert 'data-skill-key="knowledge-0" data-skill-name="corporations" data-skill-rating="1"' in (
        html
    )


def test_the_filter_field_is_on_the_filtered_tab_only_and_outside_the_form() -> None:
    client = TestClient(create_app())
    _confirm(client)
    filtered = client.get("/ui/page/skills/filtered", headers=HTMX).text
    field = re.search(r'<input\s[^>]*id="skill-filter"[^>]*>', filtered, re.S)
    assert field is not None
    assert "name=" not in field.group(0)  # never posted
    fragment = filtered[filtered.index('id="skill-allocation"') :]
    assert fragment.index('id="skill-filter"') < fragment.index("<form")
    assert "Filter skills" in filtered
    for tab in ("combat", "rated", "knowledge"):
        assert 'id="skill-filter"' not in client.get(f"/ui/page/skills/{tab}", headers=HTMX).text


@pytest.mark.parametrize("tab", ["filtered", "rated"])
def test_both_forms_keep_the_view_across_their_autosaves(tab: str) -> None:
    client = TestClient(create_app())
    _confirm(client)
    skills = client.post("/ui/skills", data={"skills_tab": tab, f"skill_{PISTOLS.id}": "1"}).text
    assert 'data-skills-tab="' + tab + '"' in skills
    assert "data-skills-view" in _sections(skills)["combat"]

    knowledge = client.post("/ui/knowledge", data={"skills_tab": tab}).text
    assert f'<input type="hidden" name="skills_tab" value="{tab}" />' in knowledge
    assert "data-skills-view" in knowledge and "skills-panel__heading" in knowledge
    # Anything else is the Knowledge tab itself.
    plain = client.post("/ui/knowledge", data={"skills_tab": "combat"}).text
    assert '<input type="hidden" name="skills_tab" value="knowledge" />' in plain
    assert "data-skills-view" not in plain


def test_the_dropdown_lists_every_tab_with_the_current_one_selected() -> None:
    client = TestClient(create_app())
    _confirm(client)
    html = client.get("/ui/page/skills/social", headers=HTMX).text

    select = re.search(r'<select\s[^>]*id="skills-tab-select".*?</select>', html, re.S)
    assert select is not None
    options = re.findall(r"<option\s+value=\"([^\"]+)\"([^>]*)>([^<]+)</option>", select.group(0))
    assert [value for value, _, _ in options] == [f"/ui/page/skills/{t.slug}" for t in SKILLS_TABS]
    assert [label for _, _, label in options][-2:] == ["Filtered", "Rated"]
    flags = {value.rsplit("/", 1)[1]: attrs for value, attrs, _ in options}
    assert [slug for slug, attrs in flags.items() if "selected" in attrs] == ["social"]
    assert [slug for slug, attrs in flags.items() if "disabled" in attrs] == ["resonance"]
    # The counters' narrow row repeats all four.
    row = re.search(r'<dl class="skills-counters skills-counters--row">.*?</dl>', html, re.S)
    assert row is not None
    assert re.findall(r"<abbr[^>]*>([^<]+)</abbr>", row.group(0)) == ["S", "G", "Ka", "Kn"]


def test_the_script_has_the_hooks_the_markup_relies_on() -> None:
    script = TestClient(create_app()).get("/static/app.js").text
    assert 'querySelectorAll("section[data-skills-view]")' in script
    assert 'getAttribute("data-skills-tab")' in script
    assert 'id === "skills-tab-select"' in script
    assert "row.dataset.skillKey" in script and "row.dataset.skillName" in script
    css = TestClient(create_app()).get("/static/app.css").text
    assert "container-type: inline-size" in css
    assert "@container (max-width: 41rem)" in css
