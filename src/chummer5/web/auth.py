"""Hosted mode's login gate (WP137): the mode switch, the middleware, and the auth cookie.

**`CHUMMER5_MODE`** is `local` (the default: no login pages, the app as it always was) or `hosted`.
In hosted mode the middleware resolves the login session behind the `chummer5_auth` cookie on every
request except `/static/`, puts the user on `request.state.user` and the session's token hash on
`request.state.chargen_key` (which keys the chargen session; see `chummer5.web.session`), and turns
away anything without a valid login except `/login` and `/register`:

- a plain request gets a 303 to `/login`;
- an htmx request gets `HX-Redirect: /login`, since a 303 would be followed by the XHR and the
  login page swapped into whatever element asked.

A user holding a one-time password (an admin `reset-password`) is sent to the password page until
they replace it.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from fastapi import Request, Response
from fastapi.responses import RedirectResponse
from starlette.concurrency import run_in_threadpool

from chummer5 import accounts
from chummer5.accounts import HOSTED
from chummer5.store import Store, UserRecord
from chummer5.web.session import CHARGEN_KEY_STATE

AUTH_COOKIE_NAME = "chummer5_auth"

LOGIN_PATH = "/login"
REGISTER_PATH = "/register"
LOGOUT_PATH = "/logout"
PASSWORD_PATH = "/account/password"
# WP139: the character list, where a login or a registration lands.
CHARACTERS_PATH = "/characters"
# Reachable without a login.
PUBLIC_PATHS = frozenset({LOGIN_PATH, REGISTER_PATH})
STATIC_PREFIX = "/static/"


def is_hosted(request: Request) -> bool:
    return bool(request.app.state.mode == HOSTED)


def current_user(request: Request) -> UserRecord | None:
    """The logged-in user (hosted mode), or None."""
    user: UserRecord | None = getattr(request.state, "user", None)
    return user


def app_store(request: Request) -> Store:
    store: Store = request.app.state.store
    return store


# --- the cookie ----------------------------------------------------------------------------------

# Set by a route that wrote or deleted the auth cookie itself, so the middleware doesn't re-send
# the old token over it when it slides the session's expiry.
_COOKIE_HANDLED_STATE = "auth_cookie_handled"


def set_auth_cookie(request: Request, response: Response, token: str) -> None:
    response.set_cookie(
        AUTH_COOKIE_NAME,
        token,
        max_age=int(accounts.session_lifetime().total_seconds()),
        httponly=True,
        samesite="lax",
        # WP141: always -- the auth cookie exists only in hosted mode, which is served over TLS.
        # (Browsers also accept a Secure cookie from http://localhost, for trying hosted mode out.)
        secure=True,
    )
    setattr(request.state, _COOKIE_HANDLED_STATE, True)


def clear_auth_cookie(request: Request, response: Response) -> None:
    response.delete_cookie(AUTH_COOKIE_NAME, httponly=True, samesite="lax", secure=True)
    setattr(request.state, _COOKIE_HANDLED_STATE, True)


def redirect(request: Request, url: str) -> Response:
    """Send the browser to `url`: an htmx request by `HX-Redirect` (a full navigation), anything
    else by a 303."""
    if request.headers.get("HX-Request") == "true":
        return Response(status_code=200, headers={"HX-Redirect": url})
    return RedirectResponse(url, status_code=303)


# --- the middleware ------------------------------------------------------------------------------


async def require_login(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    path = request.url.path
    if not is_hosted(request) or path.startswith(STATIC_PREFIX):
        return await call_next(request)

    token = request.cookies.get(AUTH_COOKIE_NAME)
    resolved = (
        await run_in_threadpool(accounts.resolve_session, app_store(request), token)
        if token
        else None
    )
    if resolved is not None:
        request.state.user = resolved.user
        setattr(request.state, CHARGEN_KEY_STATE, resolved.record.token_hash)

    if path not in PUBLIC_PATHS:
        if resolved is None:
            response = redirect(request, LOGIN_PATH)
            if token:  # stale or forged: stop sending it
                clear_auth_cookie(request, response)
            return response
        if resolved.user.must_change_password and path not in (PASSWORD_PATH, LOGOUT_PATH):
            return redirect(request, PASSWORD_PATH)

    response = await call_next(request)
    if (
        token
        and resolved is not None
        and resolved.refreshed
        and not getattr(request.state, _COOKIE_HANDLED_STATE, False)
    ):
        set_auth_cookie(request, response, token)  # the cookie slides with the session
    return response
