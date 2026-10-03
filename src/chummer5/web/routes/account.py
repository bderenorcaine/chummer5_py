"""Login, registration, logout and password change (WP137). Hosted mode only: in local mode
these paths are 404s, and the app opens straight into chargen as before.

The handlers are plain `def`, so FastAPI runs them in its thread pool: each one does an scrypt hash
(about 0.3 s by design), which must not stall the event loop every chargen POST runs on.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Form, HTTPException, Request, Response
from fastapi.responses import HTMLResponse

from chummer5 import accounts
from chummer5.store import UserRecord
from chummer5.web import prefs
from chummer5.web.auth import (
    AUTH_COOKIE_NAME,
    CHARACTERS_PATH,
    LOGIN_PATH,
    PASSWORD_PATH,
    REGISTER_PATH,
    app_store,
    clear_auth_cookie,
    current_user,
    is_hosted,
    redirect,
    set_auth_cookie,
)
from chummer5.web.catalogs import templates
from chummer5.web.i18n import request_locale
from chummer5.web.prefs import DEFAULT_THEME
from chummer5.web.session import CHARGEN_KEY_STATE, SessionStore

router = APIRouter()

# Where a login or a registration lands, and where the login page sends someone already logged
# in: the character list (WP139).
LANDING_PATH = CHARACTERS_PATH
# Where a password change carries on: chargen, with the character that was open.
HOME_PATH = "/"


def _hosted_or_404(request: Request) -> None:
    if not is_hosted(request):
        raise HTTPException(status_code=404)


def _form_page(
    request: Request,
    template: str,
    *,
    title_key: str,
    error: accounts.AccountError | None = None,
    status_code: int = 200,
    **values: Any,
) -> HTMLResponse:
    user = current_user(request)
    context = {
        "title_key": title_key,
        "theme": user.theme if user and user.theme in prefs.THEMES_BY_SLUG else DEFAULT_THEME,
        "error_key": error.key if error else None,
        "error_params": error.params if error else {},
        "current_user": user,
        "html_lang": prefs.LOCALES_BY_TAG.get(
            request_locale(request), prefs.LOCALES_BY_TAG[prefs.DEFAULT_LOCALE]
        ).html_lang,
        "max_username": accounts.MAX_USERNAME_LENGTH,
        "max_password": accounts.MAX_PASSWORD_LENGTH,
        "min_password": accounts.MIN_PASSWORD_LENGTH,
        **values,
    }
    return templates.TemplateResponse(request, template, context, status_code=status_code)


def _status(error: accounts.AccountError, default: int) -> int:
    # Every hashing slot busy is the server's problem, not the form's.
    return 503 if isinstance(error, accounts.ServerBusyError) else default


def _chargen_sessions(request: Request) -> SessionStore:
    sessions: SessionStore = request.app.state.sessions
    return sessions


def _log_in(request: Request, user: UserRecord) -> Response:
    """Start a fresh login session for `user` and send them on. A login session this browser
    already had ends, along with its in-memory chargen session."""
    store = app_store(request)
    old_token = request.cookies.get(AUTH_COOKIE_NAME)
    if old_token:
        accounts.end_session(store, old_token)
        _chargen_sessions(request).discard(accounts.hash_token(old_token))
    login = accounts.start_session(store, user)
    target = PASSWORD_PATH if user.must_change_password else LANDING_PATH
    response = redirect(request, target)
    set_auth_cookie(request, response, login.token)
    return response


# --- login ---------------------------------------------------------------------------------------


@router.get(LOGIN_PATH, response_class=HTMLResponse)
def login_page(request: Request) -> Response:
    _hosted_or_404(request)
    if current_user(request) is not None:
        return redirect(request, LANDING_PATH)
    return _form_page(request, "login.html", title_key="Web_Auth_LoginTitle", username="")


@router.post(LOGIN_PATH, response_class=HTMLResponse)
def login(request: Request, username: str = Form(""), password: str = Form("")) -> Response:
    _hosted_or_404(request)
    try:
        user = accounts.authenticate(app_store(request), username, password)
    except accounts.AccountError as error:
        return _form_page(
            request,
            "login.html",
            title_key="Web_Auth_LoginTitle",
            error=error,
            status_code=_status(error, 401),
            username=username[: accounts.MAX_USERNAME_LENGTH],
        )
    return _log_in(request, user)


# --- registration --------------------------------------------------------------------------------


@router.get(REGISTER_PATH, response_class=HTMLResponse)
def register_page(request: Request) -> Response:
    _hosted_or_404(request)
    if current_user(request) is not None:
        return redirect(request, LANDING_PATH)
    return _form_page(
        request, "register.html", title_key="Web_Auth_RegisterTitle", username="", invite=""
    )


@router.post(REGISTER_PATH, response_class=HTMLResponse)
def register(
    request: Request,
    username: str = Form(""),
    password: str = Form(""),
    confirm: str = Form(""),
    invite: str = Form(""),
) -> Response:
    _hosted_or_404(request)
    try:
        user = accounts.register(app_store(request), username, password, confirm, invite)
    except accounts.AccountError as error:
        return _form_page(
            request,
            "register.html",
            title_key="Web_Auth_RegisterTitle",
            error=error,
            status_code=_status(error, 400),
            username=username[: accounts.MAX_USERNAME_LENGTH],
            invite=invite[:64],
        )
    return _log_in(request, user)


# --- logout --------------------------------------------------------------------------------------


@router.post("/logout")
def logout(request: Request) -> Response:
    _hosted_or_404(request)
    token = request.cookies.get(AUTH_COOKIE_NAME)
    if token:
        accounts.end_session(app_store(request), token)
    key = getattr(request.state, CHARGEN_KEY_STATE, None)
    if key is not None:
        _chargen_sessions(request).discard(key)
    response = redirect(request, LOGIN_PATH)
    clear_auth_cookie(request, response)
    return response


# --- password change -----------------------------------------------------------------------------


@router.get(PASSWORD_PATH, response_class=HTMLResponse)
def password_page(request: Request) -> Response:
    _hosted_or_404(request)
    return _form_page(request, "password.html", title_key="Web_Auth_PasswordTitle")


@router.post(PASSWORD_PATH, response_class=HTMLResponse)
def change_password(
    request: Request,
    current: str = Form(""),
    password: str = Form(""),
    confirm: str = Form(""),
) -> Response:
    _hosted_or_404(request)
    user = current_user(request)
    assert user is not None  # the middleware let only a logged-in request through
    try:
        login = accounts.change_password(app_store(request), user, current, password, confirm)
    except accounts.AccountError as error:
        return _form_page(
            request,
            "password.html",
            title_key="Web_Auth_PasswordTitle",
            error=error,
            status_code=_status(error, 400),
        )
    # Every older session just ended; this browser carries on in the new one, character included.
    old_key = getattr(request.state, CHARGEN_KEY_STATE, None)
    if old_key is not None:
        _chargen_sessions(request).rekey(old_key, login.token_hash)
    response = redirect(request, HOME_PATH)
    set_auth_cookie(request, response, login.token)
    return response
