"""WP98's acceptance walk: priorities -> skills -> magic -> equipment through the step nav, as a
browser would drive it (htmx `GET`s following the nav's and tab strip's own links), asserting each
composite page renders all of its constituent fragments -- the current tab's visibly, the rest
`hidden` but present.
"""

from __future__ import annotations

import re

from fastapi.testclient import TestClient

from chummer5.data.metatypes import load_metatypes
from chummer5.data.priorities import load_priorities
from chummer5.data.skills import load_skills
from chummer5.data.traditions import load_traditions
from chummer5.engine.character import metatype_choices
from chummer5.web.app import create_app
from chummer5.web.shell import STEP_PAGES_BY_SLUG

METATYPES = load_metatypes()
PRIORITIES = load_priorities()
SKILLS = load_skills()
HERMETIC = next(t for t in load_traditions() if t.name == "Hermetic")

HTMX = {"HX-Request": "true"}

# The wrapper id each fragment renders itself into -- unchanged by Phase W.
WRAPPER_IDS = {
    "_skill_allocation.html": "skill-allocation",
    "_knowledge_skills.html": "knowledge-skills",
    "_talent_selection.html": "talent-selection",
    "_spell_selection.html": "spell-selection",
    "_power_selection.html": "power-selection",
    "_spirit_selection.html": "spirit-selection",
    "_foci_selection.html": "foci-selection",
    "_resources.html": "resources",
    "_lifestyle.html": "lifestyle",
    "_vehicles.html": "vehicles",
}


def _link(html: str, css_class: str, href: str) -> str:
    """The `hx-get` of the `css_class` link pointing at `href` -- i.e. what a click requests."""
    match = re.search(rf'<a\s[^>]*class="{css_class}[^"]*"[^>]*href="{href}"[^>]*>', html, re.S)
    assert match is not None, href
    hx_get = re.search(r'hx-get="([^"]+)"', match.group(0))
    assert hx_get is not None
    return hx_get.group(1)


def _assert_whole_page(html: str, slug: str) -> str:
    """Assert every section of `slug` is in `html`, exactly one showing; return that one."""
    page = STEP_PAGES_BY_SLUG[slug]
    shown = []
    for section in page.sections:
        opening = re.search(rf'<section\s[^>]*id="subpage-{slug}-{section.slug}"[^>]*>', html)
        assert opening is not None, (slug, section.slug)
        assert f'id="{WRAPPER_IDS[section.fragment]}"' in html[opening.end() :]
        if "hidden" not in opening.group(0):
            shown.append(section.slug)
    assert len(shown) == 1, (slug, shown)
    return shown[0]


def test_walking_the_nav_renders_each_composite_page_whole() -> None:
    client = TestClient(create_app())
    shell = client.get("/").text

    # Priorities: a Magician at Talent B, so the Magic page has real content on several tabs.
    heritage = PRIORITIES.heritage["A"]
    human = next(c for c in metatype_choices(heritage, METATYPES) if c.metatype.name == "Human")
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
    spellcasting = next(s for s in SKILLS if s.name == "Spellcasting")
    counterspelling = next(s for s in SKILLS if s.name == "Counterspelling")
    client.post(
        "/ui/talent",
        data={
            "talent_letter": "B",
            "talent_codename": "Magician",
            "tradition_id": HERMETIC.id,
            "granted_skill_id": [spellcasting.id, counterspelling.id],
        },
    )

    # WP148: Skills' view tabs -- every tab renders both fragments whole, its own panel showing.
    html = client.get(_link(shell, "step-nav__item", "/ui/page/skills"), headers=HTMX).text
    for tab in STEP_PAGES_BY_SLUG["skills"].tabs:
        if not tab.enabled:
            continue  # Resonance: a disabled <span>
        tab_html = client.get(
            _link(html, "skills-tab", f"/ui/page/skills/{tab.slug}"), headers=HTMX
        ).text
        assert 'id="skill-allocation"' in tab_html and 'id="knowledge-skills"' in tab_html
        if tab.slug == "knowledge":
            assert re.search(r'<div id="knowledge-skills" class="panel">', tab_html)
        else:
            assert re.search(rf'data-skills-panel="{tab.slug}">', tab_html), tab.slug
        html = shell = tab_html

    for slug in ("magic", "equipment"):
        html = client.get(_link(shell, "step-nav__item", f"/ui/page/{slug}"), headers=HTMX).text
        _assert_whole_page(html, slug)
        # Then every tab of it, following the tab strip's own links.
        for section in STEP_PAGES_BY_SLUG[slug].sections:
            if section.slug == "powers":
                continue  # an Adept tab: a disabled <span> for this Magician, not a link
            href = f"/ui/page/{slug}/{section.slug}"
            tab_html = client.get(_link(html, "page-tabs__item", href), headers=HTMX).text
            assert _assert_whole_page(tab_html, slug) == section.slug
            shell = tab_html  # the nav rode along out of band; click the next page from it

    # The Magician's own sections have real content, not the empty guard.
    magic = client.get("/ui/page/magic/spells", headers=HTMX).text
    assert '<summary class="panel__heading">Spells</summary>' in magic
    assert '<summary class="panel__heading">Bound Spirits</summary>' in magic
    assert '<summary class="panel__heading">Foci</summary>' in magic
