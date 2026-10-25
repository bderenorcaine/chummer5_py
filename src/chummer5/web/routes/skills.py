"""Active Skills chargen step: `POST /ui/skills` (WP15, widened by WP50/WP53/WP61).

**WP62**: split out of the former `chummer5.web.app` -- see `spec/plan/phase-r-architecture-
cleanup.md`'s WP58 audit for the target shape this module is part of.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
from types import MappingProxyType
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from chummer5.data.skills import Skill
from chummer5.engine.character import Character
from chummer5.engine.skills import (
    MAX_SKILL_RATING_CREATE,
    KarmaSkillSelection,
    SkillAllocation,
    create_karma_skill_selection,
    create_skill_allocation,
    dice_pool,
    exotic_instances,
    exotic_skill_key,
    knowledge_active_points,
    natural_skill_rating,
    purchase_maximum,
    skill_point_budget,
    skill_points_spent,
    skill_purchase_rules,
    skill_rating,
    split_skill_key,
)
from chummer5.web.catalogs import (
    PRIORITIES,
    SKILLS,
    first_example,
    offered_skill_groups,
    offered_skills,
    templates,
)
from chummer5.web.forms import parse_points, parse_specializations
from chummer5.web.i18n import Message
from chummer5.web.session import resolve_session, set_session_cookie

router = APIRouter()

# WP148 (Phase Z): the Skills page's panels, one per view tab (`chummer5.web.shell.SKILLS_TABS`),
# in tab order. A category tab shows the non-exotic skills of its categories; exotic skills are
# all on Special. Resonance Active skills are never offered (Technomancers are out of scope), so
# that panel is always empty and its tab disabled.
# Each entry also names its tab's label key, the panel's heading on the Filtered/Rated views.
CATEGORY_TABS: tuple[tuple[str, str, frozenset[str]], ...] = (
    ("combat", "Web_Skills_TabCombat", frozenset({"Combat Active"})),
    ("physical", "Web_Skills_TabPhysical", frozenset({"Physical Active"})),
    ("social", "Web_Skills_TabSocial", frozenset({"Social Active"})),
    ("technical", "Web_Skills_TabTechnical", frozenset({"Technical Active"})),
    ("vehicle", "Web_Skills_TabVehicle", frozenset({"Vehicle Active"})),
    ("magical", "Web_Skills_TabMagical", frozenset({"Magical Active", "Pseudo-Magical Active"})),
    ("resonance", "Web_Skills_TabResonance", frozenset({"Resonance Active"})),
)
# WP150: the views that show every section but Group at once, each under its own heading.
MULTI_SECTION_TABS = frozenset({"filtered", "rated"})
# Every tab this fragment knows; `knowledge` shows none of its panels. An unknown `skills_tab`
# falls back to the first.
SKILLS_TAB_SLUGS = frozenset(
    {slug for slug, _, _ in CATEGORY_TABS} | {"group", "special", "knowledge"} | MULTI_SECTION_TABS
)
DEFAULT_SKILLS_TAB = "combat"


def skills_tab_from(raw: object) -> str:
    tab = str(raw or "")
    return tab if tab in SKILLS_TAB_SLUGS else DEFAULT_SKILLS_TAB


def dom_id(key: str) -> str:
    """WP148: an id-safe, collision-free form of a skill key or group name, for the stable ids
    htmx needs to restore focus after an autosave swap. A catalog id (a GUID) is used as is; an
    exotic instance key (`"{id}|{specific}"`, with free text after the bar) or a group name gets
    its free text hex-encoded, so no two keys can map to one id."""
    base, _, specific = key.partition("|")
    if not specific and all(c.isalnum() or c == "-" for c in base):
        return base
    return "x" + key.encode().hex()


def _skill_allocation_context(
    character: Character | None,
    skills_letter: str,
    skill_points: Mapping[str, int],
    group_points: Mapping[str, int],
    specializations: Mapping[str, str] = MappingProxyType({}),
    karma_skill_points: Mapping[str, int] = MappingProxyType({}),
    karma_group_points: Mapping[str, int] = MappingProxyType({}),
    karma_specializations: Mapping[str, str] = MappingProxyType({}),
    *,
    error: str | Message | None = None,
    new_exotic: Mapping[str, str] = MappingProxyType({}),
    exotic_adding: bool = False,
) -> dict[str, Any]:
    """Context for `_skill_allocation.html`. Same echo-the-submission shape as
    `chummer5.web.routes.attributes._attribute_allocation_context`; `skill_points`/`group_points`/
    `specializations` feed a throwaway `SkillAllocation` used purely for display (rating/dice-pool
    preview), independent of whether the submission actually validated.

    **WP19**: same `error`-gated re-validation as `_attribute_allocation_context` -- when `error`
    is unset, re-runs `create_skill_allocation` against `skills_letter`/`skill_points`/
    `group_points`/`specializations` purely to derive `skill_budget_warning`. See that function's
    docstring for why this needs to be re-derived fresh on every render rather than decided once at
    submission time.

    **WP50/WP65**: `skill_rows["pool"]` is the *un-specialized* pool (`specialized=False`);
    `skill_rows["pool_specialized"]` is the +2 pool, populated only for skills that actually carry a
    specialization (priority-point or Karma-funded), so the template can render "X (Y)".

    **WP53**: `karma_skill_points`/`karma_group_points`/`karma_specializations` -- submitted
    together with the priority-point fields above in the same `POST /ui/skills` form, mirroring
    WP52's `karma_attr_{code}` precedent -- feed a *preview* `KarmaSkillSelection`, built by calling
    `create_karma_skill_selection` itself against a throwaway character carrying this render's own
    `allocation` (not the character's last-committed one, since the two are submitted and validated
    together) and a deliberately huge budget, so only a genuine structural problem (an unknown id, a
    group-funding/breaking conflict, ...) -- not "over budget," which the real re-validation pass
    below already reports separately -- suppresses the preview (falls back to no Karma overlay
    rather than raising through this display-only path). `display` is `character` with that preview
    attached, which `skill_rating`/`dice_pool` read directly (see `chummer5.engine.skills`'
    own docstring for why they read `character.karma_skill_selection` rather than taking it as a
    parameter).

    **WP124**: an exotic catalog entry gets no row of its own. Each bought instance (a
    `"{id}|{specific}"` key in `skill_points`/`karma_skill_points`) gets one in its category, and
    the "add an exotic skill" row below the tables echoes `new_exotic` until it is bought.

    **WP148**: rows are grouped into one panel per Skills tab (`skill_panels`, `CATEGORY_TABS`),
    exotic instances into `exotic_rows`. Each row carries one specialization (`spec`), with
    `spec_karma` saying which pool pays for it and `spec_forced` when only Karma can: a point-
    funded specialization needs a point of the skill's own (p. 129; a grouped skill can't be
    specialized in Step Five, p. 88). `exotic_adding` (the Add Special Skills button) shows the
    add row before it has anything in it.
    """
    if character is None:
        return {"character": None, "skill_error": error}
    allocation = SkillAllocation(
        skill_points=MappingProxyType(dict(skill_points)),
        group_points=MappingProxyType(dict(group_points)),
        specializations=MappingProxyType(dict(specializations)),
    )
    try:
        preview_karma_selection: KarmaSkillSelection | None = create_karma_skill_selection(
            replace(character, skill_allocation=allocation),
            SKILLS,
            karma_skill_points,
            karma_group_points,
            karma_specializations,
            karma_budget=10**9,
        )
    except ValueError:
        preview_karma_selection = None
    display = replace(character, karma_skill_selection=preview_karma_selection)
    karma_budget = character.karma_remaining + (
        character.karma_skill_selection.karma_cost
        if character.karma_skill_selection is not None
        else 0
    )
    budget = skill_point_budget(skills_letter, PRIORITIES)
    rules = skill_purchase_rules(character)  # WP116/WP117
    # WP148: sorted by name, so each panel below comes out in name order without re-sorting --
    # the Magical panel spans two categories (Arcana is Pseudo-Magical Active).
    offered = offered_skills(character)
    exotic_bases = [s for s in offered if s.exotic]
    offered_by_category = sorted(
        [s for s in offered if not s.exotic]
        + list(exotic_instances(exotic_bases, [*skill_points, *karma_skill_points])),
        key=lambda s: (s.name, s.specific or ""),
    )
    # WP65: a specialized skill's Pool is shown as "X (Y)" -- X the base (un-specialized) pool and
    # Y the +2-specialization pool -- rather than the single specialized value WP50 rendered (which
    # hid the base). `pool` is now the un-specialized pool explicitly (not `dice_pool`'s auto-detect
    # default), and `pool_specialized` carries the specialized value only when the skill actually
    # has a specialization (priority-point or Karma-funded); the template omits the parenthetical
    # otherwise. See `chummer5.engine.skills.dice_pool`'s `specialized=` override (WP50).
    preview_karma = display.karma_skill_selection
    skill_rows = [
        {
            "skill": skill,
            "dom_id": dom_id(skill.id),
            "points": allocation.skill_points.get(skill.id, 0),
            "karma_points": karma_skill_points.get(skill.id, 0),
            # WP148: one specialization per skill, paid from points or Karma (the toggle).
            "spec": allocation.specializations.get(skill.id)
            or karma_specializations.get(skill.id, ""),
            "spec_karma": skill.id not in allocation.specializations
            and skill.id in karma_specializations,
            "spec_forced": allocation.skill_points.get(skill.id, 0) < 1,
            "spec_example": first_example(skill),
            # WP82: `natural_rating` is what the two inputs above actually bought; `rating` is the
            # total once `ImprovementType.SKILL` bonuses are counted, and it can now exceed 6 (see
            # `chummer5.engine.skills.MAX_SKILL_RATING`). The template renders `natural (rating)`
            # when they differ, under a "Rating (with bonuses)" header -- deliberately *not*
            # "augmented" the way WP81 labels the attribute equivalent; see `natural_skill_rating`'s
            # own docstring for why this project can't yet claim the delta is an augmentation.
            "natural_rating": natural_skill_rating(display, allocation, skill),
            # WP116: 7 for an Aptitude skill.
            "max_rating": purchase_maximum(skill, rules.maximum_bonus),
            "rating": skill_rating(display, allocation, skill),
            "pool": dice_pool(display, allocation, skill, specialized=False),
            "pool_specialized": (
                dice_pool(display, allocation, skill, specialized=True)
                if (
                    skill.id in allocation.specializations
                    or (preview_karma is not None and skill.id in preview_karma.specializations)
                )
                else None
            ),
        }
        for skill in offered_by_category
    ]
    # WP148: one panel per category tab, in tab order, each sorted by name (`offered_by_category`
    # already is). Zips the typed `offered_by_category` skills alongside `skill_rows`'s own dicts
    # rather than keying off `row["skill"]` -- `skill_rows`'s values are typed `object`.
    paired = list(zip(offered_by_category, skill_rows, strict=True))
    skill_panels = [
        {
            "slug": slug,
            "label_key": label_key,
            "rows": [row for skill, row in paired if not skill.exotic and skill.category in cats],
        }
        for slug, label_key, cats in CATEGORY_TABS
    ]
    exotic_rows = [row for skill, row in paired if skill.exotic]
    group_rows = [
        {
            "name": group,
            "dom_id": dom_id(group),
            # WP148: the member skills, in catalog order, for the Group tab's Components column.
            "components": [s for s in SKILLS if s.skill_group == group and not s.specific],
            "points": allocation.group_points.get(group, 0),
            "karma_points": karma_group_points.get(group, 0),
        }
        for group in offered_skill_groups(character)
    ]
    budget_warning: Message | None = None
    if error is None:
        try:
            create_skill_allocation(
                skills_letter,
                PRIORITIES,
                SKILLS,
                skill_points,
                group_points,
                specializations,
                rules,
                knowledge_active_points(character),
            )
            create_karma_skill_selection(
                replace(character, skill_allocation=allocation),
                SKILLS,
                karma_skill_points,
                karma_group_points,
                karma_specializations,
                karma_budget,
            )
        except ValueError as exc:
            budget_warning = Message.of("Web_Stale_Skills", error=str(exc))
    return {
        "character": display,
        "skill_rows": skill_rows,
        "skill_panels": skill_panels,
        "exotic_rows": exotic_rows,
        "group_rows": group_rows,
        "skills_budget": budget.skills,
        # WP117: Uncouth doubles a Social skill's points.
        "skills_remaining": budget.skills
        - skill_points_spent(allocation.skill_points, allocation.specializations, SKILLS, rules)
        - knowledge_active_points(character),  # WP125: Knowledge spend past its free pool
        "skill_budget_warning": budget_warning,
        "groups_budget": budget.skill_groups,
        "groups_remaining": budget.skill_groups - sum(allocation.group_points.values()),
        "max_skill_rating": MAX_SKILL_RATING_CREATE,
        # WP60: prefixed (not the generic "karma_budget"/"karma_remaining" this key used through
        # WP59) -- `shell.chargen_context` (WP97; `_chargen_body_context` before it) merges this
        # dict with `_skill_allocation_context`'s and `_knowledge_selection_context`'s own, and all
        # three used to return the identical generic key, so whichever was merged last (Knowledge)
        # silently clobbered the other two's numbers on every full-page render. See
        # spec/worklogs/WP60.md.
        "skill_karma_budget": karma_budget,
        "skill_karma_remaining": (
            karma_budget - preview_karma_selection.karma_cost
            if preview_karma_selection is not None
            else karma_budget
        ),
        "skill_error": error,
        "exotic_bases": exotic_bases,
        "exotic_examples": {base.id: first_example(base) for base in exotic_bases},
        "new_exotic": new_exotic,
        # WP148: the add row shows once asked for, and stays while it holds anything.
        "exotic_adding": exotic_adding or any(new_exotic.values()),
    }


def _form_int(raw: object) -> int:
    try:
        return int(str(raw))
    except ValueError:
        return 0


def _parse_specializations(
    form: Any, skills: list[Skill], skill_points: Mapping[str, int]
) -> tuple[dict[str, str], dict[str, str]]:
    """WP148: each skill's one specialization (`spec_<id>`) and its toggle (`spec_karma_<id>`,
    present means Karma), split into the point-funded and Karma-funded maps the engine takes. A
    skill without a point of its own can only pay with Karma, whatever the toggle says -- the
    same rule `_skill_allocation_context` renders the toggle forced by."""
    texts = parse_specializations(form, (s.id for s in skills), "spec_")
    specializations: dict[str, str] = {}
    karma_specializations: dict[str, str] = {}
    for skill_id, text in texts.items():
        karma = form.get(f"spec_karma_{skill_id}") is not None
        if karma or skill_points.get(skill_id, 0) < 1:
            karma_specializations[skill_id] = text
        else:
            specializations[skill_id] = text
    return specializations, karma_specializations


def _parse_exotic_skills(
    form: Any, bases: tuple[Skill, ...] | list[Skill]
) -> tuple[list[str], dict[str, str]]:
    """WP124: the instance keys already on the form (each row's hidden `exotic_key`), and the
    "add an exotic skill" row's fields as submitted."""
    base_ids = {s.id for s in bases}
    keys = [
        str(key) for key in form.getlist("exotic_key") if split_skill_key(str(key))[0] in base_ids
    ]
    new = {
        field: str(form.get(f"exotic_new_{field}") or "").strip()
        for field in ("skill", "specific", "points", "karma_points")
    }
    return keys, new


def _add_new_exotic(
    new: Mapping[str, str],
    bases: list[Skill],
    existing_keys: list[str],
    skill_points: dict[str, int],
    karma_skill_points: dict[str, int],
) -> tuple[bool, Message | None]:
    """WP124: fold the "add an exotic skill" row into the spend, once it names a skill, an item,
    and some points; returns whether it did, and why not if the row is a duplicate. Until then
    the row is only echoed back, so a half-filled one isn't lost."""
    points = _form_int(new["points"])
    karma_points = _form_int(new["karma_points"])
    if new["skill"] not in {s.id for s in bases} or not new["specific"]:
        return False, None
    if not (points or karma_points):
        return False, None
    key = exotic_skill_key(new["skill"], new["specific"])
    if key in existing_keys:
        return False, Message.of("Web_Skills_ExoticDuplicate", specific=new["specific"])
    if points:
        skill_points[key] = points
    if karma_points:
        karma_skill_points[key] = karma_points
    return True, None


@router.post("/ui/skills", response_class=HTMLResponse)
async def submit_skills(request: Request) -> HTMLResponse:
    session, new_cookie = resolve_session(request)
    session.current_page = "skills"  # WP61/WP97
    form = await request.form()
    skills_tab = skills_tab_from(form.get("skills_tab"))  # WP148: re-render the same tab
    if session.character is None:
        context = _skill_allocation_context(None, session.skills_letter, {}, {})
    else:
        previous = session.character
        # WP61: character-scoped, not the module-level `MUNDANE_SKILLS`/`MUNDANE_SKILL_GROUPS`
        # -- a magic-active character's submitted Magical Active skill points would otherwise
        # be silently dropped by the parser even though the display side (`_skill_allocation_
        # context`) already widens to offer them. See that helper's own docstring/comment.
        skills_for_form = offered_skills(previous)
        groups_for_form = offered_skill_groups(previous)
        # WP124: an exotic skill's points are submitted per instance, never on its catalog id.
        exotic_bases = [s for s in skills_for_form if s.exotic]
        exotic_keys, new_exotic = _parse_exotic_skills(form, exotic_bases)
        point_keys = [s.id for s in skills_for_form if not s.exotic] + exotic_keys
        skill_points = parse_points(form, point_keys, "skill_")
        group_points = parse_points(form, groups_for_form, "group_")
        # WP53: Karma-funded points, submitted in the same form (mirrors WP52's karma_attr_{code}
        # precedent). WP148: a specialization's pool is its row's toggle.
        karma_skill_points = parse_points(form, point_keys, "karma_skill_")
        karma_group_points = parse_points(form, groups_for_form, "karma_group_")
        specializations, karma_specializations = _parse_specializations(
            form, [s for s in skills_for_form if not s.exotic], skill_points
        )
        added, duplicate = _add_new_exotic(
            new_exotic, exotic_bases, exotic_keys, skill_points, karma_skill_points
        )
        error: str | Message | None = duplicate
        if error is None:
            try:
                allocation = create_skill_allocation(
                    session.skills_letter,
                    PRIORITIES,
                    SKILLS,
                    skill_points,
                    group_points,
                    specializations,
                    skill_purchase_rules(previous),
                    knowledge_active_points(previous),  # WP125
                )
                # WP51: this section's own currently-committed Karma-skill cost is added back onto
                # `previous.karma_remaining` -- the same "exclude this section's own prior
                # commitment" idiom `_spirit_selection_context`/`_attribute_allocation_context`
                # already established -- so re-spending exactly what was already committed doesn't
                # double-subtract it.
                karma_budget = previous.karma_remaining + (
                    previous.karma_skill_selection.karma_cost
                    if previous.karma_skill_selection is not None
                    else 0
                )
                karma_selection = create_karma_skill_selection(
                    replace(previous, skill_allocation=allocation),
                    SKILLS,
                    karma_skill_points,
                    karma_group_points,
                    karma_specializations,
                    karma_budget,
                )
            except ValueError as exc:
                error = str(exc)
            else:
                session.character = replace(
                    session.character,
                    skill_allocation=allocation,
                    karma_skill_selection=karma_selection,
                )
                if added:
                    new_exotic = {}
        context = _skill_allocation_context(
            session.character,
            session.skills_letter,
            skill_points,
            group_points,
            specializations,
            karma_skill_points,
            karma_group_points,
            karma_specializations,
            error=error,
            new_exotic=new_exotic,
            exotic_adding=form.get("exotic_add") is not None and not added,
        )
    context["skills_tab"] = skills_tab
    response = templates.TemplateResponse(request, "_skill_allocation.html", context)
    set_session_cookie(request, response, new_cookie)
    return response
