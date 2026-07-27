"""Attributes chargen step: `POST /ui/attributes` (WP15, widened by WP29/WP52).

**WP62**: split out of the former `chummer5.web.app` -- see `spec/plan/phase-r-architecture-
cleanup.md`'s WP58 audit for the target shape this module is part of. Still the one route rebuilding
via `create_character()` fresh rather than `dataclasses.replace`-ing the previous `Character` in
place (see `chummer5.web.routes.priorities.submit_priorities` for the WP19 shape this route hasn't
adopted yet) -- WP63 is the follow-up that unifies it, per that phase file's Finding 2.
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
from chummer5.web.routes.cyberware import _relink_bioware_selection, _relink_cyberware_selection
from chummer5.web.routes.foci import _relink_foci_selection
from chummer5.web.routes.qualities import _relink_metatype_qualities, _relink_quality_improvements
from chummer5.web.routes.talent import _relink_magic_selection
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
            character = create_character(
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
            # See the identical comment in submit_priorities -- a fresh Character means fresh
            # skill_allocation/quality_selection/contact_selection/resources_selection/
            # lifestyle_selection (all `None`) and a fresh, empty ImprovementIndex. Unlike
            # submit_priorities, an attribute-point edit alone doesn't invalidate skill, gear,
            # or lifestyle spend (none depend on attribute points), so all three carry forward
            # by plain reference.
            character = _relink_quality_improvements(character, previous.quality_selection)
            # WP23: metatype is unchanged here, but the fresh `create_character()` call above
            # still needs metatype_qualities' Improvements re-landed onto its new, empty index.
            character = _relink_metatype_qualities(character)
            character = _relink_contact_selection(character, previous.contact_selection)
            # WP29: same reasoning -- Talent/tradition/free-skill-grant Improvements, and the
            # Adept power selection's own Improvements, need re-landing on this fresh index too,
            # or a Magician/Adept would silently reset to Mundane on the next attribute edit.
            # `magic_points` is *not* carried from `previous` here -- it's this same request's
            # own freshly-validated submission (the Attributes form is where MAG points are
            # spent, echoing whatever was already committed unless just edited).
            character = _relink_magic_selection(character, session.talent_letter, previous)
            # WP34: cyberware's Essence/bonus Improvements need the same re-landing as
            # quality/metatype/Talent above -- a fresh `create_character()` call always starts
            # `cyberware_selection` at `None` and `improvements` empty (see `_relink_cyberware_
            # selection`'s own docstring).
            character = _relink_cyberware_selection(character, previous.cyberware_selection)
            # WP45: bioware's Essence/bonus Improvements need the identical re-landing.
            character = _relink_bioware_selection(character, previous.bioware_selection)
            # WP47: Foci's FLAT_BONUS skill Improvements need the identical re-landing.
            character = _relink_foci_selection(character, previous.foci_selection)
            character = replace(
                character,
                skill_allocation=previous.skill_allocation,
                resources_selection=previous.resources_selection,
                lifestyle_selection=previous.lifestyle_selection,
                magic_attribute_points=magic_points,
                karma_attribute_selection=karma_attribute_selection,
                # WP46: carried forward by plain reference, same as lifestyle_selection above --
                # a bound spirit has no Improvement to re-land (see chummer5.engine.spirits'
                # module docstring), so there's no relink helper needed, just a plain carry.
                # `_spirit_selection_context`'s own WP19-style re-validation is what surfaces a
                # "no longer fits" warning if this attribute edit shrank CHA/MAG below what was
                # already committed.
                bound_spirit_selection=previous.bound_spirit_selection,
                # WP49: same plain-carry treatment -- Knowledge/Language has no Improvement of
                # its own to re-land either (it only *consumes* Bilingual's
                # NATIVE_LANGUAGE_LIMIT, already re-landed by `_relink_quality_improvements`
                # above). `_knowledge_selection_context`'s own WP19-style re-validation surfaces
                # a "no longer fits" warning if this attribute edit shrank INT/LOG below what
                # was already spent.
                knowledge_selection=previous.knowledge_selection,
                # WP53: same plain-carry treatment -- neither Karma-funded selection has an
                # Improvement of its own to re-land (a Karma-funded skill/specialization is a
                # pure rating increase, not an Improvement -- see chummer5.engine.skills' own
                # WP53 paragraph), and neither depends on an attribute value, only on
                # skill_allocation/knowledge_selection, both already carried forward above.
                karma_skill_selection=previous.karma_skill_selection,
                karma_knowledge_selection=previous.karma_knowledge_selection,
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
