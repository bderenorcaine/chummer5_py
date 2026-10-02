[← back to Implementation Plan index](../Implementation%20Plan.md)

### Phase Y — Post-MVP: hosted multi-user deployment (WP136-142)

**Why now.** Raised 2026-10-02. The user wants the character creator reachable on the web, on a
cloud server they already run (a mail server and Nextcloud, both behind Caddy, with a domain set
up). Players get accounts. Each account stores a limited number of characters (100). After logging
in, a player sees their saved characters, filters the list by name, opens one (or starts a new one)
in the same chargen pages used locally, and can download any character as JSON or upload JSON or
legacy `.chum5` files.

This **reverses a standing non-goal**: `Project Overview.md` listed "Multi-user / hosted
deployment" as out of scope and described the UI as "local, single-user, no auth". See
`spec/decisions-log.md`'s 2026-10-02 entry. "Anything resembling ChummerHub" (sharing characters
between users, a public catalog) **stays out**. Every account sees only its own characters.

**The user's rulings (2026-10-02):**

| Question | Ruling |
|---|---|
| Who can register? | **Invite codes only.** No open sign-up: "that's asking to be exploited." |
| Own accounts, or reuse Nextcloud's (OIDC)? | **Own accounts, for now.** No new dependencies. Linking Nextcloud accounts (for players' related documents) is a possible later phase, not this one. |
| Are pre-priority drafts stored? | **No.** Confirming the priority selection is what "officially" starts a character. Nothing else can be entered before that anyway (every step route guards on `session.character is None`). |
| Upload formats | **Both** the native JSON save and legacy `.chum5`. The import logic already exists. |

**Defaults this file sets (not user rulings; change them here if they turn out wrong):**

- **No new runtime dependencies.** The stack stays FastAPI + Jinja2 + python-multipart + uvicorn.
  Storage is stdlib `sqlite3`. Password hashing is stdlib `hashlib.scrypt`. Uploaded XML is
  hardened by refusing any `<!DOCTYPE`/`<!ENTITY` before parsing (see WP140), not by adding
  `defusedxml`. This follows the user's "stay away from any further dependencies".
- **Accounts are managed from an admin CLI on the server**, not from an admin web page. Minting
  invites, resetting passwords and deleting users all go through `python -m chummer5.admin ...`.
  Password reset by email is out of scope, which keeps the mail server out of this app.
- **The local, single-user mode keeps working unchanged.** `start-app.sh` still opens straight into
  chargen with no login. Hosted mode is switched on by configuration (`CHUMMER5_MODE=hosted`, see
  WP137). Local mode uses the same storage with one implicit user, so local runs also get the
  character list.
- **The open character is tracked by the session, not the URL.** Every existing route and template
  endpoint stays as it is. Instead of putting the character ID in every URL, each page carries the
  open character's ID in an `hx-headers` attribute, and the server refuses requests whose ID doesn't
  match the session's (WP138). That stops a second tab from silently editing the wrong character.

**Finding 1 — the save format already covers everything a stored character needs.**
`_character_save_from_session` / `_apply_built_character_to_session`
(`web/routes/character.py`) already round-trip a confirmed character, including its Bio (WP134).
Storing a character means storing its `to_json` output. No new serialization is needed, and the
download is that same JSON verbatim.

**Finding 2 — there is already a single hook after every chargen change.** `create_app`'s
`_signal_chargen_changed` middleware already recognizes "a successful POST that changed the
character" (excluding `/ui/prefs/`) to fire the `chargen-changed` htmx event. Autosave belongs at
exactly that point. Step routes need no per-route save calls.

**Finding 3 — sessions are in-memory and never expire.** `SessionStore` (`web/session.py`) is a
process-lifetime dict that only grows. That is fine for one local user and wrong for a server. This
phase splits the session in two:

- The **login session** is persisted in SQLite and expires, so it survives restarts.
- The **chargen session** stays in memory and is rebuilt from the open character's stored save when
  it is missing (after a restart, or on first use of a login session). It is evicted when idle.

Because of autosave, a restart loses nothing past the last successful POST. A character whose
priorities aren't confirmed yet was never stored (see the ruling above), so losing it is accepted.

**Finding 4 — one uvicorn worker.** Chargen sessions live in process memory, so production runs a
single worker process. That is ample for a group of invited players. Moving chargen sessions out of
process is not in this phase.

**Server shape (for WP142):** the app runs in a container listening only on `127.0.0.1`. Caddy, which
already serves mail and Nextcloud there, gets one more site block (e.g. `chummer.<domain>`) with
`reverse_proxy` to it. Caddy handles TLS. The SQLite file lives on a mounted volume.

---

- [ ] **WP136 — Storage layer.**
  Goal: a headless persistence module that everything else in this phase builds on.
  Deliverables:
  - `chummer5.store` (new package, stdlib `sqlite3`), with tables:
    - `users` (id, username unique case-insensitive, password hash, created/last-login timestamps,
      theme, locale)
    - `invite_codes` (code, created, expires, used_by, used_at)
    - `auth_sessions` (token hash, user id, created, expires, last seen)
    - `characters` (id, owner user id, display name, street name, metatype, save JSON,
      created/updated)
  - Display name and street name are copied out of the save's Biography on every write, so the list
    and its filter never parse JSON. A schema-version table plus an ordered list of migration
    functions, applied at startup.
  - A repository API that every web route uses. No route writes SQL itself. Every character
    query is scoped by owner (`get_character(owner_id, character_id)`), so one user can never read
    another user's row through a guessed ID.
  - **Quota:** `CHARACTER_QUOTA` (default 100, configurable). Inserting a character for a user at
    quota raises `QuotaExceededError`. Overwriting an existing character never counts against it.
  - The database path comes from configuration (`CHUMMER5_DB`). Tests use a temporary file per test.
  - SQLite settings: WAL mode and foreign keys on. Every connection is short-lived and used inside a
    single request.
  Depends on: nothing new.
  Acceptance: unit tests cover the create/read/update/delete round-trip, owner scoping (user B gets
  "not found" for user A's character ID), the quota boundary (the 100th insert succeeds, the 101st
  fails, overwriting at 100 succeeds), and a migration from an empty file.

- [ ] **WP137 — Accounts and invite codes.**
  Goal: invite-only registration, login and logout. In hosted mode, nothing except the login and
  registration pages is reachable without a login.
  Deliverables:
  - **Configuration:** `CHUMMER5_MODE=local|hosted` (default `local`).
    - In `local` mode there are no login pages. Every request runs as one implicit local user,
      created on first start.
    - In `hosted` mode, a middleware redirects any request without a valid login session to
      `/login` (htmx requests get `HX-Redirect`), except `/login`, `/register` and `/static`.
  - **Passwords:** `hashlib.scrypt` with a per-user random salt, stored with its parameters so they
    can be raised later. Comparisons use `hmac.compare_digest`. Minimum length 10. No complexity
    rules.
  - **Registration** (`/register`): username + password + invite code. A code is single-use and
    optionally expires. Code consumption and user creation happen in one transaction, so two
    simultaneous registrations can't both use one code.
  - **Login sessions:**
    - A random token goes in the cookie. Only its SHA-256 hash is stored.
    - Sessions have a sliding expiry (default 30 days). Logout deletes the row.
    - Logging in issues a fresh token; the old one is never reused.
  - **Admin CLI** (`python -m chummer5.admin`):
    - `invite [--expires-days N]` prints a new code.
    - `invites` lists open codes. `revoke CODE` revokes one.
    - `users` lists accounts.
    - `reset-password USERNAME` prints a one-time temporary password.
    - `delete-user USERNAME` deletes the user and their characters, after confirmation.
  - Theme and locale preferences (`/ui/prefs/*`) are stored on the user row in hosted mode, so they
    follow the player across devices.
  - Login, registration and logout pages use the existing shell's look (base template, theme
    system) and go through the WP102 i18n layer.
  Depends on: WP136.
  Acceptance:
  - Hosted mode: an anonymous `GET /` redirects to `/login`.
  - Registration fails without a valid code, and a used code fails a second time.
  - After login the chargen shell renders. After logout the old cookie gets the redirect again.
  - Local mode: the existing test suite passes unchanged.

- [ ] **WP138 — The open character, autosave, and new-character flow.**
  Goal: chargen edits a stored character, and every change is saved.
  Deliverables:
  - The chargen session gains `character_id: int | None`. It is keyed per login session, and in
    local mode per browser cookie as today.
    - **Open:** load the stored save via the existing `_apply_built_character_to_session` and set
      `character_id`.
    - **New:** reset to a fresh `ChargenSession` with `character_id = None`.
  - **First store** happens on the priority confirmation (`POST /ui/priorities`) that first produces
    `session.character`. It inserts a row (quota-checked; at quota the confirmation is refused with
    a translated message) and sets `character_id`.
  - **Autosave:** in the same post-response place as `_signal_chargen_changed`, after a successful
    character-changing POST with `session.character` set and `character_id` set, serialize with
    `_character_save_from_session` and update the row. Skip the write if the JSON didn't change.
  - **Tab guard:**
    - The shell puts `hx-headers='{"X-Character-Id": "<id or new>"}'` on `<body>`.
    - A request whose header doesn't match the session's `character_id` gets a 409 response. The
      response re-renders a "this character was replaced by one opened in another tab — reload"
      notice instead of applying the change.
    - Requests without the header (plain navigation) are not guarded.
  - **Chargen session lifecycle:**
    - The in-memory store evicts sessions idle longer than a configurable timeout (default 2
      hours).
    - An evicted or missing chargen session for a valid login is rebuilt from the user's
      last-opened character, which is remembered on the user row.
  - The title bar shows the open character's name (or "New character") and links to the list
    (WP139).
  Depends on: WP136, WP137.
  Acceptance:
  - An edit on any step is visible after a server restart and re-login.
  - The 101st priority confirmation for a user is refused with the quota message, and nothing is
    stored.
  - A stale tab's POST gets the 409 notice, and the other character is unchanged.
  - Prefs POSTs never trigger an autosave.

- [ ] **WP139 — The character list page.**
  Goal: the landing page after login. It lists the player's characters, filtered by name.
  Deliverables:
  - `GET /characters`, the post-login landing page. Its table shows display name (street name
    first, then name, falling back to "Unnamed"), metatype, last-updated time, and actions (open,
    download, delete).
  - The list is sorted by last-updated time, newest first.
  - **Filter:** a text box with `hx-get` and a short debounce. It matches name or street name, is
    case-insensitive, and filters server-side in SQL.
  - A **New character** button. A "N / 100 characters" usage indicator. At quota, New and Upload
    are disabled and show the reason.
  - **Delete:** asks for confirmation (`hx-confirm`) and is owner-scoped. Deleting the open
    character resets the chargen session.
  - The step-nav shell gets a "My characters" link in the title bar. In hosted mode the title bar
    also shows the username and a logout link.
  - All strings go through i18n. Every theme renders the page (it reuses the shell's table and
    button styles).
  Depends on: WP138.
  Acceptance: a user with three characters sees exactly those three; filtering "ali" finds
  "Alias"-named rows only; deleting removes the row and the count drops; another user's characters
  never appear.

- [ ] **WP140 — Download and upload.**
  Goal: per-character JSON download, and uploading JSON or `.chum5` files as new characters.
  Deliverables:
  - `GET /characters/{id}/download` returns the stored JSON verbatim (owner-scoped). Its filename
    comes from the display name, sanitized to `[A-Za-z0-9_-]`, falling back to `character`.
  - The Export page's existing save button downloads the open character the same way.
  - `POST /characters/upload` takes one or more files. Each is detected by content: JSON goes through
    `from_json`, XML through `import_chum5`. Each file becomes a **new** character, quota-checked
    per file.
    - The response lists per-file results (imported as "X", or the existing translated error
      message).
    - Uploads never overwrite an existing character.
  - The Export page's existing "load" / "import .chum5" forms are rewired to this. In both modes an
    upload creates a new stored character and opens it, instead of replacing the session character
    in place.
  - **Limits:** a configurable per-file size cap (default 5 MB), enforced while reading, not after.
    At most 20 files per request.
  - **XML hardening:** reject any upload containing `<!DOCTYPE` or `<!ENTITY` before it reaches
    `ElementTree`. Legacy `.chum5` files don't use either. Check this against the fixture corpus.
  - `import_chum5` takes bytes (or a file object) in addition to a `Path`, which retires the temp-file
    workaround in `import_chum5_route`.
  Depends on: WP138, WP139.
  Acceptance:
  - A download → upload round trip produces an equal save.
  - Every `.chum5` fixture in `tests/fixtures` imports through the upload route.
  - A file with a DOCTYPE is refused. An oversized file is refused without being fully read.
  - At 99 characters, uploading three files imports one and reports two quota errors.

- [ ] **WP141 — Security pass.**
  Goal: protections suited to an internet-facing app, checked in one place.
  Deliverables:
  - **Cookies:** `HttpOnly`, `SameSite=Lax`, and `Secure` in hosted mode, on every cookie the app
    sets. That means consolidating the `response.set_cookie(SESSION_COOKIE_NAME, ...)` lines
    repeated across the routes into one helper.
  - **CSRF:** in hosted mode, every non-GET request must carry an `Origin` (or, failing that,
    `Referer`) matching the configured public origin (`CHUMMER5_PUBLIC_URL`). Otherwise it gets a
    403. This works alongside `SameSite=Lax`. It needs no tokens in the existing forms.
  - **Login throttling:** an in-process counter per username and per client IP. The client IP is
    taken from `X-Forwarded-For` only when the request comes from the configured trusted proxy
    (Caddy on localhost). After 5 failures in 15 minutes, further attempts get a delay, then a
    temporary refusal. Registration attempts are throttled the same way.
  - **Response headers:**
    - A `Content-Security-Policy` allowing only same-origin scripts and styles. Verify that
      vendored htmx and the theme fonts still load. Inline `hx-*` attributes are fine; check
      whether any inline `<script>` needs moving into `/static`.
    - `X-Content-Type-Options: nosniff`.
    - `Referrer-Policy: same-origin`.
    - `frame-ancestors 'none'`.
  - **Error pages:** no tracebacks or exception text in hosted-mode responses. The details are
    logged server-side.
  - **Input bounds:** a length cap on Bio free-text fields and on usernames, and a request-body size
    cap for non-upload routes.
  - A short `spec/` note listing what is protected and how, for future WPs to keep true.
  Depends on: WP137-140.
  Acceptance:
  - A cross-origin POST is refused.
  - The 6th bad password in a row is throttled.
  - Every theme renders under the CSP with no console violations.
  - A forced 500 shows a generic page.

- [ ] **WP142 — Production container, Caddy, backups, runbook.**
  Goal: run it on the user's server.
  Deliverables:
  - A production `Containerfile` (separate from `.devcontainer/`). It is slim, runs as a non-root
    user, installs dependencies without the dev group, and runs `uvicorn --workers 1
    --proxy-headers` on `0.0.0.0:8000` inside the container.
  - Configuration is entirely environment variables: `CHUMMER5_MODE=hosted`, `CHUMMER5_DB`,
    `CHUMMER5_PUBLIC_URL`, `CHUMMER5_TRUSTED_PROXY`, the quota, and the timeouts.
  - An example `compose`/`podman run` setup with the port published to `127.0.0.1` only and a named
    volume for the database.
  - A Caddyfile site-block snippet (`reverse_proxy 127.0.0.1:<port>`) and an upload body-size limit
    matching WP140's.
  - A backup script using SQLite's online `.backup` (safe while running), a retention example, and a
    restore procedure.
  - `spec/deployment.md` (the runbook):
    - first deploy
    - minting the first invite
    - updating to a new version
    - backup and restore
    - where logs go
    - what to check if the site is down
  - The user carries out the actual server steps. This WP's code side is verified by building the
    image and running it locally behind a local Caddy.
  Depends on: WP141.
  Acceptance: the image builds; started with a fresh volume it serves `/login`; an invite minted via
  `podman exec ... python -m chummer5.admin invite` registers a user end to end through Caddy; a
  backup taken while running restores into a working instance.
