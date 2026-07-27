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
from chummer5.engine.magic import PowerSelection, apply_power_improvements, create_power_selection
from chummer5.web.catalogs import MVP_POWERS, POWERS, templates
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


def _parse_power_picks(
    form: FormData, catalog: Iterable[Power]
) -> tuple[tuple[str, int, str | None], ...]:
    """Read `power_rating_{id}`/`power_attribute_{id}` fields off a submitted form into
    `create_power_selection`'s own `(power_id, rating, selected_attribute)` triple shape (WP29).

    A rating of 0 (the default for a power the player didn't touch) means "not purchased" -- the
    same "absence means 0" convention `chummer5.web.forms.parse_points` already established -- so
    it's simply omitted from the result rather than passed through as an invalid `rating < 1` pick.
    """
    picks: list[tuple[str, int, str | None]] = []
    for power in catalog:
        raw_rating = form.get(f"power_rating_{power.id}")
        try:
            rating = int(str(raw_rating)) if raw_rating is not None else 0
        except ValueError:
            rating = 0
        if rating <= 0:
            continue
        raw_attribute = form.get(f"power_attribute_{power.id}")
        selected_attribute = str(raw_attribute) if raw_attribute else None
        picks.append((power.id, rating, selected_attribute))
    return tuple(picks)


def _power_selection_context(
    character: Character | None,
    picks: Iterable[tuple[str, int, str | None]],
    *,
    error: str | None = None,
) -> dict[str, Any]:
    """Context for `_power_selection.html` (WP29): WP27's `create_power_selection` reaching the
    browser, gated to Adept only. `picks` is whatever should be shown filled in -- the character's
    own committed `power_selection.picks` on a clean render, or the raw submitted `(power_id,
    rating, selected_attribute)` triples on an error-echo render.
    """
    if character is None:
        return {"character": None, "power_error": error}
    if character.magic_type != "Adept":
        return {"character": character, "power_error": error}
    picked = {power_id: (rating, attribute) for power_id, rating, attribute in picks}
    rows = []
    spent = Decimal(0)
    for power in MVP_POWERS:
        rating, selected_attribute = picked.get(power.id, (0, None))
        select_attribute_bonus = next(
            (fb for fb in power.flat_bonuses if fb.target_kind == "select_attribute"), None
        )
        rows.append(
            {
                "power": power,
                "rating": rating,
                "selected_attribute": selected_attribute,
                "attribute_options": (
                    select_attribute_bonus.attribute_options
                    if select_attribute_bonus is not None
                    else ()
                ),
            }
        )
        if rating > 0:
            spent += power.points * rating
    budget = character.power_points
    return {
        "character": character,
        "power_rows": rows,
        "power_point_budget": budget,
        "power_points_spent": spent,
        "power_points_remaining": budget - spent,
        "power_error": error,
    }


@router.post("/ui/powers", response_class=HTMLResponse)
async def submit_powers(request: Request) -> HTMLResponse:
    session, new_cookie = resolve_session(request)
    session.open_section = "power-selection"  # WP61
    if session.character is None or session.character.magic_type != "Adept":
        context = _power_selection_context(session.character, ())
    else:
        form = await request.form()
        picks = _parse_power_picks(form, MVP_POWERS)
        try:
            selection = create_power_selection(picks, POWERS, session.character.power_points)
        except ValueError as exc:
            context = _power_selection_context(session.character, picks, error=str(exc))
        else:
            session.character = _replace_committed_powers(session.character, selection)
            context = _power_selection_context(session.character, picks)
    context["open_section"] = session.open_section  # WP61
    response = templates.TemplateResponse(request, "_power_selection.html", context)
    if new_cookie is not None:
        response.set_cookie(SESSION_COOKIE_NAME, new_cookie, httponly=True, samesite="lax")
    return response
