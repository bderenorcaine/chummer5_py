"""Priorities/metatype chargen step: `POST /ui/priorities` (WP14, widened by WP24/WP44), plus the
redesigned panel's read-only `GET /ui/priorities/preview`, `/layout` and `/revert` (WP143).

**WP62**: split out of the former `chummer5.web.app` -- see `spec/plan/phase-r-architecture-
cleanup.md`'s WP58 audit for the target shape this module is part of. Through WP96 it also hosted
`GET /` and `_chargen_body_context`, the cross-cutting aggregator; WP97 moved the aggregator to
`chummer5.web.shell.chargen_context` and `GET /` to `chummer5.web.routes.pages`, alongside the rest
of the application shell.

**WP143 (Phase Z, `spec/plan/phase-z-page-redesigns.md`)**: the Priorities page redesign. The POST
contract is unchanged (Finding 1): both layouts post the same five `<category>_letter` fields. The
session holds only the *confirmed* selection, so whether the form is "changed" is decided here,
by `GET /ui/priorities/preview`, against the session (Finding 2) -- the page's script never
compares selections itself. `GET /ui/metatypes` went with the Heritage dropdown it served: the
preview now re-renders the Metatype field when the Heritage letter changes the offer.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
from types import MappingProxyType
from typing import Any

from fastapi import APIRouter, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse

from chummer5.engine.build_method import (
    PRIORITY_BUILD_METHOD,
    SUM_TO_TEN_BUILD_METHOD,
    SUM_TO_TEN_POINT_VALUES,
    SUM_TO_TEN_TARGET,
    SUPPORTED_BUILD_METHODS,
    nearest_priority_assignment,
    sum_to_ten_total,
    validate_sum_to_ten_total,
)
from chummer5.engine.character import Character, MetatypeChoice, metatype_choices
from chummer5.engine.improvements import ImprovementIndex
from chummer5.engine.magic import offered_talent_options
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

# The five categories in display order -- the order Sum-to-Ten lists its rows in, the order the
# conversion and the summary use, and Priority's tie-break (Phase Z's rulings table).
CATEGORIES = ("heritage", "talent", "attributes", "skills", "resources")
CATEGORY_LABEL_KEYS = MappingProxyType(
    {
        "heritage": "Web_Priorities_Heritage",
        "talent": "Web_Tab_Talent",
        "attributes": "Label_Attributes",
        "skills": "Tab_Skills",
        "resources": "Web_Priorities_Resources",
    }
)

# WP143: the panel's status (Phase Z, Finding 2), exposed as `data-priority-status`.
STATUS_UNCONFIRMED = "unconfirmed"
STATUS_CONFIRMED = "confirmed"
STATUS_CHANGED = "changed"


@dataclass(frozen=True)
class PrioritySelection:
    """WP143: what the Priorities panel holds -- the session's confirmed selection, or whatever the
    form currently holds (which exists only in the browser until CONFIRM). Letters are keyed by
    `CATEGORIES`. `metatype_id` is `None` when no metatype is chosen."""

    build_method: str
    letters: Mapping[str, str]
    metatype_id: str | None

    @classmethod
    def of(
        cls,
        build_method: str,
        metatype_id: str | None,
        *,
        heritage: str,
        talent: str,
        attributes: str,
        skills: str,
        resources: str,
    ) -> PrioritySelection:
        letters = {
            "heritage": heritage,
            "talent": talent,
            "attributes": attributes,
            "skills": skills,
            "resources": resources,
        }
        return cls(build_method, MappingProxyType(letters), metatype_id or None)

    @classmethod
    def from_session(cls, session: ChargenSession) -> PrioritySelection:
        return cls.of(
            session.build_method,
            session.metatype_id,
            heritage=session.heritage_letter,
            talent=session.talent_letter,
            attributes=session.attributes_letter,
            skills=session.skills_letter,
            resources=session.resources_letter,
        )

    def ordered_letters(self) -> tuple[str, ...]:
        return tuple(self.letters[category] for category in CATEGORIES)

    def with_letters(self, letters: tuple[str, ...]) -> PrioritySelection:
        return replace(self, letters=MappingProxyType(dict(zip(CATEGORIES, letters, strict=True))))

    def letters_well_formed(self) -> bool:
        return all(letter in PRIORITY_LETTERS for letter in self.letters.values())

    def letters_valid(self) -> bool:
        """The method's own rule: Priority's five distinct letters, or Sum-to-Ten's exact total."""
        if not self.letters_well_formed():
            return False
        letters = self.ordered_letters()
        if self.build_method == PRIORITY_BUILD_METHOD:
            return sorted(letters) == sorted(PRIORITY_LETTERS)
        if self.build_method == SUM_TO_TEN_BUILD_METHOD:
            return sum_to_ten_total(letters) == SUM_TO_TEN_TARGET
        return False


def _metatype_offer(heritage_letter: str) -> tuple[MetatypeChoice, ...]:
    heritage = PRIORITIES.heritage.get(heritage_letter)
    return metatype_choices(heritage, METATYPES) if heritage is not None else ()


def _offered_choice(selection: PrioritySelection) -> MetatypeChoice | None:
    """The selected metatype, if the Heritage letter offers it -- never a substitute."""
    return next(
        (
            choice
            for choice in _metatype_offer(selection.letters["heritage"])
            if choice.metatype.id == selection.metatype_id
        ),
        None,
    )


def _keep_offered_metatype(selection: PrioritySelection) -> PrioritySelection:
    """Phase Z's metatype rule: keep the chosen metatype while the Heritage letter still offers it,
    otherwise fall back to none chosen (the "Choose metatype" placeholder)."""
    if selection.metatype_id is None or _offered_choice(selection) is not None:
        return selection
    return replace(selection, metatype_id=None)


def _priority_status(selection: PrioritySelection, session: ChargenSession) -> str:
    if session.character is None:
        return STATUS_UNCONFIRMED
    if selection == PrioritySelection.from_session(session):
        return STATUS_CONFIRMED
    return STATUS_CHANGED


def _priority_confirmable(selection: PrioritySelection) -> bool:
    return selection.letters_valid() and _offered_choice(selection) is not None


def _gives(category: str, letter: str, selection: PrioritySelection) -> dict[str, Any]:
    """What one placed priority gives, as data for `_priority_preview.html`'s `gives` macro
    (Phase Z's "Defaults": Heritage the chosen metatype and its special attribute points, Talent
    the options that letter offers, Attributes points, Skills skill and group points, Resources
    nuyen)."""
    row: dict[str, Any] = {"category": category, "letter": letter}
    if category == "heritage":
        choice = _offered_choice(selection)
        row["priority"] = PRIORITIES.heritage[letter]
        row["choice"] = choice
    elif category == "talent":
        row["options"] = offered_talent_options(letter, PRIORITIES)
    elif category == "attributes":
        row["points"] = PRIORITIES.attributes[letter].points
    elif category == "skills":
        row["skills"] = PRIORITIES.skills[letter].skills
        row["groups"] = PRIORITIES.skills[letter].skill_groups
    else:
        row["nuyen"] = PRIORITIES.resources[letter].nuyen
    return row


def _priority_summary(
    selection: PrioritySelection, session: ChargenSession, status: str
) -> list[dict[str, Any]]:
    """One row per category (plus the build method), each with what it gives now and -- in the
    "changed" status, on a row that differs from the confirmed priorities -- what it gave before."""
    confirmed = PrioritySelection.from_session(session)
    compare = status == STATUS_CHANGED
    rows: list[dict[str, Any]] = [
        {
            "label_key": "Web_Priorities_BuildMethod",
            "method": selection.build_method,
            "old_method": (
                confirmed.build_method
                if compare and confirmed.build_method != selection.build_method
                else None
            ),
        }
    ]
    for category in CATEGORIES:
        new = _gives(category, selection.letters[category], selection)
        old = _gives(category, confirmed.letters[category], confirmed) if compare else None
        rows.append(
            {
                "label_key": CATEGORY_LABEL_KEYS[category],
                "category": category,
                "gives": new,
                "old": old if old is not None and old != new else None,
            }
        )
    return rows


def _preview_context(
    selection: PrioritySelection, session: ChargenSession, error: Message | str | None = None
) -> dict[str, Any]:
    """`_priority_preview.html`'s context: the status line, CONFIRM/Revert state, the summary,
    and the error slot. What `GET /ui/priorities/preview` renders, and part of every full render."""
    status = _priority_status(selection, session)
    return {
        "priority_status": status,
        "priority_confirmable": _priority_confirmable(selection),
        "priority_confirmed_metatype": (
            session.character.metatype if session.character is not None else None
        ),
        "priority_gives": _priority_summary(selection, session, status),
        "priority_error": error,
    }


def _metatype_field_context(selection: PrioritySelection) -> dict[str, Any]:
    return {
        "priority_metatype_options": _metatype_offer(selection.letters["heritage"]),
        "priority_metatype_id": selection.metatype_id,
        "priority_metatype_offer": selection.letters["heritage"],
    }


def _priority_form_context(
    selection: PrioritySelection, session: ChargenSession, error: Message | str | None = None
) -> dict[str, Any]:
    """Context for `_priority_form.html`: the whole panel, in `selection.build_method`'s layout.

    Always passed through `chummer5.web.shell.chargen_context` before being rendered, which folds
    in `priority_stale_selections` (WP19) -- see that function's docstring for why it's computed
    there. Every key is `priority_`-prefixed: `chargen_context` merges every other step's context
    over this one.

    **WP143 (Phase Z)**: the redesign's two layouts. Priority shows the fixed letters A-E beside
    the five category tiles in their letter order (a hand-crafted duplicate is normalised to the
    nearest permutation, so every tile's hidden input matches its row). Sum-to-Ten shows one
    spinner row per category in display order, with the point scale as data for the script. The
    metatype is never silently substituted: `selection.metatype_id` is shown only while the
    Heritage letter offers it.
    """
    layout = (
        SUM_TO_TEN_BUILD_METHOD
        if selection.build_method == SUM_TO_TEN_BUILD_METHOD
        else PRIORITY_BUILD_METHOD
    )
    if not selection.letters_well_formed():
        # Only a hand-crafted request gets here; the error it earned is still shown.
        selection = replace(selection, letters=PrioritySelection.from_session(session).letters)
    if layout == PRIORITY_BUILD_METHOD:
        selection = selection.with_letters(nearest_priority_assignment(selection.ordered_letters()))
    selection = _keep_offered_metatype(selection)
    letters = selection.ordered_letters()
    tiles = sorted(
        (
            {"category": category, "label_key": CATEGORY_LABEL_KEYS[category], "letter": letter}
            for category, letter in zip(CATEGORIES, letters, strict=True)
        ),
        key=lambda tile: tile["letter"],
    )
    total = sum_to_ten_total(letters)
    return {
        "priority_layout": layout,
        "priority_sum_to_ten": layout == SUM_TO_TEN_BUILD_METHOD,
        "priority_build_method": selection.build_method,
        "priority_build_methods": SUPPORTED_BUILD_METHODS,
        "priority_letters": PRIORITY_LETTERS,
        "priority_tiles": tiles,
        "sum_to_ten_rows": [
            {
                "category": category,
                "label_key": CATEGORY_LABEL_KEYS[category],
                "letter": letter,
                "points": SUM_TO_TEN_POINT_VALUES[letter],
            }
            for category, letter in zip(CATEGORIES, letters, strict=True)
        ],
        # Lowest first, so a spinner's `aria-valuenow` is its index.
        "sum_to_ten_scale": sorted(SUM_TO_TEN_POINT_VALUES.items(), key=lambda item: item[1]),
        "sum_to_ten_max": max(SUM_TO_TEN_POINT_VALUES.values()),
        "sum_to_ten_total": total,
        "sum_to_ten_target": SUM_TO_TEN_TARGET,
        **_metatype_field_context(selection),
        **_preview_context(selection, session, error),
        "character": session.character,
    }


def _session_priority_form_context(session: ChargenSession) -> dict[str, Any]:
    """`_priority_form_context` for the session's own confirmed selection -- what every page
    render other than the priorities routes themselves shows."""
    return _priority_form_context(PrioritySelection.from_session(session), session)


def _form_selection(
    build_method: str,
    metatype_id: str,
    heritage_letter: str,
    talent_letter: str,
    attributes_letter: str,
    skills_letter: str,
    resources_letter: str,
) -> PrioritySelection:
    return PrioritySelection.of(
        build_method,
        metatype_id,
        heritage=heritage_letter,
        talent=talent_letter,
        attributes=attributes_letter,
        skills=skills_letter,
        resources=resources_letter,
    )


def _render_panel(
    request: Request,
    session: ChargenSession,
    new_cookie: str | None,
    selection: PrioritySelection,
    error: Message | str | None = None,
) -> HTMLResponse:
    context = chargen_context(session, _priority_form_context(selection, session, error))
    response = templates.TemplateResponse(request, "_priority_form.html", context)
    set_session_cookie(request, response, new_cookie)
    return response


# WP143: the panel's read-only GETs. GET keeps them clear of the `chargen-changed`/autosave
# middleware and of WP141's origin check, which all apply to POSTs: none of them changes the
# session. Each takes the form's own fields (`hx-include="#priority-form"`).


@router.get("/ui/priorities/preview", response_class=HTMLResponse)
def priorities_preview(
    request: Request,
    build_method: str = Query(PRIORITY_BUILD_METHOD),
    heritage_letter: str = Query(...),
    talent_letter: str = Query(...),
    attributes_letter: str = Query(...),
    skills_letter: str = Query(...),
    resources_letter: str = Query(...),
    metatype_id: str = Query(""),
    metatype_offer: str = Query(""),
) -> HTMLResponse:
    """The status line, CONFIRM/Revert and the summary for what the form holds now, compared
    against the session. Never the tiles or spinners: they hold focus and drag state. When the
    Heritage letter changed which metatypes are offered, the Metatype field comes along out of
    band (`metatype_offer` is the letter the field on the page was rendered for)."""
    session, new_cookie = resolve_session(request)
    selection = _form_selection(
        build_method,
        metatype_id,
        heritage_letter,
        talent_letter,
        attributes_letter,
        skills_letter,
        resources_letter,
    )
    if not selection.letters_well_formed():
        raise HTTPException(status_code=422, detail="Priority letters must be A-E.")
    selection = _keep_offered_metatype(selection)
    offer_changed = _metatype_offer(metatype_offer) != _metatype_offer(heritage_letter)
    context = {
        **_preview_context(selection, session),
        **_metatype_field_context(selection),
        "priority_metatype_oob": offer_changed,
    }
    response = templates.TemplateResponse(request, "_priority_preview.html", context)
    set_session_cookie(request, response, new_cookie)
    return response


@router.get("/ui/priorities/layout", response_class=HTMLResponse)
def priorities_layout(
    request: Request,
    build_method: str = Query(...),
    layout: str = Query(...),
    heritage_letter: str = Query(...),
    talent_letter: str = Query(...),
    attributes_letter: str = Query(...),
    skills_letter: str = Query(...),
    resources_letter: str = Query(...),
    metatype_id: str = Query(""),
) -> HTMLResponse:
    """The method dropdown changed: the whole panel in `build_method`'s layout, carrying the form's
    letters across (`layout` is the method the panel on the page was rendered for).

    Sum-to-Ten -> Priority goes through `nearest_priority_assignment`. Priority -> Sum-to-Ten keeps
    the letters (five distinct letters always total exactly 10), except for a never-confirmed
    character, who starts at all E: the session's default order must not show up as a "default
    distribution" (Phase Z's "Defaults"). The metatype follows the preview's rule."""
    session, new_cookie = resolve_session(request)
    if build_method not in SUPPORTED_BUILD_METHODS:
        raise HTTPException(status_code=422, detail="Unsupported build method.")
    selection = _form_selection(
        build_method,
        metatype_id,
        heritage_letter,
        talent_letter,
        attributes_letter,
        skills_letter,
        resources_letter,
    )
    if not selection.letters_well_formed():
        raise HTTPException(status_code=422, detail="Priority letters must be A-E.")
    if layout != build_method:
        if build_method == PRIORITY_BUILD_METHOD:
            selection = selection.with_letters(
                nearest_priority_assignment(selection.ordered_letters())
            )
        elif session.character is None:
            selection = selection.with_letters(("E",) * len(CATEGORIES))
    return _render_panel(request, session, new_cookie, selection)


@router.get("/ui/priorities/revert", response_class=HTMLResponse)
def priorities_revert(request: Request) -> HTMLResponse:
    """The whole panel, back to the session's confirmed selection."""
    session, new_cookie = resolve_session(request)
    return _render_panel(request, session, new_cookie, PrioritySelection.from_session(session))


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
    # WP143: defaulted, so the "Choose metatype" placeholder's empty value reaches the itemized
    # error below rather than a 422.
    metatype_id: str = Form(""),
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

    # WP97: through WP96 this re-rendered every chargen section (the whole `_chargen_body.html`),
    # since a reconfirmation can leave any carried-forward spend over budget (WP19). Under the
    # shell only the priorities page is on screen, so only it re-renders; the other steps pick up
    # the new letters whenever they are next shown (each page render re-derives its own staleness
    # fresh), and the player learns *which* steps went stale from the step nav's markers, which the
    # shell refreshes after every successful `POST` (see `chummer5.web.routes.pages`).
    # `chargen_context` is still what builds the context, because the page's own "some selections
    # no longer fit" line reads its `priority_stale_selections` aggregate. On error that aggregate
    # reflects the session's untouched (still-committed) state, while the panel itself echoes the
    # player's actual invalid submission (WP143: with its status "changed" against the session).
    if first_stored:
        # WP138: the character now has an id, so the shell's `hx-headers` must change with it.
        from chummer5.web.routes.pages import shell_swap_response

        return shell_swap_response(request, session, "priorities", new_cookie)
    selection = _form_selection(
        build_method,
        metatype_id,
        heritage_letter,
        talent_letter,
        attributes_letter,
        skills_letter,
        resources_letter,
    )
    return _render_panel(request, session, new_cookie, selection, error)
