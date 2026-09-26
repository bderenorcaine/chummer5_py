"""Qualities chargen step: `POST /ui/qualities` (WP16, widened by WP23/WP48/WP55).

**WP62**: split out of the former `chummer5.web.app` -- see `spec/plan/phase-r-architecture-
cleanup.md`'s WP58 audit for the target shape this module is part of.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import replace
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from chummer5.data.mentors import MentorSpiritArchetype
from chummer5.data.qualities import BonusSupport, Quality
from chummer5.engine.character import Character
from chummer5.engine.improvements import ImprovementSource
from chummer5.engine.lifestyle import lifestyle_cost_percent, surcharged_monthly_cost
from chummer5.engine.qualities import (
    MENTOR_SPIRIT_QUALITY_NAME,
    QUALITY_KARMA_LIMIT,
    QualityPickRequest,
    QualitySelection,
    apply_mentor_spirit_improvements,
    apply_metatype_bonus_improvements,
    apply_quality_improvements,
    choice_options,
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
    # WP113: every METATYPE-sourced Improvement goes, not just the free qualities' -- the racial
    # `<bonus>` ones are keyed by the *previous* metatype's id, which this function can't know.
    for imp in character.improvements.improvements:
        if imp.source_type is ImprovementSource.METATYPE:
            character.improvements.remove_source(imp.source_type, imp.source_id)
    metatype_qualities = resolve_metatype_qualities(character.metatype, QUALITIES)
    apply_quality_improvements(
        character, metatype_qualities, source_type=ImprovementSource.METATYPE
    )
    apply_metatype_bonus_improvements(character)
    character = replace(character, metatype_qualities=metatype_qualities)
    # The Lifestyle surcharge may have just changed (Human -> Troll doubles it), and a committed
    # selection carries its computed total -- re-price it at the new percent.
    selection = character.lifestyle_selection
    if selection is not None:
        character = replace(
            character,
            lifestyle_selection=replace(
                selection,
                cost_percent=lifestyle_cost_percent(character),
                total_cost=surcharged_monthly_cost(
                    selection.tier.monthly_cost, lifestyle_cost_percent(character)
                )
                * selection.months,
            ),
        )
    return character


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
    remaining = [
        pick.to_request()
        for pick in quality_selection.qualities
        if pick.quality.name != MENTOR_SPIRIT_QUALITY_NAME
    ]
    offered = offerable_quality_catalog(character, QUALITIES)
    return create_quality_selection(remaining, offered, **_gate_kwargs(character))


def _gate_kwargs(character: Character) -> dict[str, Any]:
    """The metatype half of `create_quality_selection`'s WP108 prerequisite check."""
    return {
        "metatype_name": character.metatype.name,
        "granted_quality_names": tuple(q.name for q in character.metatype_qualities),
    }


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


def _row_key(quality_id: str, index: int) -> str:
    """A form row's key (WP107): the bare id for a quality's first instance, `id:n` after that.

    The first instance keeps the pre-WP107 field names (`quality_id=<id>`,
    `quality_text_<id>`), so a once-only quality's form fields are unchanged.
    """
    return quality_id if index == 0 else f"{quality_id}:{index}"


def _quality_rows(
    offered: Iterable[Quality],
    requests: Sequence[QualityPickRequest],
    magic_type: str | None = None,
) -> list[dict[str, Any]]:
    """One row per quality instance to render (WP107).

    A once-only or rated quality gets exactly one row, checked when requested. A repeatable one
    gets a row per requested instance plus one blank "add another" row, so a player adds a second
    Addiction by filling in the blank row -- the row is there before they need it, and there is no
    separate add button to wire up.
    """
    rows: list[dict[str, Any]] = []
    for quality in offered:
        instances = [r for r in requests if r.quality_id == quality.id]
        shown: list[QualityPickRequest | None] = list(instances)
        if quality.repeatable or not shown:
            shown.append(None)
        if not quality.repeatable:
            shown = shown[:1]
        for index, request in enumerate(shown):
            rows.append(
                {
                    "quality": quality,
                    "key": _row_key(quality.id, index),
                    "selected": request is not None,
                    "needs_text": quality.bonus_support == BonusSupport.SELECT_TEXT,
                    "text_value": (request.text or "") if request is not None else "",
                    "rating": request.rating if request is not None else 1,
                    "max_rating": quality.max_rating,
                    # WP112: a choice-bearing quality's dropdown (Exceptional Attribute).
                    "choice_options": choice_options(quality, magic_type),
                    "choice_kind": quality.choice_kind,
                    "choice_value": request.choice if request is not None else None,
                    "another": quality.repeatable and index > 0 and request is None,
                }
            )
    return rows


def _quality_selection_context(
    character: Character | None,
    picks: Iterable[str | QualityPickRequest] | None = None,
    *,
    mentor_spirit_archetype_id: str | None = None,
    mentor_spirit_general_choice_id: str | None = None,
    error: str | None = None,
) -> dict[str, Any]:
    """Context for `_quality_selection.html`. `picks` is whatever should be shown selected -- the
    session's committed selection on a clean render (the default, `None`), or the raw submitted
    rows on an error-echo render, same shape as the attribute/skill contexts above.

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

    **WP55/WP107**: each row carries its instance's text and rating, so a `SELECT_TEXT` quality's
    detail box and a rated quality's level stepper are pre-filled with whatever's committed or was
    just submitted. See `_quality_rows` for how repeatable qualities get their extra rows.
    """
    if character is None:
        return {"character": None, "quality_error": error}
    offered = offerable_quality_catalog(character, QUALITIES)
    if picks is None:
        requests: list[QualityPickRequest] = (
            list(character.quality_selection.to_requests())
            if character.quality_selection is not None
            else []
        )
    else:
        requests = [QualityPickRequest(quality_id=p) if isinstance(p, str) else p for p in picks]
    by_id = {q.id: q for q in offered}
    positive_karma = sum(
        by_id[r.quality_id].karma * r.rating
        for r in requests
        if r.quality_id in by_id and by_id[r.quality_id].category == "Positive"
    )
    negative_karma = -sum(
        by_id[r.quality_id].karma * r.rating
        for r in requests
        if r.quality_id in by_id and by_id[r.quality_id].category == "Negative"
    )

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
        "quality_budget_warning": (
            _committed_quality_warning(character, offered) if error is None else None
        ),
        "quality_rows": _quality_rows(offered, requests, character.magic_type),
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


def _committed_quality_warning(character: Character, offered: Iterable[Quality]) -> str | None:
    """WP108: re-validate the committed picks against the character as it is *now* -- the WP19
    "no longer fits" path. A priorities or Talent change can leave a pick behind that its gate no
    longer allows (an Elf who becomes a Human keeps Human-Looking). The pick stays committed and
    the reason is shown until the player fixes it; nothing raises."""
    selection = character.quality_selection
    if selection is None:
        return None
    mentor_pick = selection.mentor_spirit
    try:
        create_quality_selection(
            selection.to_requests(),
            offered,
            magic_type=character.magic_type,
            mentor_catalog=MENTORS,
            mentor_spirit_archetype_id=mentor_pick.archetype.id if mentor_pick else None,
            mentor_spirit_general_choice_id=mentor_pick.general_choice.id if mentor_pick else None,
            **_gate_kwargs(character),
        )
    except ValueError as exc:
        return str(exc)  # an engine message: stays as-is (WP102)
    return None


def _submitted_picks(form: Any, offered: Iterable[Quality]) -> list[QualityPickRequest]:
    """Read the checked rows back into pick requests (WP107).

    A row's text is read only for a `SELECT_TEXT` quality, and its rating only for a rated one --
    the same "only meaningful when it applies" discipline the Mentor Spirit fields follow, so a
    stale box on an unchecked or text-less row never trips a validator. A rating box that isn't a
    number becomes rating 0, which `create_quality_selection` rejects with its range message.
    """
    by_id = {q.id: q for q in offered}
    picks: list[QualityPickRequest] = []
    for raw_key in form.getlist("quality_id"):
        key = str(raw_key)
        quality_id = key.split(":", 1)[0]
        quality = by_id.get(quality_id)
        if quality is None:
            # Unknown ids still reach create_quality_selection, which names them in its error.
            picks.append(QualityPickRequest(quality_id=quality_id))
            continue
        text = (
            str(form.get(f"quality_text_{key}") or "")
            if quality.bonus_support == BonusSupport.SELECT_TEXT
            else None
        )
        choice = (
            str(form.get(f"quality_choice_{key}") or "") or None
            if quality.choice_kind is not None
            else None
        )
        rating = 1
        if quality.max_rating > 1:
            try:
                rating = int(str(form.get(f"quality_rating_{key}") or "1"))
            except ValueError:
                rating = 0
        picks.append(
            QualityPickRequest(quality_id=quality_id, rating=rating, text=text, choice=choice)
        )
    return picks


@router.post("/ui/qualities", response_class=HTMLResponse)
async def submit_qualities(request: Request) -> HTMLResponse:
    session, new_cookie = resolve_session(request)
    session.current_page = "qualities"  # WP61/WP97
    if session.character is None:
        context = _quality_selection_context(None, ())
    else:
        form = await request.form()
        # WP23: validate against this character's own offerable catalog, not the raw QUALITIES
        # catalog, so a tampered/stale submission can't buy an already metatype-granted quality
        # either -- `create_quality_selection` already raises "not an MVP-offered quality id"
        # for anything not in whatever catalog it's given, so this alone is sufficient.
        offered = offerable_quality_catalog(session.character, QUALITIES)
        picks = _submitted_picks(form, offered)
        # WP48: the archetype/general-choice fields are only meaningful when Mentor Spirit
        # itself is checked -- forced to None otherwise, so unchecking the quality never
        # requires also clearing a stale dropdown just to avoid "an archetype was picked
        # without the Mentor Spirit quality" (create_quality_selection's own guard against an
        # orphaned pick, meant for a tampered/stale request, not this ordinary UI interaction).
        mentor_spirit_archetype_id: str | None = None
        mentor_spirit_general_choice_id: str | None = None
        if any(p.quality_id == MENTOR_SPIRIT_QUALITY.id for p in picks):
            raw_archetype_id = str(form.get("mentor_spirit_archetype_id") or "")
            mentor_spirit_archetype_id = raw_archetype_id or None
            raw_general_choice_id = str(form.get("mentor_spirit_general_choice_id") or "")
            mentor_spirit_general_choice_id = raw_general_choice_id or None
        try:
            selection = create_quality_selection(
                picks,
                offered,
                magic_type=session.character.magic_type,
                mentor_catalog=MENTORS,
                mentor_spirit_archetype_id=mentor_spirit_archetype_id,
                mentor_spirit_general_choice_id=mentor_spirit_general_choice_id,
                **_gate_kwargs(session.character),
            )
        except ValueError as exc:
            context = _quality_selection_context(
                session.character,
                picks,
                mentor_spirit_archetype_id=mentor_spirit_archetype_id,
                mentor_spirit_general_choice_id=mentor_spirit_general_choice_id,
                error=str(exc),
            )
        else:
            session.character = _replace_committed_qualities(session.character, selection)
            context = _quality_selection_context(session.character)
    response = templates.TemplateResponse(request, "_quality_selection.html", context)
    if new_cookie is not None:
        response.set_cookie(SESSION_COOKIE_NAME, new_cookie, httponly=True, samesite="lax")
    return response
