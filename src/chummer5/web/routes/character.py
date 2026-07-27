"""Character-sheet/save/load/import routes: `GET /character/sheet`, `GET /character/save`,
`POST /character/load` (WP11's native format), `POST /character/import-chum5` (WP12's legacy
import).

**WP62**: split out of the former `chummer5.web.app` -- see `spec/plan/phase-r-architecture-
cleanup.md`'s WP58 audit for the target shape this module is part of. Houses the two genuinely
cross-cutting aggregator/save helpers that read every committed selection off `Character` at once
(`_character_sheet_context`, `_character_save_from_session`), not just the four routes.
"""

from __future__ import annotations

import tempfile
import xml.etree.ElementTree as ET
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, Response
from starlette.datastructures import UploadFile

from chummer5.engine.character import ALLOCATABLE_ATTRIBUTES, Character
from chummer5.engine.derived import (
    drain_resistance,
    essence,
    initiative_dice,
    initiative_value,
    mental_limit,
    physical_condition_monitor,
    physical_limit,
    social_limit,
    stun_condition_monitor,
    unmodeled_effect_notes,
)
from chummer5.engine.resources import (
    STARTER_GEAR_CATALOG,
    ResourcesSelection,
    create_contact_selection,
    karma_to_nuyen,
    starting_nuyen,
)
from chummer5.engine.skills import dice_pool, skill_rating
from chummer5.io.legacy_import import UnsupportedLegacyCharacterError, import_chum5
from chummer5.io.save_format import (
    DEFAULT_TALENT_CODENAME,
    CharacterSave,
    build_character,
    create_character_save,
    from_json,
    to_json,
)
from chummer5.web.catalogs import (
    ALL_SKILLS_SORTED,
    BIOWARE,
    CYBERWARE,
    DEFAULT_LIFESTYLE_MONTHS,
    DEFAULT_LIFESTYLE_TIER_NAME,
    FOCI,
    LIFESTYLES,
    MENTORS,
    METATYPES,
    POWERS,
    PRIORITIES,
    QUALITIES,
    SKILLS,
    SPELLS,
    TRADITIONS,
    templates,
)
from chummer5.web.forms import display_karma_to_nuyen
from chummer5.web.session import SESSION_COOKIE_NAME, ChargenSession, resolve_session

router = APIRouter()


def _resources_selection_for_display(
    letter: str,
    gear_names: Iterable[str],
    lifestyle_cost: int,
    cyberware_cost: int,
    bioware_cost: int,
    karma_converted: int = 0,
    foci_cost: int = 0,
) -> ResourcesSelection:
    """Recompute a `ResourcesSelection`'s nuyen totals against `letter`'s *current* budget, without
    `create_resources_selection`'s "spend must not exceed budget" check.

    WP19 needs this because `submit_priorities` now carries a committed `ResourcesSelection`
    forward unconditionally, even across a Resources-letter change -- the stored object's own
    `resources_letter`/`nuyen_budget` fields can go stale relative to `session.resources_letter`.
    `chummer5.web.routes.resources._resources_context` never hits this (it recomputes its own
    budget/spent numbers directly from `resources_letter`/`gear_names`, never trusting the stored
    object's fields), but `_character_sheet_context` reads `resources_selection.nuyen_budget`/
    `.nuyen_remaining` straight off the stored object -- so it needs a freshly-recomputed one, and
    needs it to not raise on an over-budget carry-forward the way `create_resources_selection`
    deliberately does.

    **WP20**: `lifestyle_cost` (the character's currently-selected `lifestyle_selection.total_cost`,
    or 0 if none yet) folds into `nuyen_remaining` the same way `create_resources_selection` folds
    it in -- passed in rather than recomputed, since this function has no reason to know about
    `chummer5.engine.lifestyle` beyond the one number it needs to share a budget with.

    **WP34**: `cyberware_cost` (the character's currently-selected `cyberware_selection.nuyen_
    spent`, or 0 if none yet) folds in the same way, extending the shared budget from two sections
    to three.

    **WP45**: `bioware_cost` (the character's currently-selected `bioware_selection.nuyen_spent`,
    or 0 if none yet) folds in the same way, extending the shared budget to four sections.

    **WP43**: `karma_converted` (the character's currently-committed `resources_selection
    .karma_converted`, or 0 if none yet) tops up the available budget the same way -- see
    `chummer5.engine.resources`'s own module docstring.

    **WP47**: `foci_cost` (the character's currently-selected `foci_selection.nuyen_cost`, or 0 if
    none yet) folds in the same way, extending the shared budget to five sections.
    """
    by_name = {item.name: item for item in STARTER_GEAR_CATALOG}
    selected = tuple(by_name[name] for name in gear_names if name in by_name)
    budget = starting_nuyen(letter, PRIORITIES)
    spent = sum(item.cost for item in selected)
    return ResourcesSelection(
        resources_letter=letter,
        nuyen_budget=budget,
        gear=selected,
        nuyen_spent=spent,
        nuyen_remaining=(
            budget
            + display_karma_to_nuyen(karma_converted)
            - spent
            - lifestyle_cost
            - cyberware_cost
            - bioware_cost
            - foci_cost
        ),
        lifestyle_cost=lifestyle_cost,
        cyberware_cost=cyberware_cost,
        bioware_cost=bioware_cost,
        karma_converted=karma_converted,
        foci_cost=foci_cost,
    )


def _character_sheet_context(
    session: ChargenSession, *, error: str | None = None, info: str | None = None
) -> dict[str, Any]:
    """Context for `_character_sheet.html`: WP10's derived stats plus a read-only recap of every
    already-committed selection. Unlike the `_*_context` builders in `chummer5.web.routes`, there is
    no echo-the-submission variant here -- this page never redisplays invalid input, only the
    session's own last-known-good state (or `error`/`info`, set by the save/load routes below).

    `contact_selection` is recomputed here (via `create_contact_selection`), not read directly off
    `character.contact_selection` -- same reasoning as
    `chummer5.web.routes.contacts._relink_contact_selection`: its `free_points`/`karma_cost` depend
    on `character.attribute_value("CHA")`, so recomputing from the committed `contacts` tuple is the
    only way to guarantee this always reflects the character's *current* CHA, even if every mutating
    route's own relink call were somehow missed.

    **WP19**: `resources_selection` is now recomputed too (via `_resources_selection_for_display`),
    for the same reason -- through WP18, `session.resources_letter` only ever changed alongside a
    reset (a fresh, budget-matching `ResourcesSelection`), so trusting the stored object's own
    `nuyen_budget` was safe. WP19 removed that reset (see `submit_priorities`'s own comment), so the
    stored object's budget can now be stale relative to `session.resources_letter`; `create_
    resources_selection` itself isn't used here because it raises on an over-budget carry-forward,
    which this read-only page must still render (as a negative `nuyen_remaining`), not crash on.
    """
    character = session.character
    if character is None:
        return {"character": None, "sheet_error": error, "sheet_info": info}

    allocation = character.skill_allocation
    karma_knowledge_points = (
        character.karma_knowledge_selection.points
        if character.karma_knowledge_selection is not None
        else {}
    )
    # WP29: the full `SKILLS` catalog, not `MUNDANE_SKILLS` -- a Magician's Talent free-skill grant
    # (chummer5.engine.magic.apply_magic_skill_grant_improvements) can raise a Magical Active
    # skill's rating above 0 via a pure Improvement, with no `SkillAllocation` points spent on it at
    # all (see that function's own docstring for why it deliberately never touches the buy-UI's
    # budget), so a Magician/Adept's granted skill(s) would otherwise never appear here even though
    # they have a real, nonzero dice pool. Safe for a Mundane character too: no skill this catalog
    # adds back (Magical Active/RES-linked) can ever have nonzero `SkillAllocation` points or
    # Improvements for one (MUNDANE_SKILLS's exclusion from the *buy* UI still stands -- see that
    # constant's own comment -- so nothing offers points on them), so `rating` stays 0 and the
    # `rating > 0` filter below excludes them exactly as before this WP.
    # WP50: `dice_pool`'s own default (whether `skill.id` is in `allocation.specializations`)
    # supplies `specialized=` here, so the sheet's pool matches the buy screen's without repeating
    # the lookup.
    # WP53: `rating`/`pool` already reflect any Karma-funded skill/group spend -- `skill_rating`/
    # `dice_pool` read `character.karma_skill_selection` directly (see that module's own WP53
    # docstring paragraph), not something this context needs to fold in itself. `specialization`
    # does need the explicit fallback below: it's the one field `dice_pool`'s auto-detect resolves
    # internally without exposing which of the two sources (skill-point-funded vs. Karma-funded)
    # supplied it, and this row display needs the name itself, not just whether one exists.
    karma_skill_selection = character.karma_skill_selection
    skill_rows = (
        [
            {
                "skill": skill,
                "rating": rating,
                "specialization": (
                    allocation.specializations.get(skill.id)
                    or (
                        karma_skill_selection.specializations.get(skill.id, "")
                        if karma_skill_selection is not None
                        else ""
                    )
                ),
                "pool": dice_pool(character, allocation, skill),
            }
            for skill in ALL_SKILLS_SORTED
            if (rating := skill_rating(character, allocation, skill)) > 0
        ]
        if allocation is not None
        else []
    )
    # WP55: a SELECT_TEXT quality's chosen free-text detail is shown alongside its name (e.g.
    # "SINner (National) (UCAS)") rather than needing its own context key/template branch.
    quality_names = (
        [
            f"{q.name} ({character.quality_selection.quality_text[q.id]})"
            if q.id in character.quality_selection.quality_text
            else q.name
            for q in character.quality_selection.qualities
        ]
        if character.quality_selection is not None
        else []
    )
    # WP23: shown separately from quality_names -- these were never a karma spend (excluded from
    # quality_karma_cost below, which stays quality_selection-only), so conflating the two lists
    # would misrepresent what the player actually chose to buy.
    metatype_quality_names = [q.name for q in character.metatype_qualities]
    committed_contacts = (
        character.contact_selection.contacts if character.contact_selection is not None else ()
    )
    contact_selection = create_contact_selection(character, committed_contacts)
    committed_gear_names = (
        tuple(item.name for item in character.resources_selection.gear)
        if character.resources_selection is not None
        else ()
    )
    lifestyle_selection = character.lifestyle_selection
    cyberware_selection = character.cyberware_selection
    bioware_selection = character.bioware_selection
    foci_selection = character.foci_selection
    committed_karma_converted = (
        character.resources_selection.karma_converted
        if character.resources_selection is not None
        else 0
    )
    resources_selection = _resources_selection_for_display(
        session.resources_letter,
        committed_gear_names,
        lifestyle_selection.total_cost if lifestyle_selection is not None else 0,
        cyberware_selection.nuyen_spent if cyberware_selection is not None else 0,
        bioware_selection.nuyen_spent if bioware_selection is not None else 0,
        committed_karma_converted,
        foci_selection.nuyen_cost if foci_selection is not None else 0,
    )
    gear_counts: dict[str, int] = {}
    for item in resources_selection.gear:
        gear_counts[item.name] = gear_counts.get(item.name, 0) + 1
    # WP34: tallied the same way gear is, since duplicate cyberware purchases (a matched pair of
    # cyberlimbs) are legal -- see chummer5.engine.cyberware's own docstring.
    cyberware_counts: dict[str, int] = {}
    for cyberware_item in cyberware_selection.items if cyberware_selection is not None else ():
        cyberware_counts[cyberware_item.name] = cyberware_counts.get(cyberware_item.name, 0) + 1
    # WP45: same tallying for bioware.
    bioware_counts: dict[str, int] = {}
    for bioware_item in bioware_selection.items if bioware_selection is not None else ():
        bioware_counts[bioware_item.name] = bioware_counts.get(bioware_item.name, 0) + 1

    return {
        "character": character,
        "priority_summary": {
            "heritage": (
                f"{session.heritage_letter} — {PRIORITIES.heritage[session.heritage_letter].name}"
            ),
            "attributes": (
                f"{session.attributes_letter} — "
                f"{PRIORITIES.attributes[session.attributes_letter].name}"
            ),
            "skills": (
                f"{session.skills_letter} — {PRIORITIES.skills[session.skills_letter].name}"
            ),
            "resources": (
                f"{session.resources_letter} — "
                f"{PRIORITIES.resources[session.resources_letter].name}"
            ),
            "talent": (
                f"{session.talent_letter} — {PRIORITIES.talent[session.talent_letter].name}"
            ),
        },
        "attribute_rows": [
            {"code": code, "value": character.attribute_value(code)}
            for code in ALLOCATABLE_ATTRIBUTES
        ],
        "sheet_skill_rows": skill_rows,
        "quality_names": quality_names,
        "metatype_quality_names": metatype_quality_names,
        "contacts": contact_selection.contacts,
        "gear_rows": [
            {"name": name, "quantity": quantity} for name, quantity in sorted(gear_counts.items())
        ],
        "lifestyle_tier_name": (
            lifestyle_selection.tier.name if lifestyle_selection is not None else None
        ),
        "lifestyle_months": lifestyle_selection.months if lifestyle_selection is not None else None,
        "lifestyle_cost": (
            lifestyle_selection.total_cost if lifestyle_selection is not None else 0
        ),
        "nuyen_budget": resources_selection.nuyen_budget,
        "nuyen_remaining": resources_selection.nuyen_remaining,
        "karma_converted": resources_selection.karma_converted,
        "karma_to_nuyen_amount": karma_to_nuyen(resources_selection.karma_converted),
        "quality_karma_cost": (
            character.quality_selection.karma_cost if character.quality_selection is not None else 0
        ),
        "contact_karma_cost": contact_selection.karma_cost,
        # WP53: Step Seven's own two new Karma-spend categories, alongside quality/contact above.
        "karma_skill_cost": (
            character.karma_skill_selection.karma_cost
            if character.karma_skill_selection is not None
            else 0
        ),
        "karma_knowledge_cost": (
            character.karma_knowledge_selection.karma_cost
            if character.karma_knowledge_selection is not None
            else 0
        ),
        "initiative_value": initiative_value(character),
        "initiative_dice": initiative_dice(character),
        "physical_limit": physical_limit(character),
        "mental_limit": mental_limit(character),
        "social_limit": social_limit(character),
        "physical_cm": physical_condition_monitor(character),
        "stun_cm": stun_condition_monitor(character),
        # WP29: hidden entirely (not shown as zeroes) for Mundane -- `magic_type` gates the whole
        # block in `_character_sheet.html`, mirroring how `lifestyle_tier_name`/etc. already gate
        # their own "None until committed" sections.
        "magic_type": character.magic_type,
        # Post-WP29 correction: the *finished* MAG rating (Talent-granted base + any Special
        # Attribute Points spent + improvements), not the raw Talent-granted `magic_rating` alone
        # -- see chummer5.engine.character.Character's own docstring correction. WP35: this is
        # already the Essence-reduced value (attribute_value("MAG") itself changed, not this call
        # site) -- `magic_essence_loss`/`magic_rating_before_essence_loss` below exist only so the
        # template can show *why* it's reduced, not to recompute the reduction.
        "magic_rating": character.attribute_value("MAG"),
        "magic_essence_loss": character.magic_essence_loss,
        "magic_rating_before_essence_loss": character.magic_rating_before_essence_loss,
        "tradition_name": character.tradition.name if character.tradition is not None else None,
        "power_points": character.power_points,
        # WP48: the picked Mentor Spirit archetype (None if not taken) -- General/Magician-or-Adept
        # slot names shown for flavor even where their bonus is NOT_YET_SUPPORTED/NO_EFFECT
        # (mirrors chummer5.engine.foci's own "the pick is real even when the bonus isn't applied"
        # posture), since the advantage/disadvantage text is the point of the pick either way.
        "mentor_spirit": (
            character.quality_selection.mentor_spirit
            if character.quality_selection is not None
            else None
        ),
        "drain_resistance": drain_resistance(character),
        "spell_names": (
            [spell.name for spell in character.spell_selection.spells]
            if character.spell_selection is not None
            else []
        ),
        "spell_karma_cost": (
            character.spell_selection.karma_cost if character.spell_selection is not None else 0
        ),
        "power_rows": (
            [
                {
                    "name": pick.power.name,
                    "rating": pick.rating,
                    "selected_attribute": pick.selected_attribute,
                }
                for pick in character.power_selection.picks
            ]
            if character.power_selection is not None
            else []
        ),
        # WP46: `force` is shown live (character.attribute_value("MAG")), not the stored per-spirit
        # snapshot -- see chummer5.engine.spirits' module docstring for why the stored value can go
        # stale after a later attribute edit, and why the sheet deliberately doesn't trust it.
        "bound_spirit_rows": (
            [
                {
                    "spirit_type": spirit.spirit_type,
                    "force": character.attribute_value("MAG"),
                    "services": spirit.services,
                }
                for spirit in character.bound_spirit_selection.spirits
            ]
            if character.bound_spirit_selection is not None
            else []
        ),
        "bound_spirit_karma_cost": (
            character.bound_spirit_selection.karma_cost
            if character.bound_spirit_selection is not None
            else 0
        ),
        # WP34: current Essence (replaces the fixed "6" no character before this WP could ever
        # move away from) and a purchased-cyberware recap, the same "None until committed" shape
        # every other selection-backed sheet section already has.
        "essence": essence(character),
        "cyberware_rows": [
            {"name": name, "quantity": quantity}
            for name, quantity in sorted(cyberware_counts.items())
        ],
        # WP45: same recap for bioware, alongside cyberware's.
        "bioware_rows": [
            {"name": name, "quantity": quantity}
            for name, quantity in sorted(bioware_counts.items())
        ],
        # WP47: bonded foci recap -- name, chosen Force, and each pick's own nuyen/Karma cost.
        "foci_rows": (
            [
                {
                    "name": pick.focus.name,
                    "force": pick.force,
                    "nuyen_cost": pick.force * pick.focus.cost_per_force,
                    "karma_cost": pick.force * pick.focus.bonding_karma_per_force,
                }
                for pick in foci_selection.picks
            ]
            if foci_selection is not None
            else []
        ),
        "foci_nuyen_cost": foci_selection.nuyen_cost if foci_selection is not None else 0,
        "foci_karma_cost": foci_selection.karma_cost if foci_selection is not None else 0,
        # WP49: Knowledge/Language recap -- both empty lists for an as-yet-uncommitted selection,
        # the same "None until committed" shape every other sheet section already has.
        # WP53: `rating` here includes any Karma-funded increase on top of the free-point-funded
        # base (`character.karma_knowledge_selection.points`, keyed by name -- see that class's own
        # docstring) -- unlike skill_rows above, nothing in the engine folds this in automatically
        # (a Knowledge/Language pick's own `rating` field is the free-point-funded figure only),
        # so this context does the addition itself.
        "knowledge_skill_rows": (
            [
                {
                    "name": pick.name,
                    "category": pick.category,
                    "rating": pick.rating + karma_knowledge_points.get(pick.name, 0),
                }
                for pick in character.knowledge_selection.knowledge_skills
            ]
            if character.knowledge_selection is not None
            else []
        ),
        "language_rows": (
            [
                {
                    "name": pick.name,
                    "rating": pick.rating + karma_knowledge_points.get(pick.name, 0),
                    "native": pick.native,
                }
                for pick in character.knowledge_selection.languages
            ]
            if character.knowledge_selection is not None
            else []
        ),
        # WP56: a collapsible disclosure of every currently-held aspect's unmodeled real effect
        # (Project Overview's "Unmodeled real effects" table) -- () for a character with none (e.g.
        # a plain Human with no NO_EFFECT/SELECT_TEXT qualities), which `_character_sheet.html`
        # renders by hiding the section entirely (see this WP's own worklog for that choice).
        "unmodeled_effect_rows": unmodeled_effect_notes(character),
        "sheet_error": error,
        "sheet_info": info,
    }


def _character_save_from_session(session: ChargenSession) -> CharacterSave:
    """Build a `CharacterSave` (WP11) from a session's currently committed selections -- the
    inverse of `_apply_built_character_to_session` below. Only called once `session.character` is
    confirmed non-`None` (see `download_save`).

    **WP20**: unlike the other selections, a save's `lifestyle_tier_name`/`lifestyle_months` are
    never left as an "empty" placeholder when uncommitted -- `CharacterSave` requires a concrete
    Lifestyle (see its own docstring), so an as-yet-unvisited Lifestyle section falls back to
    `DEFAULT_LIFESTYLE_TIER_NAME`/`DEFAULT_LIFESTYLE_MONTHS` (the free "Street" tier, 1 month)
    rather than leaving the save in a state `build_character` couldn't reconstruct.

    **WP29**: `talent_letter`/`talent_codename`/`tradition_id`/`granted_skill_ids`/`spell_ids`/
    `power_picks` now thread through the character's *real* committed Talent selection instead of
    always defaulting to Mundane (`CharacterSave`'s own pre-WP29 fallback -- see its module
    docstring) -- `session.talent_letter` is the session-side letter (never folded onto `Character`
    itself, same as `skills_letter`/`resources_letter`; see `chummer5.web.session`'s docstring),
    while the codename/tradition/grant/spell/power picks all come straight off `character`'s own
    flat fields and `spell_selection`/`power_selection`, falling back to Mundane defaults only for
    an as-yet-uncommitted Talent selection (`character.magic_type is None`), mirroring the
    Lifestyle fallback immediately above.

    **WP34**: `cyberware_item_ids` threads through the same "selection, not derived value" way
    every prior field already does, defaulting to `()` for an as-yet-uncommitted selection --
    `CyberwareSelection.items` may repeat the same id (duplicate purchases are legal, see
    `chummer5.engine.cyberware`'s own docstring), so this is a flat, repeats-allowed id list, not a
    `{id: quantity}` mapping, mirroring `gear_names` immediately above.

    **WP45**: `bioware_item_ids` threads through identically.

    **WP43**: `karma_converted` reads straight off `character.resources_selection.karma_converted`
    (0 for an as-yet-uncommitted Resources section), the same "selection lives on the committed
    object, not the session" shape `gear_names` immediately above already has.

    **WP46**: `bound_spirit_picks` reads straight off `character.bound_spirit_selection.spirits` as
    `(spirit_type, services)` pairs, `()` for an as-yet-uncommitted selection -- `force` is never
    included (see `chummer5.engine.spirits`'s module docstring for why).

    **WP47**: `foci_picks` reads straight off `character.foci_selection.picks` as `(focus_id,
    force)` pairs, `()` for an as-yet-uncommitted selection -- unlike Bound Spirits' Force, a
    focus's Force *is* the player's own chosen value (not re-derived live), so it's included
    directly.

    **WP44**: `build_method` reads straight off `session.build_method` -- unlike every field above,
    it isn't re-derived from `character` at all (nothing on `Character` holds it; see
    `ChargenSession`'s own WP44 docstring paragraph for why), but it still needs to round-trip
    through a save so a reloaded Sum-to-Ten character's next priorities reconfirmation applies the
    right validity rule instead of silently falling back to Priority's bijection.

    **WP50**: `specializations` reads straight off `allocation.specializations`, `{}` for an
    as-yet-uncommitted Skills section, the same shape `skill_points`/`group_points` immediately
    above already have (it lives on the same `SkillAllocation`, not a separate `Character` field).

    **WP52**: `karma_attribute_points` reads straight off `character.karma_attribute_selection
    .points`, `{}` for an as-yet-uncommitted Karma-funded attribute spend, mirroring
    `attribute_points`'s own shape.
    """
    character = session.character
    assert character is not None
    allocation = character.skill_allocation
    quality_ids = (
        tuple(q.id for q in character.quality_selection.qualities)
        if character.quality_selection is not None
        else ()
    )
    contacts = (
        character.contact_selection.contacts if character.contact_selection is not None else ()
    )
    gear_names = (
        tuple(item.name for item in character.resources_selection.gear)
        if character.resources_selection is not None
        else ()
    )
    lifestyle_selection = character.lifestyle_selection
    spell_ids = (
        tuple(spell.id for spell in character.spell_selection.spells)
        if character.spell_selection is not None
        else ()
    )
    power_picks = (
        tuple(
            (pick.power.id, pick.rating, pick.selected_attribute)
            for pick in character.power_selection.picks
        )
        if character.power_selection is not None
        else ()
    )
    cyberware_item_ids = (
        tuple(item.id for item in character.cyberware_selection.items)
        if character.cyberware_selection is not None
        else ()
    )
    bioware_item_ids = (
        tuple(item.id for item in character.bioware_selection.items)
        if character.bioware_selection is not None
        else ()
    )
    karma_converted = (
        character.resources_selection.karma_converted
        if character.resources_selection is not None
        else 0
    )
    bound_spirit_picks = (
        tuple(
            (spirit.spirit_type, spirit.services)
            for spirit in character.bound_spirit_selection.spirits
        )
        if character.bound_spirit_selection is not None
        else ()
    )
    foci_picks = (
        tuple((pick.focus.id, pick.force) for pick in character.foci_selection.picks)
        if character.foci_selection is not None
        else ()
    )
    mentor_spirit = (
        character.quality_selection.mentor_spirit
        if character.quality_selection is not None
        else None
    )
    quality_text = (
        character.quality_selection.quality_text
        if character.quality_selection is not None
        else {}
    )
    knowledge_selection = character.knowledge_selection
    knowledge_skill_picks = (
        tuple(
            (pick.name, pick.category, pick.rating) for pick in knowledge_selection.knowledge_skills
        )
        if knowledge_selection is not None
        else ()
    )
    language_skill_picks = (
        tuple((pick.name, pick.rating, pick.native) for pick in knowledge_selection.languages)
        if knowledge_selection is not None
        else ()
    )
    return create_character_save(
        metatype_name=character.metatype.name,
        heritage_letter=session.heritage_letter,
        attributes_letter=session.attributes_letter,
        attribute_points=character.attribute_points,
        skills_letter=session.skills_letter,
        skill_points=allocation.skill_points if allocation is not None else {},
        group_points=allocation.group_points if allocation is not None else {},
        specializations=allocation.specializations if allocation is not None else {},
        quality_ids=quality_ids,
        quality_text=quality_text,
        contacts=contacts,
        resources_letter=session.resources_letter,
        gear_names=gear_names,
        lifestyle_tier_name=(
            lifestyle_selection.tier.name
            if lifestyle_selection is not None
            else DEFAULT_LIFESTYLE_TIER_NAME
        ),
        lifestyle_months=(
            lifestyle_selection.months
            if lifestyle_selection is not None
            else DEFAULT_LIFESTYLE_MONTHS
        ),
        talent_letter=session.talent_letter,
        talent_codename=character.magic_type or DEFAULT_TALENT_CODENAME,
        tradition_id=character.tradition.id if character.tradition is not None else None,
        granted_skill_ids=character.magic_granted_skill_ids,
        spell_ids=spell_ids,
        power_picks=power_picks,
        magic_attribute_points=character.magic_attribute_points,
        cyberware_item_ids=cyberware_item_ids,
        bioware_item_ids=bioware_item_ids,
        karma_converted=karma_converted,
        bound_spirit_picks=bound_spirit_picks,
        foci_picks=foci_picks,
        mentor_spirit_archetype_id=(
            mentor_spirit.archetype.id if mentor_spirit is not None else None
        ),
        mentor_spirit_general_choice_id=(
            mentor_spirit.general_choice.id if mentor_spirit is not None else None
        ),
        build_method=session.build_method,
        knowledge_skill_picks=knowledge_skill_picks,
        language_skill_picks=language_skill_picks,
        karma_attribute_points=(
            character.karma_attribute_selection.points
            if character.karma_attribute_selection is not None
            else {}
        ),
        karma_skill_points=(
            character.karma_skill_selection.skill_points
            if character.karma_skill_selection is not None
            else {}
        ),
        karma_group_points=(
            character.karma_skill_selection.group_points
            if character.karma_skill_selection is not None
            else {}
        ),
        karma_specializations=(
            character.karma_skill_selection.specializations
            if character.karma_skill_selection is not None
            else {}
        ),
        karma_knowledge_points=(
            character.karma_knowledge_selection.points
            if character.karma_knowledge_selection is not None
            else {}
        ),
    )


def _apply_built_character_to_session(
    session: ChargenSession, save: CharacterSave, built: Character
) -> None:
    """Overwrite `ChargenSession` from a successfully loaded/imported character -- used by both
    `load_save` (WP11's native format) and `import_chum5_route` (WP12's legacy import), since both
    ultimately produce the same `(CharacterSave, Character)` pair (WP18 retired the
    `BuiltCharacter` wrapper `build_character` used to return -- see `chummer5.io.save_format`'s
    docstring; `built` already carries its own `skill_allocation`/`quality_selection`/
    `contact_selection`/`resources_selection`, so there's nothing left to reassemble here). Safe to
    call regardless of the session's prior state (a fresh session or one already mid-chargen): every
    field this WP's chargen routes read is set here, none is merged with what came before.

    `built` (not a re-`create_character` call) is used for `session.character` directly --
    `build_character` already ran `apply_quality_improvements` on it (see
    `chummer5.io.save_format`), so it arrives with the right `ImprovementIndex` already populated,
    unlike `create_character`'s always-empty one (see
    `chummer5.web.routes.qualities._relink_quality_improvements`'s docstring for why that matters
    elsewhere).

    **WP29**: `session.talent_letter` is set from `save.talent_letter` (WP28's field, unused by
    this function until now -- WP24-WP28 all left this hardcoded to `DEFAULT_TALENT_LETTER` since
    no save this project's own web layer produced before WP29 could ever carry a real one; see
    `chummer5.io.save_format`'s module docstring). A save/import predating WP28 entirely still
    defaults to `DEFAULT_TALENT_LETTER` via `CharacterSave`'s own field default (`_dict_to_save`'s
    `.get(..., default)` read), so this assignment is correct for every save format version this
    project has ever written, not just post-WP29 ones.

    **WP44**: `session.build_method` is set from `save.build_method` the same way -- a save/import
    predating this WP defaults to `PRIORITY_BUILD_METHOD` via `CharacterSave`'s own field default,
    so a loaded Sum-to-Ten character's next priorities reconfirmation applies the right validity
    rule instead of silently reverting to Priority's bijection (which the carried-forward letters
    might not even satisfy, if they repeat).
    """
    session.heritage_letter = save.heritage_letter
    session.attributes_letter = save.attributes_letter
    session.skills_letter = save.skills_letter
    session.resources_letter = save.resources_letter
    session.talent_letter = save.talent_letter
    session.build_method = save.build_method
    session.metatype_id = built.metatype.id
    session.character = built


@router.get("/character/sheet", response_class=HTMLResponse)
def character_sheet(request: Request) -> HTMLResponse:
    session, new_cookie = resolve_session(request)
    context = _character_sheet_context(session)
    response = templates.TemplateResponse(request, "character_sheet.html", context)
    if new_cookie is not None:
        response.set_cookie(SESSION_COOKIE_NAME, new_cookie, httponly=True, samesite="lax")
    return response


@router.get("/character/save")
def download_save(request: Request) -> Response:
    session, new_cookie = resolve_session(request)
    if session.character is None:
        raise HTTPException(
            status_code=400, detail="Confirm a metatype and priorities before saving."
        )
    body = to_json(_character_save_from_session(session))
    response = Response(
        content=body,
        media_type="application/json",
        headers={"Content-Disposition": 'attachment; filename="character.json"'},
    )
    if new_cookie is not None:
        response.set_cookie(SESSION_COOKIE_NAME, new_cookie, httponly=True, samesite="lax")
    return response


@router.post("/character/load", response_class=HTMLResponse)
async def load_save(request: Request) -> HTMLResponse:
    session, new_cookie = resolve_session(request)
    form = await request.form()
    upload = form.get("save_file")
    error: str | None = None
    info: str | None = None
    if not isinstance(upload, UploadFile) or not upload.filename:
        error = "Choose a save file to load."
    else:
        raw = await upload.read()
        try:
            text = raw.decode("utf-8")
            save = from_json(text)
            built = build_character(
                save,
                metatypes=METATYPES,
                priorities=PRIORITIES,
                skills=SKILLS,
                qualities=QUALITIES,
                lifestyles=LIFESTYLES,
                traditions=TRADITIONS,
                spells=SPELLS,
                powers=POWERS,
                cyberware=CYBERWARE,
                bioware=BIOWARE,
                foci=FOCI,
                mentors=MENTORS,
            )
        # A user-supplied file's shape is never trusted beyond this point -- malformed JSON
        # (ValueError, via json.JSONDecodeError/UnicodeDecodeError), a missing field
        # (KeyError), a save shaped as something other than a JSON object (AttributeError, from
        # calling .get on a list/scalar), or a shape that parses but fails one of
        # build_character's own validations (ValueError) are all just "not a loadable save",
        # reported the same way rather than crashing the request.
        except (ValueError, KeyError, AttributeError) as exc:
            error = f"Could not load save: {exc}"
        else:
            _apply_built_character_to_session(session, save, built)
            info = "Character loaded."
    context = _character_sheet_context(session, error=error, info=info)
    response = templates.TemplateResponse(request, "_character_sheet.html", context)
    if new_cookie is not None:
        response.set_cookie(SESSION_COOKIE_NAME, new_cookie, httponly=True, samesite="lax")
    return response


@router.post("/character/import-chum5", response_class=HTMLResponse)
async def import_chum5_route(request: Request) -> HTMLResponse:
    session, new_cookie = resolve_session(request)
    form = await request.form()
    upload = form.get("chum5_file")
    error: str | None = None
    info: str | None = None
    if not isinstance(upload, UploadFile) or not upload.filename:
        error = "Choose a .chum5 file to import."
    else:
        raw = await upload.read()
        # `import_chum5`/`load_chum5` take a `Path`, not bytes -- write the upload to a scratch
        # file rather than widening that module's signature for this one caller. Deleted
        # automatically once the `with` block exits, success or failure.
        with tempfile.NamedTemporaryFile(suffix=".chum5") as tmp:
            tmp.write(raw)
            tmp.flush()
            try:
                result = import_chum5(
                    Path(tmp.name),
                    metatypes=METATYPES,
                    priorities=PRIORITIES,
                    skills=SKILLS,
                    qualities=QUALITIES,
                    lifestyles=LIFESTYLES,
                    traditions=TRADITIONS,
                    spells=SPELLS,
                    powers=POWERS,
                    cyberware=CYBERWARE,
                    bioware=BIOWARE,
                )
            except UnsupportedLegacyCharacterError as exc:
                error = "Cannot import: " + "; ".join(exc.reasons)
            except ET.ParseError as exc:
                error = f"Not a valid .chum5 file: {exc}"
            else:
                _apply_built_character_to_session(session, result.save, result.built)
                messages = ["Character imported."]
                if result.dropped_qualities:
                    messages.append(
                        "Dropped qualities (not MVP-supported): "
                        + ", ".join(result.dropped_qualities)
                    )
                if result.dropped_skills:
                    messages.append(
                        "Dropped skills (unresolvable): " + ", ".join(result.dropped_skills)
                    )
                # WP29: surfaced now that a real Magician/Adept import can actually succeed
                # (WP28 added these fields to `ImportResult`, but nothing reached the browser
                # for them until this WP wired traditions/spells/powers into this route at all).
                if result.dropped_spells:
                    messages.append(
                        "Dropped spells (not SR5-scoped): " + ", ".join(result.dropped_spells)
                    )
                if result.dropped_powers:
                    messages.append(
                        "Dropped powers (not MVP-supported): "
                        + ", ".join(result.dropped_powers)
                    )
                info = " ".join(messages)
    context = _character_sheet_context(session, error=error, info=info)
    response = templates.TemplateResponse(request, "_character_sheet.html", context)
    if new_cookie is not None:
        response.set_cookie(SESSION_COOKIE_NAME, new_cookie, httponly=True, samesite="lax")
    return response
