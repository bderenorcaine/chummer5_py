# Chummer5 Python

A from-scratch Python reimplementation of [Chummer5a](https://github.com/chummer5a/chummer5a) — the
Shadowrun 5E character creation tool — as a cross-platform local web app.

- [spec/Project Overview.md](spec/Project%20Overview.md) — project goals, MVP scope, and architecture decisions.
- [spec/Implementation Plan.md](spec/Implementation%20Plan.md) — work package roadmap and current status.
- [legacy/](legacy) — the original C#/WinForms codebase, kept as a rules reference, data source, and
  regression-testing oracle. Not under active development.

## Development

Runs inside the Podman-backed devcontainer (`.devcontainer/`); see Project Overview's "Development
environment" section for why. Once inside it:

```sh
uv sync --group dev             # install dependencies
uv run python -m pytest         # run the test suite
uv run uvicorn chummer5.web.app:app --reload   # run the web app at http://127.0.0.1:8000/
```

## License

GPLv3 — see [LICENSE](LICENSE). Inherited from the legacy codebase, whose data files, rules logic, and
test fixtures this project reuses.
