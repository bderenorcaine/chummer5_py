#!/usr/bin/env bash
# Run from the HOST (not from inside the devcontainer) to build and start the Chummer5 web app
# in its Podman-backed devcontainer, with the port published to the host so it's reachable from
# a normal host browser. See spec/Project Overview.md's "Development environment" section for why
# this project develops inside a container rather than on the host.
#
# Usage:
#   ./start-app.sh
#   CHUMMER5_PORT=9000 ./start-app.sh   # use a different host port
#
# Then open http://127.0.0.1:8000/ (or your chosen port). Ctrl+C stops the server; the container
# is removed automatically on exit (--rm).

set -euo pipefail

if ! command -v podman >/dev/null 2>&1; then
    echo "error: podman not found on PATH. This project's devcontainer is Podman-backed." >&2
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
IMAGE_NAME="chummer5-python-dev"
CONTAINER_NAME="chummer5-dev"
HOST_PORT="${CHUMMER5_PORT:-8000}"

# Clean up a container left behind by a previous non-graceful exit (e.g. a killed terminal) —
# --rm only removes it on a normal exit.
podman rm -f "${CONTAINER_NAME}" >/dev/null 2>&1 || true

echo "==> Building container image (${IMAGE_NAME})..."
podman build -t "${IMAGE_NAME}" -f "${SCRIPT_DIR}/.devcontainer/Containerfile" "${SCRIPT_DIR}"

echo "==> Starting Chummer5 -- once 'Uvicorn running' appears below, open:"
echo "        http://127.0.0.1:${HOST_PORT}/"
echo "    Ctrl+C stops the server."
echo

# Mounted at /workspace (matching devcontainer.json's workspaceFolder) to line up with a `.venv`
# possibly already synced under that path. Even so, invoke uvicorn as `python -m uvicorn`, not the
# bare `uvicorn` console-script -- that script's shebang is baked to the mount path in effect at
# `uv sync` time, so a `.venv` synced under any other path (e.g. by a previous run, or this
# project's own dev sessions) leaves a stale, unusable shebang. `python -m` runs the venv's
# `python` symlink directly instead, sidestepping the shebang entirely. See Project Overview's
# "Stale .venv console scripts" note.
podman run --rm -it \
    --name "${CONTAINER_NAME}" \
    -p "${HOST_PORT}:8000" \
    -v "${SCRIPT_DIR}:/workspace:Z" \
    -w /workspace \
    "${IMAGE_NAME}" \
    bash -c "uv sync --group dev && exec uv run python -m uvicorn chummer5.web.app:app --host 0.0.0.0 --port 8000"
