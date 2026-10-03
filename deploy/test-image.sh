#!/usr/bin/env bash
# Build the production image from HEAD and check it works, on THIS machine. Run from the HOST (needs
# podman), not from inside the devcontainer: the devcontainer is deliberately unprivileged, and
# podman can't build or run images inside it (decisions-log, 2026-10-03).
#
# Usage:
#   deploy/test-image.sh            # build HEAD, start it on a free loopback port, run the checks
#   KEEP=1 deploy/test-image.sh     # leave the container running afterwards, to poke at it
#
# Phase Y WPs extended the checks below (WP137: hosted mode's login gate and admin CLI; WP141: the
# CSP, the cross-site check, root-relative asset URLs; WP142: data volume, backup and restore).
# Uses loopback ports CHUMMER5_TEST_PORT (default 18005) to +2. Each check prints PASS or FAIL; the script exits non-zero if any failed.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
# shellcheck source=deploy/lib.sh
source "${SCRIPT_DIR}/lib.sh"

CONTAINER="chummer5-imagetest"
HOSTED_CONTAINER="chummer5-imagetest-hosted"
RESTORED_CONTAINER="chummer5-imagetest-restored"
# WP142: hosted mode runs on a fresh named volume, like deploy.sh's chummer5-data; a backup of it
# is restored into a second volume and served from there.
VOLUME="chummer5-imagetest-data"
RESTORED_VOLUME="chummer5-imagetest-restored"
PORT="${CHUMMER5_TEST_PORT:-18005}"
HOSTED_PORT=$((PORT + 1))
FAILED=0

check() {   # check "description" command...
    local what="$1"; shift
    if "$@" >/dev/null 2>&1; then
        echo "PASS  ${what}"
    else
        echo "FAIL  ${what}"
        FAILED=1
    fi
}

remove_all() {
    podman rm -f "${CONTAINER}" "${HOSTED_CONTAINER}" "${RESTORED_CONTAINER}" >/dev/null 2>&1 || true
    podman volume rm -f "${VOLUME}" "${RESTORED_VOLUME}" >/dev/null 2>&1 || true
}

cleanup() {
    if [[ -z "${KEEP:-}" ]]; then
        remove_all
    else
        echo "==> Left running: http://127.0.0.1:${PORT}/  (podman rm -f ${CONTAINER} when done)"
    fi
}

TAG="$(image_tag)"
echo "==> Building ${IMAGE}:${TAG}"
build_image "${TAG}"

remove_all
trap cleanup EXIT
echo "==> Starting it on 127.0.0.1:${PORT} (local mode) and 127.0.0.1:${HOSTED_PORT} (hosted mode)"
podman run -d --name "${CONTAINER}" -p "127.0.0.1:${PORT}:8000" "${IMAGE}:${TAG}" >/dev/null
# WP141: hosted mode needs its public URL (the cross-site check compares every POST's Origin).
HOSTED_ENV=(-e CHUMMER5_MODE=hosted -e "CHUMMER5_PUBLIC_URL=http://127.0.0.1:${HOSTED_PORT}")
podman run -d --name "${HOSTED_CONTAINER}" -p "127.0.0.1:${HOSTED_PORT}:8000" \
    -v "${VOLUME}:/data" "${HOSTED_ENV[@]}" "${IMAGE}:${TAG}" >/dev/null

for port in "${PORT}" "${HOSTED_PORT}"; do
    for _ in $(seq 1 30); do
        curl -fsS -o /dev/null "http://127.0.0.1:${port}/static/app.css" && break
        sleep 1
    done
done

echo "==> Checks"
check "static files are served" \
    curl -fsS -o /dev/null "http://127.0.0.1:${PORT}/static/app.css"
check "the start page renders (200)" \
    curl -fsS -o /dev/null "http://127.0.0.1:${PORT}/"
# WP141: asset URLs are root-relative, so they are right behind Caddy whatever uvicorn makes of
# the proxy headers (an absolute http:// URL on an https page would be blocked).
check "asset URLs are root-relative" \
    bash -c "curl -fsS -H 'X-Forwarded-Proto: https' -H 'Host: chummer.example.org' \
        http://127.0.0.1:${PORT}/ | grep -q 'href=\"/static/app.css\"'"
check "responses carry the Content-Security-Policy" \
    bash -c "curl -fsSI http://127.0.0.1:${PORT}/ | grep -qi '^content-security-policy: default-src'"
check "the app runs as the unprivileged user (uid 10001)" \
    bash -c "[[ \$(podman exec ${CONTAINER} id -u) == 10001 ]]"
check "the game data loaded (a priority page mentions Metatype)" \
    bash -c "curl -fsS http://127.0.0.1:${PORT}/ | grep -qi metatype"


H="http://127.0.0.1:${HOSTED_PORT}"
check "hosted: an anonymous start page redirects to /login" \
    bash -c "[[ \$(curl -sS -o /dev/null -w '%{http_code} %{redirect_url}' ${H}/) == '303 ${H}/login' ]]"
check "hosted: the login page renders (200)" \
    curl -fsS -o /dev/null "${H}/login"
INVITE="$(podman exec "${HOSTED_CONTAINER}" python -m chummer5.admin invite 2>/dev/null || true)"
check "hosted: the admin CLI mints an invite" \
    test -n "${INVITE}"
# WP141: a POST must carry the site's Origin, and the login cookie is Secure, which curl neither
# keeps nor sends back over plain http -- so the token is read off the Set-Cookie header instead.
check "hosted: a POST from another origin is refused (403)" \
    bash -c "[[ \$(curl -sS -o /dev/null -w '%{http_code}' -H 'Origin: https://evil.example' \
        -d 'username=x&password=y' ${H}/login) == 403 ]]"
check "hosted: registering with it logs in and the shell renders" \
    bash -c "TOKEN=\$(curl -fsS -D - -o /dev/null -H 'Origin: ${H}' \
        -d 'username=imagetest&password=imagetest-password&confirm=imagetest-password&invite=${INVITE}' \
        ${H}/register | sed -n 's/^set-cookie: chummer5_auth=\\([^;]*\\).*/\\1/Ip') \
        && [[ -n \$TOKEN ]] && curl -fsS -H \"Cookie: chummer5_auth=\$TOKEN\" ${H}/ | grep -qi metatype"
check "hosted: the admin CLI lists the new user" \
    bash -c "podman exec ${HOSTED_CONTAINER} python -m chummer5.admin users | grep -q '^imagetest '"

# WP142: the database is on the volume, a backup can be taken while the app runs, and that backup
# restores into a working instance (the restore procedure from spec/deployment.md, "Backups").
check "hosted: the database is on the volume" \
    bash -c "podman exec ${HOSTED_CONTAINER} test -s /data/chummer5.db"
BACKUP="$(podman exec "${HOSTED_CONTAINER}" python -m chummer5.admin backup --keep 3 2>/dev/null || true)"
check "hosted: a backup is taken while the app runs" \
    bash -c "[[ -n '${BACKUP}' ]] && podman exec ${HOSTED_CONTAINER} test -s '${BACKUP}'"
check "hosted: the backup restores into a fresh volume" \
    bash -c "podman exec ${HOSTED_CONTAINER} cat '${BACKUP}' \
        | podman run --rm -i -v ${RESTORED_VOLUME}:/data ${IMAGE}:${TAG} \
            sh -c 'cat > /data/incoming.db && python -m chummer5.admin restore --yes /data/incoming.db'"
podman run -d --name "${RESTORED_CONTAINER}" -p "127.0.0.1:$((PORT + 2)):8000" \
    -v "${RESTORED_VOLUME}:/data" "${HOSTED_ENV[@]}" "${IMAGE}:${TAG}" >/dev/null 2>&1 || true
for _ in $(seq 1 30); do
    curl -fsS -o /dev/null "http://127.0.0.1:$((PORT + 2))/login" && break
    sleep 1
done
check "restored: it serves /login" \
    curl -fsS -o /dev/null "http://127.0.0.1:$((PORT + 2))/login"
check "restored: the user registered before the backup is there" \
    bash -c "podman exec ${RESTORED_CONTAINER} python -m chummer5.admin users | grep -q '^imagetest '"

if [[ ${FAILED} -ne 0 ]]; then
    echo "==> Some checks failed. Container logs:" >&2
    podman logs --tail 40 "${CONTAINER}" >&2 || true
    podman logs --tail 40 "${HOSTED_CONTAINER}" >&2 || true
    podman logs --tail 40 "${RESTORED_CONTAINER}" >&2 || true
    exit 1
fi
echo "==> All checks passed for ${IMAGE}:${TAG}."
