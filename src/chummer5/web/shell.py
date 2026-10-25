"""The application shell (WP97): the step table the nav is built from, the cross-cutting context
aggregator every full render uses, and the nav's own context.

Phase W (`spec/plan/phase-w-ui-shell.md`) replaced the single-page accordion (`_chargen_body.html`,
WP61/WP64) with a title bar, a sidebar step nav, and one `#page` content pane. The step fragments
themselves were already per-step (WP62), so nothing here changes what a step renders -- only which
fragments are mounted together as one nav *page*, which is what `STEP_PAGES` records.

WP98 made the three pages that mount more than one fragment (Skills, Magic, Equipment) tabbed:
each fragment is a `PageSection`, and `resolve_tab`/`tabs_context` below decide which one shows.

WP148 (Phase Z) gave Skills a different kind of tab: a `PageTab` is a *view* onto the page's
fragments (a skill category, the groups, the exotic skills, ...) rather than one fragment each, so
the page mounts both its fragments unwrapped and each fragment shows the panel the tab names. See
`skills_tabs_context`. WP151 gave a composite page's section views of its own, one URL level
further down (`PageSection.views`: the Spells sub-tab's spell categories).

Not a router module: `chummer5.web.routes.pages` owns the shell/page/nav routes, and
`chummer5.web.routes.priorities` needs `chargen_context` too, so both import from here rather than
from each other.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from chummer5.engine.character import STARTING_KARMA, Character
from chummer5.engine.magic import binds_spirits, casts_spells
from chummer5.engine.resources import (
    available_nuyen,
    resources_addon_args,
    resources_gear_args,
)
from chummer5.engine.validation import Issue, SessionLetters, validate
from chummer5.web.catalogs import (
    DEFAULT_LIFESTYLE_MONTHS,
    DEFAULT_LIFESTYLE_TIER_NAME,
    PRIORITIES,
    SKILLS,
)
from chummer5.web.i18n import Message
from chummer5.web.routes.attributes import _attribute_allocation_context
from chummer5.web.routes.bio import _bio_context
from chummer5.web.routes.contacts import _contacts_context
from chummer5.web.routes.cyberware import _cyberware_context
from chummer5.web.routes.foci import _foci_selection_context
from chummer5.web.routes.knowledge import _knowledge_selection_context
from chummer5.web.routes.lifestyle import _lifestyle_context
from chummer5.web.routes.powers import _power_selection_context
from chummer5.web.routes.qualities import _quality_selection_context
from chummer5.web.routes.resources import _resources_context
from chummer5.web.routes.skills import _skill_allocation_context
from chummer5.web.routes.spells import SPELL_VIEW_SLUGS, _spell_selection_context
from chummer5.web.routes.spirits import _spirit_selection_context
from chummer5.web.routes.talent import _default_talent_codename, _talent_selection_context
from chummer5.web.routes.vehicles import _vehicles_context
from chummer5.web.session import ChargenSession


def _always(_character: Character | None) -> bool:
    return True


def _casts_spells(character: Character | None) -> bool:
    """WP121: a Magician, or a Sorcery-aspected Aspected Magician."""
    return character is not None and casts_spells(character)


def _binds_spirits(character: Character | None) -> bool:
    """WP121: a Magician, or a Conjuring-aspected Aspected Magician."""
    return character is not None and binds_spirits(character)


def _is_adept(character: Character | None) -> bool:
    return character is not None and character.magic_type == "Adept"


def _is_awakened(character: Character | None) -> bool:
    return character is not None and bool(character.magic_type)


@dataclass(frozen=True)
class PageSection:
    """One existing step fragment mounted on a nav page -- on a composite page (WP98), one sub-tab.

    `fragment` keeps its own wrapper id, `hx-target`, and route exactly as before (Finding 1).
    `warning_keys` are the context keys (that step context builder's own `*_budget_warning`) whose
    presence marks it as holding a selection that no longer fits the confirmed priorities (WP19);
    the page's nav entry is stale if any of its sections is, and a composite page's tab strip marks
    the section itself. `available` mirrors the fragment's own top-level `{% if %}` guard -- it
    must agree with it exactly (a test pins that), because a tab whose fragment renders nothing
    is shown disabled, with its unavailable reason as the explanation, rather than as an empty pane.

    Every `*_key` field is an i18n key (WP102), rendered through `_()` -- none holds display text.

    WP151: a section may declare `views`, slugs one URL level below its own tab
    (`/ui/page/{page}/{section}/{view}`, the Spells sub-tab's spell categories). The fragment draws
    its own strip for them and reads the current one from the context key `view_key`; the first is
    the one the bare sub-tab URL opens on.
    """

    slug: str
    label_key: str
    fragment: str
    warning_keys: tuple[str, ...] = ()
    available: Callable[[Character | None], bool] = _always
    unavailable_reason_key: str | None = None
    views: tuple[str, ...] = ()
    view_key: str | None = None


@dataclass(frozen=True)
class PageTab:
    """WP148: one tab of a page whose tabs are views onto its fragments, not one fragment each
    (the Skills page, `spec/plan/phase-z-page-redesigns.md`, "Redesign 4"). Every fragment is
    rendered on every tab; each one reads the current tab slug and shows the matching panel.

    `warning_keys` mark the tab stale the way a `PageSection`'s do, and name the tab a WP19 issue
    links to. A disabled tab (`enabled=False`) is still listed, as a `<span>` with its reason, so
    the tabs after it never move. Every `*_key` field is an i18n key.
    """

    slug: str
    label_key: str
    warning_keys: tuple[str, ...] = ()
    enabled: bool = True
    disabled_reason_key: str | None = None


@dataclass(frozen=True)
class StepPage:
    """One entry in the sidebar step nav.

    A page with more than one section is a composite (Finding 4) and renders them as sub-tabs
    (WP98 -- see `spec/decisions-log.md`'s 2026-09-24 entry on the intra-page pattern). `enabled=
    False` is Finding 3's two nav entries with nothing behind them yet. `locked_note_key` is a
    composite page's empty state: shown under its tab strip when every tab but the showing one is
    unavailable (Magic, for a character with no confirmed magical Talent). Every `*_key` field is
    an i18n key (WP102).
    """

    slug: str
    label_key: str
    sections: tuple[PageSection, ...] = ()
    enabled: bool = True
    disabled_reason_key: str | None = None
    # The step fragments each open with their own `<summary>` heading; only a page whose fragments
    # have none (Export's character sheet, Skills since WP148) needs the page to supply one.
    heading_key: str | None = None
    locked_note_key: str | None = None
    # WP148: view tabs (see `PageTab`), the template that draws their strip, and old tab slugs
    # that still resolve, as `(alias, tab)` pairs.
    tabs: tuple[PageTab, ...] = ()
    tab_strip: str | None = None
    # WP150: the template after the fragments -- Skills' messages, so none sits above a control.
    tab_footer: str | None = None
    tab_aliases: tuple[tuple[str, str], ...] = ()

    @property
    def tabbed(self) -> bool:
        """A WP98 composite page: one sub-tab per section. A page with view tabs is not one."""
        return len(self.sections) > 1 and not self.tabs

    def view_tab(self, slug: str) -> str | None:
        """WP148: the view tab `slug` names (directly or as an alias), or None if it names none."""
        slug = dict(self.tab_aliases).get(slug, slug)
        return slug if any(tab.slug == slug for tab in self.tabs) else None

    def tab_for_warning(self, key: str) -> str | None:
        """WP148: the view tab whose `warning_keys` include `key`, if any."""
        return next((tab.slug for tab in self.tabs if key in tab.warning_keys), None)

    @property
    def warning_keys(self) -> tuple[str, ...]:
        return tuple(key for section in self.sections for key in section.warning_keys)

    def section(self, slug: str) -> PageSection | None:
        return next((section for section in self.sections if section.slug == slug), None)


def _single(
    slug: str, label_key: str, fragment: str, *warning_keys: str
) -> tuple[PageSection, ...]:
    return (PageSection(slug, label_key, fragment, warning_keys),)


# WP148: the Skills page's tabs, in the sketch's order (`examples/ui/skills.png`) as the user
# amended it on 2026-10-25: one Knowledge tab for Knowledge and Language skills; Resonance listed
# but disabled, since Technomancers are out of scope. The page opens on the first.
SKILLS_TABS: tuple[PageTab, ...] = (
    PageTab("combat", "Web_Skills_TabCombat", ("skill_budget_warning",)),
    PageTab("physical", "Web_Skills_TabPhysical"),
    PageTab("social", "Web_Skills_TabSocial"),
    PageTab("technical", "Web_Skills_TabTechnical"),
    PageTab("vehicle", "Web_Skills_TabVehicle"),
    PageTab("group", "Web_Skills_TabGroup"),
    PageTab("magical", "Web_Skills_TabMagical"),
    PageTab(
        "resonance",
        "Web_Skills_TabResonance",
        enabled=False,
        disabled_reason_key="Web_Nav_ResonanceUnsupported",
    ),
    PageTab("knowledge", "Web_Skills_TabKnowledge", ("knowledge_budget_warning",)),
    PageTab("special", "Web_Skills_TabSpecial"),
    # WP150: views across every section but Group, narrowed by the script (`app.js`).
    PageTab("filtered", "Web_Skills_TabFiltered"),
    PageTab("rated", "Web_Skills_TabRated"),
)

# The sketch's order (`examples/ui/main_ui.png`), which is also SR5's own chargen step order.
# Skills/Magic/Equipment are the composites (Finding 4); their sections keep their old accordion
# order, which is also the order a player fills them in. Labels reuse a legacy key wherever its
# English text is exactly the label (WP102 -- see src/chummer5/lang/README.md), which is where the
# Title Case of "Adept Powers"/"Vehicles & Drones" comes from.
STEP_PAGES: tuple[StepPage, ...] = (
    StepPage(
        "priorities",
        "Label_SelectBP_Priorities",
        _single("priorities", "Label_SelectBP_Priorities", "_priority_form.html"),
    ),
    StepPage(
        "attributes",
        "Label_Attributes",
        _single(
            "attributes",
            "Label_Attributes",
            "_attribute_allocation.html",
            "attribute_budget_warning",
        ),
    ),
    StepPage(
        "qualities",
        "String_Qualities",
        _single(
            "qualities", "String_Qualities", "_quality_selection.html", "quality_budget_warning"
        ),
    ),
    # WP148: one page, two fragments, and a strip of view tabs over both (see `SKILLS_TABS`).
    StepPage(
        "skills",
        "Tab_Skills",
        (
            PageSection(
                "skills", "Tab_Skills", "_skill_allocation.html", ("skill_budget_warning",)
            ),
            PageSection(
                "knowledge",
                "Tab_Skills",
                "_knowledge_skills.html",
                ("knowledge_budget_warning",),
            ),
        ),
        heading_key="Tab_Skills",
        tabs=SKILLS_TABS,
        tab_strip="_skills_tabs.html",
        tab_footer="_skills_footer.html",
        # WP98's sub-tab slug, still linked from saved bookmarks and WP135's issue links.
        tab_aliases=(("active", "combat"),),
    ),
    StepPage(
        "magic",
        "String_AttributeMAGLong",
        (
            PageSection(
                "talent", "Web_Tab_Talent", "_talent_selection.html", ("talent_budget_warning",)
            ),
            PageSection(
                "spells",
                "String_Spells",
                "_spell_selection.html",
                ("spell_budget_warning",),
                _casts_spells,
                "Web_Magic_SpellsUnavailable",
                views=SPELL_VIEW_SLUGS,  # WP151
                view_key="spells_tab",
            ),
            PageSection(
                "powers",
                "Tab_Adept",
                "_power_selection.html",
                ("power_budget_warning",),  # WP119
                _is_adept,
                "Web_Magic_PowersUnavailable",
            ),
            PageSection(
                "spirits",
                "Web_Tab_BoundSpirits",
                "_spirit_selection.html",
                ("spirit_budget_warning",),
                _binds_spirits,
                "Web_Magic_SpiritsUnavailable",
            ),
            PageSection(
                "foci",
                "Label_SummaryFoci",
                "_foci_selection.html",
                ("foci_budget_warning",),
                _is_awakened,
                "Web_Magic_FociUnavailable",
            ),
        ),
        locked_note_key="Web_Magic_LockedNote",
    ),
    StepPage(
        "resonance",
        "String_AttributeRESLong",
        enabled=False,
        disabled_reason_key="Web_Nav_ResonanceUnsupported",
    ),
    StepPage(
        "augmentation",
        "Web_Nav_Augmentation",
        _single(
            "augmentation", "Web_Nav_Augmentation", "_cyberware.html", "cyberware_budget_warning"
        ),
    ),
    StepPage(
        "equipment",
        "Web_Nav_Equipment",
        (
            PageSection("gear", "Tab_Gear", "_resources.html", ("resources_budget_warning",)),
            PageSection(
                "lifestyle", "String_Lifestyle", "_lifestyle.html", ("lifestyle_budget_warning",)
            ),
            PageSection("vehicles", "Tab_Vehicles", "_vehicles.html", ("vehicles_budget_warning",)),
        ),
    ),
    StepPage(
        "contacts", "String_Contacts", _single("contacts", "String_Contacts", "_contacts.html")
    ),
    StepPage("bio", "Web_Nav_Bio", _single("bio", "Web_Nav_Bio", "_bio.html")),  # WP134
    StepPage(
        "export",
        "String_Export",
        _single("export", "String_Export", "_character_sheet.html"),
        heading_key="Web_Export_Heading",
    ),
)

STEP_PAGES_BY_SLUG: dict[str, StepPage] = {page.slug: page for page in STEP_PAGES}

DEFAULT_PAGE = "priorities"


def session_letters(session: ChargenSession) -> SessionLetters:
    return SessionLetters(
        heritage=session.heritage_letter,
        talent=session.talent_letter,
        attributes=session.attributes_letter,
        skills=session.skills_letter,
        resources=session.resources_letter,
        build_method=session.build_method,
    )


def validation_issues(session: ChargenSession, chargen_ctx: dict[str, Any]) -> tuple[Issue, ...]:
    """WP135: `chummer5.engine.validation.validate`'s issues, plus every step section's WP19
    "no longer fits" warning (an error: a committed spend the current priorities reject), in
    `STEP_PAGES` order. Empty before a character exists."""
    character = session.character
    if character is None:
        return ()
    stale = [
        Issue(
            "error",
            page.slug,
            "Web_Validation_Stale",
            {"warning": chargen_ctx[key]},
            section.slug if page.tabbed else page.tab_for_warning(key),
        )
        for page in STEP_PAGES
        for section in page.sections
        for key in section.warning_keys
        if chargen_ctx.get(key)
    ]
    found = validate(character, session_letters(session), priorities=PRIORITIES, skills=SKILLS)
    order = {page.slug: index for index, page in enumerate(STEP_PAGES)}
    return tuple(sorted((*found, *stale), key=lambda issue: order.get(issue.step, len(order))))


def issue_message(issue: Issue) -> Message:
    """An issue's text: its key, with every `*_key` parameter translated in turn."""
    params = {
        name: Message.of(value) if name.endswith("_key") else value
        for name, value in issue.params.items()
    }
    return Message.of(issue.key, **params)


def validation_context(session: ChargenSession, chargen_ctx: dict[str, Any]) -> dict[str, Any]:
    """WP135: the title bar's status and the Export page's issue list, grouped by step."""
    issues = validation_issues(session, chargen_ctx)
    groups = [
        {
            "page": page,
            "issues": [
                {
                    "severity": issue.severity,
                    "message": issue_message(issue),
                    "href": f"/ui/page/{page.slug}" + (f"/{issue.tab}" if issue.tab else ""),
                }
                for issue in issues
                if issue.step == page.slug
            ],
        }
        for page in STEP_PAGES
    ]
    return {
        "validation_has_character": session.character is not None,
        "validation_count": len(issues),
        "validation_errors": sum(1 for issue in issues if issue.severity == "error"),
        "validation_groups": [group for group in groups if group["issues"]],
    }


def nav_context(session: ChargenSession, chargen_ctx: dict[str, Any]) -> dict[str, Any]:
    """The step nav's own context: one item per `STEP_PAGES` entry, with the session's
    `current_page` marked and each page's WP19 staleness read off `chargen_ctx` (the same
    `chargen_context` result a full render already has, rather than re-deriving any of it).

    **WP135**: the marker widens from "no longer fits" to "has validation issues" -- a page is
    marked when `validation_issues` names it, which includes every WP19 warning.
    """
    flagged = {issue.step for issue in validation_issues(session, chargen_ctx)}
    return {
        "nav_items": [
            {
                "page": page,
                "current": page.slug == session.current_page,
                "stale": page.slug in flagged
                or any(chargen_ctx.get(key) for key in page.warning_keys),
            }
            for page in STEP_PAGES
        ]
    }


def resolve_tab(session: ChargenSession, page: StepPage, requested: str | None = None) -> str:
    """Which of a composite page's sections to show, recorded as that page's remembered tab.

    An explicitly `requested` tab (a tab link, or a bookmarked tab URL) is shown even when it is
    unavailable -- the page then shows its reason as an empty state rather than silently showing
    something else at that URL. Otherwise the remembered tab is reopened if it is still available
    (a Talent change can take Spells away), falling back to the first available section, which
    for every composite page is its first section. The caller has already rejected an unknown
    `requested` slug.
    """
    character = session.character
    if requested is not None:
        tab = requested
    else:
        remembered = page.section(session.page_tabs.get(page.slug, ""))
        if remembered is not None and remembered.available(character):
            tab = remembered.slug
        else:
            tab = next(s.slug for s in page.sections if s.available(character))
    session.page_tabs[page.slug] = tab
    return tab


def tabs_context(
    session: ChargenSession, page: StepPage, chargen_ctx: dict[str, Any], current_tab: str
) -> dict[str, Any]:
    """A composite page's tab strip: one item per section, with `current_tab` marked, availability
    read off the session's character, and per-section WP19 staleness off `chargen_ctx` (the same
    keys `nav_context` unions for the page's nav entry).
    """
    character = session.character
    items = [
        {
            "section": section,
            "current": section.slug == current_tab,
            "available": section.available(character),
            "stale": any(chargen_ctx.get(key) for key in section.warning_keys),
        }
        for section in page.sections
    ]
    locked = page.locked_note_key is not None and all(
        not item["available"] for item in items if not item["current"]
    )
    return {"tab_items": items, "current_tab": current_tab, "tabs_locked": locked}


def skills_tabs_context(
    session: ChargenSession, page: StepPage, chargen_ctx: dict[str, Any], current_tab: str
) -> dict[str, Any]:
    """WP148: the Skills page's strip -- its view tabs with `current_tab` marked -- and its four
    counters, S/G at the strip's left end and Ka/Kn at its right. The counters read the same
    committed figures as the resource panel (`resource_panel_context`), so the two always agree;
    each is `(remaining, of)`, and an overspent one is highlighted. `skills_tab` is what both
    fragments read to decide which panel shows."""
    items = [
        {
            "tab": tab,
            "slug": tab.slug,
            "href": f"/ui/page/{page.slug}/{tab.slug}",
            "stale": any(chargen_ctx.get(key) for key in tab.warning_keys),
            "enabled": tab.enabled,
            "disabled_reason_key": tab.disabled_reason_key,
        }
        for tab in page.tabs
    ]
    counters: list[dict[str, Any]] = []
    character = session.character
    if character is not None:
        counters = [
            {
                "label_key": "Web_Skills_CounterSkill",
                "title_key": "String_SkillPoints",
                "remaining": chargen_ctx["skills_remaining"],
                "of": chargen_ctx["skills_budget"],
            },
            {
                "label_key": "Web_Skills_CounterGroup",
                "title_key": "String_SkillGroupPoints",
                "remaining": chargen_ctx["groups_remaining"],
                "of": chargen_ctx["groups_budget"],
            },
            {
                "label_key": "Web_Skills_CounterKarma",
                "title_key": "String_Karma",
                "remaining": character.karma_remaining,
                "of": STARTING_KARMA,
            },
            {
                "label_key": "Web_Skills_CounterKnowledge",
                "title_key": "String_KnowledgePoints",
                "remaining": (
                    chargen_ctx["knowledge_free_points"] - chargen_ctx["knowledge_points_spent"]
                ),
                "of": chargen_ctx["knowledge_free_points"],
            },
        ]
        for counter in counters:
            counter["over"] = counter["remaining"] < 0
    return {
        "skills_tab_items": items,
        "skills_tab": current_tab,
        "skills_counters_start": counters[:2],
        "skills_counters_end": counters[2:],
    }


def resource_panel_context(session: ChargenSession, chargen_ctx: dict[str, Any]) -> dict[str, Any]:
    """The sidebar's remaining-resources panel (WP99): one row per budget, each `(remaining, of)`,
    labelled by an i18n key (WP102 -- legacy's own `String_*Points` keys, hence their Title Case).

    Nothing here is accounting. Karma is `Character.karma_remaining`, Phase O's unified ledger, so
    the panel cannot disagree with it. Nuyen is the Resources letter's pool (with any Karma
    converted into it) less `Character.nuyen_spent`. The point pools are read off `chargen_ctx` --
    the same numbers each step shows on its own page, computed from committed state -- by keys
    unique to one step context (the generic `nuyen_remaining`/`free_points` keys are merged over by
    several and would be whichever step happened to merge last; see WP60's worklog for that bug
    the first time).

    Magic's own pools only appear for the archetype that has them, the same way those sections'
    tabs do (WP98): free spells for a Magician, Power Points for an Adept.
    """
    character = session.character
    if character is None:
        return {"resource_rows": []}
    karma_converted = (
        character.resources_selection.karma_converted
        if character.resources_selection is not None
        else 0
    )
    nuyen_pool = available_nuyen(session.resources_letter, PRIORITIES, karma_converted)
    rows: list[dict[str, Any]] = [
        {"label_key": "String_Karma", "remaining": character.karma_remaining, "of": STARTING_KARMA},
        {
            "label_key": "Label_SummaryNuyen",
            "remaining": nuyen_pool - character.nuyen_spent,
            "of": nuyen_pool,
            "nuyen": True,
        },
        {
            "label_key": "String_AttributePoints",
            "remaining": chargen_ctx["primary_remaining"],
            "of": chargen_ctx["primary_budget"],
        },
        {
            "label_key": "String_SpecialAttributePoints",
            "remaining": chargen_ctx["special_remaining"],
            "of": chargen_ctx["special_budget"],
        },
        {
            "label_key": "String_SkillPoints",
            "remaining": chargen_ctx["skills_remaining"],
            "of": chargen_ctx["skills_budget"],
        },
        {
            "label_key": "String_SkillGroupPoints",
            "remaining": chargen_ctx["groups_remaining"],
            "of": chargen_ctx["groups_budget"],
        },
        {
            "label_key": "String_KnowledgePoints",
            "remaining": (
                chargen_ctx["knowledge_free_points"] - chargen_ctx["knowledge_points_spent"]
            ),
            "of": chargen_ctx["knowledge_free_points"],
        },
    ]
    if casts_spells(character):
        rows.append(
            {
                "label_key": "String_FreeSpells",
                "remaining": chargen_ctx["spells_remaining"],
                "of": chargen_ctx["spell_budget"],
            }
        )
    elif character.magic_type == "Adept":
        rows.append(
            {
                "label_key": "Web_Panel_PowerPoints",
                "remaining": chargen_ctx["power_points_remaining"],
                "of": chargen_ctx["power_point_budget"],
            }
        )
    for row in rows:
        row["over"] = row["remaining"] < 0
    return {"resource_rows": rows}


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
        character,
        session.talent_letter,
        talent_codename,
        tradition_id,
        granted_skill_ids,
        aspect=character.magic_aspect if character is not None else None,  # WP121
    )
    spell_ids = (
        tuple(spell.id for spell in character.spell_selection.spells)
        if character is not None and character.spell_selection is not None
        else ()
    )
    spell_ctx = _spell_selection_context(character, session.talent_letter, spell_ids)
    power_picks = (
        tuple((pick.power.id, pick.rating, pick.target) for pick in character.power_selection.picks)
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
        character,
        knowledge_skills,
        languages,
        karma_knowledge_points,
        knowledge_selection.specializations if knowledge_selection is not None else {},
        (
            karma_knowledge_selection.specializations
            if karma_knowledge_selection is not None
            else {}
        ),
        skills_letter=session.skills_letter,
    )
    quality_ctx = _quality_selection_context(character)
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
        addons=resources_addon_args(character.resources_selection if character else None),
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
        # WP132
        tuple((p.option.name, p.text) for p in lifestyle_selection.options)
        if lifestyle_selection is not None
        else (),
        lifestyle_selection.permanent if lifestyle_selection is not None else False,
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
        or quality_ctx.get("quality_budget_warning")
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
        **_bio_context(character),  # WP134
        **lifestyle_ctx,
        **cyberware_ctx,
        **vehicles_ctx,
        **resources_ctx,
    }
