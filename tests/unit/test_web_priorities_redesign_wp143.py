"""WP143 (Phase Z): the redesigned Priorities page's server side -- both layouts' markup, the
read-only preview/layout/revert endpoints, the status and confirmable rules, the metatype rule,
the never-confirmed all-E rule, and messages rendering after the controls.

See `spec/plan/phase-z-page-redesigns.md`. The drag/spinner behaviour itself (WP144) has no
server side beyond the markup hooks pinned here.
"""

from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient
from tests.unit.test_security_wp141 import _assert_csp_clean

from chummer5.data.metatypes import load_metatypes
from chummer5.data.priorities import load_priorities
from chummer5.engine.build_method import PRIORITY_BUILD_METHOD, SUM_TO_TEN_BUILD_METHOD
from chummer5.engine.character import metatype_choices
from chummer5.web.app import MUNDANE_SKILLS, create_app
from chummer5.web.prefs import THEMES

PRIORITIES = load_priorities()
METATYPES = load_metatypes()
HTMX = {"HX-Request": "true"}


def _metatype_id(letter: str, name: str) -> str:
    return next(
        c.metatype.id
        for c in metatype_choices(PRIORITIES.heritage[letter], METATYPES)
        if c.metatype.name == name
    )


HUMAN = _metatype_id("E", "Human")
TROLL = _metatype_id("A", "Troll")
ELF = _metatype_id("D", "Elf")

# Heritage, Talent, Attributes, Skills, Resources -- the session's defaults.
DEFAULT_LETTERS = {
    "heritage": "A",
    "talent": "E",
    "attributes": "B",
    "skills": "C",
    "resources": "D",
}


def _form(
    method: str = PRIORITY_BUILD_METHOD, metatype_id: str = HUMAN, **letters: str
) -> dict[str, str]:
    merged = {**DEFAULT_LETTERS, **letters}
    return {
        "build_method": method,
        "metatype_id": metatype_id,
        **{f"{category}_letter": letter for category, letter in merged.items()},
    }


@pytest.fixture
def client() -> TestClient:
    client = TestClient(create_app())
    client.get("/")
    return client


@pytest.fixture
def confirmed(client: TestClient) -> TestClient:
    """A character confirmed at the default letters, as a Human."""
    response = client.post("/ui/priorities", data=_form())
    assert "Confirmed: Human" in response.text
    return client


def _status(html: str) -> tuple[str, str]:
    match = re.search(r'data-priority-status="(\w+)"\s+data-priority-confirmable="(\w+)"', html)
    assert match, "no status element"
    return match.group(1), match.group(2)


def _letter_inputs(html: str) -> list[tuple[str, str]]:
    return re.findall(r'name="(\w+)_letter" value="([A-E])"', html)


def _confirm_button(html: str) -> str:
    match = re.search(r'<button\s+type="submit"[^>]*>', html)
    assert match
    return match.group(0)


def _revert_button(html: str) -> str:
    match = re.search(r'<button\s+type="button"\s+class="priority-actions__revert[^>]*>', html)
    assert match
    return match.group(0)


# --- The page's markup ----------------------------------------------------------------------------


def test_priority_layout_letters_beside_tiles_in_letter_order(client: TestClient) -> None:
    html = client.get("/ui/page/priorities", headers=HTMX).text

    assert 'id="priority-section"' in html
    assert "<details" not in html.split('id="priority-section"')[1]  # standing rule 3
    assert '<h1 class="page__heading">Priority &amp; metatype selection</h1>' in html
    letters = re.search(r'<ol class="priority-grid__letters".*?</ol>', html, re.S)
    assert letters and "priority-tile" not in letters.group(0)  # the letters stay put
    tiles = re.search(r'<ol id="priority-tiles".*?</ol>', html, re.S)
    assert tiles
    order = re.findall(r'data-category="(\w+)"', tiles.group(0))
    assert order == ["heritage", "attributes", "skills", "resources", "talent"]  # A, B, C, D, E
    assert _letter_inputs(tiles.group(0)) == [
        ("heritage", "A"),
        ("attributes", "B"),
        ("skills", "C"),
        ("resources", "D"),
        ("talent", "E"),
    ]
    assert 'tabindex="0"' in tiles.group(0)
    assert 'role="spinbutton"' not in html


def test_method_dropdown_uses_short_labels_and_sits_outside_the_form(client: TestClient) -> None:
    html = client.get("/ui/page/priorities", headers=HTMX).text
    select = re.search(r'<select\s+id="priority-method".*?</select>', html, re.S)
    assert select
    assert 'form="priority-form"' in select.group(0)
    assert 'hx-get="/ui/priorities/layout"' in select.group(0)
    assert ">Priority</option>" in select.group(0)
    assert ">Sum-to-Ten</option>" in select.group(0)
    # The method's explanation is the panel's intro text, one per method.
    assert "Drag the five categories" in html
    assert html.index('id="priority-method"') < html.index("<form")


def test_sum_to_ten_layout_spinners(client: TestClient) -> None:
    html = client.get(
        "/ui/priorities/layout",
        params={
            **_form(SUM_TO_TEN_BUILD_METHOD),
            "layout": SUM_TO_TEN_BUILD_METHOD,
            "heritage_letter": "B",
            "talent_letter": "B",
            "attributes_letter": "B",
            "skills_letter": "E",
            "resources_letter": "D",
        },
    ).text

    rows = re.findall(r'<div class="sum-to-ten__row" data-category="(\w+)"', html)
    assert rows == ["heritage", "talent", "attributes", "skills", "resources"]  # display order
    spinner = re.search(r'<span\s+class="sum-to-ten__value".*?</span>', html, re.S)
    assert spinner
    for attribute in (
        'role="spinbutton"',
        'tabindex="0"',
        'aria-valuemin="0"',
        'aria-valuemax="4"',
        'aria-valuenow="3"',
        'aria-valuetext="B, 3 points"',
        ">B (3)</span>",
    ):
        assert attribute in spinner.group(0), attribute
    assert html.count('class="sum-to-ten__step" data-step="1"') == 5
    assert html.count('class="sum-to-ten__step" data-step="-1"') == 5
    assert ("heritage", "B") in _letter_inputs(html)
    # The point scale reaches the markup as data, lowest first, so the script has no constants.
    scale = re.search(r'<ol class="sum-to-ten__scale" hidden>(.*?)</ol>', html, re.S)
    assert scale
    assert re.findall(r'data-letter="([A-E])" data-points="(\d)"', scale.group(1)) == [
        ("E", "0"),
        ("D", "1"),
        ("C", "2"),
        ("B", "3"),
        ("A", "4"),
    ]
    assert 'data-valuetext="D, 1 point"' in scale.group(1)
    # 3+3+3+0+1 = 10: on target, no highlight.
    assert '<output class="sum-to-ten__sum">10</output> / 10' in html
    assert "sum-to-ten__row--off" not in html
    assert 'id="priority-tiles"' not in html


def test_sum_to_ten_total_off_target_is_highlighted_and_not_confirmable(
    client: TestClient,
) -> None:
    html = client.get(
        "/ui/priorities/layout",
        params={**_form(SUM_TO_TEN_BUILD_METHOD), "layout": PRIORITY_BUILD_METHOD},
    ).text  # never confirmed: all E

    assert '<output class="sum-to-ten__sum">0</output> / 10' in html
    assert "sum-to-ten__row--off" in html
    assert _status(html) == ("unconfirmed", "false")
    assert "disabled" in _confirm_button(html)


# --- Status and confirmable -------------------------------------------------------------------


def test_status_unconfirmed_before_any_character(client: TestClient) -> None:
    html = client.get("/ui/priorities/preview", params=_form()).text
    assert _status(html) == ("unconfirmed", "true")
    assert "disabled" not in _confirm_button(html)
    assert "Not confirmed yet" in html
    assert "priority-actions__revert--idle" in _revert_button(html)


def test_status_confirmed_disables_confirm(confirmed: TestClient) -> None:
    html = confirmed.get("/ui/priorities/preview", params=_form()).text
    assert _status(html) == ("confirmed", "true")
    assert "disabled" in _confirm_button(html)
    assert "Confirmed: Human" in html
    revert = _revert_button(html)
    assert "priority-actions__revert--idle" in revert and "disabled" in revert


def test_status_changed_shows_revert_and_old_to_new(confirmed: TestClient) -> None:
    html = confirmed.get(
        "/ui/priorities/preview",
        params=_form(attributes="C", skills="B"),
    ).text
    assert _status(html) == ("changed", "true")
    assert "disabled" not in _confirm_button(html)
    revert = _revert_button(html)
    assert "priority-actions__revert--idle" not in revert and "disabled" not in revert
    assert "Changed — not confirmed yet" in html
    assert "B — 20 attribute points → C — 16 attribute points" in html
    assert "C — 28 skill points, 2 skill group points → B — 36 skill points" in html
    # An unchanged line reads as usual.
    assert "D — 50000¥" in html and "→ D — 50000¥" not in html
    assert html.count("priority-summary__row--changed") == 2


def test_a_metatype_change_alone_is_a_change(confirmed: TestClient) -> None:
    html = confirmed.get("/ui/priorities/preview", params=_form(metatype_id=TROLL)).text
    assert _status(html) == ("changed", "true")
    assert "A — Human, 9 special attribute points → A — Troll, 5 special attribute points" in html


def test_a_method_change_alone_is_a_change(confirmed: TestClient) -> None:
    html = confirmed.get(
        "/ui/priorities/preview", params=_form(SUM_TO_TEN_BUILD_METHOD)
    ).text  # five distinct letters: a legal Sum-to-Ten selection too
    assert _status(html) == ("changed", "true")
    assert "Priority → Sum-to-Ten" in html


@pytest.mark.parametrize(
    ("form", "confirmable"),
    [
        (_form(), "true"),
        (_form(attributes="A"), "false"),  # Priority: a repeated letter
        (
            _form(
                SUM_TO_TEN_BUILD_METHOD,
                heritage="B",
                talent="B",
                attributes="B",
                skills="E",
                resources="D",
            ),
            "true",
        ),  # 3+3+3+0+1
        (
            _form(
                SUM_TO_TEN_BUILD_METHOD,
                heritage="A",
                talent="A",
                attributes="A",
                skills="E",
                resources="E",
            ),
            "false",
        ),  # 12
        (_form(metatype_id=""), "false"),  # no metatype chosen
        (_form("Pointbuy"), "false"),
    ],
)
def test_confirmable(client: TestClient, form: dict[str, str], confirmable: str) -> None:
    html = client.get("/ui/priorities/preview", params=form).text
    assert _status(html)[1] == confirmable


def test_preview_never_renders_the_tiles_or_spinners(client: TestClient) -> None:
    html = client.get("/ui/priorities/preview", params=_form()).text
    assert "priority-tile" not in html
    assert "spinbutton" not in html
    assert "priority-preview" not in html  # inner content only: the container stays put


def test_preview_rejects_letters_outside_a_to_e(client: TestClient) -> None:
    response = client.get("/ui/priorities/preview", params=_form(heritage="Z"))
    assert response.status_code == 422


# --- The metatype rule ------------------------------------------------------------------------


def test_preview_skips_the_metatype_field_while_the_offer_is_unchanged(
    client: TestClient,
) -> None:
    html = client.get(
        "/ui/priorities/preview",
        params={**_form(attributes="C", skills="B"), "metatype_offer": "A"},
    ).text
    assert "hx-swap-oob" not in html
    assert "metatype-select" not in html  # the field holds focus while the player picks


def test_preview_sends_the_field_when_only_the_special_points_change(client: TestClient) -> None:
    # Heritage A and B both offer every metatype, but each option's label carries its special
    # attribute points, which differ -- so the field is re-rendered, keeping the choice.
    html = client.get(
        "/ui/priorities/preview",
        params={**_form(heritage="B", attributes="A"), "metatype_offer": "A"},
    ).text
    field = re.search(r'<div id="priority-metatype".*?</div>', html, re.S)
    assert field and 'hx-swap-oob="true"' in field.group(0)
    assert f'value="{HUMAN}" selected' in field.group(0)
    assert _status(html) == ("unconfirmed", "true")


def test_preview_resets_a_metatype_no_longer_offered(client: TestClient) -> None:
    html = client.get(
        "/ui/priorities/preview",
        params={**_form(metatype_id=TROLL, heritage="D", resources="A"), "metatype_offer": "A"},
    ).text  # Heritage D offers Human and Elf only

    field = re.search(r'<div id="priority-metatype".*?</div>', html, re.S)
    assert field and 'hx-swap-oob="true"' in field.group(0)
    assert '<option value="" selected disabled>Choose metatype</option>' in field.group(0)
    assert "Troll" not in field.group(0)
    assert 'name="metatype_offer" value="D"' in field.group(0)
    assert _status(html) == ("unconfirmed", "false")
    assert "D — no metatype chosen" in html


def test_preview_keeps_a_metatype_the_new_offer_still_has(client: TestClient) -> None:
    html = client.get(
        "/ui/priorities/preview",
        params={**_form(metatype_id=ELF, heritage="D", resources="A"), "metatype_offer": "A"},
    ).text
    field = re.search(r'<div id="priority-metatype".*?</div>', html, re.S)
    assert field
    assert f'value="{ELF}" selected' in field.group(0)
    assert "Choose metatype" not in field.group(0)
    assert _status(html) == ("unconfirmed", "true")


def test_never_confirmed_page_offers_no_default_metatype(client: TestClient) -> None:
    html = client.get("/ui/page/priorities", headers=HTMX).text
    assert '<option value="" selected disabled>Choose metatype</option>' in html
    assert _status(html) == ("unconfirmed", "false")


def test_confirming_the_placeholder_is_an_itemized_error_not_a_422(client: TestClient) -> None:
    response = client.post("/ui/priorities", data=_form(metatype_id=""))
    assert response.status_code == 200
    assert "Select a metatype offered for the chosen Heritage priority." in response.text


# --- Layout switch ----------------------------------------------------------------------------


def test_sum_to_ten_to_priority_goes_through_the_conversion(client: TestClient) -> None:
    html = client.get(
        "/ui/priorities/layout",
        params={
            **_form(heritage="E", talent="E", attributes="B", skills="B", resources="B"),
            "layout": SUM_TO_TEN_BUILD_METHOD,
        },
    ).text
    assert 'id="priority-tiles"' in html
    assert sorted(_letter_inputs(html)) == [
        ("attributes", "A"),
        ("heritage", "D"),
        ("resources", "C"),
        ("skills", "B"),
        ("talent", "E"),
    ]


def test_priority_to_sum_to_ten_keeps_a_confirmed_characters_letters(
    confirmed: TestClient,
) -> None:
    html = confirmed.get(
        "/ui/priorities/layout",
        params={**_form(SUM_TO_TEN_BUILD_METHOD), "layout": PRIORITY_BUILD_METHOD},
    ).text
    assert dict(_letter_inputs(html)) == DEFAULT_LETTERS
    assert '<output class="sum-to-ten__sum">10</output> / 10' in html
    assert "Sum-to-Ten" in html and 'value="SumtoTen" selected' in html
    assert _status(html) == ("changed", "true")


def test_priority_to_sum_to_ten_starts_a_never_confirmed_character_at_all_e(
    client: TestClient,
) -> None:
    html = client.get(
        "/ui/priorities/layout",
        params={**_form(SUM_TO_TEN_BUILD_METHOD), "layout": PRIORITY_BUILD_METHOD},
    ).text
    assert {letter for _, letter in _letter_inputs(html)} == {"E"}


def test_layout_switch_keeps_the_metatype_by_the_preview_rule(confirmed: TestClient) -> None:
    kept = confirmed.get(
        "/ui/priorities/layout",
        params={**_form(SUM_TO_TEN_BUILD_METHOD), "layout": PRIORITY_BUILD_METHOD},
    ).text
    assert f'value="{HUMAN}" selected' in kept
    reset = confirmed.get(
        "/ui/priorities/layout",
        params={
            # Heritage E (Human only) once converted: E E B B B -> D E A B C, Heritage D.
            **_form(
                metatype_id=TROLL,
                heritage="E",
                talent="E",
                attributes="B",
                skills="B",
                resources="B",
            ),
            "layout": SUM_TO_TEN_BUILD_METHOD,
            "build_method": PRIORITY_BUILD_METHOD,
        },
    ).text
    assert "Choose metatype" in reset and "Troll" not in reset


def test_layout_rejects_an_unknown_method(client: TestClient) -> None:
    response = client.get(
        "/ui/priorities/layout", params={**_form("Karma"), "layout": PRIORITY_BUILD_METHOD}
    )
    assert response.status_code == 422


# --- Revert -----------------------------------------------------------------------------------


def test_revert_renders_the_confirmed_selection(confirmed: TestClient) -> None:
    html = confirmed.get("/ui/priorities/revert").text
    assert 'id="priority-section"' in html
    assert dict(_letter_inputs(html)) == DEFAULT_LETTERS
    assert _status(html) == ("confirmed", "true")


# --- The GETs change nothing ------------------------------------------------------------------


def test_the_read_only_endpoints_leave_the_session_alone(confirmed: TestClient) -> None:
    changed = _form(SUM_TO_TEN_BUILD_METHOD, metatype_id=TROLL, attributes="A", skills="A")
    for response in (
        confirmed.get("/ui/priorities/preview", params=changed),
        confirmed.get("/ui/priorities/layout", params={**changed, "layout": PRIORITY_BUILD_METHOD}),
        confirmed.get("/ui/priorities/revert"),
    ):
        assert response.status_code == 200
        assert "HX-Trigger" not in response.headers
    html = confirmed.get("/ui/page/priorities", headers=HTMX).text
    assert dict(_letter_inputs(html)) == DEFAULT_LETTERS
    assert _status(html) == ("confirmed", "true")


# --- Messages sit below every control ---------------------------------------------------------


def test_error_and_stale_warning_render_after_the_controls(confirmed: TestClient) -> None:
    # Spend skill points the Skills letter can't hold once it drops to E, then reconfirm badly.
    confirmed.post("/ui/priorities", data=_form(skills="A", heritage="C", metatype_id=HUMAN))
    html = confirmed.post(
        "/ui/priorities", data=_form(skills="A", heritage="C", attributes="A", metatype_id=HUMAN)
    ).text
    assert "must each use a different priority letter" in html
    error = html.index('class="error"')
    for control in (
        'id="priority-method"',
        'id="metatype-select"',
        'type="submit"',
        "priority-actions__revert",
        'class="priority-summary"',
    ):
        assert html.index(control) < error, control


def test_stale_warning_is_the_last_thing_in_the_panel(confirmed: TestClient) -> None:
    client = confirmed
    # 24 skill points spent at Skills C (28), then Skills moved to E (18): no longer fits.
    ungrouped = [s for s in MUNDANE_SKILLS if s.skill_group is None][:4]
    client.post("/ui/skills", data={f"skill_{s.id}": "6" for s in ungrouped})
    html = client.post("/ui/priorities", data=_form(skills="E", talent="C")).text
    assert "no longer fit these priorities" in html
    warning = html.index('class="warning"')
    assert html.index('class="priority-summary"') < warning
    assert html.index('type="submit"') < warning
    assert html.index("</form>") > warning


# --- Both layouts, every theme, no CSP violation ----------------------------------------------


@pytest.mark.parametrize("theme", [t.slug for t in THEMES])
@pytest.mark.parametrize("method", [PRIORITY_BUILD_METHOD, SUM_TO_TEN_BUILD_METHOD])
def test_both_layouts_render_csp_clean_under_every_theme(
    confirmed: TestClient, theme: str, method: str
) -> None:
    confirmed.post("/ui/prefs/theme", data={"theme": theme})
    panel = confirmed.get(
        "/ui/priorities/layout", params={**_form(method), "layout": PRIORITY_BUILD_METHOD}
    ).text
    _assert_csp_clean(panel, f"{method} panel ({theme})")
    confirmed.post("/ui/priorities", data=_form(method))
    page = confirmed.get("/ui/page/priorities").text
    assert f"themes/{theme}.css" in page
    assert ("spinbutton" in page) == (method == SUM_TO_TEN_BUILD_METHOD)
    _assert_csp_clean(page, f"{method} page ({theme})")
