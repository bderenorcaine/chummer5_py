"""WP149 (Phase Z): the Skills page's Knowledge tab -- one table for Knowledge and Language
skills, sorted into the engine's two lists by each row's category. See
`spec/plan/phase-z-page-redesigns.md`, "Redesign 4"."""

from __future__ import annotations

import json
import re

from fastapi.testclient import TestClient

from chummer5.data.metatypes import load_metatypes
from chummer5.data.priorities import load_priorities
from chummer5.data.skills import load_knowledge_skills
from chummer5.engine.character import metatype_choices
from chummer5.web.app import create_app
from chummer5.web.catalogs import MAX_KNOWLEDGE_TABLE_ROWS

METATYPES = load_metatypes()
PRIORITIES = load_priorities()
CATALOG = load_knowledge_skills()

HTMX = {"HX-Request": "true"}


def _confirm(client: TestClient) -> None:
    """Human, Heritage A / Attributes B / Skills C (28) / Resources D; INT 1 + LOG 1 → 4 free."""
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


def _row(i: int, name: str, category: str, rating: int = 0, **extra: str) -> dict[str, str]:
    data = {
        f"knowledge_name_{i}": name,
        f"knowledge_category_{i}": category,
        f"knowledge_rating_{i}": str(rating),
    }
    return data | {f"knowledge_{key}_{i}": value for key, value in extra.items()}


def _saved(client: TestClient) -> dict[str, object]:
    return dict(json.loads(client.get("/character/save").content))


def _rows(html: str) -> list[str]:
    body = html[html.index("<tbody>") : html.index("</tbody>")]
    return re.findall(r"<tr\b.*?</tr>", body, re.S)


def _input(row: str, name: str) -> str:
    match = re.search(rf'<(?:input|select)\b[^>]*name="{name}"[^>]*>', row, re.S)
    assert match is not None, name
    return match.group(0)


def _counter(client: TestClient, label: str) -> str:
    strip = client.get("/ui/tabs/skills?tab=knowledge").text
    match = re.search(
        rf'<abbr[^>]*>{label}</abbr></dt>\s*<dd class="skills-counter__value">([^<]+)</dd>', strip
    )
    assert match is not None, label
    return match.group(1)


def test_one_table_with_language_as_a_category_and_native_only_on_language_rows() -> None:
    client = TestClient(create_app())
    _confirm(client)
    html = client.post(
        "/ui/knowledge",
        data=_row(0, "Corporations", "Street", 1) | _row(1, "English", "Language", native="on"),
    ).text

    headers = re.findall(r"<th>(?:<abbr[^>]*>)?([^<]+)", html)
    assert headers == [
        "Name",
        "Category",
        "Attribute",
        "Native (free)",
        "Kn pts",
        "Ka pts",
        "Rating",
        "Specialization",
        "Pool",
    ]
    rows = _rows(html)
    assert len(rows) == 3  # the two filled rows and one blank
    assert "disabled" in _input(rows[0], "knowledge_native_0")
    assert "disabled" not in _input(rows[1], "knowledge_native_1")
    assert "checked" in _input(rows[1], "knowledge_native_1")
    assert '<option value="Language" selected>' in rows[1]
    assert "<td>INT</td>" in rows[0] and "<td>INT</td>" in rows[1]  # Street, Language
    assert "<td>N</td>" in rows[1]
    # A native row's points fields are disabled: a native language has no rating to buy.
    assert "disabled" in _input(rows[1], "knowledge_rating_1")
    assert "disabled" in _input(rows[1], "knowledge_karma_1")
    assert "<td>—</td>" in rows[2]  # the blank row: no category, no attribute


def test_rows_commit_to_the_list_their_category_names() -> None:
    client = TestClient(create_app())
    _confirm(client)
    client.post(
        "/ui/knowledge",
        data=_row(0, "Japanese", "Language", 1) | _row(1, "Corporations", "Street", 1),
    )
    saved = _saved(client)
    assert saved["language_skill_picks"] == [{"name": "Japanese", "rating": 1, "native": False}]
    assert saved["knowledge_skill_picks"] == [
        {"name": "Corporations", "category": "Street", "rating": 1}
    ]

    # Switching the row to Academic moves it to the other list; Native goes with the category.
    client.post(
        "/ui/knowledge",
        data=_row(0, "Japanese", "Academic", 1, native="on") | _row(1, "Corporations", "Street", 1),
    )
    saved = _saved(client)
    assert saved["language_skill_picks"] == []
    assert {"name": "Japanese", "category": "Academic", "rating": 1} in saved[
        "knowledge_skill_picks"
    ]

    client.post(
        "/ui/knowledge",
        data=_row(0, "Japanese", "Language", native="on") | _row(1, "Corporations", "Street", 1),
    )
    assert _saved(client)["language_skill_picks"] == [
        {"name": "Japanese", "rating": 0, "native": True}
    ]


def test_the_native_language_limit_still_holds() -> None:
    client = TestClient(create_app())
    _confirm(client)
    response = client.post(
        "/ui/knowledge",
        data=_row(0, "English", "Language", native="on")
        | _row(1, "Sperethiel", "Language", native="on"),
    ).text
    assert "at most 1 language" in response
    assert _saved(client)["language_skill_picks"] == []


def test_a_name_on_two_rows_is_refused() -> None:
    client = TestClient(create_app())
    _confirm(client)
    response = client.post(
        "/ui/knowledge",
        data=_row(0, "Elven", "Language", 1) | _row(1, "Elven", "Academic", 1),
    ).text
    assert "Two rows are named Elven" in response
    assert _saved(client)["knowledge_skill_picks"] == []


def test_add_knowledge_skill_adds_blank_rows_up_to_the_combined_cap() -> None:
    client = TestClient(create_app())
    _confirm(client)
    page = client.get("/ui/page/skills/knowledge", headers=HTMX).text
    html = page[page.index('id="knowledge-skills"') :]
    button = re.search(r'<button\s[^>]*class="skills-add"[^>]*>', html, re.S)
    assert button is not None
    assert 'type="button"' in button.group(0) and 'hx-post="/ui/knowledge"' in button.group(0)
    assert """hx-vals='{"knowledge_add": "1"}'""" in button.group(0)
    assert "disabled" not in button.group(0)
    assert len(_rows(html)) == 1

    assert len(_rows(client.post("/ui/knowledge", data={"knowledge_add": "1"}).text)) == 2

    full = {}
    for i in range(MAX_KNOWLEDGE_TABLE_ROWS - 1):
        full |= _row(i, f"Topic {i}", "Interest")
    html = client.post("/ui/knowledge", data=full).text
    assert len(_rows(html)) == MAX_KNOWLEDGE_TABLE_ROWS  # the last blank row still fits
    button = re.search(r'<button\s[^>]*class="skills-add"[^>]*>', html, re.S)
    assert button is not None and "disabled" in button.group(0)  # disabled, still there
    html = client.post("/ui/knowledge", data=full | {"knowledge_add": "1"}).text
    assert len(_rows(html)) == MAX_KNOWLEDGE_TABLE_ROWS


def test_the_toggle_commits_to_the_right_field_for_knowledge_and_languages() -> None:
    client = TestClient(create_app())
    _confirm(client)
    client.post(
        "/ui/knowledge",
        data=_row(0, "Corporations", "Street", 1, spec="Ares")
        | _row(1, "Japanese", "Language", 1, spec="Speak", spec_karma="1"),
    )
    saved = _saved(client)
    assert saved["knowledge_specializations"] == {"Corporations": "Ares"}
    assert saved["karma_knowledge_specializations"] == {"Japanese": "Speak"}

    # Without a rating bought with Knowledge points, only Karma can pay -- the toggle is forced.
    html = client.post(
        "/ui/knowledge",
        data=_row(0, "Corporations", "Street", 0, karma="1", spec="Ares"),
    ).text
    assert _saved(client)["karma_knowledge_specializations"] == {"Corporations": "Ares"}
    toggle = _input(_rows(html)[0], "knowledge_spec_karma_0")
    assert "checked" in toggle and "disabled" in toggle
    assert '<input type="hidden" name="knowledge_spec_karma_0" value="1" />' in html


def test_placeholders_follow_the_catalog() -> None:
    client = TestClient(create_app())
    _confirm(client)
    html = client.post(
        "/ui/knowledge",
        data=_row(0, "administration", "Professional", 1)
        | _row(1, "Klingon", "Language", 1)
        | _row(2, "My Own Topic", "Interest", 1)
        | _row(3, "", "Street"),
    ).text
    rows = _rows(html)
    administration = next(e for e in CATALOG if e.name == "Administration")
    assert f'placeholder="e.g. {administration.specializations[0]}"' in _input(
        rows[0], "knowledge_spec_0"
    )  # matched ignoring case
    assert 'placeholder="e.g. Read/Write"' in _input(rows[1], "knowledge_spec_1")
    assert "placeholder" not in _input(rows[2], "knowledge_spec_2")  # unmatched: none
    assert "placeholder" not in _input(rows[0], "knowledge_name_0")  # filled: none
    street = [e.name for e in CATALOG if e.category == "Street"]
    name_field = _input(rows[3], "knowledge_name_3")
    assert f'placeholder="e.g. {street[3 % len(street)]}"' in name_field
    # Neighbouring blank rows suggest different names.
    html = client.post("/ui/knowledge", data={"knowledge_add": "1"}).text
    fields = [_input(r, f"knowledge_name_{i}") for i, r in enumerate(_rows(html))]
    placeholders = [re.findall(r'placeholder="([^"]+)"', field) for field in fields]
    assert len(placeholders) == 2 and all(placeholders)
    assert placeholders[0] != placeholders[1]


def test_knowledge_spending_active_points_shows_in_the_s_counter() -> None:
    client = TestClient(create_app())
    _confirm(client)
    assert _counter(client, "S") == "28/28"
    page = client.post(
        "/ui/knowledge",
        data=_row(0, "Corporations", "Street", 4) | _row(1, "Gangs", "Street", 2),
    ).text
    assert "Active skill points used by Knowledge past its free points: 2." in page
    assert _counter(client, "Kn") == "0/4"
    assert _counter(client, "S") == "26/28"


def test_ids_come_from_the_row_index_and_the_echo_keeps_the_posted_order() -> None:
    client = TestClient(create_app())
    _confirm(client)
    # A Language row above a Knowledge row: the echo keeps it there (so its ids hold) ...
    html = client.post(
        "/ui/knowledge",
        data=_row(0, "Japanese", "Language", 1) | _row(1, "Corporations", "Street", 1),
    ).text
    rows = _rows(html)
    assert 'value="Japanese"' in rows[0] and 'id="knowledge-name-0"' in rows[0]
    for prefix in ("name", "category", "native", "rating", "karma", "spec-karma", "spec"):
        assert f'id="knowledge-{prefix}-1"' in rows[1]
    ids = re.findall(r'\bid="([^"]+)"', html)
    assert len(ids) == len(set(ids))
    # ... while a fresh page render lists Knowledge skills first, then Languages.
    page = client.get("/ui/page/skills/knowledge", headers=HTMX).text
    names = re.findall(r'name="knowledge_name_\d+"\s+value="([^"]*)"', page)
    assert names == ["Corporations", "Japanese", ""]


def test_no_submit_button_no_details_and_messages_at_the_bottom() -> None:
    client = TestClient(create_app())
    _confirm(client)
    html = client.post("/ui/knowledge", data=_row(0, "Corporations", "Nope", 1)).text
    assert "<details" not in html
    assert 'type="submit"' not in html
    messages = html.index(
        '<div id="knowledge-messages" class="skills-messages" hx-swap-oob="true">'
    )
    assert html.index('class="error"') > messages > html.index("</form>")
    assert '<input type="hidden" name="skills_tab" value="knowledge" />' in html
