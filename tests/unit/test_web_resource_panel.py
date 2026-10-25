"""WP99: the sidebar's remaining-resources panel (`chummer5.web.shell.resource_panel_context`,
`_resource_panel.html`, `GET /ui/resource-panel`).

The panel is a display of numbers that already exist, so the central assertion is agreement: its
Karma figure is `Character.karma_remaining` (Phase O's unified ledger) after spends on several
different pages, and its nuyen figure is the Resources pool less every spender's committed cost.
It refreshes itself on the same `chargen-changed` event as the step nav rather than riding out of
band on each step `POST` (see `spec/decisions-log.md`'s 2026-09-24 WP97 entry for why the WP99
entry's own "out-of-band swap" wording was superseded).
"""

from __future__ import annotations

import re

from fastapi.testclient import TestClient

from chummer5.data.metatypes import load_metatypes
from chummer5.data.priorities import load_priorities
from chummer5.data.skills import load_skills
from chummer5.data.traditions import load_traditions
from chummer5.engine.character import STARTING_KARMA, Character, metatype_choices
from chummer5.engine.resources import available_nuyen
from chummer5.web.app import LIFESTYLES, MUNDANE_SKILLS, MVP_QUALITIES, create_app
from chummer5.web.session import SESSION_COOKIE_NAME

METATYPES = load_metatypes()
PRIORITIES = load_priorities()
SKILLS = load_skills()
HERMETIC = next(t for t in load_traditions() if t.name == "Hermetic")
CATLIKE = next(q for q in MVP_QUALITIES if q.name == "Catlike")

HTMX = {"HX-Request": "true"}


def _human_id() -> str:
    heritage = PRIORITIES.heritage["A"]
    return next(
        c for c in metatype_choices(heritage, METATYPES) if c.metatype.name == "Human"
    ).metatype.id


def _confirm_human(client: TestClient, **letters: str) -> None:
    client.get("/")
    data = {
        "heritage_letter": "A",
        "talent_letter": "E",
        "attributes_letter": "B",
        "skills_letter": "C",
        "resources_letter": "D",
        "metatype_id": _human_id(),
        **letters,
    }
    assert client.post("/ui/priorities", data=data).status_code == 200


def _character(client: TestClient) -> Character:
    app = client.app
    session = app.state.sessions.get(client.cookies[SESSION_COOKIE_NAME])  # type: ignore[attr-defined]
    assert session is not None and session.character is not None
    return session.character


def _panel_rows(html: str) -> dict[str, tuple[int, int, bool]]:
    """`{label: (remaining, of, over)}` for every row of the panel in `html`."""
    panel = re.search(r'<section\s[^>]*id="resource-panel".*?</section>', html, re.S)
    assert panel is not None, "no resource panel"
    rows = {}
    for row in re.finditer(
        r'<div class="resource-panel__row( resource-panel__row--over)?">\s*'
        r'<dt class="resource-panel__label">([^<]+)</dt>\s*'
        r'<dd class="resource-panel__value">\s*(-?[\d.]+)¥?\s*'
        r'<span class="resource-panel__of">of (-?[\d.]+)',
        panel.group(0),
    ):
        rows[row.group(2)] = (
            int(float(row.group(3))),
            int(float(row.group(4))),
            bool(row.group(1)),
        )
    return rows


def test_before_a_character_exists_the_panel_says_what_unlocks_it() -> None:
    client = TestClient(create_app())

    html = client.get("/").text

    assert 'id="resource-panel"' in html
    assert "Confirm priorities and a metatype to see your budgets." in html
    assert _panel_rows(html) == {}


def test_the_panel_sits_in_the_sidebar_of_every_full_render_but_not_in_page_swaps() -> None:
    client = TestClient(create_app())
    _confirm_human(client)

    shell = client.get("/ui/page/attributes").text
    sidebar = re.search(r'<aside class="app-shell__sidebar">.*?</aside>', shell, re.S)
    assert sidebar is not None
    assert 'id="resource-panel"' in sidebar.group(0)
    # A nav click changes nothing the panel shows, so it doesn't ride along.
    assert 'id="resource-panel"' not in client.get("/ui/page/skills", headers=HTMX).text


def test_the_panel_refreshes_itself_on_every_successful_post() -> None:
    client = TestClient(create_app())
    html = client.get("/").text

    opening = re.search(r'<section\s[^>]*id="resource-panel"[^>]*>', html, re.S)
    assert opening is not None
    assert 'hx-get="/ui/resource-panel"' in opening.group(0)
    assert 'hx-trigger="chargen-changed from:body"' in opening.group(0)
    assert 'hx-swap="outerHTML"' in opening.group(0)
    for url in ("/ui/attributes", "/ui/qualities", "/ui/resources"):
        assert client.post(url, data={}).headers["HX-Trigger"] == "chargen-changed", url
    assert 'id="resource-panel"' in client.get("/ui/resource-panel").text


def test_the_panels_karma_is_the_unified_ledger_after_spends_on_three_pages() -> None:
    client = TestClient(create_app())
    _confirm_human(client)

    assert _panel_rows(client.get("/ui/resource-panel").text)["Karma"] == (
        STARTING_KARMA,
        STARTING_KARMA,
        False,
    )
    spends = (
        ("/ui/qualities", {"quality_id": CATLIKE.id}),  # Qualities page
        ("/ui/attributes", {"karma_attr_BOD": "1"}),  # Attributes page: 1 -> 2 is 10 Karma
        (
            "/ui/contacts",  # Contacts page: 12 points against CHA 1 x 3 free
            {"contact_name_0": "Fixer", "contact_connection_0": "6", "contact_loyalty_0": "6"},
        ),
    )
    previous = STARTING_KARMA
    for url, data in spends:
        client.post(url, data=data)
        remaining, of, _ = _panel_rows(client.get("/ui/resource-panel").text)["Karma"]
        assert remaining == _character(client).karma_remaining, url
        assert remaining < previous, f"{url} spent nothing -- the test would prove nothing"
        assert of == STARTING_KARMA
        previous = remaining


def test_the_panels_nuyen_is_the_pool_less_every_spender() -> None:
    client = TestClient(create_app())
    _confirm_human(client, resources_letter="B", attributes_letter="D")
    pool = available_nuyen("B", PRIORITIES)
    assert _panel_rows(client.get("/ui/resource-panel").text)["Nuyen"] == (pool, pool, False)

    low = next(tier for tier in LIFESTYLES if tier.name == "Low")
    client.post("/ui/lifestyle", data={"lifestyle_tier": "Low", "lifestyle_months": "2"})
    client.post("/ui/resources", data={"karma_converted": "3"})

    character = _character(client)
    pool = available_nuyen("B", PRIORITIES, 3)
    assert character.nuyen_spent == 2 * low.monthly_cost
    remaining, of, _ = _panel_rows(client.get("/ui/resource-panel").text)["Nuyen"]
    assert (remaining, of) == (pool - 2 * low.monthly_cost, pool)
    # Converting Karma is a Karma spend too (WP89): the Karma row moves with it.
    assert _panel_rows(client.get("/ui/resource-panel").text)["Karma"][0] == STARTING_KARMA - 3


def test_the_point_pools_are_the_numbers_each_step_shows_on_its_own_page() -> None:
    client = TestClient(create_app())
    _confirm_human(client)
    skill = next(s for s in MUNDANE_SKILLS if s.skill_group is None)
    client.post("/ui/attributes", data={"attr_BOD": "3", "attr_EDG": "1"})
    client.post("/ui/skills", data={f"skill_{skill.id}": "4"})

    rows = _panel_rows(client.get("/ui/resource-panel").text)
    budget = PRIORITIES.attributes["B"].points
    assert rows["Attribute Points"] == (budget - 3, budget, False)
    special = _character(client).special_attribute_points
    assert rows["Special Attribute Points"] == (special - 1, special, False)
    skills = PRIORITIES.skills["C"]
    assert rows["Skill Points"] == (skills.skills - 4, skills.skills, False)
    assert rows["Skill Group Points"] == (skills.skill_groups, skills.skill_groups, False)
    assert "Knowledge Points" in rows
    # And they agree with what the step's own page prints.
    attributes_page = client.get("/ui/page/attributes", headers=HTMX).text
    assert f'budget-box__value">{budget - 3}/{budget}<' in attributes_page
    skills_page = client.get("/ui/page/skills", headers=HTMX).text  # WP148: the strip's counter
    assert f'view-counter__value">{skills.skills - 4}/{skills.skills}<' in skills_page


def test_an_over_budget_pool_is_flagged() -> None:
    client = TestClient(create_app())
    _confirm_human(client, skills_letter="C", resources_letter="D")
    ungrouped = [s for s in MUNDANE_SKILLS if s.skill_group is None][:5]
    points = {s.id: 6 for s in ungrouped[:4]} | {ungrouped[4].id: 1}  # 25 of C's 28
    client.post("/ui/skills", data={f"skill_{sid}": str(v) for sid, v in points.items()})
    assert _panel_rows(client.get("/ui/resource-panel").text)["Skill Points"][2] is False

    _confirm_human(client, skills_letter="D", resources_letter="C")  # 22 points now

    remaining, of, over = _panel_rows(client.get("/ui/resource-panel").text)["Skill Points"]
    assert (remaining, of, over) == (22 - 25, 22, True)


def test_magic_pools_appear_only_for_the_archetype_that_has_them() -> None:
    spellcasting = next(s for s in SKILLS if s.name == "Spellcasting")
    counterspelling = next(s for s in SKILLS if s.name == "Counterspelling")
    pistols = next(s for s in SKILLS if s.name == "Pistols")
    talents = {
        "Magician": {
            "tradition_id": HERMETIC.id,
            "granted_skill_id": [spellcasting.id, counterspelling.id],
        },
        "Adept": {"granted_skill_id": [pistols.id]},
    }
    for codename, extra in talents.items():
        client = TestClient(create_app())
        _confirm_human(
            client,
            talent_letter="B",
            attributes_letter="C",
            skills_letter="D",
            resources_letter="E",
        )
        mundane = _panel_rows(client.get("/ui/resource-panel").text)
        assert "Free Spells" not in mundane and "Power Points" not in mundane

        client.post("/ui/talent", data={"talent_letter": "B", "talent_codename": codename, **extra})

        rows = _panel_rows(client.get("/ui/resource-panel").text)
        if codename == "Magician":
            assert "Power Points" not in rows
            assert rows["Free Spells"][:2] == (7, 7)  # letter B Magician: 7 free spells
        else:
            assert "Free Spells" not in rows
            assert rows["Power Points"][:2] == (6, 6)  # letter B Adept: Magic 6 -> 6 PP
