"""The application shell (WP97): the step table the nav is built from, the cross-cutting context
aggregator every full render uses, and the nav's own context.

Phase W (`spec/plan/phase-w-ui-shell.md`) replaced the single-page accordion (`_chargen_body.html`,
WP61/WP64) with a title bar, a sidebar step nav, and one `#page` content pane. The step fragments
themselves were already per-step (WP62), so nothing here changes what a step renders -- only which
fragments are mounted together as one nav *page*, which is what `STEP_PAGES` records.

Not a router module: `chummer5.web.routes.pages` owns the shell/page/nav routes, and
`chummer5.web.routes.priorities` needs `chargen_context` too, so both import from here rather than
from each other.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from chummer5.engine.resources import resources_gear_args
from chummer5.web.catalogs import DEFAULT_LIFESTYLE_MONTHS, DEFAULT_LIFESTYLE_TIER_NAME
from chummer5.web.routes.attributes import _attribute_allocation_context
from chummer5.web.routes.contacts import _contacts_context
from chummer5.web.routes.cyberware import _cyberware_context
from chummer5.web.routes.foci import _foci_selection_context
from chummer5.web.routes.knowledge import _knowledge_selection_context
from chummer5.web.routes.lifestyle import _lifestyle_context
from chummer5.web.routes.powers import _power_selection_context
from chummer5.web.routes.qualities import _quality_selection_context
from chummer5.web.routes.resources import _resources_context
from chummer5.web.routes.skills import _skill_allocation_context
from chummer5.web.routes.spells import _spell_selection_context
from chummer5.web.routes.spirits import _spirit_selection_context
from chummer5.web.routes.talent import _default_talent_codename, _talent_selection_context
from chummer5.web.routes.vehicles import _vehicles_context
from chummer5.web.session import ChargenSession


@dataclass(frozen=True)
class StepPage:
    """One entry in the sidebar step nav.

    `fragments` are the existing per-step partials mounted, in order, as this page's content --
    each keeps its own wrapper id, `hx-target`, and route exactly as before (Finding 1).
    `warning_keys` are the context keys (each step context builder's own `*_budget_warning`) whose
    presence marks this page in the nav as holding a selection that no longer fits the confirmed
    priorities (WP19) -- the nav marker is how that warning reaches a player who isn't looking at
    the page. `enabled=False` is Finding 3's two nav entries with nothing behind them yet.
    """

    slug: str
    label: str
    fragments: tuple[str, ...] = ()
    warning_keys: tuple[str, ...] = ()
    enabled: bool = True
    disabled_reason: str | None = None
    # The step fragments each open with their own `<summary>` heading; only a page whose fragment
    # has none (Export's character sheet) needs the page to supply one.
    heading: str | None = None


# The sketch's order (`examples/ui/main_ui.png`), which is also SR5's own chargen step order.
# Skills/Magic/Equipment are composites (Finding 4) that WP98 gives real intra-page structure; until
# then they stack their fragments in their old accordion order.
STEP_PAGES: tuple[StepPage, ...] = (
    StepPage("priorities", "Priorities", ("_priority_form.html",)),
    StepPage(
        "attributes",
        "Attributes",
        ("_attribute_allocation.html",),
        ("attribute_budget_warning",),
    ),
    StepPage("qualities", "Qualities", ("_quality_selection.html",)),
    StepPage(
        "skills",
        "Skills",
        ("_skill_allocation.html", "_knowledge_skills.html"),
        ("skill_budget_warning", "knowledge_budget_warning"),
    ),
    StepPage(
        "magic",
        "Magic",
        (
            "_talent_selection.html",
            "_spell_selection.html",
            "_power_selection.html",
            "_spirit_selection.html",
            "_foci_selection.html",
        ),
        (
            "talent_budget_warning",
            "spell_budget_warning",
            "spirit_budget_warning",
            "foci_budget_warning",
        ),
    ),
    StepPage(
        "resonance",
        "Resonance",
        enabled=False,
        disabled_reason="Technomancers are not supported yet.",
    ),
    StepPage(
        "augmentation",
        "Augmentation",
        ("_cyberware.html",),
        ("cyberware_budget_warning",),
    ),
    StepPage(
        "equipment",
        "Equipment",
        ("_resources.html", "_lifestyle.html", "_vehicles.html"),
        ("resources_budget_warning", "lifestyle_budget_warning", "vehicles_budget_warning"),
    ),
    StepPage("contacts", "Contacts", ("_contacts.html",)),
    StepPage(
        "bio",
        "Bio",
        enabled=False,
        disabled_reason="Character background details are not supported yet.",
    ),
    StepPage(
        "export",
        "Export",
        ("_character_sheet.html",),
        heading="Character sheet & export",
    ),
)

STEP_PAGES_BY_SLUG: dict[str, StepPage] = {page.slug: page for page in STEP_PAGES}

DEFAULT_PAGE = "priorities"


def nav_context(session: ChargenSession, chargen_ctx: dict[str, Any]) -> dict[str, Any]:
    """The step nav's own context: one item per `STEP_PAGES` entry, with the session's
    `current_page` marked and each page's WP19 staleness read off `chargen_ctx` (the same
    `chargen_context` result a full render already has, rather than re-deriving any of it).
    """
    return {
        "nav_items": [
            {
                "page": page,
                "current": page.slug == session.current_page,
                "stale": any(chargen_ctx.get(key) for key in page.warning_keys),
            }
            for page in STEP_PAGES
        ]
    }


def chargen_context(session: ChargenSession, priority_ctx: dict[str, Any]) -> dict[str, Any]:
    """Merge the priority-form context with a clean (non-error) render of every other chargen
    section, reflecting the session's currently committed state.

    **WP97**: moved here from `chummer5.web.routes.priorities` (where it was
    `_chargen_body_context`), unchanged in substance. Its callers are now the page/nav renders in
    `chummer5.web.routes.pages` and `POST /ui/priorities`, which still needs it for
    `priority_stale_selections` but now renders only its own fragment from it. The per-step
    `*_budget_warning` keys it merges are also what `nav_context` reads for the nav's stale-step
    markers -- the aggregate flag says *that* something went stale, the markers say *where*.

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
            (spirit.spirit_type, spirit.force, spirit.services)
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
    # WP66: split committed gear back into flat names + Rating-priced (name, rating) picks so a
    # priority reconfirm re-validates each rating item at its chosen rating, not as a bare name.
    gear_names, rating_gear = (
        resources_gear_args(character.resources_selection)
        if character is not None and character.resources_selection is not None
        else ((), ())
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
    # WP42: the whole purchase *tree*, not just its top-level ids. WP41 passed ids because the
    # picker had no plugin row to render one in; now that it has, a committed limb's plugins have to
    # survive a full-page re-render, or re-submitting the (unchanged) form would drop them -- the
    # identical reason `bioware_requests` below carries its chosen skills rather than bare ids
    # (WP80). Bundled nodes are omitted by `to_requests()` and re-attached on the way back in.
    cyberware_requests = (
        character.cyberware_selection.to_requests()
        if character is not None and character.cyberware_selection is not None
        else ()
    )
    cyberware_cost = (
        character.cyberware_selection.nuyen_spent
        if character is not None and character.cyberware_selection is not None
        else 0
    )
    # WP80: requests, not bare ids -- a committed `Reflex Recorder`'s chosen skill has to survive
    # a full-page re-render, or re-submitting the (unchanged) form would drop it.
    bioware_requests = (
        character.bioware_selection.to_requests()
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
    # WP93: vehicles are the sixth (and last) spender of the shared Step Six nuyen pool.
    vehicle_ids = (
        character.vehicle_selection.vehicle_ids
        if character is not None and character.vehicle_selection is not None
        else ()
    )
    vehicle_cost = (
        character.vehicle_selection.nuyen_spent
        if character is not None and character.vehicle_selection is not None
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
        vehicle_cost,
        rating_gear,
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
        vehicle_cost,
    )
    cyberware_ctx = _cyberware_context(
        character,
        session.resources_letter,
        cyberware_requests,
        bioware_requests,
        gear_cost,
        lifestyle_cost,
        karma_converted,
        foci_cost,
        vehicle_cost,
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
        vehicle_cost,
    )
    vehicles_ctx = _vehicles_context(
        character,
        session.resources_letter,
        vehicle_ids,
        gear_cost,
        lifestyle_cost,
        cyberware_cost,
        bioware_cost,
        karma_converted,
        foci_cost,
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
        or vehicles_ctx.get("vehicles_budget_warning")
    )
    priority_ctx = {**priority_ctx, "priority_stale_selections": stale}
    return {
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
        **vehicles_ctx,
        **resources_ctx,
    }
