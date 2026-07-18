"""FastAPI application factory: the web UI's entry point.

WP14 — first real chargen screen (see `spec/Implementation Plan.md`, Phase F). Lets a player
assign priority letters A-D to Heritage/Attributes/Skills/Resources (Talent is forced to E and
never offered as a choice — see `spec/Project Overview.md`'s MVP scope) and pick a metatype for
the chosen Heritage letter, backed by WP6's `chummer5.engine.character` functions directly so the
UI's result is exactly what those functions would produce for the same inputs. State lives in a
server-side, in-memory `ChargenSession` (`chummer5.web.session`) keyed by an opaque cookie — this
is a local, single-user app, so nothing fancier (database, client-side state) is warranted.

Run locally: `uv run uvicorn chummer5.web.app:app --reload` (or `python -m uvicorn ...` — same
`uv run python -m X` workaround as `pytest`/`ruff`/`mypy`, see Project Overview.md's Development
environment note), then open http://127.0.0.1:8000/.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from chummer5.data.metatypes import load_metatypes
from chummer5.data.priorities import load_priorities
from chummer5.engine.character import create_character, metatype_choices
from chummer5.web.session import (
    PRIORITY_LETTERS,
    SESSION_COOKIE_NAME,
    ChargenSession,
    SessionStore,
)

WEB_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = WEB_DIR / "templates"
STATIC_DIR = WEB_DIR / "static"

# Static rules data: parsed once per process, not per request (Project Overview's "parsed once at
# startup" rule for `chummer5.data` loaders).
METATYPES = load_metatypes()
PRIORITIES = load_priorities()


def _priority_form_context(
    *,
    heritage_letter: str,
    attributes_letter: str,
    skills_letter: str,
    resources_letter: str,
    metatype_id: str | None,
    character: object,
    error: str | None,
) -> dict[str, Any]:
    heritage = PRIORITIES.heritage.get(heritage_letter)
    metatype_options = metatype_choices(heritage, METATYPES) if heritage is not None else ()
    return {
        "letters": PRIORITY_LETTERS,
        "heritage_priorities": PRIORITIES.heritage,
        "attributes_priorities": PRIORITIES.attributes,
        "skills_priorities": PRIORITIES.skills,
        "resources_priorities": PRIORITIES.resources,
        "metatype_options": metatype_options,
        "selected": {
            "heritage_letter": heritage_letter,
            "attributes_letter": attributes_letter,
            "skills_letter": skills_letter,
            "resources_letter": resources_letter,
            "metatype_id": metatype_id,
        },
        "character": character,
        "error": error,
    }


def create_app() -> FastAPI:
    """Build the FastAPI app: priority-letter + metatype selection, WP14's real chargen screen."""
    app = FastAPI(title="Chummer5")
    app.state.sessions = SessionStore()
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
    templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

    def resolve_session(request: Request) -> tuple[ChargenSession, str | None]:
        """Look up this request's session by cookie, creating one if absent.

        Returns the session plus a new cookie value to set on the *actual* response the caller
        ends up returning -- not `None`, `Depends`-injected `Response`. FastAPI only merges an
        injected `Response`'s headers into the final response when the endpoint returns a plain
        value; every route here returns a `TemplateResponse` (already a `Response`) directly, and
        FastAPI substitutes that wholesale rather than merging headers onto it (confirmed by
        reading `fastapi/routing.py`'s request handler) -- so the cookie has to be set on the
        object that's actually returned.
        """
        store: SessionStore = request.app.state.sessions
        session_id = request.cookies.get(SESSION_COOKIE_NAME)
        session = store.get(session_id) if session_id else None
        if session is not None:
            return session, None
        new_session_id, session = store.create()
        return session, new_session_id

    @app.get("/", response_class=HTMLResponse)
    def index(request: Request) -> HTMLResponse:
        session, new_cookie = resolve_session(request)
        context = _priority_form_context(
            heritage_letter=session.heritage_letter,
            attributes_letter=session.attributes_letter,
            skills_letter=session.skills_letter,
            resources_letter=session.resources_letter,
            metatype_id=session.metatype_id,
            character=session.character,
            error=None,
        )
        response = templates.TemplateResponse(request, "chargen.html", context)
        if new_cookie is not None:
            response.set_cookie(SESSION_COOKIE_NAME, new_cookie, httponly=True, samesite="lax")
        return response

    @app.get("/ui/metatypes", response_class=HTMLResponse)
    def metatype_options_fragment(request: Request, heritage_letter: str) -> HTMLResponse:
        heritage = PRIORITIES.heritage.get(heritage_letter)
        metatype_options = metatype_choices(heritage, METATYPES) if heritage is not None else ()
        context = {
            "metatype_options": metatype_options,
            "selected": {"metatype_id": None},
        }
        return templates.TemplateResponse(request, "_metatype_select.html", context)

    @app.post("/ui/priorities", response_class=HTMLResponse)
    def submit_priorities(
        request: Request,
        heritage_letter: str = Form(...),
        attributes_letter: str = Form(...),
        skills_letter: str = Form(...),
        resources_letter: str = Form(...),
        metatype_id: str = Form(...),
    ) -> HTMLResponse:
        session, new_cookie = resolve_session(request)
        submitted_letters = (heritage_letter, attributes_letter, skills_letter, resources_letter)
        error: str | None = None
        character = session.character

        if sorted(submitted_letters) != sorted(PRIORITY_LETTERS):
            error = (
                "Heritage, Attributes, Skills, and Resources must each use a different "
                f"priority letter ({', '.join(PRIORITY_LETTERS)}), one each."
            )
        else:
            heritage = PRIORITIES.heritage[heritage_letter]
            choice = next(
                (c for c in metatype_choices(heritage, METATYPES) if c.metatype.id == metatype_id),
                None,
            )
            if choice is None:
                error = "Select a metatype offered for the chosen Heritage priority."
            else:
                character = create_character(
                    choice, heritage_letter, attributes_letter, PRIORITIES, {}
                )
                session.heritage_letter = heritage_letter
                session.attributes_letter = attributes_letter
                session.skills_letter = skills_letter
                session.resources_letter = resources_letter
                session.metatype_id = metatype_id
                session.character = character

        context = _priority_form_context(
            heritage_letter=heritage_letter,
            attributes_letter=attributes_letter,
            skills_letter=skills_letter,
            resources_letter=resources_letter,
            metatype_id=metatype_id,
            character=character,
            error=error,
        )
        response = templates.TemplateResponse(request, "_priority_form.html", context)
        if new_cookie is not None:
            response.set_cookie(SESSION_COOKIE_NAME, new_cookie, httponly=True, samesite="lax")
        return response

    return app


app = create_app()
