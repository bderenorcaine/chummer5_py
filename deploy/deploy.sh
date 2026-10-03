#!/usr/bin/env bash
# Build the production image from the current commit and deploy it to the server over SSH.
# Run from the HOST (needs podman, git, ssh), not from inside the devcontainer.
# See spec/deployment.md for what each step does and why.
#
# Usage:
#   deploy/deploy.sh user@server            # build HEAD, ship it, restart, health-check
#   CHUMMER5_TAG=0.1.0 deploy/deploy.sh user@server
#                                           # skip the build; restart on an image tag the server
#                                           # already has (this is how you roll back)
#
# Settings (environment variables, all optional):
#   REMOTE_CONTAINER_CMD  container CLI on the server: podman (default) or docker
#   CHUMMER5_HOST_PORT    loopback port on the server that Caddy proxies to (default 8005)
#   BUILD_PLATFORM        e.g. linux/arm64 if the server's CPU differs from this machine's

set -euo pipefail

if [[ $# -ne 1 ]]; then
    sed -n '2,15p' "$0" >&2
    exit 2
fi

SERVER="$1"
RCMD="${REMOTE_CONTAINER_CMD:-podman}"
HOST_PORT="${CHUMMER5_HOST_PORT:-8005}"
CONTAINER="chummer5"
STATE_DIR='$HOME/chummer5'   # on the server; single-quoted so the server's shell expands it

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
# shellcheck source=deploy/lib.sh
source "${SCRIPT_DIR}/lib.sh"

remote() { ssh "${SERVER}" "$@"; }

# ---------------------------------------------------------------- 0. can the server run it?
# Checked first, so a server that can't run the container fails in seconds, not after the build
# and the copy. Runs over a non-interactive ssh, which doesn't read the login profile: a tool that
# works in an interactive session on the server can still be missing from this PATH. Each check
# below is one a first deploy actually tripped over (spec/deployment.md, "First deploy", step 2).
# POSIX sh on purpose: it runs in whatever login shell the server's user has.
PREFLIGHT='
missing=""
for tool in RCMD curl gunzip; do
    command -v "$tool" >/dev/null 2>&1 || missing="$missing $tool"
done
if [ -n "$missing" ]; then
    echo "not installed, or not on the PATH of a non-interactive ssh:$missing"
    exit 0
fi
if ! problem="$(RCMD info 2>&1 >/dev/null)"; then
    echo "\"RCMD info\" fails: $problem"
    exit 0
fi
if [ RCMD = podman ] && [ "$(podman info --format "{{.Host.Security.Rootless}}" 2>/dev/null)" = true ]; then
    user="$(id -un)"
    grep -q "^$user:" /etc/subuid 2>/dev/null && grep -q "^$user:" /etc/subgid 2>/dev/null \
        || echo "rootless podman: $user has no range in /etc/subuid and /etc/subgid"
    command -v slirp4netns >/dev/null 2>&1 || command -v pasta >/dev/null 2>&1 \
        || echo "rootless podman: no network helper (slirp4netns, or pasta from passt)"
    # Without lingering, the container dies with this ssh session: the health check passes, and
    # the site is a 502 from the moment the deploy ends.
    if command -v loginctl >/dev/null 2>&1 \
        && [ "$(loginctl show-user "$user" --property=Linger --value 2>/dev/null)" != yes ]; then
        echo "rootless podman: lingering is off for $user, so the container would stop when this ssh session ends (sudo loginctl enable-linger $user)"
    fi
fi
'
PROBLEMS="$(remote "${PREFLIGHT//RCMD/${RCMD}}")"
if [[ -n "${PROBLEMS}" ]]; then
    echo "error: ${SERVER} can't run the container yet:" >&2
    while IFS= read -r line; do echo "  - ${line}" >&2; done <<< "${PROBLEMS}"
    echo "Server setup, including the packages rootless podman needs: spec/deployment.md," >&2
    echo "\"First deploy\". If the server has Docker instead: REMOTE_CONTAINER_CMD=docker $0 ${SERVER}" >&2
    exit 1
fi

# ---------------------------------------------------------------- 1. which version is this?
if [[ -n "${CHUMMER5_TAG:-}" ]]; then
    TAG="${CHUMMER5_TAG}"
    echo "==> Redeploying existing image ${IMAGE}:${TAG} (no build)"
else
    # A release is a commit tagged v<version>; anything else deploys as a dev build whose tag
    # still says exactly which commit it is (deploy/lib.sh).
    TAG="$(image_tag)"
    echo "==> Deploying ${IMAGE}:${TAG} to ${SERVER}"

    # ------------------------------------------------------------ 2. build from that commit
    build_image "${TAG}"

    # ------------------------------------------------------------ 3. ship the image
    echo "==> Copying image to ${SERVER} (this is the slow part)"
    podman save "${IMAGE}:${TAG}" | gzip | remote "gunzip | ${RCMD} load"
fi

# ---------------------------------------------------------------- 4. swap the container
PREVIOUS="$(remote "cat ${STATE_DIR}/current-tag 2>/dev/null || true")"
echo "==> Restarting (previous: ${PREVIOUS:-none})"
# Publishing on 127.0.0.1 only: the app is reachable through Caddy and nothing else.
remote "${RCMD} rm -f ${CONTAINER} >/dev/null 2>&1 || true
        ${RCMD} run -d --name ${CONTAINER} --restart unless-stopped \
            -p 127.0.0.1:${HOST_PORT}:8000 ${IMAGE}:${TAG} >/dev/null"

# ---------------------------------------------------------------- 5. health check
echo "==> Waiting for the app to answer on 127.0.0.1:${HOST_PORT}"
if remote "for i in \$(seq 1 30); do
               curl -fsS -o /dev/null http://127.0.0.1:${HOST_PORT}/static/app.css && exit 0
               sleep 1
           done; exit 1"; then
    remote "mkdir -p ${STATE_DIR} && echo '${TAG}' > ${STATE_DIR}/current-tag"
    echo "==> OK: ${IMAGE}:${TAG} is live."
else
    echo "error: the new container did not come up. Its log:" >&2
    remote "${RCMD} logs --tail 50 ${CONTAINER}" >&2 || true
    if [[ -n "${PREVIOUS}" && "${PREVIOUS}" != "${TAG}" ]]; then
        echo "==> Rolling back to ${PREVIOUS}" >&2
        CHUMMER5_TAG="${PREVIOUS}" "$0" "${SERVER}"
    fi
    exit 1
fi
