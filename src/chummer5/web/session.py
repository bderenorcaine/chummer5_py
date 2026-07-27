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

from fastapi import Request

from chummer5.engine.build_method import PRIORITY_BUILD_METHOD
from chummer5.engine.character import Character

SESSION_COOKIE_NAME = "chummer5_session"

# The 5 priority letters SR5's own priority table uses across all 5 categories (Heritage, Talent,
# Attributes, Skills, Resources). Through WP23, Talent was a hardcoded, unoffered assumption
# (always letter E, "Mundane" -- see the Project Overview's "Talent forced to E" note) and this
# tuple covered only the other four categories' A-D range. WP24 makes Talent a real 5th category a
# player assigns a letter to (still resolving to Mundane unconditionally -- see
# `chummer5.web.app._priority_form_context`'s docstring -- no new player-visible capability yet),
# so the letter range widens to the full A-E every category can legally draw from.
PRIORITY_LETTERS = ("A", "B", "C", "D", "E")

# An arbitrary-but-valid starting assignment (a permutation of PRIORITY_LETTERS) so the first
# page a player sees already has a legal selection to adjust, rather than an empty/invalid one.
# Talent defaults to E specifically (not just "whichever letter is left over") because E is the
# *only* letter whose Talent option list actually includes "Mundane" (confirmed against
# `priorities.xml`: A-D's Talent options are all real archetypes -- Magician, Adept, ... -- with no
# Mundane entry at all) -- so this default reproduces pre-WP24 behavior exactly for every
# character built without touching the new Talent selector.
DEFAULT_HERITAGE_LETTER = "A"
DEFAULT_ATTRIBUTES_LETTER = "B"
DEFAULT_SKILLS_LETTER = "C"
DEFAULT_RESOURCES_LETTER = "D"
DEFAULT_TALENT_LETTER = "E"


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

    `heritage_letter`/`attributes_letter`/`skills_letter`/`resources_letter`/`talent_letter`/
    `metatype_id` remain genuine sibling state, not folded into `Character`: they're the
    *pre-confirmation* priority-form selection a player is still adjusting, which exists before any
    `Character` does (the very first page load has no character yet, but still needs a legal
    starting letter assignment -- see the `DEFAULT_*_LETTER` constants below). Once a
    metatype+priorities submission is confirmed, `heritage_letter`/`attributes_letter` are
    duplicated onto the resulting `Character` too (it needs them for its own attribute-range/budget
    lookups), but `skills_letter`/`resources_letter`/`talent_letter`/`metatype_id` have no
    `Character`-side equivalent at all, so this session-level copy remains the only copy for all
    four regardless.

    **WP24**: `talent_letter` joins this group as pure plumbing -- a player can now assign Talent
    any of the 5 letters (see `PRIORITY_LETTERS`' widened range above), but nothing on `Character`
    reads it yet: `submit_priorities` still resolves Talent's *option* unconditionally to
    `priorities.mundane_talent()` regardless of which letter was chosen (see
    `chummer5.web.app._priority_form_context`'s docstring), so there is nothing for a `Character`
    field to hold yet. `Character` gains its own `talent_letter` only once WP25 needs to look up
    that letter's real option list against `priorities.talent` -- the same "add the field when
    something actually reads it" reasoning `skills_letter`/`resources_letter` already follow, not
    the `heritage_letter`/`attributes_letter` precedent (those two are needed immediately, by
    `create_character`'s own budget validation).

    `character` is only set once a metatype + a full, valid set of priority letters has been
    confirmed (WP14); WP15 replaces it with a new `Character` carrying real attribute-point spend
    on every valid attribute-allocation submission.

    **WP44**: `build_method` joins this group as pure session-side state too, for the same reason
    `skills_letter`/`resources_letter`/`talent_letter` do -- `Character`/`create_character` never
    validated the 5-letter assignment's *shape* (bijection vs. Sum-to-Ten's repeats-allowed/sum-to-
    10 rule) to begin with; that check only ever lived in `chummer5.web.app.submit_priorities`
    itself (see its own docstring). Which rule to apply on the *next* reconfirmation is therefore
    exactly the kind of pre-`Character` UI state this class already exists to hold -- `Character`
    gains no `build_method` field of its own, mirroring `talent_letter`'s WP24 precedent (see that
    paragraph below). Defaults to `PRIORITY_BUILD_METHOD` so every pre-WP44 caller (every existing
    test, every session created before a player ever touches the new selector) keeps today's
    bijection behavior unchanged.

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

    **WP61**: `open_section` is the same kind of genuine pre-`Character`-independent UI scratch
    state as the priority letters above -- which of the 14 `_chargen_body.html` sections currently
    renders its `<details>` open, in the one-section-at-a-time accordion. Defaults to
    `"priority-section"` (the first real step) for a fresh session; every section's own successful
    `POST` sets it to that section's own id before rendering, so the section a player just used
    stays open on the next full-page render. Not folded into `Character` -- it isn't part of the
    character being built, only of how the page is currently laid out.

    **Post-WP61 fix**: each section's `<details>` originally also carried a shared
    `name="chargen-section"` attribute, opting into the browser's *native* exclusive-accordion
    grouping (only one `<details>` sharing a `name` can be open at once) on top of the
    `open_section`-driven server state above. That combination raced with htmx's own `outerHTML`
    swap: htmx inserts the freshly-rendered (already-`open`) `<details>` *before* removing the old
    one, so for an instant two same-`name` elements are both open, and the browser's exclusivity
    logic reacts by closing the newly-inserted one -- collapsing the very section a player just
    interacted with (e.g. every click of an attribute's +/- spinner) rather than the stale one being
    replaced. Since exactly one section being open is already fully server-driven (only the section
    matching `open_section` ever renders with `open`), the native grouping bought nothing for the
    request/response path and only broke it; the `name` attribute was removed from every section's
    `<details>` rather than worked around. The one behavior change: manually clicking open a
    *different* section's `<summary>` (no server round trip involved) no longer auto-closes the
    previously open one client-side -- it does once either section's own form next submits and
    re-renders with the current `open_section`.
    """

    heritage_letter: str = DEFAULT_HERITAGE_LETTER
    attributes_letter: str = DEFAULT_ATTRIBUTES_LETTER
    skills_letter: str = DEFAULT_SKILLS_LETTER
    resources_letter: str = DEFAULT_RESOURCES_LETTER
    talent_letter: str = DEFAULT_TALENT_LETTER
    build_method: str = PRIORITY_BUILD_METHOD
    metatype_id: str | None = None
    character: Character | None = None
    open_section: str = "priority-section"


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


def resolve_session(request: Request) -> tuple[ChargenSession, str | None]:
    """Look up this request's session by cookie, creating one if absent.

    Returns the session plus a new cookie value to set on the *actual* response the caller ends
    up returning -- not `None`, `Depends`-injected `Response`. FastAPI only merges an injected
    `Response`'s headers into the final response when the endpoint returns a plain value; every
    route in `chummer5.web.routes` returns a `TemplateResponse` (already a `Response`) directly,
    and FastAPI substitutes that wholesale rather than merging headers onto it (confirmed by
    reading `fastapi/routing.py`'s request handler) -- so the cookie has to be set on the object
    that's actually returned.

    **WP62**: moved here from a `create_app()`-local closure -- it only ever read `request.app
    .state.sessions` and `SESSION_COOKIE_NAME`, both already module-level/request-derived, so the
    closure captured nothing `create_app()`-local and could move verbatim. Living in
    `chummer5.web.session` (rather than `chummer5.web.catalogs`) keeps every route module's import
    of it alongside `ChargenSession`/`SessionStore`/`SESSION_COOKIE_NAME`, which it's built
    directly out of.
    """
    store: SessionStore = request.app.state.sessions
    session_id = request.cookies.get(SESSION_COOKIE_NAME)
    session = store.get(session_id) if session_id else None
    if session is not None:
        return session, None
    new_session_id, session = store.create()
    return session, new_session_id
