"""Adept Powers chargen step: `POST /ui/powers` (WP29), gated to Adept only.

**WP62**: split out of the former `chummer5.web.app` -- see `spec/plan/phase-r-architecture-
cleanup.md`'s WP58 audit for the target shape this module is part of.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import replace
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from starlette.datastructures import FormData

from chummer5.data.powers import Power
from chummer5.engine.character import Character
from chummer5.engine.improvements import ImprovementSource
from chummer5.engine.magic import (
    PowerSelection,
    apply_power_improvements,
    create_power_selection,
    learned_skill_ratings,
    power_max_rating,
    power_target_options,
)
from chummer5.web.catalogs import MVP_POWERS, POWERS, SKILLS, templates
from chummer5.web.session import SESSION_COOKIE_NAME, resolve_session

router = APIRouter()


def _remove_adept_power_improvements(character: Character) -> None:
    """Remove every currently-held `ADEPT_POWER`-sourced Improvement from `character.improvements`.

    Each purchased power is its own source instance (`source_id` is the power's own id, per
    `apply_power_improvements`), so retracting "every power this character has" means one
    `remove_source` call per distinct id, not a single shared one the way the Talent free-skill
    grant's `MAGIC_SKILL_GRANT_SOURCE_ID` is. `character.improvements.improvements` is a snapshot
    tuple (see `ImprovementIndex`), so it's safe to iterate while `remove_source` mutates the
    underlying list -- the same pattern `chummer5.web.routes.qualities._replace_committed_qualities`
    already uses for `QUALITY`-sourced Improvements.
    """
    for imp in character.improvements.improvements:
        if imp.source_type == ImprovementSource.ADEPT_POWER:
            character.improvements.remove_source(ImprovementSource.ADEPT_POWER, imp.source_id)


def _replace_committed_powers(character: Character, selection: PowerSelection) -> Character:
    """Swap whatever `ADEPT_POWER`-sourced Improvements `character.improvements` currently holds
    for `selection`'s, and re-attach `selection` as `character.power_selection` -- mirrors
    `chummer5.web.routes.qualities._replace_committed_qualities`'s identical shape.
    """
    _remove_adept_power_improvements(character)
    apply_power_improvements(character, selection)
    return replace(character, power_selection=selection)


def _row_key(power_id: str, index: int) -> str:
    """A form row's key (WP119): the bare id for a power's first instance, `id:n` after that --
    the same convention the quality form uses (WP107), so a once-only power's field names are
    unchanged."""
    return power_id if index == 0 else f"{power_id}:{index}"


def _parse_power_picks(
    form: FormData, catalog: Iterable[Power]
) -> tuple[tuple[str, int, str | None], ...]:
    """Read `power_rating_{key}`/`power_target_{key}` fields off a submitted form into
    `create_power_selection`'s `(power_id, rating, target)` triples (WP29; per instance since
    WP119, see `_row_key`). `power_attribute_{key}` is WP29's name for the target field and is
    still read.

    A rating of 0 (the default for a power the player didn't touch) means "not purchased" -- the
    same "absence means 0" convention `chummer5.web.forms.parse_points` already established -- so
    it's simply omitted from the result rather than passed through as an invalid `rating < 1` pick.
    """
    by_id = {power.id: power for power in catalog}
    picks: list[tuple[str, int, str | None]] = []
    for raw_key in form.keys():
        if not str(raw_key).startswith("power_rating_"):
            continue
        key = str(raw_key).removeprefix("power_rating_")
        power_id = key.split(":", 1)[0]
        if power_id not in by_id:
            continue
        raw_rating = form.get(raw_key)
        try:
            rating = int(str(raw_rating)) if raw_rating is not None else 0
        except ValueError:
            rating = 0
        if rating <= 0:
            continue
        raw_target = form.get(f"power_target_{key}") or form.get(f"power_attribute_{key}")
        picks.append((power_id, rating, str(raw_target) if raw_target else None))
    return tuple(picks)


def _power_rows(
    picks: Iterable[tuple[str, int, str | None]], magic_rating: int
) -> list[dict[str, Any]]:
    """One row per power instance (WP119). A repeatable power gets a row per bought instance plus
    a blank "another" row, like a repeatable quality."""
    requests = list(picks)
    rows: list[dict[str, Any]] = []
    for power in MVP_POWERS:
        instances: list[tuple[str, int, str | None] | None] = [
            r for r in requests if r[0] == power.id
        ]
        if power.repeatable or not instances:
            instances.append(None)
        if not power.repeatable:
            instances = instances[:1]
        for index, instance in enumerate(instances):
            rows.append(
                {
                    "power": power,
                    "key": _row_key(power.id, index),
                    "rating": instance[1] if instance is not None else 0,
                    "target": instance[2] if instance is not None else None,
                    "target_kind": power.target_kind,
                    "target_options": power_target_options(power),
                    "max_rating": power_max_rating(power, magic_rating),
                    "another": power.repeatable and index > 0 and instance is None,
                }
            )
    return rows


def _power_selection_context(
    character: Character | None,
    picks: Iterable[tuple[str, int, str | None]],
    *,
    error: str | None = None,
) -> dict[str, Any]:
    """Context for `_power_selection.html` (WP29): WP27's `create_power_selection` reaching the
    browser, gated to Adept only. `picks` is whatever should be shown filled in -- the character's
    own committed `power_selection.picks` on a clean render, or the raw submitted `(power_id,
    rating, target)` triples on an error-echo render.
    """
    if character is None:
        return {"character": None, "power_error": error}
    if character.magic_type != "Adept":
        return {"character": character, "power_error": error}
    requests = list(picks)
    by_id = {power.id: power for power in MVP_POWERS}
    spent = sum(
        (
            by_id[power_id].points * rating + by_id[power_id].extra_point_cost
            for power_id, rating, _ in requests
            if power_id in by_id and rating > 0
        ),
        Decimal(0),
    )
    budget = character.power_points
    return {
        "character": character,
        "power_rows": _power_rows(requests, budget),
        "power_point_budget": budget,
        "power_points_spent": spent,
        "power_points_remaining": budget - spent,
        "power_budget_warning": _committed_power_warning(character) if error is None else None,
        "power_error": error,
    }


def _quality_names(character: Character) -> tuple[str, ...]:
    """WP119: every quality the character holds, for a power's `<forbidden>` check."""
    picked = character.quality_selection.qualities if character.quality_selection else ()
    return (*(p.quality.name for p in picked), *(q.name for q in character.metatype_qualities))


def _committed_power_warning(character: Character) -> str | None:
    """WP119: re-check the committed powers against the character as it is now -- Improved
    Ability's skill must still be known, and its levels still fit (the WP19 "no longer fits"
    path). Nothing raises; the reason is shown."""
    selection = character.power_selection
    if selection is None:
        return None
    try:
        create_power_selection(
            [(p.power.id, p.rating, p.target) for p in selection.picks],
            POWERS,
            character.power_points,
            learned_skill_ratings=learned_skill_ratings(character, SKILLS),
            quality_names=_quality_names(character),
        )
    except ValueError as exc:
        return str(exc)
    return None


@router.post("/ui/powers", response_class=HTMLResponse)
async def submit_powers(request: Request) -> HTMLResponse:
    session, new_cookie = resolve_session(request)
    session.current_page = "magic"  # WP61/WP97
    if session.character is None or session.character.magic_type != "Adept":
        context = _power_selection_context(session.character, ())
    else:
        form = await request.form()
        picks = _parse_power_picks(form, MVP_POWERS)
        try:
            selection = create_power_selection(
                picks,
                POWERS,
                session.character.power_points,
                learned_skill_ratings=learned_skill_ratings(session.character, SKILLS),
                quality_names=_quality_names(session.character),
            )
        except ValueError as exc:
            context = _power_selection_context(session.character, picks, error=str(exc))
        else:
            session.character = _replace_committed_powers(session.character, selection)
            context = _power_selection_context(session.character, picks)
    response = templates.TemplateResponse(request, "_power_selection.html", context)
    if new_cookie is not None:
        response.set_cookie(SESSION_COOKIE_NAME, new_cookie, httponly=True, samesite="lax")
    return response
