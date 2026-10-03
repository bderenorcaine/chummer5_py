# Security: what is protected, and how

Written by WP141 (Phase Y) for an internet-facing hosted deployment. **A WP that touches any of
these areas keeps this file true**: it updates the entry, or it says in its worklog why an entry no
longer applies. Most of it lives in `chummer5.web.security`, and `tests/unit/test_security_wp141.py`
checks each entry.

Local mode (`CHUMMER5_MODE=local`, the default) serves one person on `127.0.0.1` with no login. It
gets the response headers and the body cap, but not the hosted-only checks below.

## Accounts and sessions (WP137)

- **Passwords:** `hashlib.scrypt`, a per-user salt, and the parameters stored with the hash.
  Comparisons use `hmac.compare_digest`. Hashing runs in a bounded pool, so a flood of logins
  can't exhaust memory. Minimum length 10, maximum 1024.
- **Registration is by invite only.** A code is single-use and may expire. Consuming the code and
  creating the user happen in one transaction.
- **Login sessions:** a random token in the cookie, of which only the SHA-256 is stored. Expiry
  slides (default 30 days). A login issues a fresh token. Logout deletes the row. A password reset
  or change ends every session the user has.
- **The login gate:** in hosted mode, every request except `/login`, `/register` and `/static/`
  needs a valid session.

## Cookies (WP141)

| Cookie | Set by | Flags |
|---|---|---|
| `chummer5_auth` (hosted login) | `auth.set_auth_cookie` / `clear_auth_cookie` only | `HttpOnly`, `SameSite=Lax`, `Secure` |
| `chummer5_session` (chargen session, local mode) | `session.set_session_cookie` only | `HttpOnly`, `SameSite=Lax`, and `Secure` in hosted mode |

A test makes sure `set_cookie(` appears nowhere else in the web layer. Browsers accept `Secure`
cookies from `http://localhost`, so hosted mode can still be tried locally.

## Cross-site requests (WP141)

- In hosted mode, every request other than GET, HEAD or OPTIONS must come from
  `CHUMMER5_PUBLIC_URL`'s origin. Its `Origin` header is checked or, when there is none, its
  `Referer`. Otherwise the answer is 403. This covers `/login` and `/register` too (login CSRF).
  No tokens are needed in the forms.
- Together with `SameSite=Lax`, a cross-site form or script can neither ride a session nor plant
  one.
- **GET requests must stay free of side effects** for this to hold. A new route that changes
  anything is a POST.
- Hosted mode doesn't start without a valid `CHUMMER5_PUBLIC_URL`.

## Brute force (WP141)

- Login, registration and password change are throttled per account and per client address
  (`security.Throttle`, in process memory). Five failures in 15 minutes and the next attempt must
  wait 30 s, doubling with each further failure. Ten and attempts are refused until the oldest
  failure is 15 minutes old.
- A throttled attempt is refused with 429 before any password is hashed. It is never held open,
  because that would tie up a worker thread.
- A successful login clears the account's count, not the address's.
- **The client address:** the connection's peer. `X-Forwarded-For` (its last entry, the one the
  proxy appended) is used only when the peer is in `CHUMMER5_TRUSTED_PROXY` (default
  `127.0.0.1,::1`). If uvicorn's `--proxy-headers` already rewrote the peer, that rewrite stands.
- The counts are per process and reset on restart. That is acceptable with one worker
  (Phase Y, Finding 4).

## Response headers and the Content-Security-Policy (WP141)

Every response, in both modes and including refusals and error pages, carries these headers:

- **`Content-Security-Policy`:** `default-src`, `script-src`, `style-src`, `img-src`, `font-src`,
  `connect-src` and `form-action` are all `'self'`. `base-uri`, `object-src` and
  `frame-ancestors` are `'none'`. There is no `'unsafe-inline'` and no `'unsafe-eval'`.
- **`X-Content-Type-Options: nosniff`.**
- **`Referrer-Policy: same-origin`.**
- **`X-Frame-Options: DENY`.**

What the CSP needs from every page and template (enforced by
`test_no_template_carries_code_the_csp_would_block` and the per-theme page test):

- **No inline `<script>`**, no `on*=` attributes, no `javascript:` URLs. Page behavior goes in
  `static/app.js` (or `static/tabs.js`), as listeners on `document` that survive htmx swaps.
- **No `style=` attributes and no `<style>` elements.** Styling goes in `app.css` and the theme
  files.
- **No htmx code evaluation:** no `hx-on`, no `js:` values, no event filters
  (`hx-trigger="input[...]"`). Every `htmx-config` sets `allowEval: false`,
  `allowScriptTags: false` and `includeIndicatorStyles: false`. For a filtered trigger, dispatch
  a custom event from `app.js` (see `number-input`).
- **Nothing loaded from another site**, and no `data:` URIs. Fonts are the player's installed
  fonts (the font hint), not web fonts.
- **Asset and form URLs are root-relative:** templates' `url_for` returns a path
  (`catalogs._root_relative_url_for`). An absolute URL built behind the proxy could come out
  `http://`, which an https page blocks.

## Uploads (WP140)

- A per-file cap (`CHUMMER5_UPLOAD_MAX_MB`, default 10). Past it nothing more of the file is
  kept. At most 20 files per request.
- A whole-body cap, checked against `Content-Length` before reading and counted while reading.
- Every `.chum5` is parsed with `defusedxml`: no entity declarations, no external references. The
  game data XML under `legacy/` is trusted and keeps the stdlib parser.
- Every failure becomes a per-file message, never a 500. Uploads only ever create new characters,
  within the quota.

## Input bounds (WP141)

- Request bodies are capped at 1 MB everywhere except `POST /characters/upload`. A body without a
  length (chunked) is refused there too.
- Bio fields: 2000 characters for one-line fields and 20000 for long ones, enforced by the engine
  (`biography.max_length`) and mirrored as `maxlength`. Usernames: 32. Passwords: 1024. The list
  filter: 200.

## Data access

- Every character query is scoped by owner in SQL (`get_character(owner_id, id)`). Someone else's
  id is indistinguishable from a missing one (404).
- No route writes SQL itself (`chummer5.store` only).

## Errors (WP141)

- In hosted mode, every error is a generic page (`templates/error.html`): the status code and one
  translated sentence. FastAPI's 4xx details, which echo input, are dropped.
- A 500's traceback goes to the server log only. Starlette re-raises after the handler, and
  uvicorn logs it.
- Local mode keeps the developer-facing details.

## Out of scope, knowingly

- **Rate limiting beyond the account forms.** Chargen requests are only reachable after login,
  and each costs milliseconds.
- **Origin checks in local mode.** It listens on loopback only, and a cross-site request carries
  no `SameSite=Lax` session cookie, so it would only start a fresh, empty session.
- **Accounts don't lock out.** The throttle delays and refuses for a while, but a correct password
  works again once the wait is over. A lockout would let anyone lock out a known username.
