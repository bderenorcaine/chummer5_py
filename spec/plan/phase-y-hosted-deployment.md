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

**The user's rulings (2026-10-02, refined 2026-10-03):**

| Question | Ruling |
|---|---|
| Who can register? | **Invite codes only.** This is a hobby project for the user and the people they play with, not a public service. It is not meant to be commercially relevant or to become the default place SR5 players build characters. The audience is "whoever the user invites", so an invite is the right gate. That open sign-up would also be "asking to be exploited" is a second reason. |
| Own accounts, or reuse Nextcloud's (OIDC)? | **Own accounts, for now.** Linking Nextcloud accounts (for players' related documents) is a possible later phase, not this one. |
| New dependencies? | **Avoid them by default, but security wins.** For a public-facing app, a well-established library that does input hardening properly is preferred over a hand-rolled check. `defusedxml` is approved for this (WP140). |
| Admin web page? | **Not in this phase**, maybe later. The CLI is the admin surface for now, documented in `spec/admin-primer.md`. |
| Are pre-priority drafts stored? | **No.** Confirming the priority selection is what "officially" starts a character. Nothing else can be entered before that anyway (every step route guards on `session.character is None`). |
| Upload formats | **Both** the native JSON save and legacy `.chum5`. The import logic already exists. |

**Defaults this file sets (not user rulings; change them here if they turn out wrong):**

- **One new runtime dependency: `defusedxml`.** Otherwise the stack stays FastAPI + Jinja2 +
  python-multipart + uvicorn. Storage is stdlib `sqlite3`. Password hashing is stdlib
  `hashlib.scrypt`, which is a sound choice, not a stopgap. Uploaded XML is parsed through
  `defusedxml.ElementTree` (WP140). Any further dependency still needs a reason of the same kind:
  security, not convenience.
- **Accounts are managed from an admin CLI on the server**, not from an admin web page. Minting
  invites, resetting passwords and deleting users all go through `python -m chummer5.admin ...`.
  Password reset by email is out of scope, which keeps the mail server out of this app.
  `spec/admin-primer.md` lists every command. Each WP that adds or changes one updates it. Keep the
  CLI's functions callable from Python (not only through `argparse`) so a later admin page can
  reuse them.
- **The local, single-user mode keeps working unchanged.** `start-app.sh` still opens straight into
  chargen with no login. Hosted mode is switched on by configuration (`CHUMMER5_MODE=hosted`, see
  WP137). Local mode uses the same storage with one implicit user, so local runs also get the
  character list.
- **The open character is tracked by the session, not the URL.** Every existing route and template
  endpoint stays as it is. Instead of putting the character ID in every URL, each page carries the
  open character's ID in an `hx-headers` attribute, and the server refuses requests whose ID doesn't
  match the session's (WP138). That stops a second tab from silently editing the wrong character.
  - **Consequence:** one *browser* has one open character at a time, across all its tabs. The chargen
    session is keyed by the login session, which is one browser's cookie. Tabs are not separate
    copies. They are windows onto the same server-side character. Different devices (each its own
    login) each have their own open character.
    - Two tabs on the **same** character edit the same thing. Each step POST sends that step's
      whole form, so a tab left open on a step that was changed elsewhere will overwrite that
      change if it submits the step later.
    - Opening a **different** character in one tab makes every other tab stale. Their next edit
      gets the 409 notice.
    - **Switching warns first (user ruling 2026-10-03).** Every action that changes the open
      character asks for explicit confirmation before it does anything. Those actions are: open,
      new, upload (which opens the imported character), and deleting the open character. See
      WP138's "switch warning".
    - **Two devices on the same character** each hold their own in-memory copy. Each autosave
      writes its whole copy, so without a guard the second device would silently undo the
      first one's edits. WP138's revision check refuses that write instead.
    - Opening two characters side by side is not a goal of this phase. If it becomes one, the open
      character moves into the URL, or the session keys on a per-tab ID instead.

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

One worker does not mean one thread. The `async def` step POST handlers run on the worker's event
loop, one at a time. The plain `def` GET handlers run in FastAPI's thread pool (40 threads by
default), so they can run during another request. The GIL still lets only one of them execute
Python at any moment. Two consequences:

- Requests are short (milliseconds of CPU), so a handful of players never queue in a way they
  notice.
- A GET can read a `ChargenSession` while a POST is replacing its character. That is harmless
  today, because the POST swaps in a new frozen `Character` with one assignment. Autosave must
  serialize from that one snapshot. It must not read `session.character` twice.

A worker per session is not something uvicorn can do. Its workers are processes that share one
listening socket, and the OS hands each connection to whichever worker accepts it, with no
stickiness. Pinning sessions to workers would need a routing layer in front, or moving chargen
state out of process (re-serialized every request). Neither pays off at this scale.

**Server shape (for WP142):** the app runs in a container listening only on `127.0.0.1`. Caddy, which
already serves mail and Nextcloud there, gets one more site block (e.g. `chummer.<domain>`) with
`reverse_proxy` to it. Caddy handles TLS. The SQLite file lives on a mounted volume.

**Suggested models (judgement call, 2026-10-03).** Each WP names the model suggested for
implementing it. Opus is suggested where the plan can't list every trap, so the implementer has to
find unlisted ones. That is concentrated in WP138 and WP141. If a WP runs on Sonnet anyway, follow
it with an Opus `/code-review high`.

---

- [x] **WP136 — Storage layer.**
  *Suggested model:* Sonnet. Plain SQLite with a fully specified schema and unit-testable acceptance.
  Goal: a headless persistence module that everything else in this phase builds on.
  Deliverables:
  - `chummer5.store` (new package, stdlib `sqlite3`), with tables:
    - `users` (id, username unique case-insensitive, password hash, created/last-login timestamps,
      theme, locale)
    - `invite_codes` (code, created, expires, used_by, used_at)
    - `auth_sessions` (token hash, user id, created, expires, last seen)
    - `characters` (id, owner user id, display name, street name, metatype, save JSON,
      revision, created/updated). `revision` backs WP138's cross-device check.
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

- [x] **WP137 — Accounts and invite codes.**
  *Suggested model:* Sonnet, then an Opus `/code-review high`. The spec is concrete, but it's auth code, where mistakes (a non-constant-time compare, a session that survives a reset) pass every test.
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
    - Both end every login session that user has, so a reset logs out a possibly stolen session.
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

- [x] **WP138 — The open character, autosave, and new-character flow.**
  *Suggested model:* **Opus.** The densest WP: middleware ordering, the revision check, the tab guard and its two htmx traps, the multi-tab check, and thread-pool reads of the session. Most failures here are silent wrong behavior, not failing tests.
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
    - The shell puts `hx-headers='{"X-Character-Id": "<id or new>"}'` on an element *inside*
    `<body>` that wraps the whole shell, not on `<body>` itself.
    - **Trap:** `historyCacheSize` is 0 (WP97), so back/forward re-fetches the page and swaps
      the body's *contents*. Attributes on `<body>` survive that swap. A tab could then go back
      to a page that shows the current character but still sends the previous character's ID.
    - Every htmx request carries the header, GETs included (`hx-headers` is inherited). A
      mismatched **GET** (a stale tab moving to another step) answers `HX-Refresh: true`, so the tab
      simply reloads into the current character. A mismatched **POST** gets a 409. The response
      re-renders a "this character was replaced by one opened in another tab — reload" notice
      instead of applying the change.
    - **Trap:** htmx 2's default `responseHandling` does not swap 4xx responses. The 409 needs
      an entry in base.html's `htmx-config` (`{"code": "409", "swap": true}`) or the notice never
      shows.
    - Requests without the header (plain, non-htmx navigation) are not guarded. They render the
      current character anyway.
  - **Revision check (cross-device):**
    - `characters` gets a `revision` integer. The chargen session remembers the revision it
      loaded or last saved.
    - Autosave runs `UPDATE ... SET revision = revision + 1 WHERE id = ? AND revision = ?`.
    - If no row matches, another device saved in the meantime. The change is not written, and the
      response shows a "this character was changed elsewhere — reload to get the latest version"
      notice, like the tab guard's 409.
    - Reloading rebuilds the session from the stored row.
  - **Switch warning:**
    - Every control that changes the open character carries `hx-confirm`. That covers the list's
      Open, New character, Upload, and Delete when the target is the open character.
    - The text says other tabs in this browser will stop working until reloaded, and names the
      character being left.
    - A small script in `/static` (CSP-safe, WP141) uses a `BroadcastChannel` to tell whether
      another tab of the app is open in this browser. The confirmation appears only when one is.
      It cannot see other devices. They aren't affected (see the revision check).
    - Nothing switches until the user clicks OK. Cancel leaves everything as it was.
  - **Chargen session lifecycle:**
    - The in-memory store evicts sessions idle longer than a configurable timeout (default 2
      hours). Since WP137, hosted chargen sessions are keyed by the login's token hash. One whose
      login ended other than by logout (expiry, an admin reset, a password change on another
      device) is otherwise never freed, so eviction must cover those too (WP137 review, 2026-10-03).
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
  - Opening character B, then using back/forward in the same tab, sends B's ID (the history-swap
    trap above).
  - Two sessions (two clients) open the same character. Both edit it. The second autosave is
    refused with the "changed elsewhere" notice, and the first one's edit is intact.
  - With a second tab open, Open/New asks for confirmation. Cancel changes nothing, and the
    other tab keeps working. With no other tab, there is no prompt.
  - Prefs POSTs never trigger an autosave.

- [x] **WP139 — The character list page.**
  *Suggested model:* Sonnet. A standard list page in the existing shell's style.
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
    character resets the chargen session. Its confirmation also carries WP138's other-tabs
    warning.
  - Open, New and Upload carry WP138's switch warning.
  - The step-nav shell gets a "My characters" link in the title bar. In hosted mode the title bar
    also shows the username and a logout link.
  - All strings go through i18n. Every theme renders the page (it reuses the shell's table and
    button styles).
  **From WP138 (2026-10-03):** the pieces are in place. `POST /characters/{id}/open` and
  `POST /characters/new` exist (`web/routes/characters.py`). `open_character_context()`
  (`web/persistence.py`) gives every switch control its `hx-confirm` text
  (`open_character.switch_question`), and `static/tabs.js` decides whether to show it. Deleting the
  open character should end in `persistence.new_character()`. The title bar's
  `_open_character.html` is where the "My characters" link goes.
  Depends on: WP138.
  Acceptance: a user with three characters sees exactly those three; filtering "ali" finds
  "Alias"-named rows only; deleting removes the row and the count drops; another user's characters
  never appear.

- [x] **WP140 — Download and upload.**
  *Suggested model:* Sonnet. It reuses the existing import logic. The limits and `defusedxml` are specified.
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
    in place. **WP138 already does the "new stored character, then open it" part** for the two
    existing single-file routes (`_store_as_new_character` in `web/routes/character.py`). What is
    left is moving them onto `/characters/upload`.
  - **Limits:** a configurable per-file size cap (default ~~5 MB~~ 10 MB, see below), enforced while reading, not after.
    At most 20 files per request.
  - **XML hardening:** parse uploaded XML with `defusedxml.ElementTree` (added as a runtime
    dependency, see the 2026-10-03 ruling). It refuses entity declarations and external
    references, which blocks entity-expansion bombs and external-entity reads. Legacy `.chum5`
    files don't use either. Check this against the fixture corpus. Only the upload path needs it.
    The game data XML under `legacy/` is trusted and keeps stdlib parsing.
  - `import_chum5` takes bytes (or a file object) in addition to a `Path`, which retires the temp-file
    workaround in `import_chum5_route`.
  **From WP139 (2026-10-03):** the list page has no Download link and no Upload control yet;
  both are this WP's. Download goes in each row's actions cell (`_character_list.html`, beside
  Open/Continue and Delete). Upload goes in `.character-list__toolbar` next to New, is disabled
  with the same `at_quota` reason, and carries the switch warning
  (`open_character.switch_question`, only when `open_character.stored`, like New). Since the list
  is outside `#app-shell`, an upload from it should end in a full navigation to `/` (as Open does),
  not `pages.shell_swap_response`.
  **Outcome (WP140, 2026-10-03):** two departures from the above, both in the decisions log.
  The per-file default is 10 MB, because legacy saves embed mugshots and one corpus file is
  5.7 MB (`CHUMMER5_UPLOAD_MAX_MB`). An upload from the list stores its files and opens none of
  them, so it carries no switch warning; only the Export page's upload (`?open=true`) opens what it
  stored. The old `/character/load` and `/character/import-chum5` routes are gone.
  Depends on: WP138, WP139.
  Acceptance:
  - A download → upload round trip produces an equal save.
  - Every `.chum5` fixture in `tests/fixtures` imports through the upload route.
  - A file declaring an entity is refused with a translated error, not a 500. An oversized file is
    refused without being fully read.
  - At 99 characters, uploading three files imports one and reports two quota errors.

- [x] **WP141 — Security pass.**
  *Suggested model:* **Opus.** The CSP will break things in non-obvious ways (`base.html`'s inline script). Origin checks and IP throttling behind a proxy are easy to get subtly wrong, and tests rarely catch it.
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
    cap for non-upload routes. (`POST /characters/upload` already caps its own body while reading,
    `chummer5.web.uploads`; WP140.)
  - A short `spec/` note listing what is protected and how, for future WPs to keep true.
  **Outcome (WP141, 2026-10-03):** `spec/security.md` is the resulting list. Beyond the
  deliverables above, the CSP needed htmx's event filters (`input[event.target.type=='number']`)
  replaced by a custom `number-input` event, since htmx evaluates filters with `new Function`.
  Templates' `url_for` now gives root-relative paths, so asset URLs no longer depend on uvicorn
  trusting the proxy's headers.
  Depends on: WP137-140.
  Acceptance:
  - A cross-origin POST is refused.
  - The 6th bad password in a row is throttled.
  - Every theme renders under the CSP with no console violations.
  - A forced 500 shows a generic page.

- [ ] **WP142 — Production container, Caddy, backups, runbook.**
  *Suggested model:* Sonnet. Mostly done already (`deploy/`). What remains is the backup script, the runbook and `test-image.sh` checks.
  Goal: run it on the user's server.
  **Head start (2026-10-03):** `deploy/` already has a production `Containerfile`, `deploy.sh` and
  an example Caddy block. They were written so the user could deploy the pre-Phase-Y app (local
  mode) behind Caddy `basicauth`. This WP extends them: hosted-mode environment, data volume,
  backup script, and dropping `basicauth` once WP137's login is live. The versioning scheme
  (`spec/deployment.md`'s "Versions" section) is already set.
  Deliverables:
  - A production `Containerfile` (separate from `.devcontainer/`). It is slim, runs as a non-root
    user, installs dependencies without the dev group, and runs `uvicorn --workers 1
    --proxy-headers` on `0.0.0.0:8000` inside the container.
  - Configuration is entirely environment variables: `CHUMMER5_MODE=hosted`, `CHUMMER5_DB`,
    `CHUMMER5_PUBLIC_URL`, `CHUMMER5_TRUSTED_PROXY`, the quota, the timeouts, and the upload cap
    (`CHUMMER5_UPLOAD_MAX_MB`, WP140).
    **From WP141:** hosted mode refuses to start without `CHUMMER5_PUBLIC_URL`, and refuses every
    form if it doesn't match the browser's address. `CHUMMER5_TRUSTED_PROXY` must be the address
    Caddy's connections arrive from *inside the container*. With rootless podman's port
    forwarding that may not be `127.0.0.1`, so check it (log `request.client.host` once, or
    compare the throttle across two clients). Getting it wrong lumps every player into one
    address for the login throttle. It doesn't open a hole. `deploy/test-image.sh` already runs
    its hosted container with a public URL and checks the 403.
  - An example `compose`/`podman run` setup with the port published to `127.0.0.1` only and a named
    volume for the database.
  - A Caddyfile site-block snippet (`reverse_proxy 127.0.0.1:<port>`) and an upload body-size limit
    matching WP140's. (WP140 set `deploy/Caddyfile.example` to 210MB, just above the app's own
    whole-request cap, so the app answers an oversized upload readably.)
  - A backup script using SQLite's online `.backup` (safe while running), a retention example, and a
    restore procedure.
  - `spec/deployment.md` (the runbook):
    - first deploy
    - minting the first invite
    - updating to a new version
    - backup and restore
    - where logs go
    - what to check if the site is down
  - The user carries out the actual server steps.
  - **Verification is split.**
    - The devcontainer has curl, sqlite3 and Caddy (2.6, so `basicauth`). There, the agent runs
      the app with uvicorn behind a local Caddy built from `deploy/Caddyfile.example`, and tests
      the backup script against a live database.
    - Image-level checks (build, fresh volume serves `/login`, backup restores into a working
      container) go into `deploy/test-image.sh`. The user runs that on the host, because podman
      can't run inside the unprivileged devcontainer.
  Depends on: WP141.
  Acceptance: the image builds; started with a fresh volume it serves `/login`; an invite minted via
  `podman exec ... python -m chummer5.admin invite` registers a user end to end through Caddy; a
  backup taken while running restores into a working instance.
