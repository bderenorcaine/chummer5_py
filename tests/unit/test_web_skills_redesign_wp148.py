"""WP148 (Phase Z): the redesigned Skills page -- a strip of view tabs with four counters, one
panel per tab, the specialization toggle, Add Special Skills, and Arcana for Mundane characters.
See `spec/plan/phase-z-page-redesigns.md`, "Redesign 4"."""

from __future__ import annotations

import json
import re

import pytest
from fastapi.testclient import TestClient

from chummer5.data.metatypes import load_metatypes
from chummer5.data.priorities import load_priorities
from chummer5.data.skills import load_skills
from chummer5.data.traditions import load_traditions
from chummer5.engine.character import STARTING_KARMA, metatype_choices
from chummer5.engine.skills import exotic_skill_key
from chummer5.web.app import MUNDANE_SKILLS, create_app
from chummer5.web.routes.skills import dom_id
from chummer5.web.shell import SKILLS_TABS

METATYPES = load_metatypes()
PRIORITIES = load_priorities()
SKILLS = load_skills()
BY_NAME = {s.name: s for s in SKILLS}
HERMETIC = next(t for t in load_traditions() if t.name == "Hermetic")
ARCANA = BY_NAME["Arcana"]
PISTOLS = BY_NAME["Pistols"]
AUTOMATICS = BY_NAME["Automatics"]
EXOTIC_RANGED = BY_NAME["Exotic Ranged Weapon"]
FLAMETHROWER = exotic_skill_key(EXOTIC_RANGED.id, "Flamethrower")

HTMX = {"HX-Request": "true"}
PANEL_TABS = [t.slug for t in SKILLS_TABS if t.slug != "knowledge"]


def _confirm(client: TestClient, *, talent_letter: str = "E", skills_letter: str = "C") -> None:
    """Human at Heritage A; Skills C (28 points, 2 group points) unless told otherwise."""
    client.get("/")
    human = next(
        c
        for c in metatype_choices(PRIORITIES.heritage["A"], METATYPES)
        if c.metatype.name == "Human"
    )
    rest = [x for x in "BCDE" if x not in (talent_letter, skills_letter)]
    response = client.post(
        "/ui/priorities",
        data={
            "heritage_letter": "A",
            "talent_letter": talent_letter,
            "skills_letter": skills_letter,
            "attributes_letter": rest[0],
            "resources_letter": rest[1],
            "metatype_id": human.metatype.id,
        },
    )
    assert response.status_code == 200


def _saved(client: TestClient) -> dict[str, object]:
    return dict(json.loads(client.get("/character/save").content))


def _panel(html: str, slug: str) -> str:
    """The opening tag of one panel."""
    match = re.search(rf'<section\s[^>]*data-skills-panel="{slug}"[^>]*>', html)
    assert match is not None, slug
    return match.group(0)


def _shown_panels(html: str) -> list[str]:
    return [slug for slug in PANEL_TABS if " hidden" not in _panel(html, slug)]


def _panel_body(html: str, slug: str) -> str:
    start = html.index(_panel(html, slug))
    return html[start : html.index("</section>", start)]


def _counters(html: str) -> dict[str, tuple[str, bool]]:
    found = re.findall(
        r'<div class="skills-counter( skills-counter--over)?"[^>]*>\s*'
        r"<dt[^>]*><abbr[^>]*>([^<]+)</abbr></dt>\s*<dd[^>]*>([^<]+)</dd>",
        html,
    )
    return {label: (value, bool(over)) for over, label, value in found}


# --- The strip ------------------------------------------------------------------------------------


def test_the_strip_lists_the_tabs_in_order_with_resonance_disabled() -> None:
    client = TestClient(create_app())
    _confirm(client)
    html = client.get("/ui/page/skills", headers=HTMX).text

    strip = html[html.index('id="skills-tabs"') : html.index("</nav>", html.index("skills-tabs"))]
    assert re.findall(r'href="/ui/page/skills/([a-z]+)"', strip) == [
        t.slug for t in SKILLS_TABS if t.enabled
    ]
    resonance = re.search(r"<span\s[^>]*skills-tab--disabled[^>]*>", strip)
    assert resonance is not None
    assert 'aria-disabled="true"' in resonance.group(0)
    assert 'title="Technomancers are not supported yet."' in resonance.group(0)
    # The strip re-fetches itself for the tab it was rendered for.
    assert 'hx-get="/ui/tabs/skills?tab=combat"' in strip
    assert 'hx-trigger="chargen-changed from:body"' in strip


@pytest.mark.parametrize("slug", PANEL_TABS)
def test_each_tab_shows_its_own_panel_and_hides_the_rest(slug: str) -> None:
    client = TestClient(create_app())
    _confirm(client)
    html = client.get(f"/ui/page/skills/{slug}", headers=HTMX).text

    assert _shown_panels(html) == [slug]
    assert 'id="knowledge-skills" class="panel" hidden' in html
    current = re.search(r"<(?:a|span)\s[^>]*skills-tab--current[^>]*>", html)
    assert current is not None and 'aria-current="page"' in current.group(0)
    if slug != "resonance":  # a disabled <span>, reachable only by URL
        assert f'href="/ui/page/skills/{slug}"' in current.group(0)
    assert f'<input type="hidden" name="skills_tab" value="{slug}" />' in html


def test_the_knowledge_tab_shows_only_the_knowledge_fragment() -> None:
    client = TestClient(create_app())
    _confirm(client)
    html = client.get("/ui/page/skills/knowledge", headers=HTMX).text

    assert _shown_panels(html) == []
    assert '<div id="knowledge-skills" class="panel">' in html
    assert '<div class="skills-messages" hidden>' in html


def test_the_page_opens_on_combat_and_the_old_slug_aliases_it() -> None:
    client = TestClient(create_app())
    _confirm(client)

    assert _shown_panels(client.get("/ui/page/skills", headers=HTMX).text) == ["combat"]
    client.get("/ui/page/skills/social", headers=HTMX)
    # Not remembered beyond the URL: the nav opens the page on Combat again.
    assert _shown_panels(client.get("/ui/page/skills", headers=HTMX).text) == ["combat"]
    assert _shown_panels(client.get("/ui/page/skills/active", headers=HTMX).text) == ["combat"]
    full = client.get("/ui/page/skills/group").text
    assert full.lstrip().lower().startswith("<!doctype html>")
    assert _shown_panels(full) == ["group"]
    assert client.get("/ui/page/skills/nope").status_code == 404


def test_the_counters_show_remaining_over_budget_and_follow_a_change() -> None:
    client = TestClient(create_app())
    _confirm(client)
    budget = PRIORITIES.skills["C"]

    counters = _counters(client.get("/ui/page/skills", headers=HTMX).text)
    assert list(counters) == ["S", "G", "Ka", "Kn"]
    assert counters["S"] == (f"{budget.skills}/{budget.skills}", False)
    assert counters["G"] == (f"{budget.skill_groups}/{budget.skill_groups}", False)
    assert counters["Ka"] == (f"{STARTING_KARMA}/{STARTING_KARMA}", False)
    assert counters["Kn"][0].split("/")[0] == counters["Kn"][0].split("/")[1]

    client.post(
        "/ui/skills",
        data={f"skill_{PISTOLS.id}": "3", f"karma_skill_{PISTOLS.id}": "1", "group_Athletics": "1"},
    )
    counters = _counters(client.get("/ui/tabs/skills?tab=social").text)
    assert counters["S"] == (f"{budget.skills - 3}/{budget.skills}", False)
    assert counters["G"] == (f"{budget.skill_groups - 1}/{budget.skill_groups}", False)
    assert counters["Ka"] == (f"{STARTING_KARMA - 8}/{STARTING_KARMA}", False)  # 3->4: 4 x 2


def test_an_overspent_counter_is_highlighted() -> None:
    client = TestClient(create_app())
    _confirm(client, skills_letter="C")
    ungrouped = [s for s in MUNDANE_SKILLS if s.skill_group is None and not s.exotic][:5]
    client.post(
        "/ui/skills",
        data={f"skill_{s.id}": str(v) for s, v in zip(ungrouped, (6, 6, 6, 6, 1), strict=True)},
    )
    _confirm(client, skills_letter="D")  # 22 points: the 25 spent no longer fit

    counters = _counters(client.get("/ui/tabs/skills").text)
    assert counters["S"] == ("-3/22", True)
    assert counters["G"][1] is False


def test_the_strip_refresh_keeps_its_tab_and_rejects_unknown_ones() -> None:
    client = TestClient(create_app())
    _confirm(client)
    strip = client.get("/ui/tabs/skills?tab=vehicle").text
    assert "skills-tab--current" in strip[strip.index("/ui/page/skills/vehicle") - 300 :][:400]
    assert 'hx-get="/ui/tabs/skills?tab=vehicle"' in strip
    assert 'hx-get="/ui/tabs/skills?tab=combat"' in client.get("/ui/tabs/skills?tab=x").text


# --- Panels ---------------------------------------------------------------------------------------


def test_the_magical_tab_holds_only_arcana_for_a_mundane_character_who_can_buy_it() -> None:
    client = TestClient(create_app())
    _confirm(client)
    html = client.get("/ui/page/skills/magical", headers=HTMX).text

    body = _panel_body(html, "magical")
    assert re.findall(r'name="skill_([^"]+)"', body) == [ARCANA.id]

    response = client.post("/ui/skills", data={f"skill_{ARCANA.id}": "2"})
    assert "error" not in response.text
    assert _saved(client)["skill_points"] == {ARCANA.id: 2}


def test_an_awakened_character_sees_every_magical_skill_in_name_order() -> None:
    client = TestClient(create_app())
    _confirm(client, talent_letter="B", skills_letter="C")
    spellcasting, counterspelling = BY_NAME["Spellcasting"], BY_NAME["Counterspelling"]
    client.post(
        "/ui/talent",
        data={
            "talent_letter": "B",
            "talent_codename": "Magician",
            "tradition_id": HERMETIC.id,
            "granted_skill_id": [spellcasting.id, counterspelling.id],
        },
    )
    body = _panel_body(client.get("/ui/page/skills/magical", headers=HTMX).text, "magical")
    ids = re.findall(r'name="skill_([^"]+)"', body)
    names = [s.name for s in SKILLS if s.id in ids]
    assert ARCANA.id in ids and spellcasting.id in ids
    order = {s.id: s.name for s in SKILLS}
    assert [order[i] for i in ids] == sorted(names)


def test_the_resonance_panel_explains_itself() -> None:
    client = TestClient(create_app())
    _confirm(client)
    body = _panel_body(client.get("/ui/page/skills/resonance", headers=HTMX).text, "resonance")
    assert "Technomancers are not supported yet." in body
    assert "<input" not in body


def test_the_group_panel_lists_each_groups_components() -> None:
    client = TestClient(create_app())
    _confirm(client)
    body = _panel_body(client.get("/ui/page/skills/group", headers=HTMX).text, "group")

    members = [s.name for s in SKILLS if s.skill_group == "Firearms"]
    assert f"<td>{', '.join(members)}</td>" in body
    assert "Group Points" in body and 'name="group_Firearms"' in body
    assert 'name="karma_group_Firearms"' in body
    assert "Arcana" not in body  # no group


def test_exotic_skills_live_on_the_special_tab_only() -> None:
    client = TestClient(create_app())
    _confirm(client)
    client.post(
        "/ui/skills",
        data={
            "exotic_new_skill": EXOTIC_RANGED.id,
            "exotic_new_specific": "Flamethrower",
            "exotic_new_points": "2",
        },
    )
    html = client.get("/ui/page/skills/special", headers=HTMX).text
    assert f'name="skill_{FLAMETHROWER}"' in _panel_body(html, "special")
    assert f'name="skill_{FLAMETHROWER}"' not in _panel_body(html, "combat")
    assert "<td>Flamethrower</td>" in _panel_body(html, "special")
    assert f'name="skill_{EXOTIC_RANGED.id}"' not in html


def test_add_special_skills_reveals_the_add_row_and_filling_it_commits() -> None:
    client = TestClient(create_app())
    _confirm(client)
    html = client.get("/ui/page/skills/special", headers=HTMX).text
    special = _panel_body(html, "special")
    assert 'id="exotic-skill-add"' not in special
    button = re.search(r'<button\s[^>]*class="skills-add"[^>]*>', special, re.S)
    assert button is not None
    assert 'type="button"' in button.group(0)
    assert 'hx-post="/ui/skills"' in button.group(0)
    assert """hx-vals='{"exotic_add": "1"}'""" in button.group(0)

    added = client.post("/ui/skills", data={"exotic_add": "1", "skills_tab": "special"}).text
    assert 'id="exotic-skill-add"' in added
    # Choosing a skill (an autosave without points yet) keeps the row.
    kept = client.post(
        "/ui/skills", data={"exotic_new_skill": EXOTIC_RANGED.id, "exotic_new_points": "0"}
    ).text
    assert 'id="exotic-skill-add"' in kept

    done = client.post(
        "/ui/skills",
        data={
            "exotic_new_skill": EXOTIC_RANGED.id,
            "exotic_new_specific": "Flamethrower",
            "exotic_new_points": "3",
            "skills_tab": "special",
        },
    ).text
    assert _saved(client)["skill_points"] == {FLAMETHROWER: 3}
    assert 'id="exotic-skill-add"' not in done
    assert f'name="exotic_key" value="{FLAMETHROWER}"' in done


# --- The specialization toggle ------------------------------------------------------------------


def test_the_toggle_commits_a_points_or_a_karma_specialization() -> None:
    client = TestClient(create_app())
    _confirm(client)

    client.post("/ui/skills", data={f"skill_{PISTOLS.id}": "3", f"spec_{PISTOLS.id}": "Revolvers"})
    saved = _saved(client)
    assert saved["specializations"] == {PISTOLS.id: "Revolvers"}
    assert saved["karma_specializations"] == {}

    response = client.post(
        "/ui/skills",
        data={
            f"skill_{PISTOLS.id}": "3",
            f"spec_{PISTOLS.id}": "Revolvers",
            f"spec_karma_{PISTOLS.id}": "1",
        },
    ).text
    saved = _saved(client)
    assert saved["specializations"] == {}
    assert saved["karma_specializations"] == {PISTOLS.id: "Revolvers"}
    toggle = re.search(rf'<input[^>]*id="spec-karma-{PISTOLS.id}"[^>]*>', response, re.S)
    assert toggle is not None
    assert "checked" in toggle.group(0) and "disabled" not in toggle.group(0)
    assert 'role="switch"' in toggle.group(0)
    assert 'aria-label="Specialization paid with Karma"' in toggle.group(0)


def test_the_toggle_is_forced_to_karma_without_a_point_of_the_skills_own() -> None:
    client = TestClient(create_app())
    _confirm(client)

    page = client.get("/ui/page/skills", headers=HTMX).text
    toggle = re.search(rf'<input[^>]*id="spec-karma-{PISTOLS.id}"[^>]*>', page, re.S)
    assert toggle is not None
    assert "checked" in toggle.group(0) and "disabled" in toggle.group(0)
    assert f'<input type="hidden" name="spec_karma_{PISTOLS.id}" value="1" />' in page

    # Rated by Karma alone, with no toggle field posted at all: still the Karma map.
    client.post(
        "/ui/skills",
        data={f"karma_skill_{PISTOLS.id}": "1", f"spec_{PISTOLS.id}": "Revolvers"},
    )
    saved = _saved(client)
    assert saved["karma_specializations"] == {PISTOLS.id: "Revolvers"}
    assert saved["specializations"] == {}

    # A grouped skill's points belong to the group: Karma, breaking it (WP53).
    client.post(
        "/ui/skills", data={"group_Firearms": "2", f"spec_{AUTOMATICS.id}": "Assault Rifles"}
    )
    assert _saved(client)["karma_specializations"] == {AUTOMATICS.id: "Assault Rifles"}


def test_exotic_rows_have_no_toggle() -> None:
    client = TestClient(create_app())
    _confirm(client)
    client.post(
        "/ui/skills",
        data={
            "exotic_new_skill": EXOTIC_RANGED.id,
            "exotic_new_specific": "Flamethrower",
            "exotic_new_points": "2",
        },
    )
    special = _panel_body(client.get("/ui/page/skills/special", headers=HTMX).text, "special")
    assert "spec-toggle" not in special and "spec_" not in special


# --- Placeholders, ids, markup rules ------------------------------------------------------------


def test_each_text_field_has_its_own_placeholder() -> None:
    client = TestClient(create_app())
    _confirm(client)
    html = client.get("/ui/page/skills", headers=HTMX).text

    for skill in (PISTOLS, AUTOMATICS):
        field = re.search(rf'<input[^>]*id="spec-{skill.id}"[^>]*>', html, re.S)
        assert field is not None
        assert f'placeholder="e.g. {skill.specializations[0]}"' in field.group(0)

    # Bracketed suggestions are templates, not examples: Disenchanting has only "[Type]".
    assert "e.g. [" not in client.get("/ui/page/skills/magical", headers=HTMX).text

    added = client.post(
        "/ui/skills", data={"exotic_add": "1", "exotic_new_skill": EXOTIC_RANGED.id}
    ).text
    assert f'placeholder="e.g. {EXOTIC_RANGED.specializations[0]}"' in added
    melee = BY_NAME["Exotic Melee Weapon"]
    added = client.post("/ui/skills", data={"exotic_add": "1", "exotic_new_skill": melee.id}).text
    assert 'placeholder="e.g. Monofilament Whip"' in added


def test_every_control_has_a_stable_unique_id() -> None:
    client = TestClient(create_app())
    _confirm(client)
    client.post(
        "/ui/skills",
        data={
            "exotic_new_skill": EXOTIC_RANGED.id,
            "exotic_new_specific": "Flame|thrower x",
            "exotic_new_points": "2",
        },
    )
    html = client.post("/ui/skills", data={"exotic_add": "1"}).text
    html = client.post(
        "/ui/skills",
        data={
            "exotic_key": exotic_skill_key(EXOTIC_RANGED.id, "Flame|thrower x"),
            f"skill_{exotic_skill_key(EXOTIC_RANGED.id, 'Flame|thrower x')}": "2",
            "exotic_add": "1",
        },
    ).text

    controls = re.findall(r"<(?:input|select)\b(?![^>]*type=\"hidden\")[^>]*>", html, re.S)
    ids = [re.search(r'\bid="([^"]+)"', c) for c in controls]
    assert all(ids), [c for c, i in zip(controls, ids, strict=True) if not i]
    values = [i.group(1) for i in ids if i]
    assert len(values) == len(set(values))
    assert all(re.fullmatch(r"[A-Za-z0-9-]+", v) for v in values)
    assert f'id="group-{dom_id("Close Combat")}"' in html
    assert f'id="skill-{dom_id(exotic_skill_key(EXOTIC_RANGED.id, "Flame|thrower x"))}"' in html
    assert dom_id("a|b c") != dom_id("a|b-c") != dom_id("a-b c")


def test_no_submit_button_no_details_and_messages_after_the_panels() -> None:
    client = TestClient(create_app())
    _confirm(client)
    response = client.post("/ui/skills", data={f"skill_{PISTOLS.id}": "99"}).text

    assert "<details" not in response
    assert 'type="submit"' not in response
    assert "<button" in response  # Add Special Skills, which is type="button"
    assert response.index('class="error"') > response.rindex("</section>")
    assert response.index('class="error"') > response.index("</form>")


def test_skills_tab_survives_an_autosave() -> None:
    client = TestClient(create_app())
    _confirm(client)
    response = client.post(
        "/ui/skills", data={"skills_tab": "technical", f"skill_{PISTOLS.id}": "2"}
    ).text
    assert _shown_panels(response) == ["technical"]
    assert '<input type="hidden" name="skills_tab" value="technical" />' in response
    # A bad value falls back to the first tab instead of hiding everything.
    assert _shown_panels(client.post("/ui/skills", data={"skills_tab": "x"}).text) == ["combat"]


def test_the_knowledge_fragment_stays_visible_after_its_own_autosave() -> None:
    client = TestClient(create_app())
    _confirm(client)
    response = client.post("/ui/knowledge", data={}).text
    assert '<div id="knowledge-skills" class="panel">' in response


def test_validation_issues_link_to_the_tab_that_fixes_them() -> None:
    client = TestClient(create_app())
    _confirm(client)
    sheet = client.get("/ui/page/export", headers=HTMX).text
    assert 'href="/ui/page/skills/active"' in sheet  # unspent skill points -> Combat (alias)
    assert 'href="/ui/page/skills/group"' in sheet  # unspent group points -> Group
    assert 'href="/ui/page/skills/knowledge"' in sheet
