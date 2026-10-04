"""WP141: the security pass -- cookies, the cross-site request check, login throttling, the
response headers and what the CSP needs from every page, hosted error pages, and input bounds.
`spec/security.md` is the list these tests keep true."""

from __future__ import annotations

import re
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from starlette.requests import Request
from tests.fixtures.hosted import PUBLIC_URL, hosted_client
from tests.unit.test_open_character_wp138 import confirm

from chummer5 import accounts
from chummer5.engine.biography import MAX_SHORT_FIELD_LENGTH, create_biography
from chummer5.store import Store
from chummer5.web.app import create_app
from chummer5.web.catalogs import STATIC_DIR, TEMPLATES_DIR
from chummer5.web.prefs import THEMES
from chummer5.web.security import CONTENT_SECURITY_POLICY, Throttle, client_ip
from chummer5.web.shell import STEP_PAGES

PASSWORD = "correct horse battery"


@pytest.fixture(autouse=True)
def _cheap_scrypt(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(accounts, "SCRYPT_PARAMS", accounts.ScryptParams(n=2**4, r=8, p=1))
    monkeypatch.setattr(accounts, "_dummy_hash", None)


@pytest.fixture
def store(tmp_path: Path) -> Store:
    return Store(tmp_path / "wp141.db")


@pytest.fixture
def app(store: Store):  # type: ignore[no-untyped-def]
    return create_app(mode="hosted", store=store)


@pytest.fixture
def client(app) -> Iterator[TestClient]:  # type: ignore[no-untyped-def]
    with hosted_client(app) as c:
        yield c


@pytest.fixture
def local(store: Store) -> Iterator[TestClient]:
    with TestClient(create_app(mode="local", store=store), follow_redirects=False) as c:
        yield c


def make_user(store: Store, username: str = "alice") -> None:
    accounts.register(store, username, PASSWORD, PASSWORD, accounts.mint_invite(store).code)


def login(client: TestClient, username: str = "alice", password: str = PASSWORD, **kw):  # type: ignore[no-untyped-def]
    return client.post("/login", data={"username": username, "password": password}, **kw)


class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


# --- cookies -------------------------------------------------------------------------------------


def _set_cookie_headers(response) -> list[str]:  # type: ignore[no-untyped-def]
    return response.headers.get_list("set-cookie")


def test_hosted_auth_cookie_is_secure_httponly_lax(client: TestClient, store: Store) -> None:
    make_user(store)
    [cookie] = [c for c in _set_cookie_headers(login(client)) if c.startswith("chummer5_auth=")]
    lowered = cookie.lower()
    assert "secure" in lowered and "httponly" in lowered and "samesite=lax" in lowered
    logout = client.post("/logout")
    [cleared] = [c for c in _set_cookie_headers(logout) if c.startswith("chummer5_auth=")]
    assert "secure" in cleared.lower()


def test_local_session_cookie_is_httponly_lax_not_secure(local: TestClient) -> None:
    [cookie] = _set_cookie_headers(local.get("/"))
    lowered = cookie.lower()
    assert cookie.startswith("chummer5_session=")
    assert "httponly" in lowered and "samesite=lax" in lowered and "secure" not in lowered


def test_cookies_are_set_in_one_place_each() -> None:
    """The chargen cookie only through `session.set_session_cookie`, the auth cookie only through
    `auth.py`'s helpers, so their flags can't drift between routes."""
    web = Path(TEMPLATES_DIR).parent
    setters = sorted(
        path.name
        for path in web.rglob("*.py")
        for line in path.read_text().splitlines()
        if "set_cookie(" in line and "def " not in line
    )
    assert setters == ["auth.py", "session.py"]


# --- cross-site requests -------------------------------------------------------------------------


def test_a_cross_origin_post_is_refused(client: TestClient, store: Store) -> None:
    make_user(store)
    login(client)
    response = client.post(
        "/characters/new", headers={"Origin": "https://evil.example", "HX-Request": "true"}
    )
    assert response.status_code == 403
    assert "That request was refused" in response.text
    assert client.get("/").status_code == 200  # still logged in, nothing switched


def test_login_itself_is_origin_checked(app, store: Store) -> None:  # type: ignore[no-untyped-def]
    make_user(store)
    attacker = TestClient(app, base_url=PUBLIC_URL, follow_redirects=False)
    response = attacker.post(
        "/login",
        data={"username": "alice", "password": PASSWORD},
        headers={"Origin": "https://evil.example"},
    )
    assert response.status_code == 403 and "chummer5_auth" not in response.headers.get(
        "set-cookie", ""
    )


@pytest.mark.parametrize(
    "headers",
    [
        {},  # neither Origin nor Referer
        {"Origin": "null"},
        {"Origin": "http://testserver"},  # the right host over the wrong scheme
        {"Origin": "https://testserver.evil.example"},
        {"Referer": "https://evil.example/page"},
    ],
)
def test_missing_or_foreign_origins_are_refused(app, headers: dict[str, str]) -> None:  # type: ignore[no-untyped-def]
    bare = TestClient(app, base_url=PUBLIC_URL, follow_redirects=False)
    response = bare.post("/login", data={"username": "a", "password": "b"}, headers=headers)
    assert response.status_code == 403


@pytest.mark.parametrize(
    "headers",
    [
        {"Origin": PUBLIC_URL},
        {"Origin": "HTTPS://TestServer:443"},  # same origin, spelled differently
        {"Referer": f"{PUBLIC_URL}/login?next=x"},  # no Origin: the Referer decides
    ],
)
def test_same_origin_posts_pass(app, store: Store, headers: dict[str, str]) -> None:  # type: ignore[no-untyped-def]
    make_user(store)
    bare = TestClient(app, base_url=PUBLIC_URL, follow_redirects=False)
    response = bare.post(
        "/login", data={"username": "alice", "password": PASSWORD}, headers=headers
    )
    assert response.status_code == 303


def test_gets_are_not_origin_checked(app) -> None:  # type: ignore[no-untyped-def]
    bare = TestClient(app, base_url=PUBLIC_URL, follow_redirects=False)
    assert bare.get("/login", headers={"Origin": "https://evil.example"}).status_code == 200


def test_local_mode_has_no_origin_check(local: TestClient) -> None:
    assert local.post("/characters/new", headers={"Origin": "https://elsewhere"}).status_code == 303


def test_hosted_mode_needs_a_public_url(monkeypatch: pytest.MonkeyPatch, store: Store) -> None:
    monkeypatch.delenv("CHUMMER5_PUBLIC_URL")
    with pytest.raises(ValueError, match="CHUMMER5_PUBLIC_URL must be set"):
        create_app(mode="hosted", store=store)
    monkeypatch.setenv("CHUMMER5_PUBLIC_URL", "chummer.example.org")
    with pytest.raises(ValueError, match="http"):
        create_app(mode="hosted", store=store)
    create_app(mode="local", store=store)  # local mode doesn't need one


@pytest.mark.parametrize(
    ("url", "origin"),
    [
        ("https://Chummer.Example.org/", "https://chummer.example.org"),
        ("https://chummer.example.org:443/x?y", "https://chummer.example.org"),
        ("http://localhost:8000", "http://localhost:8000"),
        ("http://[::1]:80/", "http://[::1]"),
        ("ftp://example.org", None),
        ("null", None),
        ("https://", None),
        ("http://host:notaport", None),
    ],
)
def test_origin_normalization(url: str, origin: str | None) -> None:
    assert accounts.origin_of(url) == origin


# --- login throttling ----------------------------------------------------------------------------


def test_the_sixth_bad_password_in_a_row_is_throttled(client: TestClient, store: Store) -> None:
    make_user(store)
    for _ in range(5):
        assert login(client, password="wrong password!").status_code == 401
    response = login(client, password="wrong password!")
    assert response.status_code == 429
    assert re.search(r"Too many failed attempts\. Wait \d+ s and try again\.", response.text)
    # throttled means refused unchecked: the right password doesn't get through either
    assert login(client).status_code == 429


def test_the_wait_passes_and_a_success_clears_the_account(app, store: Store) -> None:  # type: ignore[no-untyped-def]
    clock = FakeClock()
    app.state.throttle = Throttle(clock=clock)
    make_user(store)
    client = hosted_client(app)
    for _ in range(5):
        login(client, password="wrong password!")
    assert login(client).status_code == 429
    clock.now += 31
    assert login(client).status_code == 303
    assert app.state.throttle.wait("login-user:alice") == 0


def test_a_spray_across_usernames_from_one_address_is_throttled(
    client: TestClient, store: Store
) -> None:
    for name in ("u1", "u2", "u3", "u4", "u5"):
        login(client, username=name, password="wrong password!")
    make_user(store, "fresh")
    assert login(client, username="fresh").status_code == 429


def test_the_address_comes_from_the_trusted_proxy_only(
    app, store: Store, monkeypatch: pytest.MonkeyPatch
) -> None:  # type: ignore[no-untyped-def]
    make_user(store)
    client = hosted_client(app)
    # The test client's peer is "testclient", not a trusted proxy: X-Forwarded-For is ignored,
    # so rotating it doesn't escape the per-address count.
    for n in range(5):
        login(client, username=f"x{n}", password="bad password!", headers=_xff(f"10.0.0.{n}"))
    assert login(client, headers=_xff("10.9.9.9")).status_code == 429


def test_behind_the_trusted_proxy_each_client_is_counted_apart(
    monkeypatch: pytest.MonkeyPatch, store: Store
) -> None:
    monkeypatch.setenv("CHUMMER5_TRUSTED_PROXY", "testclient")
    client = hosted_client(create_app(mode="hosted", store=store))
    make_user(store)
    for n in range(5):
        login(client, username=f"x{n}", password="bad password!", headers=_xff("10.0.0.1"))
    assert login(client, headers=_xff("10.0.0.2")).status_code == 303  # another client
    assert login(client, headers=_xff("10.0.0.1")).status_code == 429


def _xff(address: str) -> dict[str, str]:
    return {"X-Forwarded-For": f"203.0.113.7, {address}"}


def test_registration_is_throttled(client: TestClient) -> None:
    for n in range(5):
        response = client.post(
            "/register",
            data={
                "username": f"new{n}",
                "password": PASSWORD,
                "confirm": PASSWORD,
                "invite": "NOT-A-CODE",
            },
        )
        assert response.status_code == 400
    response = client.post(
        "/register",
        data={"username": "new9", "password": PASSWORD, "confirm": PASSWORD, "invite": "X"},
    )
    assert response.status_code == 429


def test_throttle_backs_off_then_locks_then_forgets() -> None:
    clock = FakeClock()
    throttle = Throttle(clock=clock)
    for _ in range(4):
        throttle.failed("k")
    assert throttle.wait("k") == 0
    throttle.failed("k")  # 5th
    assert throttle.wait("k") == 30
    clock.now += 30
    assert throttle.wait("k") == 0
    throttle.failed("k")  # 6th: the delay doubles
    assert throttle.wait("k") == 60
    for _ in range(4):
        throttle.failed("k")  # 10 in all: locked until the oldest leaves the window
    assert throttle.wait("k") == 15 * 60 - 30
    clock.now += 15 * 60
    assert throttle.wait("k") == 0
    throttle.failed("other")
    throttle.succeeded("other")
    assert throttle.wait("other") == 0


def test_throttle_memory_is_bounded() -> None:
    clock = FakeClock()
    throttle = Throttle(clock=clock, max_keys=100)
    for n in range(500):
        throttle.failed(f"k{n}")
    assert len(throttle._failures) <= 100


def test_client_ip_without_a_proxy() -> None:
    class State:
        trusted_proxies = frozenset({"127.0.0.1"})

    class App:
        state = State()

    def request(peer: str, xff: str | None) -> Request:
        headers = [(b"x-forwarded-for", xff.encode())] if xff else []
        return Request({"type": "http", "client": (peer, 1), "headers": headers, "app": App()})

    assert client_ip(request("198.51.100.1", "10.0.0.1")) == "198.51.100.1"
    assert client_ip(request("127.0.0.1", "10.0.0.9, 198.51.100.2")) == "198.51.100.2"
    assert client_ip(request("127.0.0.1", None)) == "127.0.0.1"


# --- response headers and the CSP ----------------------------------------------------------------


def _assert_security_headers(response) -> None:  # type: ignore[no-untyped-def]
    assert response.headers["Content-Security-Policy"] == CONTENT_SECURITY_POLICY
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["Referrer-Policy"] == "same-origin"


def test_the_policy_allows_only_same_origin_and_no_framing() -> None:
    directives = dict(d.split(" ", 1) for d in CONTENT_SECURITY_POLICY.split("; "))
    assert directives["script-src"] == "'self'" and directives["style-src"] == "'self'"
    assert directives["frame-ancestors"] == "'none'"
    assert "unsafe" not in CONTENT_SECURITY_POLICY


def test_every_response_carries_the_headers(client: TestClient, local: TestClient) -> None:
    for response in (
        client.get("/login"),
        client.get("/"),  # the redirect to /login
        client.get("/static/app.css"),
        client.post("/login", headers={"Origin": "https://evil.example"}),  # a refusal
        local.get("/"),
        local.get("/static/vendor/htmx/htmx.min.js"),
    ):
        _assert_security_headers(response)


_INLINE_SCRIPT = re.compile(r"<script(?![^>]*\bsrc=)[^>]*>", re.I)
_EVENT_HANDLER = re.compile(r"<[^>]+\son[a-z]+\s*=", re.I)
_STYLE_ATTR = re.compile(r"<[^>]+\sstyle\s*=", re.I)


def _assert_csp_clean(html: str, where: str) -> None:
    """What would show as a CSP violation in a browser console, checked in the markup."""
    assert not _INLINE_SCRIPT.search(html), f"inline <script> in {where}"
    assert not _EVENT_HANDLER.search(html), f"on* handler in {where}"
    assert not _STYLE_ATTR.search(html), f"style attribute in {where}"
    assert "<style" not in html, f"<style> element in {where}"
    assert "javascript:" not in html, f"javascript: URL in {where}"
    assert "hx-on" not in html, f"hx-on in {where}"
    for trigger in re.findall(r'hx-trigger="([^"]*)"', html):
        assert "[" not in trigger, f"htmx event filter (evaluated code) in {where}: {trigger}"
    # Resources only: an <a href> off-site (the legal footer's license and source links) is a
    # navigation, which the CSP does not govern.
    resources = re.findall(r'\bsrc="([^"]+)"', html)
    resources += re.findall(r'<link\b[^>]*\bhref="([^"]+)"', html)
    for url in resources:
        assert not re.match(r"(https?:)?//", url), f"off-site resource in {where}: {url}"
    if "htmx.min.js" in html:
        config = re.search(r'name="htmx-config"\s+content=\'([^\']*)\'', html)
        assert config, f"htmx without htmx-config in {where}"
        for setting in (
            '"allowEval": false',
            '"allowScriptTags": false',
            '"includeIndicatorStyles": false',
        ):
            assert setting in config.group(1), f"{setting} missing in {where}"


@pytest.mark.parametrize("theme", [t.slug for t in THEMES])
def test_every_page_under_every_theme_is_csp_clean(local: TestClient, theme: str) -> None:
    confirm(local)
    local.post("/ui/prefs/theme", data={"theme": theme})
    pages = ["/", "/characters", "/character/sheet"]
    pages += [f"/ui/page/{p.slug}" for p in STEP_PAGES if p.enabled]
    for url in pages:
        response = local.get(url)
        assert response.status_code == 200, url
        assert f"themes/{theme}.css" in response.text, url
        _assert_csp_clean(response.text, f"{url} ({theme})")


def test_account_and_error_pages_are_csp_clean(client: TestClient) -> None:
    for url in ("/login", "/register", "/no-such-page"):
        _assert_csp_clean(client.get(url).text, url)


def test_no_template_carries_code_the_csp_would_block() -> None:
    """The rendered pages above cover what one character shows; this covers every branch."""
    for path in Path(TEMPLATES_DIR).glob("*.html"):
        source = re.sub(r"\{#.*?#\}", "", path.read_text(), flags=re.S)
        _assert_csp_clean(source, path.name)


def test_stylesheets_and_scripts_load_nothing_off_site() -> None:
    for path in [*Path(STATIC_DIR).rglob("*.css"), *Path(STATIC_DIR).glob("*.js")]:
        text = path.read_text()
        assert "@import" not in text, path
        assert not re.search(r"url\(\s*['\"]?(https?:)?//", text), path
        assert "data:" not in text, path  # img-src/font-src are 'self' only


# --- error pages ---------------------------------------------------------------------------------


def test_a_forced_500_shows_a_generic_page(app, store: Store) -> None:  # type: ignore[no-untyped-def]
    @app.get("/boom")
    def boom() -> None:
        raise RuntimeError("secret internal detail")

    make_user(store)
    client = hosted_client(app, raise_server_exceptions=False)
    login(client)
    response = client.get("/boom")
    assert response.status_code == 500
    assert "Something went wrong on the server" in response.text
    assert "secret internal detail" not in response.text and "Traceback" not in response.text
    _assert_security_headers(response)


def test_hosted_4xx_pages_carry_no_detail(client: TestClient, store: Store) -> None:
    make_user(store)
    login(client)
    missing = client.get("/ui/page/no-such-step")
    assert missing.status_code == 404
    assert "There is no page here." in missing.text and "no-such-step" not in missing.text
    invalid = client.get("/characters/not-a-number/download")
    assert invalid.status_code == 422 and "not-a-number" not in invalid.text


def test_local_mode_keeps_developer_details(local: TestClient) -> None:
    response = local.get("/ui/page/no-such-step")
    assert response.status_code == 404 and "no-such-step" in response.text


# --- input bounds --------------------------------------------------------------------------------


def test_oversized_bodies_are_refused(local: TestClient) -> None:
    big = "x" * (1024 * 1024 + 1)
    response = local.post("/ui/bio", data={"name": big})
    assert response.status_code == 413
    _assert_security_headers(response)


def test_chunked_bodies_are_refused_outside_the_upload(local: TestClient) -> None:
    def chunks() -> Iterator[bytes]:
        yield b"name=x"

    response = local.post(
        "/ui/bio",
        content=chunks(),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert response.status_code == 411


def test_the_upload_is_exempt_from_the_general_cap(local: TestClient) -> None:
    confirm(local)
    big = b"{" + b" " * (2 * 1024 * 1024) + b"}"
    response = local.post(
        "/characters/upload", files=[("files", ("big.json", big, "application/json"))]
    )
    assert response.status_code == 200  # answered by the upload's own handling
    assert "Could not load save" in response.text


def test_bio_fields_are_bounded(local: TestClient) -> None:
    with pytest.raises(ValueError, match="at most 2000"):
        create_biography({"name": "x" * (MAX_SHORT_FIELD_LENGTH + 1)})
    create_biography({"concept": "x" * 1021})  # the longest legacy concept still fits
    confirm(local)
    page = local.get("/ui/page/bio").text
    assert f'name="name" value="" maxlength="{MAX_SHORT_FIELD_LENGTH}"' in page
    assert 'name="notes" rows="5" maxlength="20000"' in page


def test_usernames_are_bounded(client: TestClient) -> None:
    assert f'maxlength="{accounts.MAX_USERNAME_LENGTH}"' in client.get("/login").text
