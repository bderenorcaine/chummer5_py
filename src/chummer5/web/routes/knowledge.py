"""Knowledge/Language skills chargen step: `POST /ui/knowledge` (WP49, widened by WP53). Since
WP149 it is the Skills page's Knowledge tab: one table for Knowledge and Language skills.

**WP62**: split out of the former `chummer5.web.app` -- see `spec/plan/phase-r-architecture-
cleanup.md`'s WP58 audit for the target shape this module is part of.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
from types import MappingProxyType
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from starlette.datastructures import FormData

from chummer5.data.knowledge import (
    KNOWLEDGE_CATEGORIES,
    KNOWLEDGE_CATEGORY_NAMES,
    LANGUAGE_LINKED_ATTRIBUTE,
)
from chummer5.data.skills import Skill
from chummer5.engine.character import Character
from chummer5.engine.knowledge import (
    LANGUAGE_CATEGORY,
    KnowledgeSkillPick,
    LanguageSkillPick,
    create_karma_knowledge_selection,
    create_knowledge_selection,
    free_knowledge_points,
    knowledge_dice_pool,
    knowledge_points_spent,
    language_dice_pool,
    native_language_limit,
)
from chummer5.engine.skills import (
    MAX_SKILL_RATING_CREATE,
    SPECIALIZATION_BONUS,
    skill_point_budget,
    skill_points_spent,
    skill_purchase_rules,
)
from chummer5.web.catalogs import (
    KNOWLEDGE_CATALOG,
    MAX_KNOWLEDGE_TABLE_ROWS,
    PRIORITIES,
    SKILLS,
    first_example,
    templates,
)
from chummer5.web.i18n import Message
from chummer5.web.session import resolve_session, set_session_cookie

router = APIRouter()


@dataclass(frozen=True)
class KnowledgeRow:
    """WP149: one row of the Skills page's Knowledge tab, as submitted or as committed. Knowledge
    and Language skills share the table; `category` is one of the four knowledge categories,
    `Language`, or blank on a row the player hasn't finished. `rating` is the Knowledge-points
    rating (Kn pts) and `karma_points` the Karma-bought ranks (Ka pts) on top. `spec_karma` is the
    specialization toggle (on = Karma)."""

    name: str = ""
    category: str = ""
    native: bool = False
    rating: int = 0
    karma_points: int = 0
    specialization: str = ""
    spec_karma: bool = False

    @property
    def is_language(self) -> bool:
        return self.category == LANGUAGE_CATEGORY

    @property
    def blank(self) -> bool:
        return not (
            self.name or self.category or self.rating or self.karma_points or self.specialization
        )

    @property
    def spec_forced(self) -> bool:
        """Only Karma can pay for the specialization: a point-funded one needs a rating of 1+ from
        Knowledge points, unless the language is native (WP125, `_check_specialization`)."""
        return not self.native and self.rating < 1


def _form_int(raw: object) -> int:
    """A malformed number reads as 0, leaving range checks to the engine (WP49's choice)."""
    try:
        return int(str(raw))
    except ValueError:
        return 0


def _parse_rows(form: FormData) -> list[KnowledgeRow]:
    """WP149: the Knowledge tab's one row series (`knowledge_*_<i>`), in row order, with trailing
    blank rows dropped. A blank row in the middle stays, so no row below it changes index (its
    ids are built from the index). Native counts only on a Language row: turning a Language row
    into another category drops it."""
    rows = []
    for i in range(MAX_KNOWLEDGE_TABLE_ROWS):
        category = str(form.get(f"knowledge_category_{i}") or "")
        rows.append(
            KnowledgeRow(
                name=str(form.get(f"knowledge_name_{i}") or "").strip(),
                category=category,
                native=category == LANGUAGE_CATEGORY
                and form.get(f"knowledge_native_{i}") is not None,
                rating=_form_int(form.get(f"knowledge_rating_{i}", "0")),
                karma_points=_form_int(form.get(f"knowledge_karma_{i}", "0")),
                specialization=str(form.get(f"knowledge_spec_{i}") or "").strip(),
                spec_karma=form.get(f"knowledge_spec_karma_{i}") is not None,
            )
        )
    while rows and rows[-1].blank:
        rows.pop()
    return rows


@dataclass(frozen=True)
class _Picks:
    knowledge_skills: tuple[KnowledgeSkillPick, ...]
    languages: tuple[LanguageSkillPick, ...]
    karma_points: dict[str, int]
    specializations: dict[str, str]
    karma_specializations: dict[str, str]
    duplicate: str | None


def _sort_rows(rows: list[KnowledgeRow]) -> _Picks:
    """WP149: sort the named rows into the engine's two pick lists by category, and key Karma and
    specializations by name as the engine does (WP53/WP125). A name may appear on one row only:
    with one table, a Knowledge skill and a Language sharing a name would make those name-keyed
    maps ambiguous, so the first repeated name is reported instead (the engine would reject the
    ambiguity too, but only once Karma or a specialization referred to it)."""
    knowledge: list[KnowledgeSkillPick] = []
    languages: list[LanguageSkillPick] = []
    karma_points: dict[str, int] = {}
    specializations: dict[str, str] = {}
    karma_specializations: dict[str, str] = {}
    seen: set[str] = set()
    duplicate = None
    for row in rows:
        if not row.name:
            continue
        if row.name in seen and duplicate is None:
            duplicate = row.name
        seen.add(row.name)
        if row.is_language:
            languages.append(LanguageSkillPick(row.name, row.rating, row.native))
        else:
            knowledge.append(KnowledgeSkillPick(row.name, row.category, row.rating))
        if row.karma_points:
            karma_points[row.name] = row.karma_points
        if row.specialization:
            target = karma_specializations if row.spec_karma or row.spec_forced else specializations
            target[row.name] = row.specialization
    return _Picks(
        tuple(knowledge),
        tuple(languages),
        karma_points,
        specializations,
        karma_specializations,
        duplicate,
    )


def rows_from_picks(
    knowledge_skills: tuple[KnowledgeSkillPick, ...],
    languages: tuple[LanguageSkillPick, ...],
    karma_points: Mapping[str, int],
    specializations: Mapping[str, str],
    karma_specializations: Mapping[str, str],
) -> list[KnowledgeRow]:
    """WP149: the committed picks as table rows, Knowledge skills first and then Languages (the
    session's order, as the two tables had it). Only a page render uses this order; an autosave
    echoes the rows in the order they were posted, so nothing moves while the player edits."""

    def row(name: str, category: str, rating: int, native: bool) -> KnowledgeRow:
        return KnowledgeRow(
            name=name,
            category=category,
            native=native,
            rating=rating,
            karma_points=karma_points.get(name, 0),
            specialization=specializations.get(name) or karma_specializations.get(name, ""),
            spec_karma=name not in specializations and name in karma_specializations,
        )

    return [row(k.name, k.category, k.rating, False) for k in knowledge_skills] + [
        row(la.name, LANGUAGE_CATEGORY, la.rating, la.native) for la in languages
    ]


def active_points_left(character: Character, skills_letter: str) -> int:
    """WP125: the Active skill points the Skills step leaves for Knowledge/Language (p. 88)."""
    allocation = character.skill_allocation
    spent = (
        skill_points_spent(
            allocation.skill_points,
            allocation.specializations,
            SKILLS,
            skill_purchase_rules(character),
        )
        if allocation is not None
        else 0
    )
    # Never negative: an Active overspend is the Skills step's own warning, not this one's.
    return max(0, skill_point_budget(skills_letter, PRIORITIES).skills - spent)


def _catalog_entry(name: str) -> Skill | None:
    """The `<knowledgeskills>` entry whose name matches `name`, ignoring case."""
    return _CATALOG_BY_NAME.get(name.casefold())


_CATALOG_BY_NAME = {entry.name.casefold(): entry for entry in KNOWLEDGE_CATALOG}
# WP149: an unmatched Language row's specialization example. Every catalog language suggests
# Read/Write, Speak and a dialect.
LANGUAGE_SPEC_EXAMPLE = "Read/Write"


def _name_example(row: KnowledgeRow, index: int) -> Skill | None:
    """WP149: a blank name field's "e.g. ..." -- a catalog entry from the row's category if it has
    one, else from the whole catalog, chosen by row index so neighbouring rows differ."""
    if row.name:
        return None
    entries = [e for e in KNOWLEDGE_CATALOG if e.category == row.category] or list(
        KNOWLEDGE_CATALOG
    )
    return entries[index % len(entries)] if entries else None


def _spec_example(row: KnowledgeRow) -> str | None:
    """WP149: the specialization field's "e.g. ...": the matching catalog entry's first suggested
    specialization; Read/Write for an unmatched Language row; nothing for any other unmatched
    name, since an example borrowed from another skill would mislead."""
    entry = _catalog_entry(row.name) if row.name else None
    if entry is not None:
        example = first_example(entry)
        if example is not None:
            return example
    return LANGUAGE_SPEC_EXAMPLE if row.is_language else None


def _row_context(character: Character, row: KnowledgeRow, index: int) -> dict[str, Any]:
    """One row for `_knowledge_skills.html`, with its dice pool. `pool` is `None` -- rendered
    blank -- for an unnamed or unrated row, or one whose category isn't chosen yet (its linked
    attribute is unknown); a native language has fluency "N" rather than a pool. Otherwise it is
    `rating + Ka pts + linked attribute`, and `pool_specialized` the +2 pool when the row has a
    specialization (WP68/WP125, shown as "X (Y)" like an Active skill's)."""
    total = row.rating + row.karma_points
    pool: int | None = None
    if row.name and total >= 1:
        if row.is_language and not row.native:
            pool = language_dice_pool(character, total)
        elif row.category in KNOWLEDGE_CATEGORY_NAMES:
            pool = knowledge_dice_pool(character, row.category, total)
    return {
        "index": index,
        "row": row,
        "attribute": _LINKED_ATTRIBUTES.get(row.category),
        "total": total,
        "pool": pool,
        "pool_specialized": (
            pool + SPECIALIZATION_BONUS if pool is not None and row.specialization else None
        ),
        "name_example": _name_example(row, index),
        "spec_example": _spec_example(row),
    }


_LINKED_ATTRIBUTES = {c.name: c.linked_attribute for c in KNOWLEDGE_CATEGORIES} | {
    LANGUAGE_CATEGORY: LANGUAGE_LINKED_ATTRIBUTE
}


def _knowledge_selection_context(
    character: Character | None,
    knowledge_skills: tuple[KnowledgeSkillPick, ...],
    languages: tuple[LanguageSkillPick, ...],
    karma_points: Mapping[str, int] = MappingProxyType({}),
    specializations: Mapping[str, str] = MappingProxyType({}),
    karma_specializations: Mapping[str, str] = MappingProxyType({}),
    *,
    skills_letter: str,
    error: str | Message | None = None,
    rows: list[KnowledgeRow] | None = None,
    add_row: bool = False,
) -> dict[str, Any]:
    """Context for `_knowledge_skills.html`. Same echo-the-submission/re-validate-fresh shape as
    `chummer5.web.routes.skills._skill_allocation_context`: when `error` is unset, re-runs
    `create_knowledge_selection` purely to detect whether an attribute edit since the last commit
    shrank INT/LOG below what's already spent (WP19-style "no longer fits" staleness).

    **WP53**: `karma_points` is keyed by pick *name* (see `chummer5.engine.knowledge`'s own WP53
    paragraph for why). **WP125**: so are `specializations`/`karma_specializations`, and the spend
    past the free pool is drawn from the Active skill points `skills_letter` leaves.

    **WP149**: one table for Knowledge and Language skills. `rows` is the submission in posted
    order (an autosave's echo); a page render passes none and gets the committed picks via
    `rows_from_picks`. Either way the table ends in one blank row, plus another when `add_row`
    (the Add Knowledge Skill button), up to `MAX_KNOWLEDGE_TABLE_ROWS`. The Kn and Ka figures are
    the Skills strip's counters now, so only the Active points Knowledge uses are stated here.
    """
    if character is None:
        return {"character": None, "knowledge_error": error}
    shown = list(
        rows
        if rows is not None
        else rows_from_picks(
            knowledge_skills, languages, karma_points, specializations, karma_specializations
        )
    )
    for _ in range(2 if add_row else 1):
        if len(shown) < MAX_KNOWLEDGE_TABLE_ROWS:
            shown.append(KnowledgeRow())
    free_points = free_knowledge_points(character)
    points_spent = knowledge_points_spent(knowledge_skills, languages, specializations)
    active_points_available = active_points_left(character, skills_letter)
    budget_warning: Message | None = None
    if error is None:
        karma_budget = character.karma_remaining + (
            character.karma_knowledge_selection.karma_cost
            if character.karma_knowledge_selection is not None
            else 0
        )
        try:
            selection = create_knowledge_selection(
                character, knowledge_skills, languages, specializations, active_points_available
            )
            create_karma_knowledge_selection(
                replace(character, knowledge_selection=selection),
                karma_points,
                karma_budget,
                karma_specializations,
            )
        except ValueError as exc:
            budget_warning = Message.of("Web_Stale_Knowledge", error=str(exc))
    return {
        "character": character,
        "knowledge_rows": [_row_context(character, row, i) for i, row in enumerate(shown)],
        "knowledge_at_cap": len(shown) >= MAX_KNOWLEDGE_TABLE_ROWS,
        "knowledge_categories": KNOWLEDGE_CATEGORIES,
        "language_category": LANGUAGE_CATEGORY,
        "knowledge_free_points": free_points,
        "knowledge_points_spent": min(points_spent, free_points),
        # WP125: the part past the free pool, paid from the Active skill points.
        "knowledge_active_points_used": max(0, points_spent - free_points),
        "native_language_limit": native_language_limit(character),
        "max_skill_rating": MAX_SKILL_RATING_CREATE,
        "knowledge_budget_warning": budget_warning,
        "knowledge_error": error,
    }


@router.post("/ui/knowledge", response_class=HTMLResponse)
async def submit_knowledge(request: Request) -> HTMLResponse:
    session, new_cookie = resolve_session(request)
    session.current_page = "skills"  # WP61/WP97
    if session.character is None:
        context = _knowledge_selection_context(None, (), (), skills_letter=session.skills_letter)
    else:
        form = await request.form()
        # WP149: one row series for both kinds of skill, sorted into the engine's two lists.
        rows = _parse_rows(form)
        picks = _sort_rows(rows)
        previous = session.character
        error: str | Message | None = None
        if picks.duplicate is not None:
            error = Message.of("Web_Knowledge_DuplicateName", name=picks.duplicate)
        else:
            try:
                selection = create_knowledge_selection(
                    previous,
                    picks.knowledge_skills,
                    picks.languages,
                    picks.specializations,
                    active_points_left(previous, session.skills_letter),
                )
                karma_budget = previous.karma_remaining + (
                    previous.karma_knowledge_selection.karma_cost
                    if previous.karma_knowledge_selection is not None
                    else 0
                )
                karma_selection = create_karma_knowledge_selection(
                    replace(previous, knowledge_selection=selection),
                    picks.karma_points,
                    karma_budget,
                    picks.karma_specializations,
                )
            except ValueError as exc:
                error = str(exc)
            else:
                session.character = replace(
                    session.character,
                    knowledge_selection=selection,
                    karma_knowledge_selection=karma_selection,
                )
        context = _knowledge_selection_context(
            session.character,
            picks.knowledge_skills,
            picks.languages,
            picks.karma_points,
            picks.specializations,
            picks.karma_specializations,
            skills_letter=session.skills_letter,
            error=error,
            rows=rows,
            add_row=form.get("knowledge_add") is not None,
        )
    response = templates.TemplateResponse(request, "_knowledge_skills.html", context)
    set_session_cookie(request, response, new_cookie)
    return response
