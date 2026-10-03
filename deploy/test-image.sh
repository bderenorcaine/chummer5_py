#!/usr/bin/env bash
# Build the production image from HEAD and check it works, on THIS machine. Run from the HOST (needs
# podman), not from inside the devcontainer: the devcontainer is deliberately unprivileged, and
# podman can't build or run images inside it (decisions-log, 2026-10-03).
#
# Usage:
#   deploy/test-image.sh            # build HEAD, start it on a free loopback port, run the checks
#   KEEP=1 deploy/test-image.sh     # leave the container running afterwards, to poke at it
#
# Phase Y WPs extend the checks below (WP137: /login in hosted mode; WP142: data volume, backup
# and restore). Each check prints PASS or FAIL; the script exits non-zero if any failed.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
# shellcheck source=deploy/lib.sh
source "${SCRIPT_DIR}/lib.sh"

CONTAINER="chummer5-imagetest"
PORT="${CHUMMER5_TEST_PORT:-18005}"
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

cleanup() {
    if [[ -z "${KEEP:-}" ]]; then
        podman rm -f "${CONTAINER}" >/dev/null 2>&1 || true
    else
        echo "==> Left running: http://127.0.0.1:${PORT}/  (podman rm -f ${CONTAINER} when done)"
    fi
}

TAG="$(image_tag)"
echo "==> Building ${IMAGE}:${TAG}"
build_image "${TAG}"

podman rm -f "${CONTAINER}" >/dev/null 2>&1 || true
trap cleanup EXIT
echo "==> Starting it on 127.0.0.1:${PORT}"
podman run -d --name "${CONTAINER}" -p "127.0.0.1:${PORT}:8000" "${IMAGE}:${TAG}" >/dev/null

for _ in $(seq 1 30); do
    curl -fsS -o /dev/null "http://127.0.0.1:${PORT}/static/app.css" && break
    sleep 1
done

echo "==> Checks"
check "static files are served" \
    curl -fsS -o /dev/null "http://127.0.0.1:${PORT}/static/app.css"
check "the start page renders (200)" \
    curl -fsS -o /dev/null "http://127.0.0.1:${PORT}/"
check "asset URLs follow X-Forwarded-Proto (proxy headers trusted)" \
    bash -c "curl -fsS -H 'X-Forwarded-Proto: https' -H 'Host: chummer.example.org' \
        http://127.0.0.1:${PORT}/ | grep -q 'https://chummer.example.org/static/app.css'"
check "the app runs as the unprivileged user (uid 10001)" \
    bash -c "[[ \$(podman exec ${CONTAINER} id -u) == 10001 ]]"
check "the game data loaded (a priority page mentions Metatype)" \
    bash -c "curl -fsS http://127.0.0.1:${PORT}/ | grep -qi metatype"

if [[ ${FAILED} -ne 0 ]]; then
    echo "==> Some checks failed. Container log:" >&2
    podman logs --tail 40 "${CONTAINER}" >&2 || true
    exit 1
fi
echo "==> All checks passed for ${IMAGE}:${TAG}."
