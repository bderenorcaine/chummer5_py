"""FastAPI application factory: the web UI's entry point.

WP13 — first slice of Phase F (see `spec/Implementation Plan.md`). Deliberately does nothing
chargen-related yet: one trivial page, rendered through the same Jinja2 + HTMX stack every later
UI work package builds on, plus one HTMX-driven endpoint that proves the round trip (browser ->
FastAPI -> Jinja2-rendered HTML fragment -> DOM swap) actually works end to end. WP14+ replace the
trivial page with real chargen screens and add server-side in-memory character-in-progress state
keyed by a session cookie — neither exists here on purpose.

Run locally: `uv run uvicorn chummer5.web.app:app --reload` (or `python -m uvicorn ...` — same
`uv run python -m X` workaround as `pytest`/`ruff`/`mypy`, see Project Overview.md's Development
environment note), then open http://127.0.0.1:8000/.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

WEB_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = WEB_DIR / "templates"
STATIC_DIR = WEB_DIR / "static"


def create_app() -> FastAPI:
    """Build the FastAPI app: one trivial page plus an HTMX round-trip demo endpoint."""
    app = FastAPI(title="Chummer5")
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
    templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

    @app.get("/", response_class=HTMLResponse)
    def index(request: Request) -> HTMLResponse:
        return templates.TemplateResponse(request, "index.html", {"count": 0})

    @app.post("/ui/counter", response_class=HTMLResponse)
    def increment_counter(request: Request, count: int = Form(0)) -> HTMLResponse:
        return templates.TemplateResponse(request, "_counter.html", {"count": count + 1})

    return app


app = create_app()
