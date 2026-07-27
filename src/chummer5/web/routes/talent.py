"""Talent (Magic-type/tradition/free-skill-grant) chargen step: `POST /ui/talent` and its
`GET /ui/talent-options` refresh fragment (WP29).

**WP62**: split out of the former `chummer5.web.app` -- see `spec/plan/phase-r-architecture-
cleanup.md`'s WP58 audit for the target shape this module is part of.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from chummer5.engine.character import Character
from chummer5.engine.improvements import ImprovementSource
from chummer5.engine.magic import (
    MAGIC_SKILL_GRANT_SOURCE_ID,
    MagicSelection,
    apply_magic_skill_grant_improvements,
    apply_power_improvements,
    create_magic_selection,
    magic_skill_grant_eligible_skills,
    offered_talent_options,
)
from chummer5.io.save_format import DEFAULT_TALENT_CODENAME
from chummer5.web.catalogs import PRIORITIES, SKILLS, TRADITIONS, templates
from chummer5.web.routes.foci import _remove_foci_improvements
from chummer5.web.routes.powers import _remove_adept_power_improvements
from chummer5.web.routes.qualities import _strip_mentor_spirit_selection
from chummer5.web.session import SESSION_COOKIE_NAME, resolve_session

router = APIRouter()


def _default_talent_codename(talent_letter: str) -> str:
    """The codename a fresh (or not-yet-visited) Talent section pre-fills for `talent_letter` --
    its first offered option (`"Mundane"` at letter E, since no other A-D letter offers one -- see
    `chummer5.web.session`'s own docstring), the same "starts at a legal, harmless default"
    precedent `chummer5.web.catalogs.DEFAULT_LIFESTYLE_TIER_NAME` et al. already set.
    """
    options = offered_talent_options(talent_letter, PRIORITIES)
    return options[0].codename if options else DEFAULT_TALENT_CODENAME


def _talent_selection_context(
    character: Character | None,
    talent_letter: str,
    talent_codename: str,
    tradition_id: str | None,
    granted_skill_ids: tuple[str, ...],
    *,
    error: str | None = None,
) -> dict[str, Any]:
    """Context for `_talent_selection.html` (WP29): Phase I's Magic-type/tradition/free-skill-grant
    selection reaching the browser, echo-the-submission shaped like every other chargen form here.
    `talent_codename`/`tradition_id`/`granted_skill_ids` are whatever should be shown selected --
    the character's own committed values on a clean render, or the raw submitted form values on an
    error-echo render, mirroring `chummer5.web.routes.qualities._quality_selection_context`'s
    identical `quality_ids` parameter.

    **WP19-style staleness re-validation**: when `error` is unset and a Talent selection is already
    committed (`character.magic_type is not None`), re-runs `create_magic_selection` against the
    *current* `talent_letter` purely to derive `talent_budget_warning` -- a priorities
    reconfirmation can change which letter Talent sits on, or which options that letter even offers,
    the same way it can shrink an attribute/skill/resources budget (see
    `chummer5.web.routes.attributes._attribute_allocation_context`'s identical pattern).
    """
    if character is None:
        return {"character": None, "talent_error": error}
    options = offered_talent_options(talent_letter, PRIORITIES)
    selected_option = next((o for o in options if o.codename == talent_codename), None)
    eligible_skills = (
        magic_skill_grant_eligible_skills(selected_option, SKILLS)
        if selected_option is not None
        else ()
    )
    budget_warning: str | None = None
    if error is None and character.magic_type is not None:
        try:
            create_magic_selection(
                talent_letter,
                character.magic_type,
                character.tradition.id if character.tradition is not None else None,
                character.magic_granted_skill_ids,
                PRIORITIES,
                TRADITIONS,
                SKILLS,
            )
        except ValueError as exc:
            budget_warning = (
                f"No longer fits since priorities were last confirmed: {exc}. "
                "Reconfirm Talent below to continue."
            )
    return {
        "character": character,
        "talent_letter": talent_letter,
        "talent_letter_name": PRIORITIES.talent[talent_letter].name,
        "talent_options": options,
        "selected_codename": talent_codename,
        "traditions": TRADITIONS,
        "selected_tradition_id": tradition_id,
        "eligible_skills": eligible_skills,
        "selected_skill_ids": set(granted_skill_ids),
        "skill_qty": selected_option.skill_qty if selected_option is not None else None,
        "talent_error": error,
        "talent_budget_warning": budget_warning,
    }


def _relink_magic_selection(
    character: Character, talent_letter: str, previous: Character
) -> Character:
    """Re-apply a carried-forward Talent selection's free-skill-grant Improvements (and a carried-
    forward Adept power selection's Improvements) onto a freshly built `Character`, and re-attach
    `magic_type`/`magic_rating`/`tradition`/`magic_granted_skill_ids`/`spell_selection`/
    `power_selection` themselves.

    Mirrors `chummer5.web.routes.qualities._relink_quality_improvements`/
    `_relink_metatype_qualities`: `create_character()` always starts every one of those fields at
    its Mundane/unset default and a brand-new, empty `ImprovementIndex` (see that function's
    docstring) -- `submit_attributes` is the one route that still rebuilds this way (WP19 left it
    that way; see its own worklog), so without this helper a Magician/Adept's entire Talent
    selection would silently reset to Mundane on the very next attribute-point edit.

    Re-derives the Talent selection via `create_magic_selection` (using `talent_letter` -- the
    session's *current* one, not necessarily whatever letter was in effect when `previous` was
    built) rather than trusting `previous`'s own snapshot, the same "recompute, don't just
    re-attach" reasoning `chummer5.web.routes.contacts._relink_contact_selection` already uses --
    `Character` has no field for the free-skill grant's *rating* (only the granted skill *ids*), so
    the rating has to be re-resolved from the matched Talent option regardless. Safe to call
    unconditionally: a no-op if `previous.magic_type is None` (still Mundane, nothing to carry).
    """
    if previous.magic_type is None:
        return character
    selection = create_magic_selection(
        talent_letter,
        previous.magic_type,
        previous.tradition.id if previous.tradition is not None else None,
        previous.magic_granted_skill_ids,
        PRIORITIES,
        TRADITIONS,
        SKILLS,
    )
    apply_magic_skill_grant_improvements(character, selection, SKILLS)
    character = replace(
        character,
        magic_type=selection.magic_type,
        magic_rating=selection.magic_rating,
        tradition=selection.tradition,
        magic_granted_skill_ids=selection.granted_skill_ids,
        spell_selection=previous.spell_selection,
        power_selection=previous.power_selection,
    )
    if previous.power_selection is not None:
        apply_power_improvements(character, previous.power_selection)
    return character


def _replace_committed_talent(character: Character, selection: MagicSelection) -> Character:
    """Swap whatever `TALENT`-sourced free-skill-grant Improvement `character.improvements`
    currently holds for `selection`'s, and re-attach the 4 flat magic fields.

    A (re)confirmed Talent selection also resets `spell_selection`/`power_selection`/`bound_spirit_
    selection`/`foci_selection` to `None` and drops any `ADEPT_POWER`-/`FOCUS`-sourced Improvements
    -- a changed archetype (Mundane -> Magician, Magician -> Adept, or even a changed
    tradition/letter) invalidates whatever spell/power/spirit/Foci budget those selections were
    validated against (a changed tradition in particular changes which spirit types are even
    offered -- see `chummer5.engine.spirits.offered_spirit_types`; a changed Magic rating changes
    Foci's own count/Force caps -- see `chummer5.engine.foci`), and there is no sensible partial-
    carry-forward the way there is for e.g. attribute points against a resized budget (see this WP's
    worklog for the full reasoning). The player re-picks spells/powers/spirits/foci after any Talent
    change, the same "start that stage over" behavior a metatype swap already gives
    `skill_allocation` et al. pre-WP19 -- Talent is foundational in the same way, just narrower in
    what it resets.

    **Post-WP29 correction**: `magic_attribute_points` resets to `0` for the identical reason --
    a changed `magic_rating` (different letter/codename) changes how much headroom is even left to
    spend, so whatever was previously spent can't be blindly carried forward; the player re-spends
    from the Attributes section after any Talent change, same as spells/powers.

    **WP48**: `quality_selection`'s Mentor Spirit portion (if any) gets the identical "reset on any
    Talent (re)confirmation" treatment via `_strip_mentor_spirit_selection`, applied surgically
    rather than wholesale -- see that function's own docstring for why `quality_selection` as a
    whole can't just be reset to `None` the way spells/powers/spirits/foci are.
    """
    character.improvements.remove_source(ImprovementSource.TALENT, MAGIC_SKILL_GRANT_SOURCE_ID)
    _remove_adept_power_improvements(character)
    _remove_foci_improvements(character)
    quality_selection = _strip_mentor_spirit_selection(character, character.quality_selection)
    apply_magic_skill_grant_improvements(character, selection, SKILLS)
    return replace(
        character,
        magic_type=selection.magic_type,
        magic_rating=selection.magic_rating,
        tradition=selection.tradition,
        magic_granted_skill_ids=selection.granted_skill_ids,
        spell_selection=None,
        power_selection=None,
        bound_spirit_selection=None,
        foci_selection=None,
        magic_attribute_points=0,
        quality_selection=quality_selection,
    )


@router.get("/ui/talent-options", response_class=HTMLResponse)
def talent_options_fragment(
    request: Request, talent_letter: str, talent_codename: str
) -> HTMLResponse:
    """WP29: mirrors `chummer5.web.routes.priorities.metatype_options_fragment` -- refreshes the
    tradition dropdown and free-skill-grant checkboxes inside `_talent_selection.html` when the
    player picks a different Talent codename, without a full-page/full-body round trip. Unlike the
    metatype fragment, this one is triggered by the codename radio group *inside* `_talent_selection
    .html` itself, not by the Talent letter selector in `_priority_form.html` -- changing the
    letter there only takes effect (and refreshes which codenames are even offered) once the
    priority form is actually submitted, the same "no live cross-section refresh" scope boundary
    WP20 already documented for gear/Lifestyle.
    """
    options = offered_talent_options(talent_letter, PRIORITIES)
    option = next((o for o in options if o.codename == talent_codename), None)
    eligible_skills = (
        magic_skill_grant_eligible_skills(option, SKILLS) if option is not None else ()
    )
    context: dict[str, Any] = {
        "selected_codename": talent_codename,
        "traditions": TRADITIONS,
        "selected_tradition_id": None,
        "eligible_skills": eligible_skills,
        "selected_skill_ids": set(),
        "skill_qty": option.skill_qty if option is not None else None,
    }
    return templates.TemplateResponse(request, "_talent_options.html", context)


@router.post("/ui/talent", response_class=HTMLResponse)
async def submit_talent(request: Request) -> HTMLResponse:
    session, new_cookie = resolve_session(request)
    session.open_section = "talent-selection"  # WP61
    if session.character is None:
        context = _talent_selection_context(None, session.talent_letter, "Mundane", None, ())
    else:
        form = await request.form()
        talent_codename = str(form.get("talent_codename") or "")
        raw_tradition_id = form.get("tradition_id")
        tradition_id = str(raw_tradition_id) if raw_tradition_id else None
        granted_skill_ids = tuple(str(v) for v in form.getlist("granted_skill_id"))
        try:
            selection = create_magic_selection(
                session.talent_letter,
                talent_codename,
                tradition_id,
                granted_skill_ids,
                PRIORITIES,
                TRADITIONS,
                SKILLS,
            )
        except ValueError as exc:
            context = _talent_selection_context(
                session.character,
                session.talent_letter,
                talent_codename,
                tradition_id,
                granted_skill_ids,
                error=str(exc),
            )
        else:
            session.character = _replace_committed_talent(session.character, selection)
            context = _talent_selection_context(
                session.character,
                session.talent_letter,
                selection.magic_type or "Mundane",
                tradition_id,
                selection.granted_skill_ids,
            )
    context["open_section"] = session.open_section  # WP61
    response = templates.TemplateResponse(request, "_talent_selection.html", context)
    if new_cookie is not None:
        response.set_cookie(SESSION_COOKIE_NAME, new_cookie, httponly=True, samesite="lax")
    return response
