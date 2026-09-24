"""Knowledge/Language skills chargen step: `POST /ui/knowledge` (WP49, widened by WP53).

**WP62**: split out of the former `chummer5.web.app` -- see `spec/plan/phase-r-architecture-
cleanup.md`'s WP58 audit for the target shape this module is part of.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
from types import MappingProxyType
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from starlette.datastructures import FormData

from chummer5.data.knowledge import (
    KNOWLEDGE_CATEGORIES,
    KNOWLEDGE_CATEGORY_NAMES,
    SUGGESTED_LANGUAGES,
)
from chummer5.engine.character import Character
from chummer5.engine.knowledge import (
    KarmaKnowledgeSelection,
    KnowledgeSelection,
    KnowledgeSkillPick,
    LanguageSkillPick,
    create_karma_knowledge_selection,
    create_knowledge_selection,
    free_knowledge_points,
    knowledge_dice_pool,
    language_dice_pool,
    native_language_limit,
)
from chummer5.engine.skills import MAX_SKILL_RATING_CREATE
from chummer5.web.catalogs import MAX_KNOWLEDGE_ROWS, MAX_LANGUAGE_ROWS, templates
from chummer5.web.session import SESSION_COOKIE_NAME, resolve_session

router = APIRouter()


def _parse_knowledge_skills(form: FormData, max_rows: int) -> tuple[KnowledgeSkillPick, ...]:
    """Read up to `max_rows` Knowledge-skill rows off a submitted form -- mirrors
    `chummer5.web.routes.contacts._parse_contacts`'s identical fixed-row shape. Any row whose name
    field is blank is skipped entirely; a malformed rating is treated as 0 rather than dropping the
    row (`create_knowledge_selection`'s own 1-6 range check is what rejects a 0, the same "let the
    engine validate what it's already responsible for" choice `_parse_contacts` makes for
    Connection/Loyalty).
    """
    picks = []
    for i in range(max_rows):
        name = str(form.get(f"knowledge_name_{i}") or "").strip()
        if not name:
            continue
        category = str(form.get(f"knowledge_category_{i}") or "")
        try:
            rating = int(str(form.get(f"knowledge_rating_{i}", "0")))
        except ValueError:
            rating = 0
        picks.append(KnowledgeSkillPick(name=name, category=category, rating=rating))
    return tuple(picks)


def _parse_languages(form: FormData, max_rows: int) -> tuple[LanguageSkillPick, ...]:
    """Read up to `max_rows` Language-skill rows off a submitted form -- same shape as
    `_parse_knowledge_skills` above, plus a `native` checkbox.
    """
    picks = []
    for i in range(max_rows):
        name = str(form.get(f"language_name_{i}") or "").strip()
        if not name:
            continue
        native = form.get(f"language_native_{i}") is not None
        try:
            rating = int(str(form.get(f"language_rating_{i}", "0")))
        except ValueError:
            rating = 0
        picks.append(LanguageSkillPick(name=name, rating=rating, native=native))
    return tuple(picks)


def _parse_karma_points_by_name(
    form: FormData, name_prefix: str, karma_prefix: str, max_rows: int
) -> dict[str, int]:
    """Read `{name_prefix}{i}`/`{karma_prefix}{i}` row pairs off a submitted form into a sparse
    `{name: karma_points}` dict (WP53) -- keyed by the row's own name, not its index, since
    `create_karma_knowledge_selection` resolves Karma spend by name (see that function's own
    docstring). A fresh pass over the raw form fields, independent of `_parse_knowledge_skills`/
    `_parse_languages`'s own compacted (blank rows skipped) output -- pairing a karma field with
    the compacted list by index would misalign the moment an earlier row is blank.
    """
    points: dict[str, int] = {}
    for i in range(max_rows):
        name = str(form.get(f"{name_prefix}{i}") or "").strip()
        if not name:
            continue
        raw = form.get(f"{karma_prefix}{i}")
        if raw is None:
            continue
        try:
            value = int(str(raw))
        except ValueError:
            continue
        if value != 0:
            points[name] = value
    return points


def _knowledge_row(
    character: Character,
    knowledge_skills: tuple[KnowledgeSkillPick, ...],
    karma_points: Mapping[str, int],
    i: int,
) -> dict[str, Any]:
    """One echoed Knowledge-skill row for `_knowledge_skills.html`, incl. its dice `pool` (WP68).
    `pool` is `None` -- rendered blank -- for a padding row past the submitted picks, a not-yet-
    named/rated row, or a row whose `category` isn't one of the 4 real Knowledge categories (its
    linked attribute is unknown until a valid category is chosen); otherwise it's
    `rating + karma pts + linked attribute`, mirroring the active-skills picker's Karma-inclusive
    pool.
    """
    if i >= len(knowledge_skills):
        return {
            "index": i,
            "name": "",
            "category": "",
            "rating": "",
            "karma_points": 0,
            "pool": None,
        }
    pick = knowledge_skills[i]
    karma = karma_points.get(pick.name, 0)
    pool = (
        knowledge_dice_pool(character, pick.category, pick.rating + karma)
        if pick.category in KNOWLEDGE_CATEGORY_NAMES and pick.rating >= 1
        else None
    )
    return {
        "index": i,
        "name": pick.name,
        "category": pick.category,
        "rating": pick.rating,
        "karma_points": karma,
        "pool": pool,
    }


def _language_row(
    character: Character,
    languages: tuple[LanguageSkillPick, ...],
    karma_points: Mapping[str, int],
    i: int,
) -> dict[str, Any]:
    """One echoed Language-skill row for `_knowledge_skills.html`, incl. its dice `pool` (WP68). A
    native pick has fluency "N" rather than a numeric rating, so `pool` stays `None` and the
    template renders "N"; a rated pick's `pool` is `rating + karma pts + INT`.
    """
    if i >= len(languages):
        return {
            "index": i,
            "name": "",
            "rating": "",
            "native": False,
            "karma_points": 0,
            "pool": None,
        }
    pick = languages[i]
    karma = karma_points.get(pick.name, 0)
    pool = (
        language_dice_pool(character, pick.rating + karma)
        if not pick.native and pick.rating >= 1
        else None
    )
    return {
        "index": i,
        "name": pick.name,
        "rating": pick.rating,
        "native": pick.native,
        "karma_points": karma,
        "pool": pool,
    }


def _knowledge_selection_context(
    character: Character | None,
    knowledge_skills: tuple[KnowledgeSkillPick, ...],
    languages: tuple[LanguageSkillPick, ...],
    karma_points: Mapping[str, int] = MappingProxyType({}),
    *,
    error: str | None = None,
) -> dict[str, Any]:
    """Context for `_knowledge_skills.html`. Same echo-the-submission/re-validate-fresh shape as
    `chummer5.web.routes.skills._skill_allocation_context` -- `knowledge_skills`/`languages` feed a
    throwaway echo of the submission regardless of whether it actually validated; when `error` is
    unset, re-runs `create_knowledge_selection` purely to detect whether an attribute edit since
    the last commit shrank INT/LOG below what's already spent (WP19-style "no longer fits"
    staleness), the same re-derive-fresh-on-every-render precedent every other carried-forward
    selection follows.

    **WP53**: `karma_points` -- submitted in the same form as `knowledge_skills`/`languages`,
    keyed by pick *name* (see `chummer5.engine.knowledge`'s own WP53 paragraph for why) -- feeds a
    *preview* `KarmaKnowledgeSelection`, the same "call the real validator against a throwaway
    huge budget, fall back to no overlay on any structural failure" shape
    `_skill_allocation_context` uses, since Knowledge/Language picks have no dice-pool preview to
    compute (only a "Karma remaining" summary line and each row's own Karma-boosted total).
    """
    if character is None:
        return {"character": None, "knowledge_error": error}
    knowledge_rows = [
        _knowledge_row(character, knowledge_skills, karma_points, i)
        for i in range(MAX_KNOWLEDGE_ROWS)
    ]
    language_rows = [
        _language_row(character, languages, karma_points, i) for i in range(MAX_LANGUAGE_ROWS)
    ]
    free_points = free_knowledge_points(character)
    points_spent = sum(k.rating for k in knowledge_skills) + sum(
        la.rating for la in languages if not la.native
    )
    preview_knowledge_selection = KnowledgeSelection(
        knowledge_skills=knowledge_skills,
        languages=languages,
        free_points=free_points,
        points_spent=points_spent,
        native_language_limit=native_language_limit(character),
    )
    try:
        preview_karma_knowledge: KarmaKnowledgeSelection | None = create_karma_knowledge_selection(
            replace(character, knowledge_selection=preview_knowledge_selection),
            karma_points,
            karma_budget=10**9,
        )
    except ValueError:
        preview_karma_knowledge = None
    karma_budget = character.karma_remaining + (
        character.karma_knowledge_selection.karma_cost
        if character.karma_knowledge_selection is not None
        else 0
    )
    budget_warning: str | None = None
    if error is None:
        try:
            create_knowledge_selection(character, knowledge_skills, languages)
            create_karma_knowledge_selection(
                replace(character, knowledge_selection=preview_knowledge_selection),
                karma_points,
                karma_budget,
            )
        except ValueError as exc:
            budget_warning = (
                f"No longer fits since attributes were last confirmed: {exc}. "
                "Adjust the entries below to continue."
            )
    return {
        "character": character,
        "knowledge_rows": knowledge_rows,
        "language_rows": language_rows,
        "knowledge_categories": KNOWLEDGE_CATEGORIES,
        "suggested_languages": SUGGESTED_LANGUAGES,
        "knowledge_free_points": free_points,
        "knowledge_points_spent": points_spent,
        "native_language_limit": native_language_limit(character),
        "max_skill_rating": MAX_SKILL_RATING_CREATE,
        "knowledge_budget_warning": budget_warning,
        # WP60: prefixed -- see the identical comment in
        # `chummer5.web.routes.attributes._attribute_allocation_context`.
        "knowledge_karma_budget": karma_budget,
        "knowledge_karma_remaining": (
            karma_budget - preview_karma_knowledge.karma_cost
            if preview_karma_knowledge is not None
            else karma_budget
        ),
        "knowledge_error": error,
    }


@router.post("/ui/knowledge", response_class=HTMLResponse)
async def submit_knowledge(request: Request) -> HTMLResponse:
    session, new_cookie = resolve_session(request)
    session.current_page = "skills"  # WP61/WP97
    if session.character is None:
        context = _knowledge_selection_context(None, (), ())
    else:
        form = await request.form()
        knowledge_skills = _parse_knowledge_skills(form, MAX_KNOWLEDGE_ROWS)
        languages = _parse_languages(form, MAX_LANGUAGE_ROWS)
        # WP53: Karma-funded points, keyed by name, submitted in the same form.
        karma_points = _parse_karma_points_by_name(
            form, "knowledge_name_", "knowledge_karma_", MAX_KNOWLEDGE_ROWS
        )
        karma_points.update(
            _parse_karma_points_by_name(
                form, "language_name_", "language_karma_", MAX_LANGUAGE_ROWS
            )
        )
        previous = session.character
        try:
            selection = create_knowledge_selection(previous, knowledge_skills, languages)
            karma_budget = previous.karma_remaining + (
                previous.karma_knowledge_selection.karma_cost
                if previous.karma_knowledge_selection is not None
                else 0
            )
            karma_selection = create_karma_knowledge_selection(
                replace(previous, knowledge_selection=selection), karma_points, karma_budget
            )
        except ValueError as exc:
            context = _knowledge_selection_context(
                session.character, knowledge_skills, languages, karma_points, error=str(exc)
            )
        else:
            session.character = replace(
                session.character,
                knowledge_selection=selection,
                karma_knowledge_selection=karma_selection,
            )
            context = _knowledge_selection_context(
                session.character, knowledge_skills, languages, karma_points
            )
    response = templates.TemplateResponse(request, "_knowledge_skills.html", context)
    if new_cookie is not None:
        response.set_cookie(SESSION_COOKIE_NAME, new_cookie, httponly=True, samesite="lax")
    return response
