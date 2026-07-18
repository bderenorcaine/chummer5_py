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
    across multiple requests as a player works through the chargen screens.

    **WP18's fold.** Through WP17, this class carried `character` plus four more sibling fields
    (`skill_allocation`, `quality_selection`, `contacts`, `gear_names`) that were independently
    threaded through here, the save format, and legacy import, and only reunited with `character`
    ad hoc (`chummer5.io.save_format`'s now-retired `BuiltCharacter`). WP18 moved all four onto
    `chummer5.engine.character.Character` itself (see its docstring), so this class now holds only
    `character` -- every one of those four is read as `character.skill_allocation`,
    `character.quality_selection`, `character.contact_selection`, `character.resources_selection`
    from here on, each `None` until that stage of chargen is committed (the old `session.contacts`/
    `session.gear_names` defaulted to `()` instead; the equivalent reads are now
    `character.contact_selection.contacts if character.contact_selection else ()` and
    `[item.name for item in character.resources_selection.gear] if character.resources_selection
    else ()`).

    `heritage_letter`/`attributes_letter`/`skills_letter`/`resources_letter`/`metatype_id` remain
    genuine sibling state, not folded into `Character`: they're the *pre-confirmation* priority-form
    selection a player is still adjusting, which exists before any `Character` does (the very first
    page load has no character yet, but still needs a legal starting letter assignment -- see the
    `DEFAULT_*_LETTER` constants below). Once a metatype+priorities submission is confirmed,
    `heritage_letter`/`attributes_letter` are duplicated onto the resulting `Character` too (it
    needs them for its own attribute-range/budget lookups), but `skills_letter`/`resources_letter`/
    `metatype_id` have no `Character`-side equivalent at all, so this session-level copy remains
    the only copy for all four regardless.

    `character` is only set once a metatype + a full, valid set of priority letters has been
    confirmed (WP14); WP15 replaces it with a new `Character` carrying real attribute-point spend
    on every valid attribute-allocation submission.

    **WP19**: reconfirming priorities/metatype (`chummer5.web.app.submit_priorities`) no longer
    resets anything. Through WP18, a changed Attributes/Skills/Resources letter or metatype
    invalidated the old point spend's budget, so `attribute_points`, `skill_allocation`, and
    `resources_selection` (gear) were all discarded outright on every reconfirmation, valid or not.
    WP19 replaces that with re-validate-in-place: every prior selection is carried forward via
    `dataclasses.replace` regardless of whether it still fits the new letters/metatype, and
    `chummer5.web.app`'s `_attribute_allocation_context`/`_skill_allocation_context`/
    `_resources_context` each re-derive (and surface, as a distinct "no longer fits" message) fresh
    on every render whether it still does -- an over-budget carry-forward is allowed to sit
    visibly-invalid rather than blocking chargen, until the player edits that section back within
    budget. `quality_selection` and `contact_selection` were never reset on reconfirmation to begin
    with (unchanged from WP16): none of the 3 MVP-offered qualities are metatype-gated or
    priority-letter-budgeted, and a contact's Connection/Loyalty aren't validated against
    metatype/priorities at all -- only the *free* contact-point budget (`CHA * 3`) depends on the
    character, and that's recomputed fresh from the current `Character` on every render.
    """

    heritage_letter: str = DEFAULT_HERITAGE_LETTER
    attributes_letter: str = DEFAULT_ATTRIBUTES_LETTER
    skills_letter: str = DEFAULT_SKILLS_LETTER
    resources_letter: str = DEFAULT_RESOURCES_LETTER
    metatype_id: str | None = None
    character: Character | None = None


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
