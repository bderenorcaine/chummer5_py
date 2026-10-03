#!/usr/bin/env bash
# Take a backup of the server's database and copy it to THIS machine. Safe while the app runs:
# SQLite's online backup API takes a consistent snapshot (chummer5.store.backup).
# See spec/deployment.md, "Backups".
#
# Usage:
#   deploy/backup.sh user@server              # into ./backups/
#   deploy/backup.sh user@server ~/chummer-backups
#
# Settings (environment variables, all optional):
#   REMOTE_CONTAINER_CMD  container CLI on the server: podman (default) or docker
#   KEEP                  backups to keep in the server's volume, newest first (default 30)
#
# A copy stays in the volume's backups/ folder on the server too; this one is the copy that
# survives losing the server. Nightly backups on the server itself: spec/deployment.md.

set -euo pipefail

if [[ $# -lt 1 || $# -gt 2 ]]; then
    sed -n '2,13p' "$0" >&2
    exit 2
fi

SERVER="$1"
DEST="${2:-backups}"
RCMD="${REMOTE_CONTAINER_CMD:-podman}"
KEEP="${KEEP:-30}"
CONTAINER="chummer5"

mkdir -p "${DEST}"
echo "==> Backing up on ${SERVER}"
REMOTE_PATH="$(ssh "${SERVER}" "${RCMD} exec ${CONTAINER} python -m chummer5.admin backup --keep ${KEEP}")"
NAME="$(basename "${REMOTE_PATH}")"
echo "==> Copying ${NAME} here"
# Through the container (cat), so this needs no access to where the volume lives on the host.
ssh "${SERVER}" "${RCMD} exec ${CONTAINER} cat '${REMOTE_PATH}'" > "${DEST}/${NAME}.partial"
mv "${DEST}/${NAME}.partial" "${DEST}/${NAME}"
# The file is a plain SQLite database: check it here too, if this machine has sqlite3.
if command -v sqlite3 >/dev/null; then
    [[ "$(sqlite3 "${DEST}/${NAME}" 'PRAGMA integrity_check')" == ok ]] \
        || { echo "error: ${DEST}/${NAME} fails the integrity check" >&2; exit 1; }
fi
echo "==> OK: ${DEST}/${NAME} ($(du -h "${DEST}/${NAME}" | cut -f1))"
