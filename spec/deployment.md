# Deployment

How Chummer5 gets from this repository onto the server, and how versions are numbered. Started
2026-10-03, before Phase Y. Phase Y's WP142 extends it into the full runbook: database volume,
backups, and the switch from Caddy `basicauth` to the app's own accounts. Day-to-day admin commands
are in `admin-primer.md`.

## The picture

```
 player's browser
      │  https://chummer.<domain>
      ▼
 ┌────────────────────────── the server ──────────────────────────┐
 │  Caddy (already running for mail + Nextcloud)                   │
 │    • TLS certificate, renewed automatically                     │
 │    • basicauth   (interim, until hosted mode)                   │
 │    • reverse_proxy → 127.0.0.1:8005                             │
 │          │                                                      │
 │          ▼  only reachable from the server itself               │
 │  container "chummer5"  (image chummer5:<version>)               │
 │    uvicorn, 1 worker, port 8000 inside                          │
 │    chargen sessions in memory   ← lost on every restart (today) │
 │    [Phase Y: + volume with chummer5.db]                         │
 └─────────────────────────────────────────────────────────────────┘
```

Three ideas carry the whole design:

1. **The image is the release.** A container image bundles Python, the locked dependencies, the
   code and the game data. The server runs that exact image and builds nothing. Moving to a new
   version means "start a different image". Rolling back means "start the old one again". Old
   images stay on the server until you prune them.
2. **Caddy is the only door.** The container publishes its port on `127.0.0.1` only. Nothing from
   the internet reaches uvicorn except through Caddy, which handles TLS and (for now) the password
   prompt.
3. **The server holds no source code.** You build on your own machine and send the image over SSH.
   The server needs a container runtime, `curl` and SSH. It needs no git, no Python and no repo
   checkout.

## What `deploy/deploy.sh` does

`deploy/deploy.sh user@server`, run on your machine (not in the devcontainer):

1. **Names the version.** It reads `version` from `pyproject.toml`. If HEAD is tagged
   `v<version>`, the image tag is `<version>` (a release). Otherwise it is
   `<version>-dev.<commit>` (for example `0.1.0-dev.a53f9b966`). Either way the tag says exactly
   which code is running.
2. **Builds from the commit, not the working tree.** It runs `git archive HEAD` into a temporary
   folder, copying only what the app needs at runtime: `src/`, `pyproject.toml`, `uv.lock`, and
   `legacy/Chummer/data` + `legacy/Chummer/lang`, which the loaders read at runtime. Then it runs
   `podman build -f deploy/Containerfile`. Uncommitted changes are left out, with a warning.
   - The Containerfile has two stages. The first installs uv and syncs the locked, non-dev
     dependencies. The second copies the result into a clean `python:3.12-slim` image, adds the
     legacy data, and runs as an unprivileged user.
3. **Ships the image.** It pipes `podman save | gzip | ssh server "gunzip | podman load"`. This
   sends the whole image (about 55 MB compressed, mostly the Python base image; the app
   itself is under 10 MB). A registry would only send changed layers,
   but it is one more service to run. Not worth it at this scale.
4. **Swaps the container.** It removes the old `chummer5` container and starts the new image with
   `--restart unless-stopped` and `-p 127.0.0.1:8005:8000`.
5. **Checks health and rolls back.** It polls `http://127.0.0.1:8005/static/app.css` on the server
   for up to 30 s. If the new version answers, it records the tag in `~/chummer5/current-tag`. If
   not, it prints the container's log and restarts the previous tag.

Settings, all optional:

- `REMOTE_CONTAINER_CMD=docker` if the server uses Docker. Default: `podman`.
- `CHUMMER5_HOST_PORT`: the loopback port Caddy proxies to. Default: `8005`.
- `BUILD_PLATFORM=linux/arm64`: only if the server's CPU differs from your machine's.

## Testing an image before deploying

`deploy/test-image.sh`, run on your machine, builds HEAD exactly as `deploy.sh` does. It then
starts the image on a loopback port and runs a few checks: static files, the start page, proxy
headers, the non-root user, and that the game data loaded. `KEEP=1` leaves it running so you can
look at it in a browser.

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
5. **Deploy:** `deploy/deploy.sh user@server`.
6. **Caddy:** add the block from `deploy/Caddyfile.example` to the server's Caddyfile:
   - Replace the domain.
   - Create one `basicauth` line per player. Run `caddy hash-password` on the server for each
     hash.
   - Reload with `sudo systemctl reload caddy`. **Do step 1 first, and check it.**

   Caddy fetches the certificate from Let's Encrypt itself, which works only once DNS points at
   the server. If Caddy tried earlier, the browser says **"Secure connection failed"** (Caddy has
   no certificate for the name), and Caddy waits longer between each retry.
   `sudo systemctl restart caddy` makes it try again now, then `journalctl -u caddy -f` should
   show "certificate obtained successfully". If it says "too many failed authorizations", Let's
   Encrypt's limit of 5 failed attempts per name per hour was used up: wait an hour and restart
   again.
7. Open `https://chummer.<domain>`, enter a basic-auth login, and you should see chargen.

## Every later deploy

```
git switch python_reimplementation      # or whichever branch you deploy
git pull
deploy/deploy.sh user@server
```

**Until Phase Y lands, a deploy wipes every in-progress character.** They live only in the
container's memory. Tell players to save (Export → download JSON) before you deploy. They can load
that file afterwards. WP136-138 remove this caveat.

## Rolling back

```
ssh user@server podman images chummer5      # which versions are there?
CHUMMER5_TAG=0.1.0 deploy/deploy.sh user@server
```

Once Phase Y's database exists, rolling back across a schema migration needs the backup from before
the upgrade (WP142 documents this).

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
