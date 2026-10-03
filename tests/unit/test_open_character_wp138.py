"""WP138: the stored open character -- first store, autosave, restore, the tab guard, the
cross-device revision check, switching, and session eviction."""

from __future__ import annotations

import json
import re
import threading
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from starlette.requests import Request

from chummer5 import accounts
from chummer5.engine.character import metatype_choices
from chummer5.store import Store
from chummer5.web import persistence
from chummer5.web.app import create_app
from chummer5.web.catalogs import METATYPES, PRIORITIES
from chummer5.web.session import SESSION_COOKIE_NAME, ChargenSession, SessionStore

PASSWORD = "correct horse battery"


def _metatype_id(name: str) -> str:
    choices = metatype_choices(PRIORITIES.heritage["A"], METATYPES)
    return next(c.metatype.id for c in choices if c.metatype.name == name)


HUMAN = _metatype_id("Human")
ELF = _metatype_id("Elf")


def confirm(client: TestClient, metatype: str = HUMAN, token: str | None = None):  # type: ignore[no-untyped-def]
    data = {
        "heritage_letter": "A",
        "attributes_letter": "B",
        "skills_letter": "C",
        "resources_letter": "D",
        "talent_letter": "E",
        "metatype_id": metatype,
    }
    return client.post("/ui/priorities", data=data, headers=_htmx(token))


def bio(client: TestClient, name: str, token: str | None = None):  # type: ignore[no-untyped-def]
    return client.post("/ui/bio", data={"name": name}, headers=_htmx(token))


def _htmx(token: str | None) -> dict[str, str]:
    headers = {"HX-Request": "true"}
    if token is not None:
        headers[persistence.CHARACTER_ID_HEADER] = token
    return headers


def shell_token(html: str) -> str:
    """The id the page's `hx-headers` would send."""
    match = re.search(r"hx-headers='\{\"X-Character-Id\": \"([^\"]+)\"\}'", html)
    assert match, "no hx-headers on the page"
    return match.group(1)


def stored(store: Store, owner: int, character_id: int) -> dict:  # type: ignore[type-arg]
    record = store.get_character(owner, character_id)
    assert record is not None
    return json.loads(record.save_json)  # type: ignore[no-any-return]


# --- fixtures ------------------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _cheap_scrypt(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(accounts, "SCRYPT_PARAMS", accounts.ScryptParams(n=2**4, r=8, p=1))
    monkeypatch.setattr(accounts, "_dummy_hash", None)


@pytest.fixture
def store(tmp_path: Path) -> Store:
    return Store(tmp_path / "wp138.db", quota=100)


@pytest.fixture
def local(store: Store) -> Iterator[TestClient]:
    with TestClient(create_app(mode="local", store=store), follow_redirects=False) as c:
        yield c


def local_owner(store: Store) -> int:
    return accounts.ensure_local_user(store).id


@pytest.fixture
def hosted_app(store: Store):  # type: ignore[no-untyped-def]
    return create_app(mode="hosted", store=store)


def logged_in(app, store: Store, username: str = "alice") -> TestClient:  # type: ignore[no-untyped-def]
    client = TestClient(app, follow_redirects=False)
    if store.get_user_by_name(username) is None:
        code = accounts.mint_invite(store).code
        response = client.post(
            "/register",
            data={"username": username, "password": PASSWORD, "confirm": PASSWORD, "invite": code},
        )
    else:
        response = client.post("/login", data={"username": username, "password": PASSWORD})
    assert response.status_code == 303
    return client


def user_id(store: Store, username: str = "alice") -> int:
    user = store.get_user_by_name(username)
    assert user is not None
    return user.id


# --- first store ---------------------------------------------------------------------------------


def test_nothing_is_stored_before_the_priority_confirmation(
    local: TestClient, store: Store
) -> None:
    assert shell_token(local.get("/").text) == "new"
    assert store.count_characters(local_owner(store)) == 0
    assert bio(local, "Nobody").status_code == 200  # no character yet: nothing to store
    assert store.count_characters(local_owner(store)) == 0


def test_first_confirmation_stores_and_swaps_the_shell(local: TestClient, store: Store) -> None:
    response = confirm(local, token="new")
    assert response.status_code == 200
    assert response.headers["HX-Retarget"] == "#app-shell"
    assert response.headers["HX-Reswap"] == "outerHTML"
    owner = local_owner(store)
    [summary] = store.list_characters(owner)
    assert shell_token(response.text) == str(summary.id)  # the new id reaches the tab at once
    assert stored(store, owner, summary.id)["metatype_name"] == "Human"
    user = store.get_user(owner)
    assert user is not None and user.last_character_id == summary.id


def test_reconfirmation_updates_rather_than_inserts(local: TestClient, store: Store) -> None:
    token = shell_token(confirm(local).text)
    response = confirm(local, ELF, token=token)
    assert "HX-Retarget" not in response.headers  # an ordinary fragment again
    owner = local_owner(store)
    assert store.count_characters(owner) == 1
    assert stored(store, owner, int(token))["metatype_name"] == "Elf"


def test_confirmation_at_quota_is_refused_and_stores_nothing(tmp_path: Path) -> None:
    store = Store(tmp_path / "quota.db", quota=2)
    with TestClient(create_app(mode="local", store=store), follow_redirects=False) as client:
        for _ in range(2):
            confirm(client)
            client.post("/characters/new")
        response = confirm(client)
        assert response.status_code == 200
        assert "You already have 2 characters" in response.text
        assert "HX-Retarget" not in response.headers
        assert store.count_characters(local_owner(store)) == 2
        assert shell_token(client.get("/").text) == "new"
        assert "Confirmed:" not in client.get("/").text


# --- autosave ------------------------------------------------------------------------------------


def test_every_change_is_saved_and_survives_a_restart(store: Store) -> None:
    app = create_app(mode="hosted", store=store)
    client = logged_in(app, store)
    token = shell_token(confirm(client).text)
    assert bio(client, "Ghost", token).status_code == 200
    confirm(client, ELF, token=token)

    # A new process: no chargen session survives, and the old login cookie is forgotten too.
    restarted = create_app(mode="hosted", store=store)
    again = logged_in(restarted, store)
    page = again.get("/").text
    assert shell_token(page) == token
    assert "Ghost" in page
    assert "Confirmed: Elf" in page


def test_local_mode_restores_after_a_restart_by_cookie(store: Store) -> None:
    with TestClient(create_app(mode="local", store=store), follow_redirects=False) as first:
        token = shell_token(confirm(first).text)
        bio(first, "Ghost", token)
        cookie = first.cookies[SESSION_COOKIE_NAME]
    with TestClient(create_app(mode="local", store=store), follow_redirects=False) as second:
        second.cookies.set(SESSION_COOKIE_NAME, cookie)  # the browser still has it
        page = second.get("/")
        assert shell_token(page.text) == token and "Ghost" in page.text
        assert page.cookies.get(SESSION_COOKIE_NAME) not in (None, cookie)  # a fresh id
        # A browser with no cookie at all starts a new character, as before WP138.
        fresh = TestClient(second.app, follow_redirects=False)
        assert shell_token(fresh.get("/").text) == "new"


def test_unchanged_saves_are_skipped(local: TestClient, store: Store) -> None:
    token = shell_token(confirm(local).text)
    owner = local_owner(store)
    bio(local, "Same", token)
    revision = store.get_character(owner, int(token)).revision  # type: ignore[union-attr]
    bio(local, "Same", token)
    local.get("/ui/page/skills", headers=_htmx(token))
    assert store.get_character(owner, int(token)).revision == revision  # type: ignore[union-attr]


def test_prefs_posts_never_autosave(
    local: TestClient, store: Store, monkeypatch: pytest.MonkeyPatch
) -> None:
    token = shell_token(confirm(local).text)
    calls: list[str] = []
    real = persistence.autosave

    def counting(request: Request, session: ChargenSession) -> persistence.SaveOutcome:
        calls.append(request.url.path)
        return real(request, session)

    monkeypatch.setattr(persistence, "autosave", counting)
    assert (
        local.post("/ui/prefs/theme", data={"theme": "classic"}, headers=_htmx(token)).status_code
        == 200
    )
    assert calls == []
    bio(local, "Changed", token)
    assert calls == ["/ui/bio"]


def test_failed_posts_do_not_autosave(local: TestClient, store: Store) -> None:
    token = shell_token(confirm(local).text)
    owner = local_owner(store)
    revision = store.get_character(owner, int(token)).revision  # type: ignore[union-attr]
    response = local.post("/ui/prefs/theme", data={"theme": "nope"}, headers=_htmx(token))
    assert response.status_code == 422
    assert store.get_character(owner, int(token)).revision == revision  # type: ignore[union-attr]


# --- the tab guard -------------------------------------------------------------------------------


def test_stale_tab_post_gets_the_notice_and_changes_nothing(
    local: TestClient, store: Store
) -> None:
    first = shell_token(confirm(local).text)
    bio(local, "Alpha", first)
    local.post("/characters/new")
    second = shell_token(confirm(local, ELF, token="new").text)
    bio(local, "Beta", second)
    owner = local_owner(store)
    before = (stored(store, owner, int(first)), stored(store, owner, int(second)))

    stale = bio(local, "Overwritten", first)  # a tab still showing the first character
    assert stale.status_code == 409
    assert stale.headers["HX-Retarget"] == "#page"
    assert "Another tab of this browser has opened a different character" in stale.text
    assert "HX-Trigger" not in stale.headers  # nothing changed, so nothing re-fetches
    assert (stored(store, owner, int(first)), stored(store, owner, int(second))) == before
    assert "Overwritten" not in local.get("/").text


def test_stale_tab_get_is_told_to_reload(local: TestClient) -> None:
    first = shell_token(confirm(local).text)
    local.post("/characters/new")
    response = local.get("/ui/page/skills", headers=_htmx(first))
    assert response.headers["HX-Refresh"] == "true"
    assert response.text == ""


def test_a_new_tab_still_on_new_is_stale_once_a_character_is_stored(local: TestClient) -> None:
    confirm(local, token="new")
    assert bio(local, "Late", "new").status_code == 409


def test_requests_without_the_header_are_not_guarded(local: TestClient) -> None:
    confirm(local)
    assert bio(local, "Plain").status_code == 200  # no header: not an htmx tab
    assert local.get("/").status_code == 200


def test_the_id_lives_inside_body_so_history_restores_renew_it(local: TestClient) -> None:
    """Opening B, then back/forward: htmx re-fetches the page (historyCacheSize 0) and swaps the
    body's *contents*. The id must come with those contents, not sit on <body> itself."""
    a = shell_token(confirm(local).text)
    local.post("/characters/new")
    b = shell_token(confirm(local, ELF, token="new").text)
    restore = local.get(
        "/ui/page/priorities", headers={"HX-Request": "true", "HX-History-Restore-Request": "true"}
    )
    html = restore.text
    body_tag = re.search(r"<body[^>]*>", html)
    assert body_tag and "hx-headers" not in body_tag.group(0)
    assert shell_token(html) == b != a
    inside_body = html[body_tag.end() :]
    assert 'id="app-shell"' in inside_body and "X-Character-Id" in inside_body


def test_htmx_config_lets_409_swap(local: TestClient) -> None:
    html = local.get("/").text
    config = re.search(r"name=\"htmx-config\"\s+content='([^']+)'", html)
    assert config
    parsed = json.loads(config.group(1))
    assert parsed["historyCacheSize"] == 0
    codes = [entry["code"] for entry in parsed["responseHandling"]]
    assert codes.index("409") < codes.index("[45]..")
    assert {"code": "409", "swap": True} in parsed["responseHandling"]


# --- the revision check --------------------------------------------------------------------------


def test_second_device_autosave_is_refused_and_the_first_edit_kept(
    hosted_app,
    store: Store,  # type: ignore[no-untyped-def]
) -> None:
    laptop = logged_in(hosted_app, store)
    token = shell_token(confirm(laptop).text)
    phone = logged_in(hosted_app, store)  # a second login: its own chargen session, same character
    assert shell_token(phone.get("/").text) == token

    assert bio(laptop, "From laptop", token).status_code == 200
    refused = bio(phone, "From phone", token)
    assert refused.status_code == 409
    assert "changed on another device" in refused.text

    owner = user_id(store)
    assert stored(store, owner, int(token))["biography"]["name"] == "From laptop"
    # the phone's session reloaded the stored version: its next edit builds on the laptop's
    assert "From laptop" in phone.get("/").text
    assert bio(phone, "From phone, again", token).status_code == 200
    assert stored(store, owner, int(token))["biography"]["name"] == "From phone, again"


def test_character_deleted_elsewhere_resets_the_session(local: TestClient, store: Store) -> None:
    token = shell_token(confirm(local).text)
    store.delete_character(local_owner(store), int(token))
    refused = bio(local, "Ghost", token)
    assert refused.status_code == 409
    assert shell_token(local.get("/").text) == "new"


def test_concurrent_autosaves_of_one_session_never_conflict_with_each_other(
    local: TestClient, store: Store
) -> None:
    token = shell_token(confirm(local).text)
    app = local.app
    session = next(iter(app.state.sessions._sessions.values()))  # type: ignore[attr-defined]
    request = Request({"type": "http", "app": app, "headers": [], "state": {}})
    from dataclasses import replace

    outcomes: list[persistence.SaveOutcome] = []
    barrier = threading.Barrier(6)

    def edit(i: int) -> None:
        with session.lock:
            character = session.character
            session.character = replace(
                character, biography=replace(character.biography, name=f"n{i}")
            )
        barrier.wait()
        outcomes.append(persistence.autosave(request, session))

    threads = [threading.Thread(target=edit, args=(i,)) for i in range(6)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert persistence.SaveOutcome.CONFLICT not in outcomes
    saved = stored(store, local_owner(store), int(token))["biography"]["name"]
    assert saved == session.character.biography.name


# --- switching -----------------------------------------------------------------------------------


def test_new_resets_and_open_switches_back(local: TestClient, store: Store) -> None:
    first = shell_token(confirm(local).text)
    bio(local, "Alpha", first)
    response = local.post("/characters/new", headers={"HX-Request": "true"})
    assert response.headers["HX-Redirect"] == "/"
    assert shell_token(local.get("/").text) == "new"
    user = store.get_user(local_owner(store))
    assert user is not None and user.last_character_id is None

    opened = local.post(f"/characters/{first}/open")
    assert opened.status_code == 303 and opened.headers["location"] == "/"
    page = local.get("/").text
    assert shell_token(page) == first and "Alpha" in page
    user = store.get_user(local_owner(store))
    assert user is not None and user.last_character_id == int(first)


def test_switching_is_not_tab_guarded(local: TestClient) -> None:
    first = shell_token(confirm(local).text)
    local.post("/characters/new")
    # a stale tab can still switch: the switch is what the player asked for
    assert local.post("/characters/new", headers=_htmx(first)).status_code == 200


def test_cannot_open_another_users_character(hosted_app, store: Store) -> None:  # type: ignore[no-untyped-def]
    alice = logged_in(hosted_app, store, "alice")
    token = shell_token(confirm(alice).text)
    bob = logged_in(hosted_app, store, "bob")
    assert bob.post(f"/characters/{token}/open").status_code == 404
    assert bob.post("/characters/99999/open").status_code == 404
    assert shell_token(bob.get("/").text) == "new"


def test_load_stores_a_new_character_and_leaves_the_open_one(
    local: TestClient, store: Store
) -> None:
    first = shell_token(confirm(local).text)
    bio(local, "Original", first)
    owner = local_owner(store)
    save = json.dumps(stored(store, owner, int(first)))
    before = stored(store, owner, int(first))

    response = local.post(
        "/character/load",
        files={"save_file": ("x.json", save.encode(), "application/json")},
        headers=_htmx(first),
    )
    assert response.status_code == 200
    assert response.headers["HX-Retarget"] == "#app-shell"
    second = shell_token(response.text)
    assert second != first
    assert "Loaded" in response.text or "loaded" in response.text
    assert store.count_characters(owner) == 2
    assert stored(store, owner, int(first)) == before


def test_title_bar_names_the_open_character(local: TestClient) -> None:
    assert "New character" in local.get("/ui/open-character").text
    token = shell_token(confirm(local).text)
    assert "Unnamed" in local.get("/ui/open-character").text
    bio(local, "Ghost", token)
    fragment = local.get("/ui/open-character").text
    assert "Ghost" in fragment
    assert 'hx-confirm="Leave “Ghost”?' in fragment
    assert 'hx-trigger="chargen-changed from:body"' in fragment


def test_switch_controls_carry_the_warning_and_the_script_loads(local: TestClient) -> None:
    page = local.get("/").text
    assert "/static/tabs.js" in page
    assert 'hx-post="/characters/new"' not in page  # nothing to leave yet
    token = shell_token(confirm(local).text)
    bio(local, "Ghost", token)
    export = local.get("/ui/page/export").text
    assert export.count('hx-confirm="Leave “Ghost”?') == 3  # New, load, import
    assert local.get("/static/tabs.js").status_code == 200


# --- lifecycle -----------------------------------------------------------------------------------


def test_idle_sessions_are_evicted() -> None:
    sessions = SessionStore(idle_seconds=60)
    key, session = sessions.create()
    session.last_used -= 61
    sessions.create()
    assert sessions.sweep() == 1
    assert sessions.get(key) is None and len(sessions) == 1


def test_evicted_session_is_rebuilt_from_the_last_opened_character(
    hosted_app,
    store: Store,  # type: ignore[no-untyped-def]
) -> None:
    client = logged_in(hosted_app, store)
    token = shell_token(confirm(client).text)
    bio(client, "Survivor", token)
    sessions: SessionStore = hosted_app.state.sessions
    for session in sessions._sessions.values():
        session.last_used -= sessions.idle_seconds + 1
    assert sessions.sweep() >= 1
    page = client.get("/").text
    assert shell_token(page) == token and "Survivor" in page


def test_orphaned_hosted_session_ages_out(hosted_app, store: Store) -> None:  # type: ignore[no-untyped-def]
    """WP137 review: a login ended by an admin reset leaves its chargen session unreachable."""
    client = logged_in(hosted_app, store)
    confirm(client)
    sessions: SessionStore = hosted_app.state.sessions
    assert len(sessions) == 1
    accounts.reset_password(store, "alice")
    assert client.get("/").headers["location"] == "/login"
    for session in sessions._sessions.values():
        session.last_used -= sessions.idle_seconds + 1
    sessions.sweep()
    assert len(sessions) == 0


@pytest.mark.parametrize("value", ["2h", "0", "-5", "inf"])
def test_bad_idle_timeout_stops_startup(value: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CHUMMER5_SESSION_IDLE_MINUTES", value)
    with pytest.raises(ValueError, match="CHUMMER5_SESSION_IDLE_MINUTES"):
        create_app(mode="local")
