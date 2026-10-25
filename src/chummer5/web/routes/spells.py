"""Spells chargen step: `POST /ui/spells` (WP29), gated to Magician only.

**WP62**: split out of the former `chummer5.web.app` -- see `spec/plan/phase-r-architecture-
cleanup.md`'s WP58 audit for the target shape this module is part of.

**WP151** (Phase Z, "Redesign 5"): the fragment is the Skills page's style -- a strip of view tabs
(one per spell category) with three counters, one panel per view. A view is a URL one level below
the Magic page's Spells sub-tab (`/ui/page/magic/spells/<view>`, `chummer5.web.shell`'s
`PageSection.views`), and the form carries it through autosave in a hidden `spells_tab`.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import replace
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from chummer5.engine.character import STARTING_KARMA, Character
from chummer5.engine.magic import (
    casts_spells,
    create_spell_selection,
    offered_talent_options,
)
from chummer5.web.catalogs import PRIORITIES, SPELLS, templates
from chummer5.web.i18n import Message
from chummer5.web.session import resolve_session, set_session_cookie

router = APIRouter()

# WP151: the Spells sub-tab's views -- one per spell category, in catalog order (Combat, Detection,
# Health, Illusion, Manipulation, Rituals), slugged by the lower-cased category. The first is the
# one the sub-tab opens on.
SPELL_CATEGORY_VIEWS: tuple[tuple[str, str], ...] = tuple(
    (category.lower(), category) for category in dict.fromkeys(spell.category for spell in SPELLS)
)
SPELL_VIEW_SLUGS: tuple[str, ...] = tuple(slug for slug, _category in SPELL_CATEGORY_VIEWS)
_SPELLS_URL = "/ui/page/magic/spells"


def spell_view(requested: str | None) -> str:
    """The view a posted `spells_tab` names, or the first one if it names none."""
    return requested if requested in SPELL_VIEW_SLUGS else SPELL_VIEW_SLUGS[0]


def _counter(label_key: str, title_key: str, remaining: int, of: int) -> dict[str, Any]:
    return {
        "label_key": label_key,
        "title_key": title_key,
        "remaining": remaining,
        "of": of,
        "over": remaining < 0,
    }


def _spell_selection_context(
    character: Character | None,
    talent_letter: str,
    spell_ids: Iterable[str],
    *,
    error: str | None = None,
    tab: str | None = None,
) -> dict[str, Any]:
    """Context for `_spell_selection.html` (WP29): WP26's `create_spell_selection` reaching the
    browser, gated to Magician only (see `_chargen_body.html`'s own gating note). `spell_ids` is
    whatever should be shown checked, same echo-the-submission shape as `_quality_selection_
    context`'s `picks`.

    **WP54**: the Karma budget the staleness check below uses is `character.karma_remaining` with
    this section's own currently-committed cost added back in -- the same "exclude this section's
    own prior commitment" idiom `_spirit_selection_context`/`_foci_selection_context` already use.
    (WP151 retired the fragment's own Karma-cost sentences; Ka shows the character's leftover.)

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

    **WP151**: `spell_panels` (one per view, in strip order, each with its rows), the strip's
    `spell_tab_items`, and three counters, each `remaining/of`: F, the free spells left (floored at
    0 -- spells past the free ones are bought with Karma, not overspent); C, what the known-spell
    cap (Magic x 2) leaves; and Ka, the character's leftover Karma (the resource panel's figure).
    `spells_tab` is the view showing; the shell sets it from the URL on a page render.
    """
    if character is None:
        return {"character": None, "spell_error": error}
    # WP121: a Sorcery-aspected Aspected Magician casts too -- with no free spells, since its
    # Talent option grants none (the budget reads the character's own option).
    if not casts_spells(character):
        return {"character": character, "spell_error": error}
    magician_option = next(
        (
            o
            for o in offered_talent_options(talent_letter, PRIORITIES)
            if o.codename == character.magic_type
        ),
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
    panels = [
        {
            "slug": slug,
            "category": category,
            "rows": [
                {"spell": spell, "selected": spell.id in ids}
                for spell in SPELLS
                if spell.category == category
            ],
        }
        for slug, category in SPELL_CATEGORY_VIEWS
    ]
    budget_warning: Message | None = None
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
            budget_warning = Message.of("Web_Stale_Spells", error=str(exc))
    spells_remaining = max(budget - len(ids), 0)
    return {
        "character": character,
        "spells_available": True,  # WP121: the template's gate
        "spells_tab": spell_view(tab),
        "spell_tab_items": [
            {
                "slug": slug,
                "href": f"{_SPELLS_URL}/{slug}",
                "category": category,
                "stale": False,
                "enabled": True,
                "disabled_reason_key": None,
            }
            for slug, category in SPELL_CATEGORY_VIEWS
        ],
        "spell_panels": panels,
        "spell_counters_start": [
            _counter("Web_Spells_CounterFree", "String_FreeSpells", spells_remaining, budget),
            _counter(
                "Web_Spells_CounterCap", "MessageTitle_SpellLimit", max_known - len(ids), max_known
            ),
        ],
        "spell_counters_end": [
            _counter(
                "Web_Spells_CounterKarma",
                "String_Karma",
                character.karma_remaining,
                STARTING_KARMA,
            ),
        ],
        "spell_budget": budget,
        "spells_remaining": spells_remaining,
        "spell_error": error,
        "spell_budget_warning": budget_warning,
    }


@router.post("/ui/spells", response_class=HTMLResponse)
async def submit_spells(request: Request) -> HTMLResponse:
    session, new_cookie = resolve_session(request)
    session.current_page = "magic"  # WP61/WP97
    form = await request.form()
    tab = spell_view(str(form.get("spells_tab", "")))
    if session.character is None or not casts_spells(session.character):
        context = _spell_selection_context(session.character, session.talent_letter, (), tab=tab)
    else:
        spell_ids = [str(v) for v in form.getlist("spell_id")]
        magician_option = next(
            (
                o
                for o in offered_talent_options(session.talent_letter, PRIORITIES)
                if o.codename == session.character.magic_type
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
                session.character, session.talent_letter, spell_ids, error=str(exc), tab=tab
            )
        else:
            session.character = replace(session.character, spell_selection=selection)
            context = _spell_selection_context(
                session.character, session.talent_letter, spell_ids, tab=tab
            )
    response = templates.TemplateResponse(request, "_spell_selection.html", context)
    set_session_cookie(request, response, new_cookie)
    return response
