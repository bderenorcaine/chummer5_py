"""WP98: the composite nav pages -- Magic and Equipment (and Skills until WP148 gave it view tabs,
see `test_web_skills_redesign_wp148.py`) -- as a tab strip over their sections
(`chummer5.web.shell.PageSection`).

The pattern (see `spec/decisions-log.md`, 2026-09-24): a tab is a link that re-renders the whole
page with that section showing, and the page still renders *every* section's fragment, all but the
current one `hidden`. These tests pin the three properties that decision rests on -- every
fragment stays in the page, a tab's availability agrees exactly with its fragment's own guard, and
the tab strip keeps up with changes made on another tab -- plus the tab URLs themselves.
"""

from __future__ import annotations

import html as html_lib
import re

import pytest
from fastapi.testclient import TestClient

from chummer5.data.metatypes import load_metatypes
from chummer5.data.priorities import load_priorities
from chummer5.data.skills import load_skills
from chummer5.data.traditions import load_traditions
from chummer5.engine.character import metatype_choices
from chummer5.web.app import MUNDANE_SKILLS, create_app
from chummer5.web.i18n import translate
from chummer5.web.shell import STEP_PAGES, STEP_PAGES_BY_SLUG

METATYPES = load_metatypes()
PRIORITIES = load_priorities()
SKILLS = load_skills()
HERMETIC = next(t for t in load_traditions() if t.name == "Hermetic")
SPELLCASTING = next(s for s in SKILLS if s.name == "Spellcasting")
COUNTERSPELLING = next(s for s in SKILLS if s.name == "Counterspelling")
PISTOLS = next(s for s in SKILLS if s.name == "Pistols")

HTMX = {"HX-Request": "true"}

# Each composite page's sections: (tab slug, the fragment's own wrapper id).
COMPOSITES = {
    "magic": (
        ("talent", "talent-selection"),
        ("spells", "spell-selection"),
        ("powers", "power-selection"),
        ("spirits", "spirit-selection"),
        ("foci", "foci-selection"),
    ),
    "equipment": (("gear", "resources"), ("lifestyle", "lifestyle"), ("vehicles", "vehicles")),
}


def _human_id() -> str:
    heritage = PRIORITIES.heritage["A"]
    return next(
        c for c in metatype_choices(heritage, METATYPES) if c.metatype.name == "Human"
    ).metatype.id


def _confirm_human(client: TestClient, *, talent_letter: str = "E", **letters: str) -> None:
    client.get("/")
    remaining = [letter for letter in ("B", "C", "D", "E") if letter != talent_letter]
    data = {
        "heritage_letter": "A",
        "talent_letter": talent_letter,
        "attributes_letter": remaining[0],
        "skills_letter": remaining[1],
        "resources_letter": remaining[2],
        "metatype_id": _human_id(),
        **letters,
    }
    assert client.post("/ui/priorities", data=data).status_code == 200


def _confirm_talent(client: TestClient, codename: str) -> None:
    """Confirm `codename` at Talent letter B (see `test_web_magic.py` for the letter choice)."""
    data: dict[str, str | list[str]] = {"talent_letter": "B", "talent_codename": codename}
    if codename == "Magician":
        data |= {
            "tradition_id": HERMETIC.id,
            "granted_skill_id": [SPELLCASTING.id, COUNTERSPELLING.id],
        }
    elif codename == "Adept":
        data |= {"granted_skill_id": [PISTOLS.id]}
    response = client.post("/ui/talent", data=data)
    assert f"Confirmed: {codename}" in response.text


def _subpage(html: str, page: str, tab: str) -> str:
    """The opening tag of one section's wrapper on a composite page."""
    match = re.search(rf'<section\s[^>]*id="subpage-{page}-{tab}"[^>]*>', html, re.S)
    assert match is not None, f"no section {tab!r} on {page!r}"
    return match.group(0)


def _tab(html: str, label: str) -> str:
    """The markup of the one tab labelled `label` (an `<a>` or a disabled `<span>`)."""
    match = re.search(
        rf'<(a|span)\s[^>]*class="page-tabs__item[^"]*"[^>]*>{re.escape(html_lib.escape(label))}(?=[\s<]).*?</\1>',
        html,
        re.S,
    )
    assert match is not None, f"no tab {label!r}"
    return match.group(0)


def _shown_tab(html: str, page: str) -> str:
    shown = [
        tab
        for tab, _ in COMPOSITES[page]
        if "hidden" not in _subpage(html, page, tab).split(">")[0].split()
    ]
    assert len(shown) == 1, shown
    return shown[0]


def test_exactly_the_composite_pages_are_tabbed() -> None:
    tabbed = {page.slug for page in STEP_PAGES if page.tabbed}
    assert tabbed == set(COMPOSITES)
    for slug, sections in COMPOSITES.items():
        assert tuple(s.slug for s in STEP_PAGES_BY_SLUG[slug].sections) == tuple(
            tab for tab, _ in sections
        )


@pytest.mark.parametrize("slug", sorted(COMPOSITES))
def test_a_composite_page_renders_every_fragment_with_only_the_first_tab_showing(
    slug: str,
) -> None:
    client = TestClient(create_app())
    _confirm_human(client, talent_letter="B")
    _confirm_talent(client, "Magician")

    html = client.get(f"/ui/page/{slug}", headers=HTMX).text

    assert 'id="page-tabs"' in html
    for tab, wrapper_id in COMPOSITES[slug]:
        # Every fragment stays in the page, inside its own section, under its own id.
        section_start = html.index(_subpage(html, slug, tab))
        assert html.index(f'id="{wrapper_id}"', section_start) > section_start
    assert _shown_tab(html, slug) == COMPOSITES[slug][0][0]


def test_a_single_section_page_has_no_tab_strip() -> None:
    client = TestClient(create_app())
    _confirm_human(client)

    for slug in ("priorities", "attributes", "qualities", "augmentation", "contacts", "export"):
        html = client.get(f"/ui/page/{slug}", headers=HTMX).text
        assert "page-tabs" not in html, slug
        assert "subpage" not in html, slug


def test_a_tab_link_shows_that_section_and_is_remembered_by_the_page() -> None:
    client = TestClient(create_app())
    _confirm_human(client)

    html = client.get("/ui/page/equipment", headers=HTMX).text
    lifestyle = _tab(html, "Lifestyle")
    assert 'href="/ui/page/equipment/lifestyle"' in lifestyle
    assert 'hx-get="/ui/page/equipment/lifestyle"' in lifestyle
    assert 'hx-target="#page"' in lifestyle
    assert 'hx-swap="innerHTML"' in lifestyle
    assert 'hx-push-url="true"' in lifestyle

    html = client.get("/ui/page/equipment/lifestyle", headers=HTMX).text
    assert _shown_tab(html, "equipment") == "lifestyle"
    assert "page-tabs__item--current" in _tab(html, "Lifestyle")
    assert 'aria-current="page"' in _tab(html, "Lifestyle")
    assert "page-tabs__item--current" not in _tab(html, "Gear")

    # Leave, come back through the nav: the page reopens on the tab the player left it on.
    client.get("/ui/page/magic", headers=HTMX)
    html = client.get("/ui/page/equipment", headers=HTMX).text
    assert _shown_tab(html, "equipment") == "lifestyle"
    assert _shown_tab(client.get("/ui/page/magic", headers=HTMX).text, "magic") == "talent"


def test_a_direct_tab_url_renders_the_full_shell_and_bad_tabs_404() -> None:
    client = TestClient(create_app())
    _confirm_human(client)

    html = client.get("/ui/page/equipment/vehicles").text
    assert html.lstrip().lower().startswith("<!doctype html>")
    assert '<main id="page"' in html
    assert _shown_tab(html, "equipment") == "vehicles"
    assert "hx-swap-oob" not in html

    fragment = client.get("/ui/page/equipment/vehicles", headers=HTMX).text
    assert "<!doctype html>" not in fragment.lower()
    assert 'hx-swap-oob="true"' in fragment  # the nav rides along, as for a page GET

    assert client.get("/ui/page/equipment/no-such-tab").status_code == 404
    assert client.get("/ui/page/skills/no-such-tab").status_code == 404
    assert client.get("/ui/page/attributes/attributes").status_code == 404
    assert client.get("/ui/page/bio/anything").status_code == 404
    assert client.get("/ui/tabs/attributes").status_code == 404
    assert client.get("/ui/tabs/skills").status_code == 200


@pytest.mark.parametrize("talent", [None, "Mundane", "Magician", "Adept"])
def test_magic_tab_availability_agrees_with_each_fragments_own_guard(talent: str | None) -> None:
    """A tab is disabled exactly when its fragment renders nothing -- the `available` predicates
    in `shell.py` mirror the fragments' `{% if %}` guards, and this is what keeps them in step."""
    client = TestClient(create_app())
    if talent is None:
        client.get("/")
    else:
        _confirm_human(client, talent_letter="B")
        if talent != "Mundane":
            _confirm_talent(client, talent)

    html = client.get("/ui/page/magic", headers=HTMX).text

    page = STEP_PAGES_BY_SLUG["magic"]
    for section, (tab, wrapper_id) in zip(page.sections, COMPOSITES["magic"], strict=True):
        wrapper = re.search(rf'<div id="{wrapper_id}"[^>]*>(.*?)\n</div>', html, re.S)
        assert wrapper is not None, wrapper_id
        has_content = bool(wrapper.group(1).strip())
        tab_markup = _tab(html, translate("en-us", section.label_key))
        if has_content:
            assert tab_markup.startswith("<a"), (talent, tab)
        else:
            assert tab_markup.startswith("<span"), (talent, tab)
            assert 'aria-disabled="true"' in tab_markup
            assert section.unavailable_reason_key is not None
            reason = translate("en-us", section.unavailable_reason_key)
            assert f'title="{reason}"' in tab_markup


def test_mundane_magic_page_is_the_talent_tab_plus_an_explained_empty_state() -> None:
    client = TestClient(create_app())
    _confirm_human(client)

    html = client.get("/ui/page/magic", headers=HTMX).text

    assert _shown_tab(html, "magic") == "talent"
    assert "open up here once you confirm a Magician or Adept Talent" in html
    # A direct link to an unavailable tab says why, rather than showing an empty pane ...
    spells = client.get("/ui/page/magic/spells", headers=HTMX).text
    assert _shown_tab(spells, "magic") == "spells"
    assert "Spells need a confirmed Magician Talent." in spells
    assert "subpage__unavailable" in spells
    # ... but the nav never reopens the page on one: it falls back to the first available tab.
    assert _shown_tab(client.get("/ui/page/magic", headers=HTMX).text, "magic") == "talent"


def test_a_magician_sees_no_locked_note_and_a_disabled_powers_tab() -> None:
    client = TestClient(create_app())
    _confirm_human(client, talent_letter="B")
    _confirm_talent(client, "Magician")

    html = client.get("/ui/page/magic/spells", headers=HTMX).text

    assert _shown_tab(html, "magic") == "spells"
    assert "page-tabs__note" not in html
    assert _tab(html, "Adept Powers").startswith("<span")
    assert "subpage__unavailable" not in html


def test_the_tab_strip_refreshes_itself_after_a_change_on_another_tab() -> None:
    """Confirming a Talent is a POST from the Talent tab that swaps only the Talent fragment;
    the strip re-fetches itself on `chargen-changed`, and that re-fetch un-disables Spells."""
    client = TestClient(create_app())
    _confirm_human(client, talent_letter="B")
    html = client.get("/ui/page/magic", headers=HTMX).text
    strip = re.search(r'<nav\s[^>]*id="page-tabs"[^>]*>', html, re.S)
    assert strip is not None
    assert 'hx-get="/ui/tabs/magic"' in strip.group(0)
    assert 'hx-trigger="chargen-changed from:body"' in strip.group(0)
    assert _tab(html, "Spells").startswith("<span")

    _confirm_talent(client, "Magician")

    refreshed = client.get("/ui/tabs/magic").text
    assert _tab(refreshed, "Spells").startswith("<a")
    assert "page-tabs__item--current" in _tab(refreshed, "Talent")
    assert "page-tabs__note" not in refreshed


def test_the_strip_refresh_keeps_marking_the_tab_on_screen_even_once_it_is_unavailable() -> None:
    client = TestClient(create_app())
    _confirm_human(client, talent_letter="B")
    _confirm_talent(client, "Magician")
    client.get("/ui/page/magic/spells", headers=HTMX)

    _confirm_talent(client, "Adept")  # takes Spells away while it is the tab on screen

    refreshed = client.get("/ui/tabs/magic").text
    assert _tab(refreshed, "Spells").startswith("<span")
    assert "page-tabs__item--current" in _tab(refreshed, "Spells")


def test_a_stale_section_is_marked_on_its_own_tab() -> None:
    client = TestClient(create_app())
    _confirm_human(client, talent_letter="E")  # Skills letter D after the permutation: B/C/D
    ungrouped = [s for s in MUNDANE_SKILLS if s.skill_group is None][:5]
    points = {s.id: 6 for s in ungrouped[:4]} | {ungrouped[4].id: 1}  # 25 points
    # Put Skills on C (28 points) so the 25 fit, then move it to D (22) so they don't.
    _confirm_human(client, talent_letter="E", skills_letter="C", resources_letter="D")
    client.post("/ui/skills", data={f"skill_{sid}": str(v) for sid, v in points.items()})
    assert "view-tab__marker" not in client.get("/ui/tabs/skills").text

    _confirm_human(client, talent_letter="E", skills_letter="D", resources_letter="C")

    # WP148: on the Skills page's view tabs, Combat (the page's first tab) carries the
    # active-skill warning and Knowledge its own.
    html = client.get("/ui/page/skills", headers=HTMX).text
    combat = re.search(r'<a\s[^>]*class="view-tab[^"]*"[^>]*/skills/combat".*?</a>', html, re.S)
    knowledge = re.search(
        r'<a\s[^>]*class="view-tab[^"]*"[^>]*/skills/knowledge".*?</a>', html, re.S
    )
    assert combat is not None and knowledge is not None
    assert "view-tab__marker" in combat.group(0)
    assert "view-tab--stale" in combat.group(0)
    assert "view-tab__marker" not in knowledge.group(0)
