"""In-memory chargen session store, keyed by a browser cookie.

WP14 is the first WP with any UI-visible mutable state — the Implementation Plan's own wording
for it, verbatim, is "server-side in-memory character-in-progress state keyed by a session
cookie". A process-lifetime `dict` keyed by an opaque cookie value is sufficient for this
project's actual deployment shape (Project Overview: "local, single-user, no auth"); a database
or client-side-state design would be solving a multi-user/persistence problem this app doesn't
have.

Each `create_app()` call gets its own `SessionStore` (stored on `app.state.sessions`, not a
module-level singleton) so that tests using separate `TestClient(create_app())` instances never
leak session state into each other.
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass

from chummer5.engine.character import Character
from chummer5.engine.skills import SkillAllocation

SESSION_COOKIE_NAME = "chummer5_session"

# The 4 priority letters MVP actually offers a choice over (see chummer5.engine.character and
# the Project Overview's "Talent forced to E" note — Talent consumes E unconditionally for every
# mundane MVP character, which is why these four categories only ever draw from A-D).
PRIORITY_LETTERS = ("A", "B", "C", "D")

# An arbitrary-but-valid starting assignment (a permutation of PRIORITY_LETTERS) so the first
# page a player sees already has a legal selection to adjust, rather than an empty/invalid one.
DEFAULT_HERITAGE_LETTER = "A"
DEFAULT_ATTRIBUTES_LETTER = "B"
DEFAULT_SKILLS_LETTER = "C"
DEFAULT_RESOURCES_LETTER = "D"


@dataclass
class ChargenSession:
    """One browser session's in-progress chargen state.

    Mutable (unlike the frozen engine dataclasses it wraps) because it's the thing that changes
    across multiple requests as a player works through the chargen screens. `character` is only
    set once a metatype + a full, valid set of priority letters has been confirmed (WP14); WP15
    replaces it with a new `Character` carrying real attribute-point spend on every valid
    attribute-allocation submission. `skill_allocation` is WP15's equivalent for skill/skill-group
    point spend -- `None` until the first valid skill-allocation submission, mirroring
    `character`'s own "unset until confirmed" shape. Both `character` and `skill_allocation` are
    reset (attribute points to empty, skill_allocation to `None`) whenever priorities/metatype are
    re-confirmed (`chummer5.web.app.submit_priorities`), since a changed Attributes/Skills letter
    or metatype invalidates the old point spend's budget.
    """

    heritage_letter: str = DEFAULT_HERITAGE_LETTER
    attributes_letter: str = DEFAULT_ATTRIBUTES_LETTER
    skills_letter: str = DEFAULT_SKILLS_LETTER
    resources_letter: str = DEFAULT_RESOURCES_LETTER
    metatype_id: str | None = None
    character: Character | None = None
    skill_allocation: SkillAllocation | None = None


class SessionStore:
    """Process-lifetime `session id -> ChargenSession` map."""

    def __init__(self) -> None:
        self._sessions: dict[str, ChargenSession] = {}

    def create(self) -> tuple[str, ChargenSession]:
        session_id = secrets.token_urlsafe(24)
        session = ChargenSession()
        self._sessions[session_id] = session
        return session_id, session

    def get(self, session_id: str) -> ChargenSession | None:
        return self._sessions.get(session_id)
