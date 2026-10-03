"""WP137: invite-only accounts, login sessions, the hosted-mode login gate, and the admin CLI."""

from __future__ import annotations

import io
import sqlite3
import threading
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from chummer5 import accounts, admin
from chummer5.store import InviteInvalidError, Store
from chummer5.web.app import create_app
from chummer5.web.auth import AUTH_COOKIE_NAME
from chummer5.web.session import SESSION_COOKIE_NAME

PASSWORD = "correct horse battery"


@pytest.fixture(autouse=True)
def _cheap_scrypt(monkeypatch: pytest.MonkeyPatch) -> None:
    """Production parameters cost 0.3 s per hash; the tests only need the same code path."""
    monkeypatch.setattr(accounts, "SCRYPT_PARAMS", accounts.ScryptParams(n=2**4, r=8, p=1))
    monkeypatch.setattr(accounts, "_dummy_hash", None)


@pytest.fixture
def store(tmp_path: Path) -> Store:
    return Store(tmp_path / "hosted.db")


@pytest.fixture
def client(store: Store) -> Iterator[TestClient]:
    with TestClient(create_app(mode="hosted", store=store), follow_redirects=False) as c:
        yield c


def new_client(store: Store, client: TestClient) -> TestClient:
    """A second browser on the same server."""
    return TestClient(client.app, follow_redirects=False)


def invite(store: Store, **kwargs: float) -> str:
    return accounts.format_invite(accounts.mint_invite(store, **kwargs).code)


def register(client: TestClient, code: str, username: str = "alice", password: str = PASSWORD):  # type: ignore[no-untyped-def]
    return client.post(
        "/register",
        data={"username": username, "password": password, "confirm": password, "invite": code},
    )


def login(client: TestClient, username: str = "alice", password: str = PASSWORD):  # type: ignore[no-untyped-def]
    return client.post("/login", data={"username": username, "password": password})


def run_admin(store: Store, *argv: str) -> tuple[int, str]:
    out = io.StringIO()
    code = admin.main(list(argv), store=store, out=out)
    return code, out.getvalue()


# --- passwords -----------------------------------------------------------------------------------


def test_password_hash_round_trip_and_stored_parameters() -> None:
    stored = accounts.hash_password(PASSWORD)
    assert stored.startswith("scrypt$16$8$1$")
    assert accounts.verify_password(PASSWORD, stored)
    assert not accounts.verify_password(PASSWORD + "x", stored)
    assert accounts.hash_password(PASSWORD) != stored  # per-user random salt


def test_old_hash_still_verifies_after_parameters_rise(monkeypatch: pytest.MonkeyPatch) -> None:
    old = accounts.hash_password(PASSWORD)
    monkeypatch.setattr(accounts, "SCRYPT_PARAMS", accounts.ScryptParams(n=2**5, r=8, p=1))
    assert accounts.verify_password(PASSWORD, old)
    assert accounts.hash_password(PASSWORD).startswith("scrypt$32$")


@pytest.mark.parametrize("stored", ["!", "", "scrypt$x", "bcrypt$1$2$3$4$5"])
def test_unusable_hashes_never_match(stored: str) -> None:
    assert not accounts.verify_password("", stored)
    assert not accounts.verify_password(PASSWORD, stored)


def test_production_parameters_are_owasp_minimum() -> None:
    # The autouse fixture lowers them for speed, so check the module's own default in its source.
    source = Path(accounts.__file__).read_text()
    assert "SCRYPT_PARAMS = ScryptParams(n=2**17, r=8, p=1)" in source


# --- the gate ------------------------------------------------------------------------------------


def test_anonymous_request_redirects_to_login(client: TestClient) -> None:
    response = client.get("/")
    assert response.status_code == 303
    assert response.headers["location"] == "/login"
    # every chargen route, POSTs included
    assert client.post("/ui/bio", data={}).headers["location"] == "/login"
    assert client.get("/ui/page/skills").headers["location"] == "/login"


def test_anonymous_htmx_request_gets_hx_redirect(client: TestClient) -> None:
    response = client.get("/ui/nav", headers={"HX-Request": "true"})
    assert response.headers["HX-Redirect"] == "/login"
    assert "location" not in response.headers


def test_public_pages_and_static_need_no_login(client: TestClient) -> None:
    for path in ("/login", "/register"):
        page = client.get(path)
        assert page.status_code == 200
        assert "⟦" not in page.text  # every string has a catalog entry
    assert client.get("/static/app.css").status_code == 200


def test_forged_cookie_is_refused_and_cleared(client: TestClient) -> None:
    client.cookies.set(AUTH_COOKIE_NAME, "not-a-real-token")
    response = client.get("/")
    assert response.headers["location"] == "/login"
    assert f'{AUTH_COOKIE_NAME}=""' in response.headers["set-cookie"]


# --- registration --------------------------------------------------------------------------------


def test_registration_needs_a_valid_code(client: TestClient, store: Store) -> None:
    for code in ("", "AAAA-BBBB-CCCC-DDDD"):
        response = register(client, code)
        assert response.status_code == 400
        assert "That invite code is not valid" in response.text
    assert store.get_user_by_name("alice") is None


def test_registration_logs_in_and_a_used_code_fails_the_second_time(
    client: TestClient, store: Store
) -> None:
    code = invite(store)
    response = register(client, code)
    assert response.status_code == 303 and response.headers["location"] == "/characters"
    assert client.cookies.get(AUTH_COOKIE_NAME)
    user = store.get_user_by_name("alice")
    assert user is not None
    assert client.get("/").status_code == 200

    other = new_client(store, client)
    again = register(other, code, username="bob")
    assert again.status_code == 400
    assert store.get_user_by_name("bob") is None
    assert store.list_open_invites() == []


def test_code_is_typed_forgivingly(client: TestClient, store: Store) -> None:
    code = invite(store)
    assert register(client, " " + code.lower().replace("-", " ") + " ").status_code == 303


def test_rejected_registration_leaves_the_code_unused(client: TestClient, store: Store) -> None:
    store.create_user("Alice", "x")
    code = invite(store)
    taken = register(client, code, username="ALICE")
    assert taken.status_code == 400 and "That username is taken." in taken.text
    short = register(client, code, username="carol", password="short")
    assert short.status_code == 400 and "at least 10 characters" in short.text
    mismatch = client.post(
        "/register",
        data={"username": "carol", "password": PASSWORD, "confirm": PASSWORD + "!", "invite": code},
    )
    assert "The two passwords differ." in mismatch.text
    bad_name = register(client, code, username="no spaces")
    assert "only letters, digits" in bad_name.text
    assert len(store.list_open_invites()) == 1
    assert register(client, code, username="carol").status_code == 303


def test_expired_code_fails(client: TestClient, store: Store) -> None:
    code = invite(store, expires_days=1)
    with sqlite3.connect(store.path) as db:
        db.execute("UPDATE invite_codes SET expires = '2000-01-01T00:00:00+00:00'")
    assert register(client, code).status_code == 400


def test_simultaneous_registrations_cannot_share_a_code(store: Store) -> None:
    code = accounts.mint_invite(store).code
    barrier = threading.Barrier(8)
    results: list[str] = []

    def attempt(i: int) -> None:
        barrier.wait()
        try:
            store.register_user(f"user{i}", "h", code)
            results.append("ok")
        except InviteInvalidError:
            results.append("refused")

    threads = [threading.Thread(target=attempt, args=(i,)) for i in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sorted(results) == ["ok"] + ["refused"] * 7
    assert len(store.list_users()) == 1


# --- login and logout ----------------------------------------------------------------------------


@pytest.fixture
def alice(client: TestClient, store: Store) -> TestClient:
    """`client`, registered and logged in as alice."""
    assert register(client, invite(store)).status_code == 303
    return client


def test_login_renders_shell_and_logout_ends_the_session(alice: TestClient, store: Store) -> None:
    alice.post("/logout")
    assert alice.get("/").headers["location"] == "/login"
    response = login(alice)
    assert response.status_code == 303 and response.headers["location"] == "/characters"
    page = alice.get("/")
    assert page.status_code == 200
    assert "alice" in page.text and '/logout"' in page.text

    old_token = alice.cookies[AUTH_COOKIE_NAME]
    out = alice.post("/logout")
    assert out.headers["location"] == "/login"
    assert f'{AUTH_COOKIE_NAME}=""' in out.headers["set-cookie"]
    # the old cookie, replayed, is dead
    alice.cookies.set(AUTH_COOKIE_NAME, old_token)
    assert alice.get("/").headers["location"] == "/login"


def test_wrong_password_and_unknown_user_look_the_same(alice: TestClient) -> None:
    alice.post("/logout")
    wrong = login(alice, password="wrong password!")
    unknown = login(alice, username="nobody")
    assert wrong.status_code == unknown.status_code == 401
    assert "Wrong username or password." in wrong.text
    assert "Wrong username or password." in unknown.text
    assert AUTH_COOKIE_NAME not in alice.cookies


def test_username_is_case_insensitive_at_login(alice: TestClient) -> None:
    alice.post("/logout")
    assert login(alice, username="ALICE").status_code == 303


def test_login_issues_a_fresh_token_and_ends_the_old_one(alice: TestClient, store: Store) -> None:
    first = alice.cookies[AUTH_COOKIE_NAME]
    assert login(alice).status_code == 303
    second = alice.cookies[AUTH_COOKIE_NAME]
    assert second != first
    with sqlite3.connect(store.path) as db:
        hashes = {row[0] for row in db.execute("SELECT token_hash FROM auth_sessions")}
    assert hashes == {accounts.hash_token(second)}


def test_only_the_token_hash_is_stored(alice: TestClient, store: Store) -> None:
    token = alice.cookies[AUTH_COOKIE_NAME]
    with sqlite3.connect(store.path) as db:
        dump = "\n".join(db.iterdump())
    assert token not in dump
    assert accounts.hash_token(token) in dump


def test_logged_in_user_skips_the_login_page(alice: TestClient) -> None:
    assert alice.get("/login").headers["location"] == "/characters"
    assert alice.get("/register").headers["location"] == "/characters"


def test_auth_cookie_flags(client: TestClient, store: Store) -> None:
    response = register(client, invite(store))
    cookie = response.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=lax" in cookie and "max-age=2592000" in cookie


# --- expiry --------------------------------------------------------------------------------------


def _set_session_times(store: Store, **columns: str) -> None:
    with sqlite3.connect(store.path) as db:
        for column, value in columns.items():
            db.execute(f"UPDATE auth_sessions SET {column} = ?", (value,))


def test_expired_session_is_refused(alice: TestClient, store: Store) -> None:
    _set_session_times(store, expires=(datetime.now(UTC) - timedelta(seconds=1)).isoformat())
    assert alice.get("/").headers["location"] == "/login"


def test_expiry_slides_when_the_session_is_used(alice: TestClient, store: Store) -> None:
    soon = datetime.now(UTC) + timedelta(days=1)
    _set_session_times(
        store,
        expires=soon.isoformat(),
        last_seen=(datetime.now(UTC) - timedelta(hours=1)).isoformat(),
    )
    response = alice.get("/")
    assert response.status_code == 200
    assert AUTH_COOKIE_NAME in response.headers.get("set-cookie", "")
    with sqlite3.connect(store.path) as db:
        (expires,) = db.execute("SELECT expires FROM auth_sessions").fetchone()
    assert datetime.fromisoformat(expires) > datetime.now(UTC) + timedelta(days=29)


def test_recently_seen_session_is_not_rewritten(alice: TestClient) -> None:
    response = alice.get("/")
    assert AUTH_COOKIE_NAME not in response.headers.get("set-cookie", "")


def test_session_lifetime_is_configurable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CHUMMER5_SESSION_DAYS", "7")
    assert accounts.session_lifetime() == timedelta(days=7)


# --- chargen session keyed by the login ----------------------------------------------------------


def test_chargen_session_belongs_to_the_login(alice: TestClient, store: Store) -> None:
    alice.get("/")
    key = accounts.hash_token(alice.cookies[AUTH_COOKIE_NAME])
    sessions = alice.app.state.sessions  # type: ignore[attr-defined]
    assert sessions.get(key) is not None
    assert SESSION_COOKIE_NAME not in alice.cookies  # no separate chargen cookie in hosted mode
    alice.post("/logout")
    assert sessions.get(key) is None

    # the next person on this browser starts clean
    assert register(alice, invite(store), username="bob").status_code == 303
    alice.get("/")
    bob_key = accounts.hash_token(alice.cookies[AUTH_COOKIE_NAME])
    assert sessions.get(bob_key) is not None and bob_key != key


# --- preferences follow the account --------------------------------------------------------------


def test_prefs_are_stored_on_the_user_and_follow_to_another_device(
    alice: TestClient, store: Store
) -> None:
    assert alice.post("/ui/prefs/theme", data={"theme": "classic"}).status_code == 200
    user = store.get_user_by_name("alice")
    assert user is not None and user.theme == "classic"

    laptop = new_client(store, alice)
    login(laptop)
    assert "themes/classic.css" in laptop.get("/").text


# --- password reset and change -------------------------------------------------------------------


def test_reset_password_ends_sessions_and_forces_a_change(alice: TestClient, store: Store) -> None:
    status, temporary = run_admin(store, "reset-password", "alice")
    assert status == 0
    temporary = temporary.strip()
    assert len(temporary) >= accounts.MIN_PASSWORD_LENGTH
    # the possibly stolen session is dead
    assert alice.get("/").headers["location"] == "/login"
    assert login(alice).status_code == 401  # the old password no longer works

    response = login(alice, password=temporary)
    assert response.headers["location"] == "/account/password"
    assert alice.get("/").headers["location"] == "/account/password"
    htmx = alice.get("/ui/nav", headers={"HX-Request": "true"})
    assert htmx.headers["HX-Redirect"] == "/account/password"
    password_page = alice.get("/account/password").text
    assert "Your password was reset" in password_page and "⟦" not in password_page

    changed = alice.post(
        "/account/password",
        data={"current": temporary, "password": "a brand new one", "confirm": "a brand new one"},
    )
    assert changed.headers["location"] == "/"
    assert alice.get("/").status_code == 200
    user = store.get_user_by_name("alice")
    assert user is not None and not user.must_change_password


def test_password_change_needs_the_current_password(alice: TestClient) -> None:
    response = alice.post(
        "/account/password",
        data={"current": "wrong password", "password": "another one!", "confirm": "another one!"},
    )
    assert response.status_code == 400
    assert "The current password is wrong." in response.text


def test_password_change_ends_other_sessions_but_keeps_this_one(
    alice: TestClient, store: Store
) -> None:
    phone = new_client(store, alice)
    login(phone)
    alice.get("/")
    sessions = alice.app.state.sessions  # type: ignore[attr-defined]
    before = sessions.get(accounts.hash_token(alice.cookies[AUTH_COOKIE_NAME]))

    alice.post(
        "/account/password",
        data={"current": PASSWORD, "password": "new password 1", "confirm": "new password 1"},
    )
    assert alice.get("/").status_code == 200
    assert phone.get("/").headers["location"] == "/login"
    # the chargen session moved to the new login, character and all
    assert sessions.get(accounts.hash_token(alice.cookies[AUTH_COOKIE_NAME])) is before


# --- admin CLI -----------------------------------------------------------------------------------


def test_admin_invites_list_and_revoke(store: Store) -> None:
    status, out = run_admin(store, "invites")
    assert (status, out.strip()) == (0, "no open invites")
    _, code = run_admin(store, "invite", "--expires-days", "7")
    code = code.strip()
    assert len(code) == 19 and code.count("-") == 3
    _, listing = run_admin(store, "invites")
    assert code in listing and "never" not in listing
    assert run_admin(store, "revoke", code.lower())[0] == 0
    assert run_admin(store, "revoke", code)[0] == 1
    assert store.list_open_invites() == []


def test_admin_users_lists_accounts(alice: TestClient, store: Store) -> None:
    status, out = run_admin(store, "users")
    assert status == 0 and out.startswith("alice  characters 0")
    assert "last login never" not in out  # registering logs in


def test_admin_delete_user_confirms_first(
    alice: TestClient, store: Store, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("builtins.input", lambda prompt: "not alice")
    assert run_admin(store, "delete-user", "alice")[0] == 1
    assert store.get_user_by_name("alice") is not None

    monkeypatch.setattr("builtins.input", lambda prompt: "alice")
    assert run_admin(store, "delete-user", "alice")[0] == 0
    assert store.get_user_by_name("alice") is None
    assert alice.get("/").headers["location"] == "/login"


def test_admin_delete_user_yes_and_unknown(store: Store) -> None:
    store.create_user("dave", "h")
    assert run_admin(store, "delete-user", "dave", "--yes")[0] == 0
    assert run_admin(store, "delete-user", "dave", "--yes")[0] == 1
    assert run_admin(store, "reset-password", "dave")[0] == 1


# --- local mode ----------------------------------------------------------------------------------


def test_local_mode_has_no_login(tmp_path: Path) -> None:
    store = Store(tmp_path / "local.db")
    with TestClient(create_app(mode="local", store=store), follow_redirects=False) as c:
        assert c.get("/").status_code == 200
        assert c.get("/login").status_code == 404
        assert c.post("/logout").status_code == 404
        assert '/logout"' not in c.get("/").text
    local = store.get_user_by_name(accounts.LOCAL_USERNAME)
    assert local is not None
    assert not accounts.verify_password("", local.password_hash)


def test_mode_comes_from_the_environment(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("CHUMMER5_MODE", "hosted")
    with TestClient(create_app(), follow_redirects=False) as c:
        assert c.get("/").headers["location"] == "/login"
    monkeypatch.setenv("CHUMMER5_MODE", "public")
    with pytest.raises(ValueError):
        create_app()


# --- review fixes (2026-10-03) -------------------------------------------------------------------


def test_hashing_runs_at_most_two_at_a_time(monkeypatch: pytest.MonkeyPatch) -> None:
    import hashlib
    import time

    real = hashlib.scrypt
    lock = threading.Lock()
    running = peak = 0

    def slow_scrypt(*args: object, **kwargs: object) -> bytes:
        nonlocal running, peak
        with lock:
            running += 1
            peak = max(peak, running)
        time.sleep(0.05)
        with lock:
            running -= 1
        return real(*args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(accounts.hashlib, "scrypt", slow_scrypt)
    threads = [threading.Thread(target=accounts.hash_password, args=(PASSWORD,)) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert peak == accounts.MAX_CONCURRENT_HASHES == 2


def test_no_free_hashing_slot_answers_busy(
    alice: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    alice.post("/logout")
    full = threading.BoundedSemaphore(1)
    full.acquire()
    monkeypatch.setattr(accounts, "_hash_slots", full)
    monkeypatch.setattr(accounts, "HASH_WAIT_SECONDS", 0.01)
    response = login(alice)
    assert response.status_code == 503
    assert "The server is busy." in response.text


def _no_hashing(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(password: str) -> str:
        raise AssertionError("hashed a password for a registration that was always going to fail")

    monkeypatch.setattr(accounts, "hash_password", refuse)


def test_bogus_invite_is_refused_before_any_hashing(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _no_hashing(monkeypatch)
    response = register(client, "AAAA-BBBB-CCCC-DDDD")
    assert response.status_code == 400 and "That invite code is not valid" in response.text


def test_taken_username_is_refused_before_any_hashing(
    client: TestClient, store: Store, monkeypatch: pytest.MonkeyPatch
) -> None:
    store.create_user("alice", "x")
    code = invite(store)
    _no_hashing(monkeypatch)
    assert "That username is taken." in register(client, code).text
    assert len(store.list_open_invites()) == 1


def test_the_local_username_is_reserved(client: TestClient, store: Store) -> None:
    code = invite(store)
    for name in ("local", "LOCAL"):
        assert "That username is taken." in register(client, code, username=name).text
    assert store.get_user_by_name("local") is None


def test_login_to_an_unusable_account_costs_a_full_hash(
    client: TestClient, store: Store, monkeypatch: pytest.MonkeyPatch
) -> None:
    accounts.ensure_local_user(store)
    burned: list[str] = []
    monkeypatch.setattr(accounts, "_burn_password_check", burned.append)
    response = login(client, username="local", password="anything at all")
    assert response.status_code == 401
    assert burned == ["anything at all"]


def test_local_mode_refuses_to_adopt_a_real_account(store: Store) -> None:
    store.create_user("local", accounts.hash_password(PASSWORD))
    with pytest.raises(RuntimeError, match="real account"):
        accounts.ensure_local_user(store)


@pytest.mark.parametrize("value", ["30d", "0", "-1", "nan", "inf", "99999"])
def test_bad_session_days_stop_a_hosted_start(
    value: str, monkeypatch: pytest.MonkeyPatch, store: Store
) -> None:
    monkeypatch.setenv("CHUMMER5_SESSION_DAYS", value)
    with pytest.raises(ValueError, match="CHUMMER5_SESSION_DAYS"):
        create_app(mode="hosted", store=store)
    create_app(mode="local", store=store)  # local mode never reads it


def test_password_change_is_not_a_login(alice: TestClient, store: Store) -> None:
    with sqlite3.connect(store.path) as db:
        db.execute("UPDATE users SET last_login = '2026-01-01T00:00:00.000000+00:00'")
    alice.post(
        "/account/password",
        data={"current": PASSWORD, "password": "new password 1", "confirm": "new password 1"},
    )
    user = store.get_user_by_name("alice")
    assert user is not None and user.last_login == "2026-01-01T00:00:00.000000+00:00"


def test_login_records_last_login_and_purges_expired_sessions(
    alice: TestClient, store: Store
) -> None:
    with sqlite3.connect(store.path) as db:
        db.execute("UPDATE users SET last_login = NULL")
        db.execute(
            "INSERT INTO auth_sessions VALUES "
            "('stale', 1, '2000-01-01', '2000-01-02', '2000-01-01')"
        )
    alice.post("/logout")
    login(alice)
    with sqlite3.connect(store.path) as db:
        hashes = [row[0] for row in db.execute("SELECT token_hash FROM auth_sessions")]
    assert "stale" not in hashes and len(hashes) == 1
    user = store.get_user_by_name("alice")
    assert user is not None and user.last_login is not None


def test_stamp_is_utc_whatever_the_input_zone() -> None:
    from datetime import timezone

    from chummer5.store import stamp

    moment = datetime(2026, 10, 3, 22, 0, tzinfo=timezone(timedelta(hours=2)))
    assert stamp(moment) == "2026-10-03T20:00:00.000000+00:00"
