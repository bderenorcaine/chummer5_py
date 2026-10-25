"""WP150 (Phase Z): the Skills page's Filtered and Rated views and its narrow-width dropdown. The
narrowing itself is client-side (`static/app.js`, see the WP150 worklog's browser checklist); this
pins what the script relies on. See `spec/plan/phase-z-page-redesigns.md`, "Redesign 4"."""

from __future__ import annotations

import json
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


# --- Follow-up (user rulings, 2026-10-25): messages at the bottom, ratings-only views ----------


def _fragment(html: str, wrapper_id: str) -> str:
    """One fragment's own markup: from its wrapper to the next top-level sibling."""
    start = html.index(f'<div id="{wrapper_id}"')
    ends = [
        html.find(marker, start + 1)
        for marker in ('<div id="knowledge-skills"', '<div class="skills-footer">')
    ]
    return html[start : min(e for e in ends if e > 0)]


@pytest.mark.parametrize("tab", ["combat", "knowledge", "filtered", "rated"])
def test_the_messages_sit_after_every_section_on_every_tab(tab: str) -> None:
    client = TestClient(create_app())
    _confirm(client)
    _with_picks(client)
    # Make the active-skill spend stale: Skills D (22) can't hold the 25 points below.
    ungrouped = [s for s in SKILLS if s.skill_group is None and not s.exotic][:5]
    ungrouped = [s for s in ungrouped if s.category not in ("Magical Active", "Resonance Active")]
    points = dict(zip((s.id for s in ungrouped), (6, 6, 6, 6, 1), strict=False))
    client.post("/ui/skills", data={f"skill_{sid}": str(v) for sid, v in points.items()})
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
            "skills_letter": "D",
            "resources_letter": "C",
            "talent_letter": "E",
            "metatype_id": human.metatype.id,
        },
    )
    html = client.get(f"/ui/page/skills/{tab}", headers=HTMX).text

    footer = html.index('<div class="skills-footer">')
    assert html.index("No longer fits") > footer
    assert footer > html.rindex("</form>")  # after the Knowledge section too
    assert html.index('id="knowledge-messages"') > html.index('id="skill-messages"') > footer
    for wrapper in ("skill-allocation", "knowledge-skills"):
        assert 'class="warning"' not in _fragment(html, wrapper)


def test_each_post_refreshes_its_own_messages_out_of_band() -> None:
    client = TestClient(create_app())
    _confirm(client)
    skills = client.post(
        "/ui/skills", data={"skills_tab": "rated", f"skill_{PISTOLS.id}": "99"}
    ).text
    assert 'class="error"' not in skills[: skills.index('id="skill-messages"')]
    assert '<div id="skill-messages" class="skills-messages" hx-swap-oob="true">' in skills
    assert "knowledge-messages" not in skills

    knowledge = client.post(
        "/ui/knowledge",
        data={"skills_tab": "filtered", "knowledge_name_0": "X", "knowledge_category_0": "Nope"},
    ).text
    assert 'class="error"' not in knowledge[: knowledge.index('id="knowledge-messages"')]
    assert '<div id="knowledge-messages" class="skills-messages" hx-swap-oob="true">' in knowledge
    assert "skill-messages" not in knowledge

    # A page render carries the footer itself, not out-of-band copies.
    assert "hx-swap-oob" not in client.get("/ui/page/skills").text.split("skills-footer", 1)[1]


@pytest.mark.parametrize("tab", ["filtered", "rated"])
def test_the_views_only_change_ratings(tab: str) -> None:
    client = TestClient(create_app())
    _confirm(client)
    _with_picks(client)
    client.post(
        "/ui/knowledge",
        data={
            "knowledge_name_0": "Corporations",
            "knowledge_category_0": "Street",
            "knowledge_rating_0": "1",
            "knowledge_name_1": "English",
            "knowledge_category_1": "Language",
            "knowledge_native_1": "on",
        },
    )
    html = client.get(f"/ui/page/skills/{tab}", headers=HTMX).text

    assert "skills-add" not in html  # neither Add button
    assert (
        'id="exotic-skill-add"'
        not in client.post("/ui/skills", data={"skills_tab": tab, "exotic_add": "1"}).text
    )
    knowledge = _fragment(html, "knowledge-skills")
    assert len(re.findall(r"<tr data-skill-key=", knowledge)) == 2  # no blank row
    assert 'type="text" id="knowledge-name' not in knowledge
    assert "<select" not in knowledge  # no category dropdown
    assert '<input type="hidden" name="knowledge_name_0" value="Corporations" />' in knowledge
    assert '<input type="hidden" name="knowledge_category_1" value="Language" />' in knowledge
    assert '<input type="hidden" name="knowledge_native_1" value="on" />' in knowledge
    assert 'name="knowledge_rating_0"' in knowledge  # ratings stay editable

    # Posting the view's fields back (a rating change) keeps every row as it was.
    fields = dict(
        re.findall(r'<input type="hidden" name="(knowledge_[a-z]+_\d+)" value="([^"]*)"', knowledge)
    )
    client.post(
        "/ui/knowledge",
        data=fields | {"skills_tab": tab, "knowledge_rating_0": "2", "knowledge_karma_0": "0"},
    )
    saved = json.loads(client.get("/character/save").content)
    assert saved["knowledge_skill_picks"] == [
        {"name": "Corporations", "category": "Street", "rating": 2}
    ]
    assert saved["language_skill_picks"] == [{"name": "English", "rating": 0, "native": True}]
