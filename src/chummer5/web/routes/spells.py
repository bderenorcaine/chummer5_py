"""Spells chargen step: `POST /ui/spells` (WP29), gated to Magician only.

**WP62**: split out of the former `chummer5.web.app` -- see `spec/plan/phase-r-architecture-
cleanup.md`'s WP58 audit for the target shape this module is part of.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import replace
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from chummer5.engine.character import Character
from chummer5.engine.magic import KARMA_PER_SPELL, create_spell_selection, offered_talent_options
from chummer5.web.catalogs import PRIORITIES, SPELLS, templates
from chummer5.web.session import SESSION_COOKIE_NAME, resolve_session

router = APIRouter()


def _spell_selection_context(
    character: Character | None,
    talent_letter: str,
    spell_ids: Iterable[str],
    *,
    error: str | None = None,
) -> dict[str, Any]:
    """Context for `_spell_selection.html` (WP29): WP26's `create_spell_selection` reaching the
    browser, gated to Magician only (see `_chargen_body.html`'s own gating note). `spell_ids` is
    whatever should be shown checked, same echo-the-submission shape as `_quality_selection_
    context`'s `quality_ids`.

    **WP54**: `spell_karma_budget` is `character.karma_remaining` with this section's own
    currently-committed cost added back in -- the same "exclude this section's own prior
    commitment" idiom `_spirit_selection_context`/`_foci_selection_context` already use. The
    Karma-funded spell count/cost for `spell_ids` (which may be a raw, not-yet-committed submission)
    is computed directly (`max(0, len(ids) - budget) * KARMA_PER_SPELL`) rather than by calling
    `create_spell_selection` -- the formula is a flat per-item rate with no group-breaking-style
    state to get wrong, unlike `_skill_allocation_context`'s reason for calling the real function.

    **WP19-style staleness re-validation**, mirroring `_spirit_selection_context`'s identical
    pattern: when `error` is unset and a `spell_selection` is already committed, re-runs `create_
    spell_selection` against the character's *current* state purely to derive `spell_budget_
    warning`. A committed spell_selection is carried forward unchanged by `submit_attributes`
    (a plain `dataclasses.replace`-carried field, since WP63), so an attribute-form edit that
    lowers Special-Attribute-Point-funded MAG (shrinking the Magic-Rating-x2 known cap) or spends
    more Karma elsewhere (shrinking
    `karma_remaining`) can each make a previously-valid spell_selection no longer fit -- surfaced
    here rather than silently left inconsistent, the same "surface, don't silently reset" rule
    WP19 established generally.
    """
    if character is None:
        return {"character": None, "spell_error": error}
    if character.magic_type != "Magician":
        return {"character": character, "spell_error": error}
    magician_option = next(
        (o for o in offered_talent_options(talent_letter, PRIORITIES) if o.codename == "Magician"),
        None,
    )
    budget = (magician_option.spells or 0) if magician_option is not None else 0
    magic_rating = character.attribute_value("MAG")
    max_known = magic_rating * 2
    own_committed_cost = (
        character.spell_selection.karma_cost if character.spell_selection is not None else 0
    )
    karma_budget = character.karma_remaining + own_committed_cost
    ids = set(spell_ids)
    rows = [{"spell": spell, "selected": spell.id in ids} for spell in SPELLS]
    karma_spell_count = max(0, len(ids) - budget)
    karma_cost = karma_spell_count * KARMA_PER_SPELL
    budget_warning: str | None = None
    if error is None and character.spell_selection is not None:
        try:
            create_spell_selection(
                [spell.id for spell in character.spell_selection.spells],
                SPELLS,
                budget,
                magic_rating,
                karma_budget,
            )
        except ValueError as exc:
            budget_warning = (
                f"No longer fits since priorities/attributes were last confirmed: {exc}. "
                "Reconfirm spells below to continue."
            )
    return {
        "character": character,
        "spell_rows": rows,
        "spell_budget": budget,
        "spells_selected": len(ids),
        "spells_remaining": max(budget - len(ids), 0),
        "spell_max_known": max_known,
        "spell_karma_cost": karma_cost,
        "spell_karma_budget": karma_budget,
        "spell_karma_remaining": karma_budget - karma_cost,
        "spell_error": error,
        "spell_budget_warning": budget_warning,
    }


@router.post("/ui/spells", response_class=HTMLResponse)
async def submit_spells(request: Request) -> HTMLResponse:
    session, new_cookie = resolve_session(request)
    session.open_section = "spell-selection"  # WP61
    if session.character is None or session.character.magic_type != "Magician":
        context = _spell_selection_context(session.character, session.talent_letter, ())
    else:
        form = await request.form()
        spell_ids = [str(v) for v in form.getlist("spell_id")]
        magician_option = next(
            (
                o
                for o in offered_talent_options(session.talent_letter, PRIORITIES)
                if o.codename == "Magician"
            ),
            None,
        )
        budget = (magician_option.spells or 0) if magician_option is not None else 0
        # WP54: same "add this section's own currently-committed cost back onto karma_
        # remaining" idiom every other Karma-spending submit_* handler uses.
        own_committed_cost = (
            session.character.spell_selection.karma_cost
            if session.character.spell_selection is not None
            else 0
        )
        karma_budget = session.character.karma_remaining + own_committed_cost
        try:
            selection = create_spell_selection(
                spell_ids,
                SPELLS,
                budget,
                session.character.attribute_value("MAG"),
                karma_budget,
            )
        except ValueError as exc:
            context = _spell_selection_context(
                session.character, session.talent_letter, spell_ids, error=str(exc)
            )
        else:
            session.character = replace(session.character, spell_selection=selection)
            context = _spell_selection_context(
                session.character, session.talent_letter, spell_ids
            )
    context["open_section"] = session.open_section  # WP61
    response = templates.TemplateResponse(request, "_spell_selection.html", context)
    if new_cookie is not None:
        response.set_cookie(SESSION_COOKIE_NAME, new_cookie, httponly=True, samesite="lax")
    return response
