"""WP139: the character list -- the landing page after login, its name filter, delete, the quota
indicator, and the title bar's link to it."""

from __future__ import annotations

import re
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from tests.fixtures.hosted import hosted_client
from tests.unit.test_open_character_wp138 import (
    ELF,
    PASSWORD,
    confirm,
    logged_in,
    shell_token,
    user_id,
)

from chummer5 import accounts
from chummer5.store import Store
from chummer5.web.app import create_app
from chummer5.web.prefs import THEMES

HTMX = {"HX-Request": "true"}


@pytest.fixture(autouse=True)
def _cheap_scrypt(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(accounts, "SCRYPT_PARAMS", accounts.ScryptParams(n=2**4, r=8, p=1))
    monkeypatch.setattr(accounts, "_dummy_hash", None)


@pytest.fixture
def store(tmp_path: Path) -> Store:
    return Store(tmp_path / "wp139.db", quota=100)


@pytest.fixture
def hosted_app(store: Store):  # type: ignore[no-untyped-def]
    return create_app(mode="hosted", store=store)


@pytest.fixture
def local(store: Store) -> Iterator[TestClient]:
    with TestClient(create_app(mode="local", store=store), follow_redirects=False) as c:
        yield c


def make(client: TestClient, name: str = "", street: str = "", metatype: str | None = None) -> int:
    """Start, store and name one character through the real routes; it stays open."""
    client.post("/characters/new")
    response = confirm(client) if metatype is None else confirm(client, metatype)
    character_id = int(shell_token(response.text))
    if name or street:
        assert client.post("/ui/bio", data={"name": name, "street_name": street}).status_code == 200
    return character_id


def listed_ids(html: str) -> list[int]:
    return [int(i) for i in re.findall(r'hx-post="/characters/(\d+)/delete"', html)]


# --- landing and listing -------------------------------------------------------------------------


def test_login_lands_on_the_list(hosted_app, store: Store) -> None:  # type: ignore[no-untyped-def]
    alice = logged_in(hosted_app, store, "alice")
    alice.post("/logout")
    response = alice.post("/login", data={"username": "alice", "password": PASSWORD})
    assert response.headers["location"] == "/characters"
    page = alice.get("/characters")
    assert page.status_code == 200
    assert "My characters" in page.text
    assert "alice" in page.text and '/logout"' in page.text  # the account links
    assert "No characters yet" in page.text
    assert "0 / 100 characters" in page.text


def test_anonymous_list_redirects_to_login(hosted_app) -> None:  # type: ignore[no-untyped-def]
    client = hosted_client(hosted_app)
    assert client.get("/characters").headers["location"] == "/login"


def test_a_user_sees_exactly_their_own_characters(hosted_app, store: Store) -> None:  # type: ignore[no-untyped-def]
    alice = logged_in(hosted_app, store, "alice")
    mine = [make(alice, "One"), make(alice, "Two"), make(alice, "Three")]
    bob = logged_in(hosted_app, store, "bob")
    theirs = make(bob, "Bobs")

    page = alice.get("/characters").text
    assert sorted(listed_ids(page)) == sorted(mine)
    assert "Bobs" not in page and "3 / 100 characters" in page
    assert listed_ids(bob.get("/characters").text) == [theirs]


def test_newest_change_first_and_street_name_first(local: TestClient) -> None:
    first = make(local, "Jane Doe", "Alias")
    second = make(local)  # no Bio: "Unnamed"
    page = local.get("/characters").text
    assert listed_ids(page) == [second, first]
    assert "Unnamed" in page
    assert "Alias" in page and "Jane Doe" not in page  # street name wins

    local.post(f"/characters/{first}/open")
    local.post("/ui/bio", data={"name": "Jane Doe", "street_name": "Alias2"})  # autosaved
    assert listed_ids(local.get("/characters").text) == [first, second]


def test_metatype_and_time_are_shown(local: TestClient) -> None:
    make(local, "Elfie", metatype=ELF)
    page = local.get("/characters").text
    assert "<td>Elf</td>" in page
    assert re.search(r'<time datetime="[^"]+">\d{4}-\d\d-\d\d \d\d:\d\d UTC</time>', page)


# --- the filter ----------------------------------------------------------------------------------


def test_filter_matches_name_or_street_name_case_insensitively(local: TestClient) -> None:
    make(local, "Bob")
    by_name = make(local, "Alias Smith")
    by_street = make(local, "Jane", "Aliasing")
    response = local.get("/characters", params={"q": "ALI"}, headers=HTMX)
    assert response.status_code == 200
    assert "<html" not in response.text  # the list alone, for #character-list
    assert sorted(listed_ids(response.text)) == sorted([by_name, by_street])
    assert "Bob" not in response.text
    assert "3 / 100 characters" in response.text  # usage counts all, not just matches


def test_filter_without_matches_and_like_wildcards(local: TestClient) -> None:
    make(local, "Plain")
    response = local.get("/characters", params={"q": "%"}, headers=HTMX)
    assert listed_ids(response.text) == []
    assert "No character’s name or street name contains “%”." in response.text


def test_filter_in_a_plain_request_renders_the_whole_page_prefilled(local: TestClient) -> None:
    make(local, "Alias")
    make(local, "Other")
    page = local.get("/characters", params={"q": "ali"})
    assert "<html" in page.text and 'value="ali"' in page.text
    assert len(listed_ids(page.text)) == 1
    restore = local.get(
        "/characters", params={"q": "ali"}, headers={**HTMX, "HX-History-Restore-Request": "true"}
    )
    assert "<html" in restore.text
    assert page.headers["Vary"] == "HX-Request"


# --- delete --------------------------------------------------------------------------------------


def test_delete_removes_the_row_and_the_count_drops(local: TestClient, store: Store) -> None:
    first = make(local, "First")
    second = make(local, "Second")
    response = local.post(f"/characters/{first}/delete", headers=HTMX)
    assert response.status_code == 200
    assert listed_ids(response.text) == [second]
    assert "1 / 100 characters" in response.text
    assert store.count_characters(accounts.ensure_local_user(store).id) == 1
    assert local.post(f"/characters/{first}/delete").status_code == 404  # already gone


def test_delete_keeps_the_filter(local: TestClient) -> None:
    alias = make(local, "Alias")
    other = make(local, "Alias Two")
    make(local, "Bob")
    response = local.post(f"/characters/{alias}/delete", data={"q": "ali"}, headers=HTMX)
    assert listed_ids(response.text) == [other]


def test_cannot_delete_another_users_character(hosted_app, store: Store) -> None:  # type: ignore[no-untyped-def]
    alice = logged_in(hosted_app, store, "alice")
    target = make(alice, "Kept")
    bob = logged_in(hosted_app, store, "bob")
    assert bob.post(f"/characters/{target}/delete").status_code == 404
    assert store.get_character(user_id(store, "alice"), target) is not None


def test_deleting_the_open_character_starts_a_new_one(local: TestClient, store: Store) -> None:
    kept = make(local, "Kept")
    doomed = make(local, "Doomed")  # open
    response = local.post(f"/characters/{doomed}/delete", headers=HTMX)
    assert listed_ids(response.text) == [kept]
    assert shell_token(local.get("/").text) == "new"
    user = store.get_user(accounts.ensure_local_user(store).id)
    assert user is not None and user.last_character_id is None


def test_deleting_another_character_leaves_the_open_one(local: TestClient) -> None:
    other = make(local, "Other")
    current = make(local, "Current")
    local.post(f"/characters/{other}/delete", headers=HTMX)
    assert shell_token(local.get("/").text) == str(current)


def test_delete_always_confirms_and_the_open_one_warns_about_tabs(local: TestClient) -> None:
    other = make(local, "Other")
    current = make(local, "Current")
    page = local.get("/characters").text
    other_delete = _button(page, f"/characters/{other}/delete")
    current_delete = _button(page, f"/characters/{current}/delete")
    for button in (other_delete, current_delete):
        assert 'data-confirm="always"' in button
    assert 'hx-confirm="Delete “Other”? This cannot be undone."' in other_delete
    assert "data-confirm-tabs" not in other_delete
    assert "data-confirm-tabs=" in current_delete and "Other tabs" in current_delete


def _button(html: str, post: str) -> str:
    match = re.search(r'<button[^>]*hx-post="' + re.escape(post) + r'"[^>]*>', html, re.S)
    assert match, post
    return match.group(0)


# --- open, new, and the quota --------------------------------------------------------------------


def test_open_and_new_carry_the_switch_warning(local: TestClient) -> None:
    other = make(local, "Other")
    current = make(local, "Current")
    page = local.get("/characters").text
    open_other = _button(page, f"/characters/{other}/open")
    assert "hx-confirm=" in open_other and "Leave “Current”?" in open_other
    assert f'hx-post="/characters/{current}/open"' not in page  # the open one: Continue instead
    assert "open</span>" in page  # its badge
    assert "Leave “Current”?" in _button(page, "/characters/new")
    assert "data-tabs-passive" in page  # this page doesn't count as a chargen tab


def test_new_has_no_warning_when_nothing_is_stored(local: TestClient) -> None:
    page = local.get("/characters").text
    assert "hx-confirm" not in _button(page, "/characters/new")


def test_at_quota_new_is_disabled_with_the_reason(tmp_path: Path) -> None:
    store = Store(tmp_path / "quota.db", quota=2)
    with TestClient(create_app(mode="local", store=store), follow_redirects=False) as client:
        make(client, "A")
        page = client.get("/characters").text
        assert "disabled" not in _button(page, "/characters/new")
        last = make(client, "B")
        page = client.get("/characters").text
        assert "disabled" in _button(page, "/characters/new")
        assert "2 / 2 characters" in page and "the most an account can store" in page
        response = client.post(f"/characters/{last}/delete", headers=HTMX)
        assert "disabled" not in _button(response.text, "/characters/new")


# --- the shell and themes ------------------------------------------------------------------------


def test_title_bar_links_to_the_list(local: TestClient) -> None:
    assert 'href="/characters"' in local.get("/").text
    make(local, "Named")
    assert 'href="/characters"' in local.get("/ui/open-character").text


def test_list_links_back_to_the_open_character(local: TestClient) -> None:
    assert "Back to character creation" in local.get("/characters").text
    make(local, "Named")
    assert "Back to “Named”" in local.get("/characters").text


def test_local_mode_has_no_account_links(local: TestClient) -> None:
    page = local.get("/characters").text
    assert "/logout" not in page


@pytest.mark.parametrize("theme", [t.slug for t in THEMES])
def test_every_theme_renders_the_list(local: TestClient, theme: str) -> None:
    make(local, "Styled")
    assert local.post("/ui/prefs/theme", data={"theme": theme}).status_code == 200
    page = local.get("/characters").text
    assert f"themes/{theme}.css" in page
    assert 'id="theme-stylesheet"' in page and 'id="font-hint"' in page  # the swap targets
    assert "Styled" in page
