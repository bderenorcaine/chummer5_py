"""Qualities chargen step: `POST /ui/qualities` (WP16, widened by WP23/WP48/WP55).

**WP62**: split out of the former `chummer5.web.app` -- see `spec/plan/phase-r-architecture-
cleanup.md`'s WP58 audit for the target shape this module is part of.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import replace
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from chummer5.data.mentors import MentorSpiritArchetype
from chummer5.data.qualities import BonusSupport
from chummer5.engine.character import Character
from chummer5.engine.improvements import ImprovementSource
from chummer5.engine.qualities import (
    MENTOR_SPIRIT_QUALITY_NAME,
    QUALITY_KARMA_LIMIT,
    QualitySelection,
    apply_mentor_spirit_improvements,
    apply_quality_improvements,
    create_quality_selection,
    offerable_quality_catalog,
    resolve_metatype_qualities,
)
from chummer5.web.catalogs import MENTOR_SPIRIT_QUALITY, MENTORS, QUALITIES, templates
from chummer5.web.session import SESSION_COOKIE_NAME, resolve_session

router = APIRouter()


def _relink_metatype_qualities(character: Character) -> Character:
    """(Re)populate `character.metatype_qualities` from `character.metatype`, keeping its
    Improvements in sync (WP23).

    What belongs here can genuinely change out from under `character.metatype_qualities` --
    `submit_priorities` can swap the metatype itself. So this always removes whatever
    `ImprovementSource.METATYPE` Improvements `character.metatype_qualities` currently names before
    resolving `character.metatype`'s *current* free qualities and re-applying -- correct whether
    metatype changed, stayed the same, or this is the first time it's ever been resolved. Safe to
    call unconditionally after any (re)construction of `character` (both `submit_priorities` and,
    since WP63, `submit_attributes` call it on every submission regardless of whether metatype
    could actually have changed on that route).
    """
    for quality in character.metatype_qualities:
        character.improvements.remove_source(ImprovementSource.METATYPE, quality.id)
    metatype_qualities = resolve_metatype_qualities(character.metatype, QUALITIES)
    apply_quality_improvements(
        character, metatype_qualities, source_type=ImprovementSource.METATYPE
    )
    return replace(character, metatype_qualities=metatype_qualities)


def _strip_mentor_spirit_selection(
    character: Character, quality_selection: QualitySelection | None
) -> QualitySelection | None:
    """Drop just the Mentor Spirit quality and archetype pick from an already-committed
    `QualitySelection`, keeping every other quality intact (WP48), used by
    `chummer5.web.routes.talent._replace_committed_talent`.

    Unlike spell/power/spirit/Foci selections, which `_replace_committed_talent` resets to `None`
    wholesale on any Talent change, `quality_selection` as a whole can't be reset that way -- it
    also holds every magic-*independent* quality the player picked (Catlike, Indomitable, ...),
    which a Talent change has no reason to discard. But a Mentor Spirit pick specifically *is*
    Talent-dependent (its `gated_choice` is resolved from `magic_type`, and the quality stops being
    offered at all once `magic_type` becomes `None`), so it needs the same "reset on any Talent
    (re)confirmation" treatment those other selections get, applied surgically instead of wholesale.
    Removes `MENTOR_SPIRIT`-sourced Improvements as a side effect; `QUALITY`-sourced ones for the
    remaining qualities are left untouched (`apply_quality_improvements` was never called twice for
    them, so there's nothing to remove before a no-op re-add would be needed). Returns
    `quality_selection` unchanged if nothing was ever committed, or if it never included Mentor
    Spirit in the first place.
    """
    if quality_selection is None or quality_selection.mentor_spirit is None:
        return quality_selection
    character.improvements.remove_source(
        ImprovementSource.MENTOR_SPIRIT, quality_selection.mentor_spirit.archetype.id
    )
    remaining_ids = [
        q.id for q in quality_selection.qualities if q.name != MENTOR_SPIRIT_QUALITY_NAME
    ]
    offered = offerable_quality_catalog(character, QUALITIES)
    # WP55: Mentor Spirit itself is never a SELECT_TEXT quality, so quality_selection.quality_text
    # already has exactly the right entries for remaining_ids with nothing orphaned by its removal.
    return create_quality_selection(
        remaining_ids, offered, quality_text=quality_selection.quality_text
    )


def _replace_committed_qualities(character: Character, selection: QualitySelection) -> Character:
    """Swap whatever QUALITY-/MENTOR_SPIRIT-sourced Improvements `character.improvements` currently
    holds for `selection`'s, and re-attach `selection` as `character.quality_selection`.

    `apply_quality_improvements`/`apply_mentor_spirit_improvements` only ever add -- calling either
    twice for two submissions against the same `Character` (i.e. without an intervening
    `create_character` rebuild) would double up anything that stayed selected across both, so
    previously-applied Improvements of both kinds are removed first. `MENTOR_SPIRIT` is removed
    unconditionally (a no-op when nothing was ever picked) rather than only when `selection
    .mentor_spirit is None`, since a *changed* archetype pick also needs its old Improvements gone
    before the new ones are applied (WP48).
    """
    for imp in character.improvements.improvements:
        if imp.source_type in (ImprovementSource.QUALITY, ImprovementSource.MENTOR_SPIRIT):
            character.improvements.remove_source(imp.source_type, imp.source_id)
    apply_quality_improvements(character, selection.qualities)
    if selection.mentor_spirit is not None:
        apply_mentor_spirit_improvements(character, selection.mentor_spirit)
    return replace(character, quality_selection=selection)


def _quality_selection_context(
    character: Character | None,
    quality_ids: Iterable[str],
    *,
    mentor_spirit_archetype_id: str | None = None,
    mentor_spirit_general_choice_id: str | None = None,
    quality_text: Mapping[str, str] | None = None,
    error: str | None = None,
) -> dict[str, Any]:
    """Context for `_quality_selection.html`. `quality_ids` is whatever should be shown checked --
    the session's committed selection on a clean render, or the raw submitted checkbox values on
    an error-echo render, same shape as the attribute/skill contexts above.

    **WP23**: the pickable rows come from `offerable_quality_catalog(character, QUALITIES)`, not
    the module-level `MVP_QUALITIES`, so a quality this character's metatype already grants for
    free (e.g. an Elf's Low-Light Vision) never appears as something to spend karma on again --
    also what makes Mentor Spirit itself appear as a row at all for a magic-active character (WP48).

    **WP48**: `mentor_spirit_archetype_id`/`mentor_spirit_general_choice_id` follow the identical
    "explicit override on echo/submit, fall back to the committed selection otherwise" shape --
    `None` (the default, used by the main chargen-body render) falls back to `character
    .quality_selection.mentor_spirit`; `submit_qualities` always passes an explicit value (possibly
    `None`, meaning "no archetype picked"), which must win even when it differs from what's
    committed. `mentor_spirit_offered` gates whether `_quality_selection.html` even shows the
    archetype picker at all -- mirrors `offerable_quality_catalog`'s own `character.magic_type is
    not None` gate for Mentor Spirit itself, so the picker never appears for a build where the
    quality isn't even offered.

    **WP55**: `quality_text` follows the identical "explicit override on echo/submit, fall back to
    the committed selection otherwise" shape as the Mentor Spirit fields -- `None` (the default)
    falls back to `character.quality_selection.quality_text`; `submit_qualities` always passes an
    explicit (possibly empty) mapping. Each row gets a `needs_text`/`text_value` pair so the
    template can render a free-text input next to exactly the `SELECT_TEXT` qualities, pre-filled
    with whatever's already committed or was just submitted.
    """
    if character is None:
        return {"character": None, "quality_error": error}
    offered = offerable_quality_catalog(character, QUALITIES)
    ids = set(quality_ids)
    if quality_text is None:
        quality_text = (
            character.quality_selection.quality_text
            if character.quality_selection is not None
            else {}
        )
    rows = [
        {
            "quality": q,
            "selected": q.id in ids,
            "needs_text": q.bonus_support == BonusSupport.SELECT_TEXT,
            "text_value": quality_text.get(q.id, ""),
        }
        for q in offered
    ]
    positive_karma = sum(q.karma for q in offered if q.id in ids and q.category == "Positive")
    negative_karma = -sum(q.karma for q in offered if q.id in ids and q.category == "Negative")

    committed_pick = (
        character.quality_selection.mentor_spirit
        if character.quality_selection is not None
        else None
    )
    if mentor_spirit_archetype_id is None and committed_pick is not None:
        mentor_spirit_archetype_id = committed_pick.archetype.id
        if mentor_spirit_general_choice_id is None:
            mentor_spirit_general_choice_id = committed_pick.general_choice.id
    selected_archetype: MentorSpiritArchetype | None = next(
        (a for a in MENTORS if a.id == mentor_spirit_archetype_id), None
    )

    return {
        "character": character,
        "quality_rows": rows,
        "positive_karma": positive_karma,
        "negative_karma": negative_karma,
        "karma_limit": QUALITY_KARMA_LIMIT,
        "metatype_qualities": character.metatype_qualities,
        "mentor_spirit_offered": character.magic_type is not None,
        "mentor_spirit_archetypes": MENTORS,
        "selected_mentor_spirit_archetype_id": mentor_spirit_archetype_id,
        "selected_mentor_spirit_archetype": selected_archetype,
        "selected_mentor_spirit_general_choice_id": mentor_spirit_general_choice_id,
        "quality_error": error,
    }


@router.post("/ui/qualities", response_class=HTMLResponse)
async def submit_qualities(request: Request) -> HTMLResponse:
    session, new_cookie = resolve_session(request)
    session.open_section = "quality-selection"  # WP61
    if session.character is None:
        context = _quality_selection_context(None, ())
    else:
        form = await request.form()
        quality_ids = [str(value) for value in form.getlist("quality_id")]
        # WP48: the archetype/general-choice fields are only meaningful when Mentor Spirit
        # itself is checked -- forced to None otherwise, so unchecking the quality never
        # requires also clearing a stale dropdown just to avoid "an archetype was picked
        # without the Mentor Spirit quality" (create_quality_selection's own guard against an
        # orphaned pick, meant for a tampered/stale request, not this ordinary UI interaction).
        mentor_spirit_archetype_id: str | None = None
        mentor_spirit_general_choice_id: str | None = None
        if MENTOR_SPIRIT_QUALITY.id in quality_ids:
            raw_archetype_id = str(form.get("mentor_spirit_archetype_id") or "")
            mentor_spirit_archetype_id = raw_archetype_id or None
            raw_general_choice_id = str(form.get("mentor_spirit_general_choice_id") or "")
            mentor_spirit_general_choice_id = raw_general_choice_id or None
        # WP23: validate against this character's own offerable catalog, not the raw QUALITIES
        # catalog, so a tampered/stale submission can't buy an already metatype-granted quality
        # either -- `create_quality_selection` already raises "not an MVP-offered quality id"
        # for anything not in whatever catalog it's given, so this alone is sufficient.
        offered = offerable_quality_catalog(session.character, QUALITIES)
        # WP55: only read a quality_text_{id} field for a quality that's both checked and
        # SELECT_TEXT -- mirrors the Mentor Spirit fields' "only meaningful when the quality
        # itself is checked" precedent just above, so unchecking a SINner variant never requires
        # also clearing its stale text box first.
        quality_text = {
            q.id: str(form.get(f"quality_text_{q.id}") or "")
            for q in offered
            if q.bonus_support == BonusSupport.SELECT_TEXT and q.id in quality_ids
        }
        try:
            selection = create_quality_selection(
                quality_ids,
                offered,
                magic_type=session.character.magic_type,
                mentor_catalog=MENTORS,
                mentor_spirit_archetype_id=mentor_spirit_archetype_id,
                mentor_spirit_general_choice_id=mentor_spirit_general_choice_id,
                quality_text=quality_text,
            )
        except ValueError as exc:
            context = _quality_selection_context(
                session.character,
                quality_ids,
                mentor_spirit_archetype_id=mentor_spirit_archetype_id,
                mentor_spirit_general_choice_id=mentor_spirit_general_choice_id,
                quality_text=quality_text,
                error=str(exc),
            )
        else:
            session.character = _replace_committed_qualities(session.character, selection)
            context = _quality_selection_context(
                session.character, quality_ids, quality_text=quality_text
            )
    context["open_section"] = session.open_section  # WP61
    response = templates.TemplateResponse(request, "_quality_selection.html", context)
    if new_cookie is not None:
        response.set_cookie(SESSION_COOKIE_NAME, new_cookie, httponly=True, samesite="lax")
    return response
