"""FastAPI application factory: the web UI's entry point.

WP14 — first real chargen screen (see `spec/Implementation Plan.md`, Phase F). Lets a player
assign priority letters A-D to Heritage/Attributes/Skills/Resources (Talent is forced to E and
never offered as a choice — see `spec/Project Overview.md`'s MVP scope) and pick a metatype for
the chosen Heritage letter, backed by WP6's `chummer5.engine.character` functions directly so the
UI's result is exactly what those functions would produce for the same inputs. State lives in a
server-side, in-memory `ChargenSession` (`chummer5.web.session`) keyed by an opaque cookie — this
is a local, single-user app, so nothing fancier (database, client-side state) is warranted.

**WP62**: this module used to hold every chargen route, catalog load, and context/relink helper
directly (4,499 lines by the time Phase R's WP58 audited it) -- see `spec/plan/phase-r-
architecture-cleanup.md` for the audit and target shape. It now only builds the `FastAPI` app:
catalogs/constants live in `chummer5.web.catalogs`, generic form-parsing helpers in
`chummer5.web.forms`, and every chargen step's routes/context-builders/relink-helpers in their own
`chummer5.web.routes.<step>` module (mounted below via `app.include_router(...)`). The handful of
module-level catalog constants the existing test suite imports directly from this module
(`LIFESTYLES`, `CYBERWARE`, `BIOWARE`, `MAX_CONTACT_ROWS`, `MVP_QUALITIES`,
`MUNDANE_SKILL_GROUPS`, `MUNDANE_SKILLS`) are re-exported below rather than editing every test's
import -- see the audit's own note on why that's the cheaper, equally-correct choice. No route's
URL path changed as part of this split.

Run locally: `uv run uvicorn chummer5.web.app:app --reload` (or `python -m uvicorn ...` — same
`uv run python -m X` workaround as `pytest`/`ruff`/`mypy`, see Project Overview.md's Development
environment note), then open http://127.0.0.1:8000/.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response
from fastapi.staticfiles import StaticFiles

from chummer5.web.catalogs import (
    BIOWARE,
    CYBERWARE,
    LIFESTYLES,
    MAX_CONTACT_ROWS,
    MUNDANE_SKILL_GROUPS,
    MUNDANE_SKILLS,
    MVP_QUALITIES,
    STATIC_DIR,
)
from chummer5.web.routes import (
    attributes,
    bio,
    character,
    contacts,
    cyberware,
    foci,
    knowledge,
    lifestyle,
    pages,
    powers,
    priorities,
    qualities,
    resources,
    skills,
    spells,
    spirits,
    talent,
    vehicles,
)
from chummer5.web.session import SessionStore

# The htmx event name `_step_nav.html` listens for (`hx-trigger="chargen-changed from:body"`).
CHARGEN_CHANGED_EVENT = "chargen-changed"
# Display-preference routes (`chummer5.web.prefs`), which that event deliberately skips.
PREFS_PATH_PREFIX = "/ui/prefs/"

__all__ = [
    "create_app",
    "app",
    "LIFESTYLES",
    "CYBERWARE",
    "BIOWARE",
    "MAX_CONTACT_ROWS",
    "MVP_QUALITIES",
    "MUNDANE_SKILL_GROUPS",
    "MUNDANE_SKILLS",
]


def create_app() -> FastAPI:
    """Build the FastAPI app: priority-letter + metatype selection, WP14's real chargen screen."""
    app = FastAPI(title="Chummer5")
    app.state.sessions = SessionStore()
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    # WP97: the application shell -- `GET /`, the nav's page/nav routes, and the Export page.
    app.include_router(pages.router)

    # WP97: every successful POST changes committed chargen state, which can move any step's
    # stale-selection marker in the step nav (a priorities change most of all -- WP19). Rather
    # than every step route re-rendering the nav out of band, each such response carries one
    # htmx event the nav listens for and re-fetches itself on (`_step_nav.html`).
    @app.middleware("http")
    async def _signal_chargen_changed(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        response = await call_next(request)
        # WP100: `/ui/prefs/` (theme, and WP101's language) changes presentation, not the
        # character, so it moves no nav marker or budget and must not make them all re-fetch.
        if (
            request.method == "POST"
            and response.status_code < 400
            and not request.url.path.startswith(PREFS_PATH_PREFIX)
        ):
            response.headers["HX-Trigger"] = CHARGEN_CHANGED_EVENT
        return response

    # WP62: one router per chargen step (see `chummer5.web.routes`'s own docstring); registration
    # order here is cosmetic (routes are matched by path/method, not declaration order) but mirrors
    # SR5's own chargen step order (priorities -> attributes -> talent -> skills -> ... ->
    # character sheet/save/load) for readability.
    app.include_router(priorities.router)
    app.include_router(attributes.router)
    app.include_router(talent.router)
    app.include_router(skills.router)
    app.include_router(knowledge.router)
    app.include_router(spells.router)
    app.include_router(powers.router)
    app.include_router(spirits.router)
    app.include_router(qualities.router)
    app.include_router(contacts.router)
    app.include_router(bio.router)
    app.include_router(resources.router)
    app.include_router(lifestyle.router)
    app.include_router(cyberware.router)
    app.include_router(foci.router)
    app.include_router(vehicles.router)
    app.include_router(character.router)

    return app


app = create_app()
