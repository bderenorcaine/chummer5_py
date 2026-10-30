[← back to Implementation Plan index](../Implementation%20Plan.md)

### Phase α — Post-MVP: admin web page (WP153-154)

**Why now.** Raised 2026-10-30. The user wants a small admin screen in the hosted app that lists
the signed-up users and the characters each has made. Phase Y kept the admin surface CLI-only
("Admin web page? Not in this phase, maybe later"; see `phase-y-hosted-deployment.md`'s rulings
table and `spec/decisions-log.md`'s 2026-10-03 entry). This phase is that "later". Phase Y also
built for it: `chummer5.accounts` and `chummer5.store.backup` hold the logic with no web or
`argparse` imports, so the page calls the same functions as `python -m chummer5.admin`.

**Depends on:** Phase Y (accounts, login sessions, the character list's store methods, WP141's
cross-site request check). Read `phase-y-hosted-deployment.md` only if a WP below points at a
specific part of it.

**The user's rulings (2026-10-30):**

| Question | Ruling |
|---|---|
| Who is an admin? | **A flag on the user row**, set and cleared from the CLI only (`grant-admin` / `revoke-admin`). The flag belongs to the user ID, so a later account that reuses a deleted admin's name does not inherit it. No web control grants admin. Server shell access stays the root of trust. |
| How much of a user's characters does the admin see? | **The list only:** name, street name, metatype, created, last updated, revision. The admin cannot open, download or view the sheet of another user's character. |
| Which actions does the page offer? | **Reset password** and **invite codes** (mint, list, revoke). Deleting users, backup and restore **stay CLI-only**. |
| Process | Plan first. The user reviews this file before WP153 starts. |

**Defaults this file sets (not user rulings; change them here if they turn out wrong):**

- **Hosted mode only.** In local mode there are no accounts, so every `/admin` URL is a 404 and no
  admin link is shown.
- **A non-admin gets a 404, not a 403.** This is the same choice as Phase Y's owner scoping: a
  page you may not see looks like one that doesn't exist. Anonymous requests are already turned
  away by the login middleware before any admin check runs.
- **The flag is read on every request.** The middleware already loads the user row with the login
  session, so `revoke-admin` takes effect on the admin's next request, not at their next login.
- **Admin pages are plain pages, like `/characters`,** not chargen steps. They use the same shell,
  title bar, table and button styles, and every theme. All text goes through i18n (WP102).
- **No new dependencies.**

---

- [ ] **WP153 — Admin flag, users list, and each user's characters (read-only).**
  *Suggested model:* Sonnet, then an Opus `/code-review high`. The pages are routine. The
  authorization gate is the part where a mistake passes every happy-path test.
  Goal: an admin can see every account and each account's character list. Nothing on these pages
  changes data.
  Deliverables:
  - **Schema v4:** `users.is_admin INTEGER NOT NULL DEFAULT 0` (`store/migrations.py`), and
    `UserRecord.is_admin: bool`, read the same way as `must_change_password`.
  - **CLI:** `grant-admin USERNAME` and `revoke-admin USERNAME` (an unknown user exits 1 with a
    message, like `reset-password`). `users` marks admins with `(admin)`. The logic lives in
    `chummer5.accounts`, and `admin.py` stays a thin layer. Update `spec/admin-primer.md` in the
    same commit, including a line on how to make the first admin.
  - **The gate:** one helper or dependency (e.g. `require_admin(request) -> UserRecord`) that
    raises 404 unless the mode is hosted and `current_user(request).is_admin`. Every `/admin` route
    uses it, and no admin route checks this by hand.
  - **`GET /admin`, the users list.** It shows username, an admin marker, character count, created,
    last login ("never" if none), and a marker for "must change password". Rows are sorted by
    username (what `Store.list_users()` already returns), and each username links to that user's
    page.
  - **`GET /admin/users/{user_id}`, one user's characters.** A header with the same facts as their
    users-list row, then a table of their characters: shown name (the same street-name / name /
    "Unnamed" fallback as WP139's list, so reuse its helper), metatype, created, last updated, and
    revision. It is sorted by last updated, newest first. The characters come from
    `Store.list_characters(user_id)`. Store methods take an `owner_id` argument, so the admin check
    in the route is what authorizes the read. Do not add an unscoped store method. An unknown
    `user_id` is a 404. There are no open, download or delete controls.
  - **Title bar:** an "Admin" link in `_titlebar_account.html`, rendered only for admins. It appears
    on both the chargen shell and the character list.
  Depends on: Phase Y (WP136-142).
  Acceptance:
  - Migrating a v3 database gives v4 with every existing user `is_admin = 0`.
  - `grant-admin` / `revoke-admin` round-trip, and `users` shows the marker.
  - Hosted mode, admin: `/admin` lists every user with correct character counts.
    `/admin/users/{id}` for another user lists exactly that user's characters and no one
    else's.
  - Hosted mode, a logged-in non-admin: every `/admin` URL is a 404, and the title bar has no Admin
    link.
  - An admin revoked by `revoke-admin` gets a 404 on their next request, with the same login
    session.
  - Anonymous: `/admin` redirects to `/login` (the existing middleware).
  - Local mode: every `/admin` URL is a 404, and the existing suite passes unchanged.

- [ ] **WP154 — Admin actions: reset password, invite codes.**
  *Suggested model:* Sonnet, then an Opus `/code-review high`. These are auth-affecting writes, and
  one of them puts a secret on a page.
  Goal: the CLI's `reset-password`, `invite`, `invites` and `revoke` are available from the admin
  pages, calling the same `chummer5.accounts` functions.
  Deliverables:
  - **Reset password** on `/admin/users/{user_id}`: a button behind an `hx-confirm` that names the
    user and says their sessions end. `POST /admin/users/{user_id}/reset-password` calls
    `accounts.reset_password` and shows the one-time password once, in the response, with
    `Cache-Control: no-store`. The password is never logged, and it is not shown again on reload.
    - **The admin cannot reset their own password here.** Doing so would end the admin's own
      session mid-request. The button is not shown on the admin's own row, and the route refuses it
      (400). The admin uses `/account/password` like any player.
  - **Invites** section on `/admin`:
    - A form to mint a code with an optional "expires after N days", which shows the new code
      formatted as `accounts.format_invite` gives it.
    - A table of open invites (code, created, expires or "never").
    - A Revoke button per row (`hx-confirm`).
    - A code that is already used or revoked gives the same message the CLI gives, not a 500.
  - All three POSTs use the WP153 gate. They are non-GET, so WP141's `Origin` check already covers
    them. Add a test that a cross-site POST to each one is refused.
  - `spec/admin-primer.md`: note under "Typical flows" that both flows (new player, forgotten
    password) can now also be done from `/admin`.
  Depends on: WP153.
  Acceptance:
  - An admin resets user B's password. B's existing session is logged out. B can log in once with
    the shown password and is then sent to `/account/password`.
  - An admin cannot reset their own password from `/admin`, in the UI or by a direct POST.
  - A non-admin POST to any of the three routes is a 404, and nothing changes.
  - A minted code registers a new account. A revoked code is refused at `/register`. An expired
    code does not appear in the open list.
