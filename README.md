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

### Just want to run the app?

From the host (no editing, no "Reopen in Container"), `./start-app.sh` builds the devcontainer
image and starts the web app inside it with the port published to the host — open
`http://127.0.0.1:8000/` in your own browser once it prints "Uvicorn running". Ctrl+C stops it.

## License

GPLv3 — see [LICENSE](LICENSE). Inherited from the legacy codebase, whose data files, rules logic, and
test fixtures this project reuses. [NOTICE](NOTICE) has the copyright, what changed from upstream
Chummer5a, and third-party and trademark notices.

Shadowrun and Matrix are registered trademarks and/or trademarks of The Topps Company, Inc. This is an
unofficial fan project, not affiliated with or endorsed by Topps or Catalyst Game Labs.
