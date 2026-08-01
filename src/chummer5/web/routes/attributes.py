"""Attributes chargen step: `POST /ui/attributes` (WP15, widened by WP29/WP52).

**WP62**: split out of the former `chummer5.web.app` -- see `spec/plan/phase-r-architecture-
cleanup.md`'s WP58 audit for the target shape this module is part of.

**WP63**: `submit_attributes` now builds its new `Character` via `dataclasses.replace(previous,
...)`, the same shape `chummer5.web.routes.priorities.submit_priorities` has used since WP19,
instead of a fresh `create_character()` call. `create_character` is still called, but only to
*validate* the submitted `attribute_points` (it raises `ValueError` on an invalid spend, discarded
otherwise) -- its returned `Character` is no longer what gets built on. Since `replace()` carries
every untouched field (and, crucially, the already-populated `improvements` index) forward *by
reference*, every carried-forward selection's Improvements -- quality, Talent/tradition/power,
cyberware, bioware, Foci -- simply survive an attribute edit with no relink call needed for any of
them; only `_relink_metatype_qualities` (harmless either way; metatype is unchanged on this route)
and `_relink_contact_selection` (CHA can genuinely change here) still run, mirroring
`submit_priorities` exactly. See `spec/plan/phase-r-architecture-cleanup.md`'s Finding 2 for the
"repeated relink-call accretion" bug class this retires.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
from types import MappingProxyType
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from chummer5.engine.character import (
    ALLOCATABLE_ATTRIBUTES,
    ATTRIBUTE_KARMA_PER_RATING,
    PRIMARY_ATTRIBUTES,
    SPECIAL_ATTRIBUTES,
    Character,
    KarmaAttributeSelection,
    MetatypeChoice,
    create_character,
    create_karma_attribute_points,
    karma_advancement_cost,
)
from chummer5.engine.magic import create_magic_attribute_points
from chummer5.web.catalogs import PRIORITIES, templates
from chummer5.web.forms import parse_points
from chummer5.web.routes.contacts import _relink_contact_selection
from chummer5.web.routes.qualities import _relink_metatype_qualities
from chummer5.web.session import SESSION_COOKIE_NAME, resolve_session

router = APIRouter()


def _attribute_allocation_context(
    character: Character | None,
    attribute_points: Mapping[str, int],
    magic_points: int = 0,
    karma_points: Mapping[str, int] = MappingProxyType({}),
    *,
    error: str | None = None,
) -> dict[str, Any]:
    """Context for `_attribute_allocation.html`.

    `attribute_points` is whatever should be echoed in the form's inputs -- the character's own
    committed points on a clean render, or a raw (possibly invalid) submission being redisplayed
    after a validation error, mirroring WP14's "redisplay exactly what the player entered" choice
    for the priority form. The returned `character` is a *display* copy (`dataclasses.replace`
    with `attribute_points` swapped in) rather than a re-validated one -- `attribute_value()` still
    clamps to the metatype maximum, so an over-budget preview shows a sane capped number instead of
    raising, and the caller decides separately (via `create_character`) whether to actually commit
    the submission to the session.

    **Post-WP29 correction**: `magic_points` -- Special Attribute Points spent raising MAG beyond
    `character.magic_rating` -- is a *separate* parameter from `attribute_points`, not one more key
    inside it: `create_character` itself only ever validates `ALLOCATABLE_ATTRIBUTES` (still just
    the primary 8 + EDG; see `chummer5.engine.character.Character`'s own docstring correction for
    why MAG's allocatability is character-specific, not a fixed global set `create_character` could
    validate unconditionally). When `character.magic_type is not None`, a `"MAG"` row is appended
    to `attribute_rows` with the *same* shape every other row has (`code`/`minimum`/`maximum`/
    `points`/`value`) -- `_attribute_allocation.html` needs no template branching to render it,
    since `row.minimum`/`row.maximum` already give it the correct `max="{{ row.maximum -
    row.minimum }}"` headroom on the numeric input. Absent entirely for Mundane/uncommitted-Talent
    characters, mirroring the legacy `MAGEnabled` flag's "not just zero, not allocatable at all"
    gating.

    **WP52**: `karma_points` -- leftover-Karma-funded points on top of `attribute_points`, one more
    parameter alongside `magic_points` rather than folded into `attribute_points` (mirrors that
    same "separate pool, separate parameter" split) -- `ALLOCATABLE_ATTRIBUTES` only, MAG excluded
    (see `KarmaAttributeSelection`'s own docstring). Each row's `karma_points`/`value` reflect it;
    `row.maximum - row.minimum` is deliberately *not* widened for the Karma input's own `max=` --
    the metatype maximum is the same ceiling both pools share, `create_karma_attribute_points`
    itself is what rejects the combined total exceeding it, not the template.

    **WP19**: when `error` is unset (a clean render, not an echo of a submission this same request
    just rejected), re-runs `create_character` (and, when applicable, `create_magic_attribute_
    points`/`create_karma_attribute_points`) against `character`'s own current metatype/heritage/
    attributes/Talent state and `attribute_points`/`magic_points`/`karma_points`, purely to derive
    `attribute_budget_warning` from whatever `ValueError` either raises (discarding the exception
    itself, not its message) -- `submit_priorities` no longer resets a carried-forward spend that no
    longer fits a just-reconfirmed letter/metatype (see its own comment), so this is what surfaces
    that fact, freshly, on every render for as long as it stays true. Distinct from
    `attribute_error` (sourced from a `ValueError` raised by *this specific request's* submission,
    never stored) so a
    template can style "you just typed something invalid" differently from "this was fine when you
    entered it, but a priority change since then broke it."
    """
    if character is None:
        return {"character": None, "attribute_error": error}
    # WP52: the caller's own currently-committed Karma-attribute cost is added back onto `character
    # .karma_remaining` -- the same "exclude this section's own prior commitment" idiom WP51
    # established for Bound Spirits/Foci -- so re-validating what's already spent here doesn't
    # double-subtract it.
    karma_budget = character.karma_remaining + (
        character.karma_attribute_selection.karma_cost
        if character.karma_attribute_selection is not None
        else 0
    )
    karma_preview_cost = sum(
        karma_advancement_cost(
            character.attribute_range(code).minimum + attribute_points.get(code, 0),
            points,
            ATTRIBUTE_KARMA_PER_RATING,
        )
        for code, points in karma_points.items()
        if code in ALLOCATABLE_ATTRIBUTES and points > 0
    )
    display = replace(
        character,
        attribute_points=MappingProxyType(dict(attribute_points)),
        magic_attribute_points=magic_points,
        karma_attribute_selection=KarmaAttributeSelection(
            points=MappingProxyType(dict(karma_points)), karma_cost=karma_preview_cost
        ),
    )
    primary_budget = PRIORITIES.attributes[character.attributes_letter].points
    primary_spent = sum(attribute_points.get(code, 0) for code in PRIMARY_ATTRIBUTES)
    special_spent = sum(attribute_points.get(code, 0) for code in SPECIAL_ATTRIBUTES) + magic_points
    rows = [
        {
            "code": code,
            "minimum": display.attribute_range(code).minimum,
            "maximum": display.attribute_range(code).maximum,
            "points": attribute_points.get(code, 0),
            "karma_points": karma_points.get(code, 0),
            # WP81: two numbers, not one. `natural` is what the points above actually bought;
            # `value` is the augmented total. The template shows `natural (value)` -- the core
            # rulebook's own notation, p. 95: "Record augmentation ratings in parentheses next to
            # the natural attribute rating (e.g. Strength 4 (6) ...)" -- and collapses to a bare
            # number when they're equal, which is every character with no attribute augmentation.
            "natural": display.natural_attribute_value(code),
            "value": display.attribute_value(code),
        }
        for code in ALLOCATABLE_ATTRIBUTES
    ]
    if character.magic_type is not None:
        rows.append(
            {
                "code": "MAG",
                "minimum": character.magic_rating,
                "maximum": display.attribute_range("MAG").maximum,
                "points": magic_points,
                "karma_points": None,  # WP52: MAG is not Karma-allocatable, no input to render
                # MAG has no natural/augmented split (its `magaug` equals its `magmax` for every
                # SR5-core metatype) -- see `Character.natural_attribute_value`'s own docstring.
                "natural": display.attribute_value("MAG"),
                "value": display.attribute_value("MAG"),
            }
        )
    budget_warning: str | None = None
    if error is None:
        validation_choice = MetatypeChoice(
            character.metatype, character.special_attribute_points, karma=0
        )
        try:
            create_character(
                validation_choice,
                character.heritage_letter,
                character.attributes_letter,
                PRIORITIES,
                attribute_points,
            )
            if character.magic_type is not None:
                create_magic_attribute_points(
                    character.magic_type,
                    magic_points,
                    character.magic_rating,
                    character.attribute_range("MAG").maximum,
                    character.special_attribute_points,
                    attribute_points.get("EDG", 0),
                )
            create_karma_attribute_points(
                replace(character, attribute_points=MappingProxyType(dict(attribute_points))),
                karma_points,
                karma_budget,
            )
        except ValueError as exc:
            budget_warning = (
                f"No longer fits since priorities were last confirmed: {exc}. "
                "Adjust the points below to continue."
            )
    return {
        "character": display,
        "attribute_rows": rows,
        "primary_budget": primary_budget,
        "primary_remaining": primary_budget - primary_spent,
        "special_budget": character.special_attribute_points,
        "special_remaining": character.special_attribute_points - special_spent,
        # WP60: prefixed (not the generic "karma_budget"/"karma_remaining" this key used through
        # WP59) -- `_chargen_body_context` merges this dict together with `_skill_allocation_
        # context`'s and `_knowledge_selection_context`'s own, and all three used to return the
        # identical generic key, so whichever was merged last (Knowledge) silently clobbered the
        # other two's numbers on every full-page render. See spec/worklogs/WP60.md.
        "attribute_karma_budget": karma_budget,
        "attribute_karma_remaining": karma_budget - karma_preview_cost,
        "attribute_error": error,
        "attribute_budget_warning": budget_warning,
    }


@router.post("/ui/attributes", response_class=HTMLResponse)
async def submit_attributes(request: Request) -> HTMLResponse:
    session, new_cookie = resolve_session(request)
    session.open_section = "attribute-allocation"  # WP61
    if session.character is None:
        context = _attribute_allocation_context(None, {})
    else:
        form = await request.form()
        attribute_points = parse_points(form, ALLOCATABLE_ATTRIBUTES, "attr_")
        # WP52: Karma-funded points, a separate pool from the priority-derived one above --
        # `karma_attr_{code}` fields, same `ALLOCATABLE_ATTRIBUTES` set (MAG excluded).
        karma_points = parse_points(form, ALLOCATABLE_ATTRIBUTES, "karma_attr_")
        previous = session.character
        # Post-WP29 correction: MAG's own points (when allocatable at all -- see this section's
        # own comment below) are parsed and validated separately from `attribute_points`, since
        # `create_character` only ever validates `ALLOCATABLE_ATTRIBUTES` -- see `chummer5
        # .engine.character.Character`'s docstring correction for why MAG's allocatability is
        # character-specific rather than a fixed global set.
        magic_points = (
            parse_points(form, ("MAG",), "attr_").get("MAG", 0)
            if previous.magic_type is not None
            else 0
        )
        # `create_character` only needs `metatype`/`special_attribute_points` off a
        # `MetatypeChoice` (see its own docstring) -- both are already stable fields on the
        # session's committed `Character`, so there's no need to re-look-up the Heritage
        # priority/metatype catalog here the way `submit_priorities` does.
        choice = MetatypeChoice(
            metatype=previous.metatype,
            special_attribute_points=previous.special_attribute_points,
            karma=0,
        )
        # WP51: this section's own currently-committed Karma-attribute cost is added back onto
        # `previous.karma_remaining` -- the same "exclude this section's own prior commitment"
        # idiom `_spirit_selection_context`/`_foci_selection_context` already established --
        # so re-spending exactly what was already committed doesn't double-subtract it.
        karma_budget = previous.karma_remaining + (
            previous.karma_attribute_selection.karma_cost
            if previous.karma_attribute_selection is not None
            else 0
        )
        try:
            # WP63: `create_character` is called only to *validate* the submitted
            # `attribute_points` (raises `ValueError` on an invalid spend) -- its returned,
            # fresh-and-empty `Character` is discarded rather than built on; see `character`
            # below, which is `previous` with `attribute_points` swapped in instead.
            create_character(
                choice,
                session.heritage_letter,
                session.attributes_letter,
                PRIORITIES,
                attribute_points,
            )
            if previous.magic_type is not None:
                magic_points = create_magic_attribute_points(
                    previous.magic_type,
                    magic_points,
                    previous.magic_rating,
                    previous.attribute_range("MAG").maximum,
                    previous.special_attribute_points,
                    attribute_points.get("EDG", 0),
                )
            character = replace(previous, attribute_points=MappingProxyType(dict(attribute_points)))
            karma_attribute_selection = create_karma_attribute_points(
                character, karma_points, karma_budget
            )
        except ValueError as exc:
            context = _attribute_allocation_context(
                session.character,
                attribute_points,
                magic_points,
                karma_points,
                error=str(exc),
            )
        else:
            # WP63: `character` is `previous` with `attribute_points` swapped in via
            # `dataclasses.replace` -- every other field (skill_allocation, quality_selection,
            # contact_selection, resources_selection, lifestyle_selection, cyberware_selection,
            # bioware_selection, foci_selection, bound_spirit_selection, knowledge_selection,
            # karma_skill_selection, karma_knowledge_selection, magic_type/tradition/spell_
            # selection/power_selection, and -- crucially -- the already-populated `improvements`
            # index) carries forward *by reference*, with nothing to re-land. Only two things
            # still need an explicit recompute, mirroring `submit_priorities` (WP19) exactly:
            character = _relink_metatype_qualities(character)
            # metatype is unchanged on this route, so this is a harmless no-op today (see its own
            # docstring: safe/idempotent to call unconditionally regardless) -- kept for the same
            # reason submit_priorities keeps it, not because attribute edits ever change metatype.
            character = _relink_contact_selection(character, character.contact_selection)
            # CHA can genuinely change here (an EDG/CHA attribute-point reallocation), which
            # ContactSelection.free_points/karma_cost derive from.
            character = replace(
                character,
                magic_attribute_points=magic_points,
                karma_attribute_selection=karma_attribute_selection,
            )
            session.character = character
            context = _attribute_allocation_context(
                character, attribute_points, magic_points, karma_points
            )
    context["open_section"] = session.open_section  # WP61
    response = templates.TemplateResponse(request, "_attribute_allocation.html", context)
    if new_cookie is not None:
        response.set_cookie(SESSION_COOKIE_NAME, new_cookie, httponly=True, samesite="lax")
    return response
