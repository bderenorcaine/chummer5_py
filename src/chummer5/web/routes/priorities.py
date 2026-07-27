"""Priorities/metatype chargen step: `GET /`, `GET /ui/metatypes`, `POST /ui/priorities` (WP14,
widened by WP24/WP44).

**WP62**: split out of the former `chummer5.web.app` -- see `spec/plan/phase-r-architecture-
cleanup.md`'s WP58 audit for the target shape this module is part of. Also hosts
`_chargen_body_context`, the cross-cutting aggregator that composes every other step module's own
context builder into one dict for the full-page/full-body render -- `index`/`submit_priorities` are
its only two callers (see the WP58 audit's own note on why this and `_character_sheet_context` are
the two genuine cross-cutting aggregators, not step-scoped context builders).
"""

from __future__ import annotations

from dataclasses import replace
from types import MappingProxyType
from typing import Any

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse

from chummer5.engine.build_method import (
    PRIORITY_BUILD_METHOD,
    SUM_TO_TEN_BUILD_METHOD,
    SUM_TO_TEN_TARGET,
    SUPPORTED_BUILD_METHODS,
    sum_to_ten_total,
    validate_sum_to_ten_total,
)
from chummer5.engine.character import Character, metatype_choices
from chummer5.engine.improvements import ImprovementIndex
from chummer5.web.catalogs import (
    DEFAULT_LIFESTYLE_MONTHS,
    DEFAULT_LIFESTYLE_TIER_NAME,
    METATYPES,
    PRIORITIES,
    templates,
)
from chummer5.web.routes.attributes import _attribute_allocation_context
from chummer5.web.routes.contacts import _contacts_context, _relink_contact_selection
from chummer5.web.routes.cyberware import _cyberware_context
from chummer5.web.routes.foci import _foci_selection_context
from chummer5.web.routes.knowledge import _knowledge_selection_context
from chummer5.web.routes.lifestyle import _lifestyle_context
from chummer5.web.routes.powers import _power_selection_context
from chummer5.web.routes.qualities import _quality_selection_context, _relink_metatype_qualities
from chummer5.web.routes.resources import _resources_context
from chummer5.web.routes.skills import _skill_allocation_context
from chummer5.web.routes.spells import _spell_selection_context
from chummer5.web.routes.spirits import _spirit_selection_context
from chummer5.web.routes.talent import _default_talent_codename, _talent_selection_context
from chummer5.web.session import (
    PRIORITY_LETTERS,
    SESSION_COOKIE_NAME,
    ChargenSession,
    resolve_session,
)

router = APIRouter()


def _priority_form_context(
    *,
    heritage_letter: str,
    attributes_letter: str,
    skills_letter: str,
    resources_letter: str,
    talent_letter: str,
    build_method: str,
    metatype_id: str | None,
    character: object,
    error: str | None,
) -> dict[str, Any]:
    """Context for `_priority_form.html`'s own fields (letters, metatype options, the
    duplicate-letter/unoffered-metatype `error`). Always passed through `_chargen_body_context`
    before being rendered, which folds in one more key this function doesn't set itself:
    `priority_stale_selections` (WP19) -- see that function's docstring for why it's computed
    there instead of here.

    **WP44**: `build_method` selects which validity rule `submit_priorities` applies to the same 5
    letters (Priority's bijection, or Sum-to-Ten's repeats-allowed/sum-to-10 rule) -- it doesn't
    change which letters are offered per category (both rules draw from the same A-E range every
    category already offers). `sum_to_ten_total` is computed unconditionally (cheap, and never
    raises for a merely-off-target combination -- see `chummer5.engine.build_method
    .sum_to_ten_total`'s own docstring) so the template can show a live "X/10" readout the moment
    Sum-to-Ten is selected, without a dedicated fragment endpoint; it's simply not displayed when
    `build_method == PRIORITY_BUILD_METHOD`.

    **WP24**: `talent_letter` is a real 5th field a player assigns a letter to, alongside the
    other four -- `letters`/the duplicate-letter check both widen from a 4-way to a 5-way
    permutation of `PRIORITY_LETTERS` (now A-E, see `chummer5.web.session`'s docstring) to match.
    Its chosen *letter* is echoed here like any other selection, but its *option* is not resolved
    here at all: `submit_priorities` always builds `Character` (indirectly, via `create_character`)
    against `priorities.mundane_talent()` -- letter E's own "Mundane" option -- regardless of which
    letter Talent actually landed on. This is deliberate, not an oversight: `priorities.xml` only
    ever lists a "Mundane" option under letter E (A-D's Talent lists are all real magic/resonance
    archetypes -- Magician, Adept, Technomancer, ... -- confirmed via direct inspection), so there
    is no other Mundane-compatible option this WP could resolve to even if it tried. Letting the
    player assign Talent any letter *now* (rather than only once WP25 adds real archetype picking)
    is what proves the letter-assignment plumbing works before anything meaningful depends on it --
    the same "prove the shape before it does anything" sequencing WP14 used for
    metatype+priority-letter assignment ahead of WP15's spend logic.
    """
    heritage = PRIORITIES.heritage.get(heritage_letter)
    metatype_options = metatype_choices(heritage, METATYPES) if heritage is not None else ()
    try:
        current_sum_to_ten_total = sum_to_ten_total(
            (heritage_letter, talent_letter, attributes_letter, skills_letter, resources_letter)
        )
    except ValueError:
        # Can't happen from the template's own A-E dropdowns, but a hand-crafted POST could send
        # anything -- fall back to a display-only 0 rather than letting this context builder itself
        # raise (the real validating call, `validate_sum_to_ten_total` in `submit_priorities`,
        # already turns that same bad input into the visible `error` this context also carries).
        current_sum_to_ten_total = 0
    return {
        "letters": PRIORITY_LETTERS,
        "heritage_priorities": PRIORITIES.heritage,
        "attributes_priorities": PRIORITIES.attributes,
        "skills_priorities": PRIORITIES.skills,
        "resources_priorities": PRIORITIES.resources,
        "talent_priorities": PRIORITIES.talent,
        "metatype_options": metatype_options,
        "build_methods": SUPPORTED_BUILD_METHODS,
        "priority_build_method": PRIORITY_BUILD_METHOD,
        "sum_to_ten_build_method": SUM_TO_TEN_BUILD_METHOD,
        "sum_to_ten_total": current_sum_to_ten_total,
        "sum_to_ten_target": SUM_TO_TEN_TARGET,
        "selected": {
            "heritage_letter": heritage_letter,
            "attributes_letter": attributes_letter,
            "skills_letter": skills_letter,
            "resources_letter": resources_letter,
            "talent_letter": talent_letter,
            "build_method": build_method,
            "metatype_id": metatype_id,
        },
        "character": character,
        "error": error,
    }


def _chargen_body_context(session: ChargenSession, priority_ctx: dict[str, Any]) -> dict[str, Any]:
    """Merge the priority-form context with a clean (non-error) render of every other chargen
    section, reflecting the session's currently committed state. Used by both `GET /` and a
    successful `POST /ui/priorities` (the places that render every section at once).

    **WP19**: also folds a `priority_stale_selections` flag into `priority_ctx` -- `True` if any of
    the attribute/skill/resources sections below just reported their own `*_budget_warning` (see
    those context builders), i.e. the currently-committed spend no longer fits the currently-
    confirmed priorities. Computed here, once, from the same three sub-context calls this function
    already has to make, rather than inside `_priority_form_context` itself (which would mean
    either duplicating those three `create_*` re-validation calls a second time, or restructuring
    both of its call sites to compute them first and pass the flag in) -- `_priority_form.html` is
    only ever rendered from this merged dict (see both call sites below), so it reads
    `priority_stale_selections` like any other key regardless of which function actually set it.

    **WP29** folds in `_talent_selection_context`/`_spell_selection_context`/`_power_selection_
    context` the same way, including `talent_budget_warning` into the `priority_stale_selections`
    aggregate above -- a priorities reconfirmation can move Talent to a letter that no longer offers
    the committed codename/tradition, the same "no longer fits" staleness every other carried-
    forward selection can hit.
    """
    character = session.character
    # WP29: Talent/tradition/free-skill-grant, spells, and powers -- computed first since Talent is
    # SR5's own "Step Three," ahead of Attributes/Skills, and the other two depend on `magic_type`.
    talent_codename = (
        character.magic_type
        if character is not None and character.magic_type is not None
        else _default_talent_codename(session.talent_letter)
    )
    tradition_id = (
        character.tradition.id
        if character is not None and character.tradition is not None
        else None
    )
    granted_skill_ids = character.magic_granted_skill_ids if character is not None else ()
    talent_ctx = _talent_selection_context(
        character, session.talent_letter, talent_codename, tradition_id, granted_skill_ids
    )
    spell_ids = (
        tuple(spell.id for spell in character.spell_selection.spells)
        if character is not None and character.spell_selection is not None
        else ()
    )
    spell_ctx = _spell_selection_context(character, session.talent_letter, spell_ids)
    power_picks = (
        tuple(
            (pick.power.id, pick.rating, pick.selected_attribute)
            for pick in character.power_selection.picks
        )
        if character is not None and character.power_selection is not None
        else ()
    )
    power_ctx = _power_selection_context(character, power_picks)
    spirit_picks = (
        tuple(
            (spirit.spirit_type, spirit.services)
            for spirit in character.bound_spirit_selection.spirits
        )
        if character is not None and character.bound_spirit_selection is not None
        else ()
    )
    foci_picks = (
        tuple((pick.focus.id, pick.force) for pick in character.foci_selection.picks)
        if character is not None and character.foci_selection is not None
        else ()
    )
    spirit_ctx = _spirit_selection_context(character, spirit_picks)
    attribute_points = character.attribute_points if character is not None else {}
    magic_points = character.magic_attribute_points if character is not None else 0
    karma_attribute_points = (
        character.karma_attribute_selection.points
        if character is not None and character.karma_attribute_selection is not None
        else {}
    )
    attribute_ctx = _attribute_allocation_context(
        character, attribute_points, magic_points, karma_attribute_points
    )
    allocation = character.skill_allocation if character is not None else None
    skill_points = allocation.skill_points if allocation is not None else {}
    group_points = allocation.group_points if allocation is not None else {}
    specializations = allocation.specializations if allocation is not None else {}
    karma_skill_selection = character.karma_skill_selection if character is not None else None
    karma_skill_points = (
        karma_skill_selection.skill_points if karma_skill_selection is not None else {}
    )
    karma_group_points = (
        karma_skill_selection.group_points if karma_skill_selection is not None else {}
    )
    karma_specializations = (
        karma_skill_selection.specializations if karma_skill_selection is not None else {}
    )
    skill_ctx = _skill_allocation_context(
        character,
        session.skills_letter,
        skill_points,
        group_points,
        specializations,
        karma_skill_points,
        karma_group_points,
        karma_specializations,
    )
    knowledge_selection = character.knowledge_selection if character is not None else None
    knowledge_skills = (
        knowledge_selection.knowledge_skills if knowledge_selection is not None else ()
    )
    languages = knowledge_selection.languages if knowledge_selection is not None else ()
    karma_knowledge_selection = (
        character.karma_knowledge_selection if character is not None else None
    )
    karma_knowledge_points = (
        karma_knowledge_selection.points if karma_knowledge_selection is not None else {}
    )
    knowledge_ctx = _knowledge_selection_context(
        character, knowledge_skills, languages, karma_knowledge_points
    )
    quality_ids = (
        tuple(q.id for q in character.quality_selection.qualities)
        if character is not None and character.quality_selection is not None
        else ()
    )
    quality_ctx = _quality_selection_context(character, quality_ids)
    contacts = (
        character.contact_selection.contacts
        if character is not None and character.contact_selection is not None
        else ()
    )
    contact_ctx = _contacts_context(character, contacts)
    gear_names = (
        tuple(item.name for item in character.resources_selection.gear)
        if character is not None and character.resources_selection is not None
        else ()
    )
    lifestyle_selection = character.lifestyle_selection if character is not None else None
    lifestyle_tier_name = (
        lifestyle_selection.tier.name
        if lifestyle_selection is not None
        else DEFAULT_LIFESTYLE_TIER_NAME
    )
    lifestyle_months = (
        lifestyle_selection.months if lifestyle_selection is not None else DEFAULT_LIFESTYLE_MONTHS
    )
    lifestyle_cost = lifestyle_selection.total_cost if lifestyle_selection is not None else 0
    gear_cost = (
        character.resources_selection.nuyen_spent
        if character is not None and character.resources_selection is not None
        else 0
    )
    cyberware_item_ids = (
        tuple(item.id for item in character.cyberware_selection.items)
        if character is not None and character.cyberware_selection is not None
        else ()
    )
    cyberware_cost = (
        character.cyberware_selection.nuyen_spent
        if character is not None and character.cyberware_selection is not None
        else 0
    )
    bioware_item_ids = (
        tuple(item.id for item in character.bioware_selection.items)
        if character is not None and character.bioware_selection is not None
        else ()
    )
    bioware_cost = (
        character.bioware_selection.nuyen_spent
        if character is not None and character.bioware_selection is not None
        else 0
    )
    karma_converted = (
        character.resources_selection.karma_converted
        if character is not None and character.resources_selection is not None
        else 0
    )
    foci_cost = (
        character.foci_selection.nuyen_cost
        if character is not None and character.foci_selection is not None
        else 0
    )
    resources_ctx = _resources_context(
        character,
        session.resources_letter,
        gear_names,
        lifestyle_cost,
        cyberware_cost,
        bioware_cost,
        karma_converted,
        foci_cost,
    )
    lifestyle_ctx = _lifestyle_context(
        character,
        session.resources_letter,
        lifestyle_tier_name,
        lifestyle_months,
        gear_cost,
        cyberware_cost,
        bioware_cost,
        karma_converted,
        foci_cost,
    )
    cyberware_ctx = _cyberware_context(
        character,
        session.resources_letter,
        cyberware_item_ids,
        bioware_item_ids,
        gear_cost,
        lifestyle_cost,
        karma_converted,
        foci_cost,
    )
    foci_ctx = _foci_selection_context(
        character,
        session.resources_letter,
        foci_picks,
        gear_cost,
        lifestyle_cost,
        cyberware_cost,
        bioware_cost,
        karma_converted,
    )
    stale = bool(
        talent_ctx.get("talent_budget_warning")
        or attribute_ctx.get("attribute_budget_warning")
        or skill_ctx.get("skill_budget_warning")
        or knowledge_ctx.get("knowledge_budget_warning")
        or resources_ctx.get("resources_budget_warning")
        or lifestyle_ctx.get("lifestyle_budget_warning")
        or cyberware_ctx.get("cyberware_budget_warning")
        or spirit_ctx.get("spirit_budget_warning")
        or foci_ctx.get("foci_budget_warning")
    )
    priority_ctx = {**priority_ctx, "priority_stale_selections": stale}
    return {
        # WP61: read by every section template's own `<details {% if open_section == "..." %}>`
        # -- shared via this one merged dict rather than threaded through all 14 context-builder
        # signatures, since `{% include %}` (used throughout `_chargen_body.html`) already shares
        # the including template's context with what it includes.
        "open_section": session.open_section,
        **priority_ctx,
        **talent_ctx,
        **attribute_ctx,
        **skill_ctx,
        **knowledge_ctx,
        **spell_ctx,
        **power_ctx,
        **spirit_ctx,
        **foci_ctx,
        **quality_ctx,
        **contact_ctx,
        **lifestyle_ctx,
        **cyberware_ctx,
        **resources_ctx,
    }


@router.get("/", response_class=HTMLResponse)
def index(request: Request) -> HTMLResponse:
    session, new_cookie = resolve_session(request)
    priority_ctx = _priority_form_context(
        heritage_letter=session.heritage_letter,
        attributes_letter=session.attributes_letter,
        skills_letter=session.skills_letter,
        resources_letter=session.resources_letter,
        talent_letter=session.talent_letter,
        build_method=session.build_method,
        metatype_id=session.metatype_id,
        character=session.character,
        error=None,
    )
    context = _chargen_body_context(session, priority_ctx)
    response = templates.TemplateResponse(request, "chargen.html", context)
    if new_cookie is not None:
        response.set_cookie(SESSION_COOKIE_NAME, new_cookie, httponly=True, samesite="lax")
    return response


@router.get("/ui/metatypes", response_class=HTMLResponse)
def metatype_options_fragment(request: Request, heritage_letter: str) -> HTMLResponse:
    heritage = PRIORITIES.heritage.get(heritage_letter)
    metatype_options = metatype_choices(heritage, METATYPES) if heritage is not None else ()
    context = {
        "metatype_options": metatype_options,
        "selected": {"metatype_id": None},
    }
    return templates.TemplateResponse(request, "_metatype_select.html", context)


@router.post("/ui/priorities", response_class=HTMLResponse)
def submit_priorities(
    request: Request,
    heritage_letter: str = Form(...),
    attributes_letter: str = Form(...),
    skills_letter: str = Form(...),
    resources_letter: str = Form(...),
    talent_letter: str = Form(...),
    # Defaulted, not `Form(...)`, so every pre-WP44 caller (existing tests included) that never
    # submits this new field keeps today's Priority-bijection behavior unchanged.
    build_method: str = Form(PRIORITY_BUILD_METHOD),
    metatype_id: str = Form(...),
) -> HTMLResponse:
    session, new_cookie = resolve_session(request)
    session.open_section = "priority-section"  # WP61
    submitted_letters = (
        heritage_letter,
        attributes_letter,
        skills_letter,
        resources_letter,
        talent_letter,
    )
    error: str | None = None
    character = session.character

    # WP44: which validity rule applies to the same 5 letters depends on `build_method` --
    # Priority's bijection (WP14/WP24) or Sum-to-Ten's repeats-allowed/sum-to-10 rule (see
    # `chummer5.engine.build_method`'s own docstring for why the target is exact equality, not
    # a ceiling). Neither rule is enforced anywhere below this point (`create_character` never
    # validated letter *assignment* shape to begin with -- only this function does), so an
    # unrecognized `build_method` is its own itemized error rather than silently falling back
    # to either real rule.
    if build_method == PRIORITY_BUILD_METHOD:
        if sorted(submitted_letters) != sorted(PRIORITY_LETTERS):
            error = (
                "Heritage, Talent, Attributes, Skills, and Resources must each use a different "
                f"priority letter ({', '.join(PRIORITY_LETTERS)}), one each."
            )
    elif build_method == SUM_TO_TEN_BUILD_METHOD:
        try:
            validate_sum_to_ten_total(submitted_letters)
        except ValueError as exc:
            error = str(exc)
    else:
        error = f"Unsupported build method: {build_method!r}."

    if error is None:
        heritage = PRIORITIES.heritage[heritage_letter]
        choice = next(
            (c for c in metatype_choices(heritage, METATYPES) if c.metatype.id == metatype_id),
            None,
        )
        if choice is None:
            error = "Select a metatype offered for the chosen Heritage priority."
        else:
            previous = session.character
            if previous is None:
                character = Character(
                    metatype=choice.metatype,
                    heritage_letter=heritage_letter,
                    attributes_letter=attributes_letter,
                    special_attribute_points=choice.special_attribute_points,
                    attribute_points=MappingProxyType({}),
                    improvements=ImprovementIndex(),
                )
            else:
                # WP19: re-validate the player's existing selections against the newly
                # reconfirmed letters/metatype instead of discarding them. `dataclasses.replace`
                # carries every untouched field forward *by reference* -- attribute_points,
                # skill_allocation, resources_selection, quality_selection, and (crucially)
                # `improvements`, which already has that quality's bonuses applied -- so
                # unlike the old `create_character()`-fresh design, there is no empty
                # `ImprovementIndex` to re-populate here, and calling
                # `_relink_quality_improvements` here would double the bonus
                # (`apply_quality_improvements` only ever adds). `Character` has no
                # `__post_init__` validation, so carrying forward a spend that no longer fits
                # the new Attributes/Skills/Resources budget or the new metatype's attribute
                # ranges constructs fine -- whether it *still* fits is deliberately not checked
                # here. `_attribute_allocation_context`/`_skill_allocation_context`/
                # `_resources_context` each re-derive that fresh on every render instead (see
                # their own docstrings), which is what makes a "this is now over budget" warning
                # reappear on every subsequent page load until the player actually fixes it,
                # rather than flashing once on this response and vanishing on the next `GET /`.
                character = replace(
                    previous,
                    metatype=choice.metatype,
                    heritage_letter=heritage_letter,
                    attributes_letter=attributes_letter,
                    special_attribute_points=choice.special_attribute_points,
                )
            # WP23: the metatype may have just changed (or this may be the first-ever
            # resolution, on the fresh-Character branch above) -- either way,
            # `metatype_qualities` needs to reflect `character.metatype` exactly, not whatever
            # `previous.metatype` granted.
            character = _relink_metatype_qualities(character)
            # Contacts are the one carried-forward selection that *does* need recomputing, not
            # just re-attaching: `ContactSelection.free_points`/`karma_cost` derive from
            # `character.attribute_value("CHA")`, which this same reconfirmation (a metatype
            # swap, or attribute points now read against new ranges) can itself have changed.
            character = _relink_contact_selection(character, character.contact_selection)
            session.heritage_letter = heritage_letter
            session.attributes_letter = attributes_letter
            session.skills_letter = skills_letter
            session.resources_letter = resources_letter
            session.talent_letter = talent_letter
            session.build_method = build_method
            session.metatype_id = metatype_id
            session.character = character

    # The priority form's `hx-target` is `#chargen-body` (the whole three-section wrapper, not
    # just this form) since a successful submission can change what the attribute/skill/
    # resources sections need to say about the carried-forward spend (freshly valid, or now
    # over budget -- see WP19) -- so *every* response here, error or not, has to re-render the
    # full `_chargen_body.html`, not just `_priority_form.html`. On error,
    # `_chargen_body_context` reflects the session's untouched (still-committed) attribute/
    # skill state, while `priority_ctx` alone echoes the player's actual invalid submission.
    priority_ctx = _priority_form_context(
        heritage_letter=heritage_letter,
        attributes_letter=attributes_letter,
        skills_letter=skills_letter,
        resources_letter=resources_letter,
        talent_letter=talent_letter,
        build_method=build_method,
        metatype_id=metatype_id,
        character=character,
        error=error,
    )
    context = _chargen_body_context(session, priority_ctx)
    response = templates.TemplateResponse(request, "_chargen_body.html", context)
    if new_cookie is not None:
        response.set_cookie(SESSION_COOKIE_NAME, new_cookie, httponly=True, samesite="lax")
    return response
