# Admin primer

Every command needed to run the hosted app, in one place. **Keep this file true:** any WP that adds,
renames or removes an admin command updates it in the same commit.

The **Since** column says which WP makes a command real. Commands marked *planned* don't exist yet.
Their syntax is the plan's (`plan/phase-y-hosted-deployment.md`) and may still shift slightly.

All server commands assume rootless or rootful **Podman** and the container name `chummer5`. With
Docker, replace `podman` with `docker`. Deployment itself (building, shipping, first-time setup) is
in `deployment.md`.

## Accounts and invites

The admin CLI runs inside the container, so it uses the app's own code and database:

```
podman exec -it chummer5 python -m chummer5.admin <command> [options]
```

| Task | Command | Since |
|---|---|---|
| Mint an invite code (prints it) | `invite` | planned, WP137 |
| … that expires after N days | `invite --expires-days 7` | planned, WP137 |
| List open (unused, unexpired) invites | `invites` | planned, WP137 |
| Revoke an invite | `revoke CODE` | planned, WP137 |
| List accounts | `users` | planned, WP137 |
| Reset a password (prints a one-time temporary password) | `reset-password USERNAME` | planned, WP137 |
| Delete an account and all its characters (asks first) | `delete-user USERNAME` | planned, WP137 |

Typical flows:

- **A new player.** Run `invite --expires-days 7` and send them the code with the URL. They pick
  their own username and password on `/register`.
- **Forgotten password.** Run `reset-password NAME` and give them the temporary password over a
  channel you trust. There is no email reset, by design.

**Until WP137 ships,** access is Caddy `basicauth` instead (see `deploy/Caddyfile.example`):

| Task | Command |
|---|---|
| Hash a password for a new player | `caddy hash-password` (on the server; prompts) |
| Add, change or remove a player | edit the `basicauth { … }` lines in the Caddyfile |
| Apply the change | `sudo systemctl reload caddy` |

## Deploying and rolling back (from your machine)

| Task | Command |
|---|---|
| Deploy the current commit | `deploy/deploy.sh user@server` |
| Roll back / redeploy a version the server has | `CHUMMER5_TAG=0.1.0 deploy/deploy.sh user@server` |
| Cut a release before deploying | see `deployment.md` → "Cutting a release" |

## Status and logs (on the server)

| Task | Command |
|---|---|
| Is it running? Since when? | `podman ps --filter name=chummer5` |
| Which version is live? | `cat ~/chummer5/current-tag` |
| Does it answer? | `curl -fsS -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8005/static/app.css` |
| App log (uvicorn: one line per request, plus errors) | `podman logs --tail 100 chummer5` |
| Follow the app log live | `podman logs -f chummer5` |
| Caddy's log (TLS, proxy errors, 502s) | `journalctl -u caddy --since "1 hour ago"` |
| Memory/CPU of the container | `podman stats --no-stream chummer5` |

## Starting, stopping, cleaning up (on the server)

| Task | Command |
|---|---|
| Restart (loses in-memory chargen sessions, see below) | `podman restart chummer5` |
| Stop / start | `podman stop chummer5` / `podman start chummer5` |
| List the versions kept on the server | `podman images chummer5` |
| Delete one old version | `podman rmi chummer5:0.1.0` |
| Delete every image no container uses | `podman image prune -a` (this also removes your rollback targets) |

**What a restart loses.** Today, any character not saved by its player. Players should download
their JSON save before you restart or deploy. Once WP138 ships, a restart loses at most a
pre-priorities draft. Everything after the priority confirmation is autosaved.

## Database and backups (planned)

| Task | Command | Since |
|---|---|---|
| Back up while running (SQLite online backup) | backup script, path TBD | planned, WP142 |
| Restore a backup | procedure in `deployment.md` | planned, WP142 |
| Where the database lives | named volume, mounted at the path in `CHUMMER5_DB` | planned, WP136/142 |

## If the site is down

1. `podman ps -a --filter name=chummer5`. If it isn't "Up", check `podman logs --tail 50 chummer5`
   for the reason. Then `podman start chummer5`, or redeploy the last good tag.
2. If the container is up but the browser shows 502, Caddy can't reach it. Check the `curl` line
   above. If that works, compare the port in the Caddyfile's `reverse_proxy` with
   `CHUMMER5_HOST_PORT`.
3. If there is a certificate or "connection refused" on 443, it's Caddy itself:
   `systemctl status caddy` and `journalctl -u caddy`.
4. If it was down after a server reboot, the restart policy isn't wired to systemd. See
   `deployment.md` → "First deploy", step 3.
