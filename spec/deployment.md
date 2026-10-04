# Deployment

How Chummer5 gets from this repository onto the server and stays there: the image, the server's
one-time setup, the switch to hosted mode, updates, backups and restores, logs, and how versions
are numbered. Started 2026-10-03, before Phase Y; WP142 made it the full runbook. Day-to-day admin
commands (invites, users, passwords) are in `admin-primer.md`; what the app protects and how is in
`security.md`.

## The picture

```
 player's browser
      │  https://chummer.<domain>
      ▼
 ┌────────────────────────── the server ──────────────────────────┐
 │  Caddy (already running for mail + Nextcloud)                   │
 │    • TLS certificate, renewed automatically                     │
 │    • reverse_proxy → 127.0.0.1:8005                             │
 │          │                                                      │
 │          ▼  only reachable from the server itself               │
 │  container "chummer5"  (image chummer5:<version>)               │
 │    uvicorn, 1 worker, port 8000 inside                          │
 │    settings: ~/chummer5/chummer5.env  (hosted mode, public URL) │
 │    /data  ← volume "chummer5-data"                              │
 │       chummer5.db     accounts, invites, logins, characters     │
 │       backups/        before every deploy, and nightly          │
 └─────────────────────────────────────────────────────────────────┘
```

Four ideas carry the whole design:

1. **The image is the release.** A container image bundles Python, the locked dependencies, the
   code and the game data. The server runs that exact image and builds nothing. Moving to a new
   version means "start a different image". Rolling back means "start the old one again". Old
   images stay on the server until you prune them.
2. **Caddy is the only door.** The container publishes its port on `127.0.0.1` only. Nothing from
   the internet reaches uvicorn except through Caddy, which handles TLS. Accounts and logins are
   the app's own (hosted mode).
3. **The server holds no source code.** You build on your own machine and send the image over SSH.
   The server needs a container runtime, `curl` and SSH. It needs no git, no Python and no repo
   checkout.
4. **The data lives in a volume, not the container.** Replacing the container (every deploy)
   keeps the volume, and with it every account and character. Players' in-progress edits are
   autosaved, so a deploy loses nothing but the open page, which reloads.

## What `deploy/deploy.sh` does

`deploy/deploy.sh user@server`, run on your machine (not in the devcontainer):

1. **Names the version.** It reads `version` from `pyproject.toml`. If HEAD is tagged
   `v<version>`, the image tag is `<version>` (a release). Otherwise it is
   `<version>-dev.<commit>` (for example `0.1.0-dev.a53f9b966`). Either way the tag says exactly
   which code is running.
2. **Builds from the commit, not the working tree.** It runs `git archive HEAD` into a temporary
   folder, copying only what the app needs at runtime: `src/`, `pyproject.toml`, `uv.lock`, and
   `legacy/Chummer/data` + `legacy/Chummer/lang`, which the loaders read at runtime, plus `LICENSE`
   and `NOTICE`, which the GPL requires to travel with every copy. Then it runs
   `podman build -f deploy/Containerfile`. Uncommitted changes are left out, with a warning.
   - The Containerfile has two stages. The first installs uv and syncs the locked, non-dev
     dependencies. The second copies the result into a clean `python:3.12-slim` image, adds the
     legacy data, and runs as an unprivileged user.
3. **Ships the image.** It pipes `podman save | gzip | ssh server "gunzip | podman load"`. This
   sends the whole image (about 55 MB compressed, mostly the Python base image; the app
   itself is under 10 MB). A registry would only send changed layers,
   but it is one more service to run. Not worth it at this scale.
4. **Backs up, then swaps the container.** It first takes an online backup of the running
   container's database (`admin backup --keep 30`, into the volume's `backups/`). Then it removes
   the old `chummer5` container and starts the new image with `--restart unless-stopped`,
   `-p 127.0.0.1:8005:8000`, `-v chummer5-data:/data` and, if the server has one,
   `--env-file ~/chummer5/chummer5.env`. Without that file the app runs in local mode, and the
   script says so.
5. **Checks health and rolls back.** It polls `http://127.0.0.1:8005/static/app.css` on the server
   for up to 30 s. If the new version answers, it records the tag in `~/chummer5/current-tag`. If
   not, it prints the container's log and restarts the previous tag.

Settings, all optional:

- `REMOTE_CONTAINER_CMD=docker` if the server uses Docker. Default: `podman`.
- `CHUMMER5_HOST_PORT`: the loopback port Caddy proxies to. Default: `8005`.
- `BUILD_PLATFORM=linux/arm64`: only if the server's CPU differs from your machine's.

## Testing an image before deploying

`deploy/test-image.sh`, run on your machine, builds HEAD exactly as `deploy.sh` does. It then
starts the image in local mode and in hosted mode (on a fresh volume) on loopback ports and checks:

- static files, the start page, root-relative asset URLs, the CSP header, the non-root user, and
  the game data;
- hosted mode: the redirect to `/login`, minting an invite, refusing a cross-origin POST, and
  registering through the page;
- that a backup taken while it runs restores into a fresh volume, and a container on that volume
  serves `/login` and knows the user.

`KEEP=1` leaves the containers running so you can look at them in a browser.

This is the one check that runs on the host, not in the devcontainer. The devcontainer is
unprivileged on purpose, and podman can't build or run images inside it (decisions-log,
2026-10-03). Phase Y WPs add their own checks to this script.

## First deploy (one-time server setup)

1. **DNS:** an `A` (and `AAAA`, if you have IPv6) record for `chummer.<domain>` pointing at the
   server. Copy the addresses an existing name on that server already has (e.g. `cloud.<domain>`).
   - Add it **where the domain's DNS is hosted**, which is whatever `NS` record the domain has
     (for sixthworldforge.com: Hover). It is not necessarily the server's hosting company. Records
     added in a DNS console the domain doesn't use change nothing.
   - In the provider's form, the host name is just `chummer`, not the full name.
   - **A wildcard record (`*`) hides a missing one.** Every name without its own record still
     resolves, to the wildcard's address, so the browser reaches the wrong machine and says
     "Unable to connect". Check before going on: `getent hosts chummer.<domain>` must show the
     server's address, the same as `getent hosts cloud.<domain>`. Resolvers may keep an old answer
     for the record's TTL (Hover: 15 minutes).
2. **Container runtime, curl and gzip on the server.** `deploy.sh` checks all of this first,
   before building, and says what is missing.
   - **Rootless Podman** (the default: deploying as an unprivileged user) needs more than the
     `podman` package. Debian/Ubuntu ship these as `podman`'s *recommended* packages, so they are
     missing when it was installed with `--no-install-recommends`:
     `sudo apt install podman uidmap slirp4netns fuse-overlayfs dbus-user-session catatonit`
     (`slirp4netns` is podman 4's network helper; podman 5 uses `passt` instead).
     The deploying user also needs subordinate ID ranges: if `grep <user> /etc/subuid
     /etc/subgid` finds nothing, run `sudo usermod --add-subuids 100000-165535 --add-subgids
     100000-165535 <user>`. Then, as that user, after logging in again: `podman system migrate`.
     Every `sudo` step can be run by another admin account; the deploying user needs no sudo.
   - **Docker:** the deploying user must be allowed to use the Docker socket (usually the
     `docker` group, which is effectively root on that machine). Deploy with
     `REMOTE_CONTAINER_CMD=docker`.
3. **Keep the container running.** Under Podman this needs systemd's help:
   - rootful Podman: `sudo systemctl enable --now podman-restart.service`
   - rootless Podman (deploying as a normal user): `sudo loginctl enable-linger <user>`, then, as
     that user, `systemctl --user enable --now podman-restart.service`.
     **Lingering is not optional.** Without it, systemd stops all of the user's processes when
     their last session ends, and that includes the container. The deploy's health check passes
     (its ssh session is still open), and the site answers **502 Bad Gateway** from the moment it
     closes. `deploy.sh` refuses to deploy while lingering is off. If `systemctl --user` says
     "Failed to connect to bus", log in again after enabling lingering.
   - Docker: nothing to do. The daemon honors the restart policy.
4. **SSH:** `ssh user@server true` works from your machine without a password prompt (key-based).
5. **The app's settings:** on the server, create `~/chummer5/chummer5.env`:

   ```
   CHUMMER5_MODE=hosted
   CHUMMER5_PUBLIC_URL=https://chummer.<domain>
   ```

   `CHUMMER5_PUBLIC_URL` must be exactly what players type: scheme and host, no path. If it is
   wrong, every form answers "That request was refused". Other settings are optional (see
   "Settings" below). The file is read on every deploy; after changing it, redeploy (or
   `CHUMMER5_TAG=$(ssh user@server cat chummer5/current-tag) deploy/deploy.sh user@server`).
6. **Deploy:** `deploy/deploy.sh user@server`. It should say `Settings: ... (mode: hosted)`.
7. **Caddy:** add the block from `deploy/Caddyfile.example` to the server's Caddyfile:
   - Replace the domain.
   - Reload with `sudo systemctl reload caddy`. **Do step 1 first, and check it.**

   Caddy fetches the certificate from Let's Encrypt itself, which works only once DNS points at
   the server. If Caddy tried earlier, the browser says **"Secure connection failed"** (Caddy has
   no certificate for the name), and Caddy waits longer between each retry.
   `sudo systemctl restart caddy` makes it try again now, then `journalctl -u caddy -f` should
   show "certificate obtained successfully". If it says "too many failed authorizations", Let's
   Encrypt's limit of 5 failed attempts per name per hour was used up: wait an hour and restart
   again.
8. **The first invite:** on the server, `podman exec chummer5 python -m chummer5.admin invite`.
   Open `https://chummer.<domain>/register` and register yourself with it. You land on "My
   characters". Invite players the same way (`admin-primer.md`).
9. **Nightly backups:** set up the timer under "Backups" below.

## Switching to hosted mode

For the server that already runs the pre-hosted app behind Caddy `basicauth` (the first deploy,
2026-10-03):

1. **Tell players to download their characters** (Export → download JSON). Local mode keeps
   characters in the container's memory, and the switch restarts it. Afterwards they upload the
   files on "My characters" (several at once is fine).
2. Create `~/chummer5/chummer5.env` (First deploy, step 5), then run `deploy/deploy.sh
   user@server` (step 6).
3. Mint your own invite and register (step 8). Caddy's `basicauth` still asks first; that's
   expected.
4. Remove the `basicauth { ... }` block from the server's Caddyfile (compare with
   `deploy/Caddyfile.example`), check that `request_body { max_size 210MB }` is there, and
   `sudo systemctl reload caddy`.
5. Send each player an invite code and the URL.

## Every later deploy

```
git switch python_reimplementation      # or whichever branch you deploy
git pull
deploy/test-image.sh                    # optional, but cheap
deploy/deploy.sh user@server
```

Nothing is lost. Accounts, logins and characters are in the volume, and every chargen change was
autosaved. Players' open pages stop answering for the few seconds of the swap; the next click
reloads into the same character. A database migration, if the new version has one, runs on the
first start, after the pre-deploy backup.

## Rolling back

```
ssh user@server podman images chummer5      # which versions are there?
CHUMMER5_TAG=0.1.0 deploy/deploy.sh user@server
```

`deploy.sh` also rolls back by itself when the new version doesn't answer its health check.

**Across a schema change.** If the newer version migrated the database, the older one refuses to
start: its log says `database schema is version N, newer than this program knows`. Then restore
the backup `deploy.sh` took just before the upgrade (the newest one older than that deploy) with
the old version's image, as under "Restoring" below, and start it.

## Backups

The database is one SQLite file, `/data/chummer5.db` in the volume `chummer5-data`. Every backup
is a consistent copy taken while the app runs (SQLite's online backup API), checked with SQLite's
integrity check, and named `chummer5-YYYYmmdd-HHMMSS.db` (UTC).

| Backup | Where it lands | Kept |
|---|---|---|
| Before every deploy (`deploy.sh`, automatic) | the volume's `backups/` | the newest 30, shared with the nightly ones |
| Nightly (the timer below) | the volume's `backups/` | the same 30 |
| Off the server: `deploy/backup.sh user@server [dir]`, from your machine | `./backups/` (or `dir`) on your machine | until you delete them |

The volume survives container swaps but not losing the server or its disk. **Copy one off now and
then** with `deploy/backup.sh`, after anything you'd hate to redo (a session of character
building, before a server upgrade). It also checks the copy with `sqlite3` if your machine has it.

**Nightly, on the server** (rootless podman, as the deploying user; lingering is on already):

```
mkdir -p ~/.config/systemd/user
cat > ~/.config/systemd/user/chummer5-backup.service <<'UNIT'
[Unit]
Description=Back up the Chummer5 database

[Service]
Type=oneshot
ExecStart=/usr/bin/podman exec chummer5 python -m chummer5.admin backup --keep 30
UNIT
cat > ~/.config/systemd/user/chummer5-backup.timer <<'UNIT'
[Unit]
Description=Back up the Chummer5 database nightly

[Timer]
OnCalendar=*-*-* 04:15
Persistent=true

[Install]
WantedBy=timers.target
UNIT
systemctl --user daemon-reload
systemctl --user enable --now chummer5-backup.timer
systemctl --user list-timers chummer5-backup.timer     # shows the next run
```

(Docker: a root crontab line `15 4 * * * docker exec chummer5 python -m chummer5.admin backup
--keep 30`.) To see what's there: `podman exec chummer5 ls -l /data/backups`.

### Restoring

A restore replaces the whole database: every account, character and login since that backup is
gone, and players log in again. Run it with the container stopped. The running app's
autosaves would otherwise write over the restored rows.

On the server:

```
TAG=$(cat ~/chummer5/current-tag)
podman exec chummer5 python -m chummer5.admin backup      # the state you're about to replace, just in case
podman exec chummer5 ls /data/backups                     # pick one
podman stop chummer5
podman run --rm -v chummer5-data:/data chummer5:$TAG \
    python -m chummer5.admin restore --yes /data/backups/chummer5-20261003-041500.db
podman start chummer5
```

From a copy on your machine, first put it into the volume (the container can be running):

```
ssh user@server "podman run --rm -i -v chummer5-data:/data chummer5:\$(cat ~/chummer5/current-tag) \
    sh -c 'cat > /data/backups/uploaded.db'" < backups/chummer5-20261003-041500.db
```

then restore `/data/backups/uploaded.db` as above. `restore` refuses a file that isn't a sound
Chummer5 database, or whose schema is newer than the image knows (use that newer image). An older
schema is migrated when the container starts.

## Logs

- **The app:** `podman logs --tail 100 chummer5` (`-f` to follow). This holds uvicorn's access
  log, startup errors (a bad setting stops the start and says which), every 500's traceback, and
  `refused cross-site` warnings (a wrong `CHUMMER5_PUBLIC_URL` shows up here first).
- **Caddy:** `journalctl -u caddy` (certificates, TLS, upstream errors behind a 502).
- **The backups timer:** `journalctl --user -u chummer5-backup`.

If the site is down, `admin-primer.md` → "If the site is down" goes from what the browser says to
the broken link.

## Settings

The app reads environment variables. In production they come from `~/chummer5/chummer5.env` on the
server (`deploy.sh` passes it with `--env-file`). A bad value stops the app from starting, with the
reason in its log.

| Variable | Default | Meaning |
|---|---|---|
| `CHUMMER5_MODE` | `local` | `hosted` for accounts and logins. `local` is one implicit user, no login |
| `CHUMMER5_PUBLIC_URL` | (none; required in hosted mode) | The address players use, e.g. `https://chummer.example.org`. Every POST's `Origin` must match it |
| `CHUMMER5_DB` | `/data/chummer5.db` (set by the image) | The database file. Keep it on the volume |
| `CHUMMER5_CHARACTER_QUOTA` | `100` | Characters per account |
| `CHUMMER5_SESSION_DAYS` | `30` | How long an unused login lasts |
| `CHUMMER5_SESSION_IDLE_MINUTES` | `120` | How long an unused chargen session stays in memory. Nothing is lost when it goes |
| `CHUMMER5_UPLOAD_MAX_MB` | `10` | The largest file an upload may carry. Caddy's `request_body max_size` must stay above 20 × this |
| `CHUMMER5_TRUSTED_PROXY` | `127.0.0.1,::1` | Whose `X-Forwarded-For` the login throttle believes. Not needed with the image: uvicorn already takes the client address from Caddy's header |

## Versions

**Where things stand (2026-10-03):** `pyproject.toml` has said `0.1.0` since WP1. It was never
bumped, and there are no git tags. So the project is not really using SemVer yet. The number is a
placeholder.

**From now on:**

- **One source of truth:** `version` in `pyproject.toml`. A **release** is a commit where that
  version is set and which is tagged `v<version>`. Anything else is a dev build, and `deploy.sh`
  tags it so.
- **What the numbers mean for this app.** It's an application, not a library, so "public API"
  means what players and their files depend on:
  - **MAJOR:** something players had stops working with no automatic path forward. Examples: a
    save file or stored character that can no longer be loaded, or a removed feature.
    Migrations exist to avoid this, so it should be rare.
  - **MINOR:** new capability (most WPs). Includes a save-format or database change that is
    migrated automatically.
  - **PATCH:** fixes only, nothing new.
- **0.x until Phase Y ships, then 1.0.0.** Pre-1.0 means "no compatibility promise", which is
  honest while nobody's characters are stored on the server. The first hosted release, where
  players start trusting the server with their characters, is the natural 1.0.0.
- **Separate counters stay separate.** The save file's `format_version` (`chummer5.io.save_format`)
  and Phase Y's database schema version count format changes. They are not the app version. A
  MINOR app release can raise either one, as long as it migrates old data.

**Cutting a release:**

```
uv version --bump minor        # or patch / major; updates pyproject.toml and uv.lock together
git commit -am "Release $(uv version --short)"
git tag "v$(uv version --short)"
git push && git push --tags
deploy/deploy.sh user@server
```

**Suggested first step:** tag the commit you first deploy as `v0.1.0`, since that is what
`pyproject.toml` already says. Then bump MINOR on each deploy that brings new features.
