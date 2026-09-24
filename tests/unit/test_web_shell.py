"""WP97: the application shell -- title bar, sidebar step nav, one `#page` content pane.

Replaces `test_web_accordion.py` (WP61/WP64), whose subject -- fifteen stacked `<details>`
sections kept one-open-at-a-time by `ChargenSession.open_section` plus a client-side store --
was deleted by this WP rather than ported (see `spec/plan/phase-w-ui-shell.md`, Finding 2).
`open_section` survives as `current_page`, holding a nav slug.
"""

import re

from fastapi.testclient import TestClient

from chummer5.data.metatypes import load_metatypes
from chummer5.data.priorities import load_priorities
from chummer5.engine.character import metatype_choices
from chummer5.web.app import MUNDANE_SKILLS, create_app
from chummer5.web.shell import STEP_PAGES

METATYPES = load_metatypes()
PRIORITIES = load_priorities()

HTMX = {"HX-Request": "true"}

NAV_LABELS = (
    "Priorities",
    "Attributes",
    "Qualities",
    "Skills",
    "Magic",
    "Resonance",
    "Augmentation",
    "Equipment",
    "Contacts",
    "Bio",
    "Export",
)


def _human_id() -> str:
    heritage = PRIORITIES.heritage["A"]
    return next(
        c for c in metatype_choices(heritage, METATYPES) if c.metatype.name == "Human"
    ).metatype.id


def _confirm_priorities(client: TestClient, **letters: str) -> str:
    data = {
        "heritage_letter": "A",
        "attributes_letter": "B",
        "skills_letter": "C",
        "resources_letter": "D",
        "talent_letter": "E",
        "metatype_id": _human_id(),
        **letters,
    }
    response = client.post("/ui/priorities", data=data)
    assert response.status_code == 200
    return response.text


def _nav_item(html: str, label: str) -> str:
    """The markup of the one nav entry labelled `label` (an `<a>` or a disabled `<span>`)."""
    match = re.search(
        rf'<(a|span)\s[^>]*class="step-nav__item[^"]*"[^>]*>{label}\b.*?</\1>', html, re.S
    )
    assert match is not None, f"no nav entry for {label!r}"
    return match.group(0)


def _current_items(html: str) -> list[str]:
    return re.findall(r'class="step-nav__item step-nav__item--current[^"]*"[^>]*>(\w+)', html)


def test_nav_renders_all_eleven_entries_in_the_sketch_order() -> None:
    client = TestClient(create_app())

    html = client.get("/").text

    assert tuple(page.label for page in STEP_PAGES) == NAV_LABELS
    positions = [html.index(_nav_item(html, label)) for label in NAV_LABELS]
    assert positions == sorted(positions)


def test_resonance_and_bio_are_present_but_disabled() -> None:
    client = TestClient(create_app())

    html = client.get("/").text

    for label in ("Resonance", "Bio"):
        item = _nav_item(html, label)
        assert item.startswith("<span")
        assert 'aria-disabled="true"' in item
        assert "href=" not in item and "hx-get=" not in item
    enabled = [label for label in NAV_LABELS if label not in ("Resonance", "Bio")]
    for label in enabled:
        assert _nav_item(html, label).startswith("<a")
    assert client.get("/ui/page/resonance").status_code == 404
    assert client.get("/ui/page/bio").status_code == 404
    assert client.get("/ui/page/no-such-step").status_code == 404


def test_nav_links_swap_the_page_pane_and_push_the_url() -> None:
    client = TestClient(create_app())

    item = _nav_item(client.get("/").text, "Skills")

    assert 'href="/ui/page/skills"' in item
    assert 'hx-get="/ui/page/skills"' in item
    assert 'hx-target="#page"' in item
    assert 'hx-push-url="true"' in item


def test_index_renders_the_shell_with_priorities_current() -> None:
    client = TestClient(create_app())

    html = client.get("/").text

    assert '<main id="page"' in html
    assert 'class="app-shell__titlebar"' in html
    assert _current_items(html) == ["Priorities"]
    assert 'aria-current="page"' in _nav_item(html, "Priorities")
    assert 'id="priority-section"' in html
    # Only the Priorities page is mounted -- no other step's fragment rides along any more.
    assert 'id="attribute-allocation"' not in html
    assert 'id="skill-allocation"' not in html


def test_a_page_request_from_the_nav_returns_that_step_and_only_that_step() -> None:
    client = TestClient(create_app())
    client.get("/")
    _confirm_priorities(client)

    response = client.get("/ui/page/skills", headers=HTMX)

    html = response.text
    assert "<!doctype html>" not in html.lower()
    assert 'class="app-shell' not in html
    # Skills is a composite page: both of its fragments, nothing else's.
    assert 'id="skill-allocation"' in html
    assert 'id="knowledge-skills"' in html
    for other in ("priority-section", "attribute-allocation", "talent-selection", "resources"):
        assert f'id="{other}"' not in html
    # The nav rides along out of band so its current-step marker follows the swap.
    assert 'hx-swap-oob="true"' in html
    assert _current_items(html) == ["Skills"]
    assert response.headers["Vary"] == "HX-Request"


def test_a_direct_page_url_get_renders_the_full_shell_with_that_step_selected() -> None:
    """A bookmarked or reloaded step URL -- and htmx's own history-restore request on a cache
    miss -- must get the whole document, not a bare fragment."""
    client = TestClient(create_app())
    client.get("/")
    _confirm_priorities(client)

    for headers in ({}, {**HTMX, "HX-History-Restore-Request": "true"}):
        html = client.get("/ui/page/attributes", headers=headers).text

        assert html.lstrip().lower().startswith("<!doctype html>")
        assert '<main id="page"' in html
        assert 'id="attribute-allocation"' in html
        assert 'id="priority-section"' not in html
        assert _current_items(html) == ["Attributes"]
        assert "hx-swap-oob" not in html


def test_the_character_sheet_url_is_the_export_page() -> None:
    client = TestClient(create_app())

    html = client.get("/character/sheet").text

    assert '<main id="page"' in html
    assert 'id="character-sheet"' in html
    assert _current_items(html) == ["Export"]
    assert "Character sheet &amp; export" in html


def test_a_step_post_leaves_current_page_on_that_step() -> None:
    client = TestClient(create_app())
    client.get("/")
    _confirm_priorities(client)

    for url, data, label in (
        ("/ui/attributes", {"attr_BOD": "2"}, "Attributes"),
        ("/ui/knowledge", {}, "Skills"),
        ("/ui/talent", {"talent_letter": "E", "talent_codename": "Mundane"}, "Magic"),
        ("/ui/lifestyle", {"lifestyle_tier": "Low", "lifestyle_months": "1"}, "Equipment"),
        ("/ui/cyberware", {}, "Augmentation"),
        ("/ui/contacts", {}, "Contacts"),
        ("/ui/qualities", {}, "Qualities"),
    ):
        client.post(url, data=data)
        assert _current_items(client.get("/ui/nav").text) == [label], url

    # ... including a submission that fails validation (the step still ran; the player is there).
    skill = next(s for s in MUNDANE_SKILLS if s.skill_group is None)
    client.post("/ui/skills", data={f"skill_{skill.id}": "99"})
    assert _current_items(client.get("/ui/nav").text) == ["Skills"]


def test_every_successful_post_signals_the_nav_to_refresh_itself() -> None:
    client = TestClient(create_app())
    client.get("/")

    nav = re.search(r'<nav\s[^>]*id="step-nav"[^>]*>', client.get("/").text, re.S)
    assert nav is not None
    assert 'hx-get="/ui/nav"' in nav.group(0)
    assert 'hx-trigger="chargen-changed from:body"' in nav.group(0)

    assert client.post("/ui/attributes", data={}).headers["HX-Trigger"] == "chargen-changed"
    response = client.post(
        "/ui/priorities",
        data={
            "heritage_letter": "A",
            "attributes_letter": "B",
            "skills_letter": "C",
            "resources_letter": "D",
            "talent_letter": "E",
            "metatype_id": _human_id(),
        },
    )
    assert response.headers["HX-Trigger"] == "chargen-changed"
    # GETs change nothing, so they don't signal.
    assert "HX-Trigger" not in client.get("/ui/page/skills", headers=HTMX).headers


def test_a_priorities_change_that_invalidates_a_skill_spend_marks_skills_in_the_nav() -> None:
    """The WP19 "no longer fits" warning has to reach the player without the Skills page being
    open: the priorities page says *that* something went stale, and the nav says *where*."""
    client = TestClient(create_app())
    client.get("/")
    _confirm_priorities(client)  # Skills letter C, 28 points
    ungrouped = [s for s in MUNDANE_SKILLS if s.skill_group is None][:5]
    points = {s.id: 6 for s in ungrouped[:4]} | {ungrouped[4].id: 1}  # 25 points -- fits C
    client.post("/ui/skills", data={f"skill_{sid}": str(v) for sid, v in points.items()})
    assert "step-nav__marker" not in client.get("/ui/nav").text

    # Skills C (28) -> D (22): the committed 25 points no longer fit.
    priorities_page = _confirm_priorities(client, skills_letter="D", resources_letter="C")

    # The priorities page re-renders alone -- not the fifteen sections it used to...
    assert 'id="priority-section"' in priorities_page
    assert 'id="skill-allocation"' not in priorities_page
    # ... and carries the aggregate warning, pointing at the nav.
    assert "no longer fit these priorities" in priorities_page
    assert "marked ⚠ in the step list" in priorities_page

    nav = client.get("/ui/nav").text
    assert "step-nav__marker" in _nav_item(nav, "Skills")
    assert "step-nav__item--stale" in _nav_item(nav, "Skills")
    for label in ("Priorities", "Attributes", "Magic", "Equipment", "Augmentation"):
        assert "step-nav__marker" not in _nav_item(nav, label)
    assert _current_items(nav) == ["Priorities"]

    # And the page itself still says what's wrong, once the player goes there.
    skills_page = client.get("/ui/page/skills", headers=HTMX).text
    assert "No longer fits since priorities were last confirmed" in skills_page


def test_step_panels_render_open_without_the_accordion_machinery() -> None:
    client = TestClient(create_app())
    client.get("/")
    _confirm_priorities(client)

    html = client.get("/ui/page/magic").text

    # Every step panel on the page renders open (Magic stacks Talent/Spells/Powers/Spirits/Foci;
    # a Mundane character shows only Talent's).
    assert 'id="talent-selection" class="panel"' in html
    assert "<details open>" in html
    assert "<details >" not in html
    # The WP61 collapsed-section marker and WP64 exclusivity store are gone ...
    assert '<summary class="panel__heading">Talent</summary>' in html
    assert "section:" not in html
    assert "chargen-body" not in html
    # ... while WP64's sub-category open-state store survives, keyed as before.
    skills = client.get("/ui/page/skills").text
    assert "htmx:afterSwap" in skills
    assert 'data-details-key="skillcat:' in skills
