"""Priorities/metatype chargen step: `GET /ui/metatypes`, `POST /ui/priorities` (WP14, widened by
WP24/WP44).

**WP62**: split out of the former `chummer5.web.app` -- see `spec/plan/phase-r-architecture-
cleanup.md`'s WP58 audit for the target shape this module is part of. Through WP96 it also hosted
`GET /` and `_chargen_body_context`, the cross-cutting aggregator; WP97 moved the aggregator to
`chummer5.web.shell.chargen_context` and `GET /` to `chummer5.web.routes.pages`, alongside the rest
of the application shell.
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
from chummer5.web.catalogs import METATYPES, PRIORITIES, templates
from chummer5.web.i18n import Message, MessageJoin
from chummer5.web.routes.contacts import _relink_contact_selection
from chummer5.web.routes.qualities import _relink_metatype_qualities
from chummer5.web.session import (
    PRIORITY_LETTERS,
    ChargenSession,
    resolve_session,
    set_session_cookie,
)
from chummer5.web.shell import chargen_context

router = APIRouter()


def _session_priority_form_context(session: ChargenSession) -> dict[str, Any]:
    """`_priority_form_context` for a clean (non-error) render of the session's own current
    selection -- what every page render other than `POST /ui/priorities` itself shows.
    """
    return _priority_form_context(
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
    error: Message | str | None,
) -> dict[str, Any]:
    """Context for `_priority_form.html`'s own fields (letters, metatype options, the
    duplicate-letter/unoffered-metatype `error`). Always passed through
    `chummer5.web.shell.chargen_context` before being rendered, which folds in one more key this
    function doesn't set itself: `priority_stale_selections` (WP19) -- see that function's
    docstring for why it's computed there instead of here.

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
    session.current_page = "priorities"  # WP61/WP97
    submitted_letters = (
        heritage_letter,
        attributes_letter,
        skills_letter,
        resources_letter,
        talent_letter,
    )
    error: Message | str | None = None
    character = session.character
    first_stored = False

    # WP44: which validity rule applies to the same 5 letters depends on `build_method` --
    # Priority's bijection (WP14/WP24) or Sum-to-Ten's repeats-allowed/sum-to-10 rule (see
    # `chummer5.engine.build_method`'s own docstring for why the target is exact equality, not
    # a ceiling). Neither rule is enforced anywhere below this point (`create_character` never
    # validated letter *assignment* shape to begin with -- only this function does), so an
    # unrecognized `build_method` is its own itemized error rather than silently falling back
    # to either real rule.
    if build_method == PRIORITY_BUILD_METHOD:
        if sorted(submitted_letters) != sorted(PRIORITY_LETTERS):
            error = Message.of(
                "Web_Priorities_ErrorLetters",
                letters=MessageJoin(PRIORITY_LETTERS),
            )
    elif build_method == SUM_TO_TEN_BUILD_METHOD:
        try:
            validate_sum_to_ten_total(submitted_letters)
        except ValueError as exc:
            error = str(exc)
    else:
        error = Message.of("Web_Priorities_ErrorBuildMethod", method=repr(build_method))

    if error is None:
        heritage = PRIORITIES.heritage[heritage_letter]
        choice = next(
            (c for c in metatype_choices(heritage, METATYPES) if c.metatype.id == metatype_id),
            None,
        )
        if choice is None:
            error = Message.of("Web_Priorities_ErrorMetatype")
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
                # unlike a `create_character()`-fresh rebuild, there is no empty
                # `ImprovementIndex` to re-populate here, and re-applying a quality's bonus onto
                # this already-populated index would double it
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
            # WP138: one locked step, so a concurrent autosave never snapshots the new letters
            # with the old character. The *first* confirmation goes onto a copy instead, which
            # is stored as a new character (quota-checked) and only then adopted: at quota the
            # confirmation is refused and nothing changes.
            target = session.snapshot() if session.character_id is None else session
            with session.lock:
                target.heritage_letter = heritage_letter
                target.attributes_letter = attributes_letter
                target.skills_letter = skills_letter
                target.resources_letter = resources_letter
                target.talent_letter = talent_letter
                target.build_method = build_method
                target.metatype_id = metatype_id
                target.character = character
            if target is not session:
                # Imported here: `persistence` imports `routes.character`, which imports this.
                from chummer5.web import persistence

                refused = persistence.store_new(request, session, target)
                if refused is None:
                    first_stored = True
                else:
                    error = refused
                    character = session.character

    # WP97: through WP96 this re-rendered every chargen section (the whole `_chargen_body.html`),
    # since a reconfirmation can leave any carried-forward spend over budget (WP19). Under the
    # shell only the priorities page is on screen, so only it re-renders; the other steps pick up
    # the new letters whenever they are next shown (each page render re-derives its own staleness
    # fresh), and the player learns *which* steps went stale from the step nav's markers, which the
    # shell refreshes after every successful `POST` (see `chummer5.web.routes.pages`).
    # `chargen_context` is still what builds the context, because the page's own "some selections
    # no longer fit" line reads its `priority_stale_selections` aggregate. On error that aggregate
    # reflects the session's untouched (still-committed) state, while `priority_ctx` alone echoes
    # the player's actual invalid submission.
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
    if first_stored:
        # WP138: the character now has an id, so the shell's `hx-headers` must change with it.
        from chummer5.web.routes.pages import shell_swap_response

        return shell_swap_response(request, session, "priorities", new_cookie)
    context = chargen_context(session, priority_ctx)
    response = templates.TemplateResponse(request, "_priority_form.html", context)
    set_session_cookie(request, response, new_cookie)
    return response
