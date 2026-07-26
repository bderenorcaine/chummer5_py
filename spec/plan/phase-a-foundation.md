[← back to Implementation Plan index](../Implementation%20Plan.md)

### Phase A — Foundation

- [x] **WP1 — Project scaffolding.**
  Goal: a buildable, empty Python project, developed inside a container rather than on the host.
  Deliverables: `.devcontainer/Containerfile` + `devcontainer.json` (Podman-backed; reopening the
  workspace in it relocates the VS Code extension host, including agent sessions, into the container —
  see `Project Overview.md`'s Development environment note for why, given the host is an immutable OS);
  root `.dockerignore` (excludes `legacy/` and `.git/` from build context); `pyproject.toml` (uv-managed),
  `src/chummer5/{data,engine,io,web}/` packages (empty `__init__.py`s), pytest + ruff + mypy configured,
  one smoke test.
  Depends on: nothing.
  Acceptance: `uv run pytest`, `uv run ruff check`, and `uv run mypy src` all pass **inside the
  container**. Verified via a one-off `podman run` mounting the workspace (no host Python/package
  mutation involved) — future work packages should instead develop via "Reopen in Container".

