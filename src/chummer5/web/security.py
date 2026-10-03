"""Protections for an internet-facing app (WP141). `spec/security.md` lists what is protected and
how; a change here should keep that file true.

- `security_headers`: a strict Content-Security-Policy (same-origin scripts and styles only, no
  inline code, no framing) plus `nosniff` and `Referrer-Policy`, on every response in both modes.
- `check_origin`: hosted mode's cross-site request check. Every non-GET request must come from
  `CHUMMER5_PUBLIC_URL`'s origin, by its `Origin` header or, failing that, its `Referer`.
  Alongside the cookies' `SameSite=Lax`, and with no tokens in the forms.
- `limit_body`: a request-body cap for every route but the upload (which caps its own while
  reading, `chummer5.web.uploads`).
- `install_error_pages`: hosted mode answers errors with a generic page, never exception text.
- `Throttle` and `client_ip`: the login/registration throttle (`chummer5.web.routes.account`).
"""

from __future__ import annotations

import logging
import math
import threading
import time
from collections import deque
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from chummer5 import accounts
from chummer5.web.auth import is_hosted
from chummer5.web.catalogs import templates
from chummer5.web.prefs import DEFAULT_THEME

logger = logging.getLogger(__name__)

Middleware = Callable[[Request, Callable[[Request], Awaitable[Response]]], Awaitable[Response]]

# --- response headers ----------------------------------------------------------------------------

_SELF = "'self'"
_NONE = "'none'"
# Every script, stylesheet, font and image is served from /static. htmx makes only same-origin
# requests. `form-action` keeps the login form from being re-pointed; `frame-ancestors` stops
# framing (clickjacking), with `X-Frame-Options` for browsers that predate it.
_CSP_DIRECTIVES = (
    ("default-src", _SELF),
    ("script-src", _SELF),
    ("style-src", _SELF),
    ("img-src", _SELF),
    ("font-src", _SELF),
    ("connect-src", _SELF),
    ("form-action", _SELF),
    ("base-uri", _NONE),
    ("object-src", _NONE),
    ("frame-ancestors", _NONE),
)
CONTENT_SECURITY_POLICY = "; ".join(" ".join(pair) for pair in _CSP_DIRECTIVES)
SECURITY_HEADERS = {
    "Content-Security-Policy": CONTENT_SECURITY_POLICY,
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "same-origin",
    "X-Frame-Options": "DENY",
}


def _add_security_headers(response: Response) -> None:
    for name, value in SECURITY_HEADERS.items():
        response.headers.setdefault(name, value)


async def security_headers(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    response = await call_next(request)
    _add_security_headers(response)
    return response


# --- error pages ---------------------------------------------------------------------------------

_ERROR_KEYS = {
    400: "Web_Error_BadRequest",
    403: "Web_Error_Forbidden",
    404: "Web_Error_NotFound",
    405: "Web_Error_BadRequest",
    411: "Web_Error_TooLarge",
    413: "Web_Error_TooLarge",
    422: "Web_Error_BadRequest",
    500: "Web_Error_Server",
}


def error_page(
    request: Request, status_code: int, headers: dict[str, str] | None = None
) -> Response:
    """A generic page for `status_code`: the app's look, a translated sentence, no details."""
    key = _ERROR_KEYS.get(status_code) or (
        "Web_Error_Server" if status_code >= 500 else "Web_Error_BadRequest"
    )
    response = templates.TemplateResponse(
        request,
        "error.html",
        {"message_key": key, "status_code": status_code, "theme": DEFAULT_THEME},
        status_code=status_code,
        headers=headers,
    )
    _add_security_headers(response)
    return response


def install_error_pages(app: FastAPI) -> None:
    """Hosted mode: every error is a generic page. A 500's traceback goes to the server log
    (Starlette re-raises after the handler, and uvicorn logs it); 4xx details (a FastAPI
    validation error echoes the input) are dropped."""

    async def on_http_error(request: Request, exc: Exception) -> Response:
        assert isinstance(exc, StarletteHTTPException)
        return error_page(request, exc.status_code, dict(exc.headers or {}))

    async def on_validation_error(request: Request, exc: Exception) -> Response:
        return error_page(request, 422)

    async def on_server_error(request: Request, exc: Exception) -> Response:
        return error_page(request, 500)

    app.add_exception_handler(StarletteHTTPException, on_http_error)
    app.add_exception_handler(RequestValidationError, on_validation_error)
    app.add_exception_handler(Exception, on_server_error)


# --- cross-site requests -------------------------------------------------------------------------

_SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})


def request_origin(request: Request) -> str | None:
    """Where a request says it comes from: its `Origin`, else its `Referer`'s origin."""
    origin = request.headers.get("Origin")
    if origin is not None:
        return accounts.origin_of(origin)  # "null" (a sandboxed or privacy-stripped origin): None
    referer = request.headers.get("Referer")
    return accounts.origin_of(referer) if referer else None


async def check_origin(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    if is_hosted(request) and request.method not in _SAFE_METHODS:
        if request_origin(request) != request.app.state.public_origin:
            logger.warning(
                "refused cross-site %s %s (Origin %r, Referer %r)",
                request.method,
                request.url.path,
                request.headers.get("Origin"),
                request.headers.get("Referer"),
            )
            return error_page(request, 403)
    return await call_next(request)


# --- request bodies ------------------------------------------------------------------------------

# Far above any chargen form (the Skills page posts a few kilobytes), far below anything that
# could hurt. The upload route is exempt: it caps itself while reading.
MAX_BODY_BYTES = 1024 * 1024


def limit_body(exempt_paths: frozenset[str]) -> Middleware:
    async def middleware(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        if request.method not in _SAFE_METHODS and request.url.path not in exempt_paths:
            declared = request.headers.get("Content-Length")
            if declared is None:
                # No length up front (a chunked body): browsers never send a form like that.
                if "chunked" in request.headers.get("Transfer-Encoding", "").lower():
                    return error_page(request, 411)
            elif not declared.isdigit() or int(declared) > MAX_BODY_BYTES:
                return error_page(request, 413)
        return await call_next(request)

    return middleware


# --- login throttling ----------------------------------------------------------------------------


def client_ip(request: Request) -> str:
    """The client's address: the connection's peer, or -- only when that peer is the configured
    reverse proxy -- the last `X-Forwarded-For` entry, the one the proxy itself appended (earlier
    entries are whatever the client claimed). If uvicorn's own `--proxy-headers` already rewrote
    the peer, the peer is no longer the proxy and is used as it is."""
    peer = request.client.host if request.client else ""
    if peer in request.app.state.trusted_proxies:
        forwarded = request.headers.get("X-Forwarded-For", "")
        last = forwarded.rsplit(",", 1)[-1].strip()
        if last:
            return last
    return peer


class Throttle:
    """Failed attempts per key (a username, a client address), in process memory.

    Under `free` failures in the last `window` seconds, an attempt goes ahead. From `free` on,
    each further attempt must wait `base_delay` seconds after the last failure, doubling per
    failure. From `lock_after` on, attempts are refused until the oldest failure leaves the window.
    A refused attempt is not a failure (its password is never checked), so waiting it out works.
    Waiting is a refusal with the time left, not a held-open request: a sleeping request would tie
    up a worker thread, which is its own denial of service.
    """

    def __init__(
        self,
        *,
        free: int = 5,
        window: float = 15 * 60,
        base_delay: float = 30,
        lock_after: int = 10,
        max_keys: int = 10_000,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.free = free
        self.window = window
        self.base_delay = base_delay
        self.lock_after = lock_after
        self.max_keys = max_keys
        self.clock = clock
        self._failures: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def _recent(self, key: str, now: float) -> deque[float]:
        failures = self._failures.get(key)
        if failures is None:
            return deque()
        while failures and failures[0] <= now - self.window:
            failures.popleft()
        if not failures:
            del self._failures[key]
        return failures

    def _wait_for(self, failures: deque[float], now: float) -> float:
        count = len(failures)
        if count < self.free:
            return 0.0
        if count >= self.lock_after:
            return failures[0] + self.window - now
        delay = self.base_delay * 2.0 ** (count - self.free)
        return max(0.0, failures[-1] + delay - now)

    def wait(self, *keys: str) -> int:
        """Whole seconds until an attempt for all of `keys` may go ahead; 0 means now."""
        with self._lock:
            now = self.clock()
            longest = max((self._wait_for(self._recent(k, now), now) for k in keys), default=0.0)
        return math.ceil(longest)

    def failed(self, *keys: str) -> None:
        with self._lock:
            now = self.clock()
            if len(self._failures) >= self.max_keys:
                self._sweep(now)
            for key in keys:
                self._recent(key, now)
                self._failures.setdefault(key, deque()).append(now)

    def succeeded(self, key: str) -> None:
        """Forget a key's failures (the username's, on a login that worked). A client address's
        failures stay: one good account must not reset a spray across others."""
        with self._lock:
            self._failures.pop(key, None)

    def _sweep(self, now: float) -> None:
        for key in list(self._failures):
            self._recent(key, now)
        while len(self._failures) >= self.max_keys:  # still full of live keys: drop the oldest
            oldest = min(self._failures, key=lambda k: self._failures[k][-1])
            del self._failures[oldest]
