"""FastAPI application factory: the web UI's entry point.

WP14 — first real chargen screen (see `spec/Implementation Plan.md`, Phase F). Lets a player
assign priority letters A-D to Heritage/Attributes/Skills/Resources (Talent is forced to E and
never offered as a choice — see `spec/Project Overview.md`'s MVP scope) and pick a metatype for
the chosen Heritage letter, backed by WP6's `chummer5.engine.character` functions directly so the
UI's result is exactly what those functions would produce for the same inputs. State lives in a
server-side, in-memory `ChargenSession` (`chummer5.web.session`) keyed by an opaque cookie — this
is a local, single-user app, so nothing fancier (database, client-side state) is warranted.

WP15 adds attribute and skill point allocation on top of WP14's confirmed metatype+priorities:
`POST /ui/attributes` and `POST /ui/skills` re-run WP6's `create_character` / WP7's
`create_skill_allocation` directly against the submitted point spend (same "UI is a thin layer
over an already-correct engine" precedent WP14 established), each returning just its own fragment
for a live HTMX update. `POST /ui/priorities` now re-renders all three sections together
(`_chargen_body.html`) since a changed metatype/Attributes/Skills letter invalidates whatever
attribute/skill points were already spent — see `ChargenSession`'s docstring for the reset rule.

WP16 rounds out chargen inputs with three more fragments/routes, same pattern: `POST /ui/qualities`
(WP8's `create_quality_selection`/`apply_quality_improvements`), `POST /ui/contacts` (WP9's
`create_contact_selection`), `POST /ui/resources` (WP9's `create_resources_selection`). One new
wrinkle WP16 surfaces: `create_character` always builds a `Character` with a brand-new, empty
`ImprovementIndex` (see its own docstring), so every route that calls it again for an
already-in-progress session (`submit_priorities`, `submit_attributes`) must re-apply any
already-committed quality selection's Improvements onto the fresh `Character`, or they'd silently
vanish the next time attributes are edited — see `_relink_quality_improvements`.

WP17 (the UI MVP milestone) adds a separate `/character/sheet` page: a read-only view of WP10's
derived stats (initiative, the three Limits, both condition monitors) plus a summary of every
already-committed selection, backed by `_character_sheet_context`. It's a standalone page rather
than another `_chargen_body.html` fragment, since none of the five chargen-form routes (`/ui/*`)
target it — wiring live updates into all five would mean out-of-band HTMX swaps for a view that's
explicitly "read-only finished character", not a form; a plain nav link plus its own full-page
render is simpler and matches the deliverable's own framing ("finish and persist a character",
distinct from "spend points"). The same page also hosts save/download (`GET /character/save`,
WP11's `to_json`/`create_character_save`) and load/import (`POST /character/load` for WP11's own
native format, `POST /character/import-chum5` for WP12's legacy import) — both repopulate every
`ChargenSession` field via `_apply_built_character_to_session`, the same shape `submit_priorities`
et al. already mutate, so the five chargen-form routes need no changes to pick up a loaded/imported
character on their next submission.

WP18 folds `ChargenSession`'s four sibling selection fields (`skill_allocation`,
`quality_selection`, `contacts`, `gear_names`) onto `chummer5.engine.character.Character` itself
(`skill_allocation`/`quality_selection`/`contact_selection`/`resources_selection`, each `None`
until committed) — see that module's docstring for the full rationale. Every route below now reads
and writes through `session.character.x` instead of a same-named `session.x`; `_apply_built_
character_to_session` shrinks to a straight assignment since `build_character` (WP11) now returns
a single fully-populated `Character` rather than the retired `BuiltCharacter` wrapper.
`_relink_quality_improvements` keeps its job (re-landing a carried-forward quality selection's
`Improvement`s onto a freshly `create_character`'d `Character`, since that function still starts
every `Character` with an empty `ImprovementIndex`) but now also re-attaches the `quality_selection`
field itself and returns the updated `Character`. A new sibling, `_relink_contact_selection`,
recomputes (not merely re-attaches) a carried-forward contact selection against the new
`Character`, since `ContactSelection.free_points`/`karma_cost` depend on `character.attribute_
value("CHA")`, which a metatype/attribute-point change can alter — unlike `quality_selection`
(fixed karma amounts, no character-state dependency) or `resources_selection` (depends only on the
Resources letter and the gear catalog, never on `character` itself), which are safe to carry
forward by plain reference. `submit_attributes`/`submit_priorities` still call `create_character()`
fresh on every edit rather than `dataclasses.replace`-ing the existing `Character` in place — WP18
deliberately defers that switch to WP19 (see both WPs' worklogs for why), so these two relink
helpers remain load-bearing for one more WP.

WP19 makes that switch, but only for `submit_priorities`: reconfirming priorities/metatype no
longer discards the player's attribute/skill/gear spend and rebuilds an empty `Character` — it
`dataclasses.replace`s the *previous* `Character` in place (new metatype/letters/budget, every
other field carried forward by reference, `improvements` included), then re-validates. Because
`Character` has no `__post_init__` invariant, a spend that no longer fits the newly reconfirmed
letters/metatype constructs without error; whether it still fits is instead re-derived, fresh, by
`_attribute_allocation_context`/`_skill_allocation_context`/`_resources_context` on every render
(each gains an `*_budget_warning` key from re-running its own `create_*` validator and catching
the `ValueError`, distinct from that same context's existing `*_error` key for a submission this
request itself just rejected) — so a now-invalid carry-forward stays visibly flagged across page
reloads until the player edits that section back within budget, rather than either silently
vanishing (the old reset) or blocking the rest of chargen. `_relink_quality_improvements` is no
longer called from `submit_priorities` (calling it after a `replace` that already carried
`improvements` forward would double the bonus) but remains necessary for `submit_attributes`,
which WP19 leaves on its pre-existing `create_character()`-fresh shape — see `spec/worklogs/WP19.md`
for why only `submit_priorities` needed the switch.

WP20 adds a new fragment/route, `POST /ui/lifestyle` (`chummer5.engine.lifestyle`'s
`create_lifestyle_selection`), for SR5's mandatory primary-Lifestyle purchase -- a new peer section
alongside Resources, not folded into `_resources.html`/`submit_resources`, even though both spend
from the same Resources-priority nuyen budget (see `_lifestyle_context`'s docstring for that shared-
budget wiring). `_chargen_body_context` computes the cross-section numbers each side needs
(`gear_cost` for `_lifestyle_context`, `lifestyle_cost` for `_resources_context`) and folds
`_lifestyle_context`'s own `lifestyle_budget_warning` into the same `priority_stale_selections`
aggregate WP19 introduced. `submit_priorities`'s `dataclasses.replace`-in-place carries a committed
`lifestyle_selection` forward automatically (an untouched field survives `replace` by reference, the
same reason `quality_selection`/`resources_selection` never needed special-casing there);
`submit_attributes` needed one explicit addition (carrying `lifestyle_selection` forward alongside
`skill_allocation`/`resources_selection`, since it still rebuilds via `create_character()` fresh).

Run locally: `uv run uvicorn chummer5.web.app:app --reload` (or `python -m uvicorn ...` — same
`uv run python -m X` workaround as `pytest`/`ruff`/`mypy`, see Project Overview.md's Development
environment note), then open http://127.0.0.1:8000/.
"""

from __future__ import annotations

import itertools
import tempfile
import xml.etree.ElementTree as ET
from collections.abc import Iterable, Mapping
from dataclasses import replace
from pathlib import Path
from types import MappingProxyType
from typing import Any

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.datastructures import FormData, UploadFile

from chummer5.data.lifestyle import load_lifestyles
from chummer5.data.metatypes import load_metatypes
from chummer5.data.priorities import load_priorities
from chummer5.data.qualities import load_qualities
from chummer5.data.skills import load_skills
from chummer5.engine.character import (
    ALLOCATABLE_ATTRIBUTES,
    PRIMARY_ATTRIBUTES,
    SPECIAL_ATTRIBUTES,
    Character,
    MetatypeChoice,
    create_character,
    metatype_choices,
)
from chummer5.engine.derived import (
    initiative_dice,
    initiative_value,
    mental_limit,
    physical_condition_monitor,
    physical_limit,
    social_limit,
    stun_condition_monitor,
)
from chummer5.engine.improvements import ImprovementIndex, ImprovementSource
from chummer5.engine.lifestyle import (
    MAX_LIFESTYLE_MONTHS,
    MIN_LIFESTYLE_MONTHS,
    create_lifestyle_selection,
)
from chummer5.engine.qualities import (
    QUALITY_KARMA_LIMIT,
    QualitySelection,
    apply_quality_improvements,
    create_quality_selection,
    mvp_quality_catalog,
    offerable_quality_catalog,
    resolve_metatype_qualities,
)
from chummer5.engine.resources import (
    FREE_CONTACT_POINTS_PER_CHARISMA,
    KARMA_PER_EXCESS_CONTACT_POINT,
    STARTER_GEAR_CATALOG,
    Contact,
    ContactSelection,
    ResourcesSelection,
    StarterGearItem,
    create_contact_selection,
    create_resources_selection,
    starting_nuyen,
)
from chummer5.engine.skills import (
    MAX_SKILL_RATING_CREATE,
    SkillAllocation,
    create_skill_allocation,
    dice_pool,
    skill_point_budget,
    skill_rating,
)
from chummer5.io.legacy_import import (
    UnsupportedLegacyCharacterError,
    import_chum5,
)
from chummer5.io.save_format import (
    CharacterSave,
    build_character,
    create_character_save,
    from_json,
    to_json,
)
from chummer5.web.session import (
    PRIORITY_LETTERS,
    SESSION_COOKIE_NAME,
    ChargenSession,
    SessionStore,
)

WEB_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = WEB_DIR / "templates"
STATIC_DIR = WEB_DIR / "static"

# Static rules data: parsed once per process, not per request (Project Overview's "parsed once at
# startup" rule for `chummer5.data` loaders).
METATYPES = load_metatypes()
PRIORITIES = load_priorities()
SKILLS = load_skills()
QUALITIES = load_qualities()
LIFESTYLES = load_lifestyles()

# The MVP-offered quality catalog (see chummer5.engine.qualities): 3 FLAT_BONUS qualities, all
# Positive. Computed once, mirroring MUNDANE_SKILLS/MUNDANE_SKILL_GROUPS below.
MVP_QUALITIES = mvp_quality_catalog(QUALITIES)

# WP20: the tier/months a fresh (or not-yet-visited) Lifestyle section pre-fills -- "Street" is the
# rulebook's own free tier ("Hey pal, life ain't all bad. It's free."), so this default never costs
# anything until the player actively picks something else, the same "starts at a legal, harmless
# default" precedent DEFAULT_HERITAGE_LETTER et al. already set in chummer5.web.session.
DEFAULT_LIFESTYLE_TIER_NAME = "Street"
DEFAULT_LIFESTYLE_MONTHS = MIN_LIFESTYLE_MONTHS

# Fixed number of contact-input rows the UI offers -- there's no client-side add/remove, so this
# is a plain, generously-sized table (mirrors the fixed-row attribute/skill tables) rather than
# dynamic HTML. A row with a blank name is treated as "no contact here" by `_parse_contacts`.
MAX_CONTACT_ROWS = 8

# MVP is mundane-only (Talent forced to E -- see Project Overview's MVP scope), so a fresh
# character's MAG/RES are always 0 and can never be raised in chargen. The 12 skills linked to
# those attributes (Alchemy, Summoning, Compiling, ...) would show a permanently-crippled dice
# pool (rating + 0, and none of them allow defaulting) if offered here -- excluded from the
# allocation UI for the same "excluded, not silently broken" reason WP2/WP3 exclude non-SR5
# metatypes/qualities from their catalogs. This is a UI-layer curation, not an engine change:
# `create_skill_allocation` itself is still generic and would accept points on these skills if
# submitted directly (e.g. via a hand-crafted request).
_MAGIC_ATTRIBUTES = ("MAG", "RES")
MUNDANE_SKILLS = tuple(
    sorted((s for s in SKILLS if s.attribute not in _MAGIC_ATTRIBUTES), key=lambda s: s.name)
)
MUNDANE_SKILL_GROUPS = tuple(
    sorted({s.skill_group for s in MUNDANE_SKILLS if s.skill_group is not None})
)


def _priority_form_context(
    *,
    heritage_letter: str,
    attributes_letter: str,
    skills_letter: str,
    resources_letter: str,
    metatype_id: str | None,
    character: object,
    error: str | None,
) -> dict[str, Any]:
    """Context for `_priority_form.html`'s own fields (letters, metatype options, the
    duplicate-letter/unoffered-metatype `error`). Always passed through `_chargen_body_context`
    before being rendered, which folds in one more key this function doesn't set itself:
    `priority_stale_selections` (WP19) -- see that function's docstring for why it's computed
    there instead of here.
    """
    heritage = PRIORITIES.heritage.get(heritage_letter)
    metatype_options = metatype_choices(heritage, METATYPES) if heritage is not None else ()
    return {
        "letters": PRIORITY_LETTERS,
        "heritage_priorities": PRIORITIES.heritage,
        "attributes_priorities": PRIORITIES.attributes,
        "skills_priorities": PRIORITIES.skills,
        "resources_priorities": PRIORITIES.resources,
        "metatype_options": metatype_options,
        "selected": {
            "heritage_letter": heritage_letter,
            "attributes_letter": attributes_letter,
            "skills_letter": skills_letter,
            "resources_letter": resources_letter,
            "metatype_id": metatype_id,
        },
        "character": character,
        "error": error,
    }


def _parse_points(form: FormData, keys: Iterable[str], prefix: str) -> dict[str, int]:
    """Read `{prefix}{key}` fields off a submitted form into a sparse `{key: points}` dict.

    Sparse (zero/absent/unparseable entries are simply omitted) so the result matches the
    "absence means 0" convention `chummer5.engine.character`/`chummer5.engine.skills` already use
    for `attribute_points`/`skill_points`/`group_points`. Negative values are intentionally *not*
    filtered here -- they're passed through so `create_character`/`create_skill_allocation`'s own
    "points spent must not be negative" validation produces the error, rather than this silently
    clamping input the engine is already responsible for rejecting.
    """
    points: dict[str, int] = {}
    for key in keys:
        raw = form.get(f"{prefix}{key}")
        if raw is None:
            continue
        try:
            value = int(str(raw))
        except ValueError:
            continue
        if value != 0:
            points[key] = value
    return points


def _parse_contacts(form: FormData, max_rows: int) -> tuple[Contact, ...]:
    """Read up to `max_rows` contact rows off a submitted form into `Contact`s.

    Any row whose name field is blank is skipped entirely (the fixed-row table has no client-side
    add/remove, so most rows are typically empty). A malformed Connection/Loyalty value is treated
    as 0 rather than dropping the whole row -- `create_contact_selection`'s own
    Connection/Loyalty-below-1 check is what's responsible for rejecting it, the same "let the
    engine validate what it's already responsible for" choice `_parse_points` makes for negative
    attribute/skill points.
    """
    contacts = []
    for i in range(max_rows):
        name = str(form.get(f"contact_name_{i}") or "").strip()
        if not name:
            continue
        try:
            connection = int(str(form.get(f"contact_connection_{i}", "0")))
        except ValueError:
            connection = 0
        try:
            loyalty = int(str(form.get(f"contact_loyalty_{i}", "0")))
        except ValueError:
            loyalty = 0
        free = form.get(f"contact_free_{i}") is not None
        contacts.append(Contact(name=name, connection=connection, loyalty=loyalty, free=free))
    return tuple(contacts)


def _parse_gear(form: FormData, catalog: Iterable[StarterGearItem]) -> tuple[str, ...]:
    """Expand each starter-gear item's submitted quantity into that many repeats of its name --
    `create_resources_selection`'s `gear_names` is a flat, repeats-allowed name list (see
    `chummer5.engine.resources`), not a `{name: quantity}` mapping. An unparseable or negative
    quantity is clamped to 0: unlike attribute/skill points, there's no engine-level "negative
    quantity" concept here for `create_resources_selection` to validate instead (repeating a name
    -3 times isn't a meaningful rejection to surface), so this is a plain web-robustness clamp, not
    a rule this function is offloading onto the engine.
    """
    names: list[str] = []
    for item in catalog:
        raw = form.get(f"gear_{item.name}")
        try:
            quantity = int(str(raw)) if raw is not None else 0
        except ValueError:
            quantity = 0
        names.extend([item.name] * max(quantity, 0))
    return tuple(names)


def _parse_lifestyle_months(form: FormData) -> int:
    """Read `lifestyle_months` off a submitted form, clamping an unparseable value to 0 -- the
    same "let the engine validate what it's already responsible for" choice `_parse_gear` makes for
    a negative gear quantity. `create_lifestyle_selection`'s own 1-100 range check is what rejects
    0 (or anything else out of range) with a specific message, not this parser.
    """
    raw = form.get("lifestyle_months")
    try:
        return int(str(raw)) if raw is not None else 0
    except ValueError:
        return 0


def _attribute_allocation_context(
    character: Character | None,
    attribute_points: Mapping[str, int],
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

    **WP19**: when `error` is unset (a clean render, not an echo of a submission this same request
    just rejected), re-runs `create_character` against `character`'s own current
    metatype/heritage/attributes letter and `attribute_points`, purely to derive
    `attribute_budget_warning` from whatever `ValueError` it raises (discarding the exception
    itself, not its message) -- `submit_priorities` no longer resets a carried-forward spend that
    no longer fits a just-reconfirmed letter/metatype (see its own comment), so this is what
    surfaces that fact, freshly, on every render for as long as it stays true. Distinct from
    `attribute_error` (sourced from a `ValueError` raised by *this specific request's* submission,
    never stored) so a template can style "you just typed something invalid" differently from
    "this was fine when you entered it, but a priority change since then broke it."
    """
    if character is None:
        return {"character": None, "attribute_error": error}
    display = replace(character, attribute_points=MappingProxyType(dict(attribute_points)))
    primary_budget = PRIORITIES.attributes[character.attributes_letter].points
    primary_spent = sum(attribute_points.get(code, 0) for code in PRIMARY_ATTRIBUTES)
    special_spent = sum(attribute_points.get(code, 0) for code in SPECIAL_ATTRIBUTES)
    rows = [
        {
            "code": code,
            "minimum": display.attribute_range(code).minimum,
            "maximum": display.attribute_range(code).maximum,
            "points": attribute_points.get(code, 0),
            "value": display.attribute_value(code),
        }
        for code in ALLOCATABLE_ATTRIBUTES
    ]
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
        "attribute_error": error,
        "attribute_budget_warning": budget_warning,
    }


def _skill_allocation_context(
    character: Character | None,
    skills_letter: str,
    skill_points: Mapping[str, int],
    group_points: Mapping[str, int],
    *,
    error: str | None = None,
) -> dict[str, Any]:
    """Context for `_skill_allocation.html`. Same echo-the-submission shape as the attribute
    context above; `skill_points`/`group_points` feed a throwaway `SkillAllocation` used purely for
    display (rating/dice-pool preview), independent of whether the submission actually validated.

    **WP19**: same `error`-gated re-validation as `_attribute_allocation_context` -- when `error`
    is unset, re-runs `create_skill_allocation` against `skills_letter`/`skill_points`/
    `group_points` purely to derive `skill_budget_warning`. See that function's docstring for why
    this needs to be re-derived fresh on every render rather than decided once at submission time.
    """
    if character is None:
        return {"character": None, "skill_error": error}
    allocation = SkillAllocation(
        skill_points=MappingProxyType(dict(skill_points)),
        group_points=MappingProxyType(dict(group_points)),
    )
    budget = skill_point_budget(skills_letter, PRIORITIES)
    skill_rows = [
        {
            "skill": skill,
            "points": allocation.skill_points.get(skill.id, 0),
            "rating": skill_rating(character, allocation, skill),
            "pool": dice_pool(character, allocation, skill),
        }
        for skill in MUNDANE_SKILLS
    ]
    group_rows = [
        {"name": group, "points": allocation.group_points.get(group, 0)}
        for group in MUNDANE_SKILL_GROUPS
    ]
    budget_warning: str | None = None
    if error is None:
        try:
            create_skill_allocation(skills_letter, PRIORITIES, SKILLS, skill_points, group_points)
        except ValueError as exc:
            budget_warning = (
                f"No longer fits since priorities were last confirmed: {exc}. "
                "Adjust the points below to continue."
            )
    return {
        "character": character,
        "skill_rows": skill_rows,
        "group_rows": group_rows,
        "skills_budget": budget.skills,
        "skills_remaining": budget.skills - sum(allocation.skill_points.values()),
        "skill_budget_warning": budget_warning,
        "groups_budget": budget.skill_groups,
        "groups_remaining": budget.skill_groups - sum(allocation.group_points.values()),
        "max_skill_rating": MAX_SKILL_RATING_CREATE,
        "skill_error": error,
    }


def _relink_quality_improvements(
    character: Character, quality_selection: QualitySelection | None
) -> Character:
    """Re-apply a carried-forward quality selection's bonuses onto a freshly built `Character`,
    and re-attach the selection itself (WP18 folded `quality_selection` onto `Character` -- a
    fresh `create_character()` call always starts it, like `improvements`, empty/`None`).

    `create_character` always returns a `Character` with a brand-new, empty `ImprovementIndex`
    (see its own docstring) -- every route that builds a new `Character` this way for an
    already-in-progress session has to re-land this selection's bonuses onto it, or a
    previously-picked quality's skill bonus would silently vanish the next time an attribute is
    edited. Safe to call unconditionally: returns `character` unchanged if nothing has ever been
    committed.

    **WP19 note**: still load-bearing for `submit_attributes` (unchanged this WP -- still rebuilds
    via `create_character()`), but no longer called from `submit_priorities`, which WP19 switched
    to `dataclasses.replace`-ing the *previous* `Character` in place. `replace` carries
    `improvements` forward *by reference*, already populated -- calling this function there would
    re-apply the same quality's bonus a second time (`apply_quality_improvements` only ever adds;
    see `_replace_committed_qualities`'s docstring for the same failure mode described from the
    other direction).
    """
    if quality_selection is None:
        return character
    apply_quality_improvements(character, quality_selection.qualities)
    return replace(character, quality_selection=quality_selection)


def _relink_metatype_qualities(character: Character) -> Character:
    """(Re)populate `character.metatype_qualities` from `character.metatype`, keeping its
    Improvements in sync (WP23).

    Unlike `_relink_quality_improvements` (a player's selection, only ever carried forward
    unchanged), what belongs here can genuinely change out from under `character.metatype_qualities`
    -- `submit_priorities` can swap the metatype itself. So this always removes whatever
    `ImprovementSource.METATYPE` Improvements `character.metatype_qualities` currently names (a
    no-op on the always-fresh, empty index `submit_attributes` builds, since a fresh `Character`'s
    `metatype_qualities` defaults to `()`) before resolving `character.metatype`'s *current* free
    qualities and re-applying -- correct whether metatype changed, stayed the same, or this is the
    first time it's ever been resolved. Safe to call unconditionally after any (re)construction of
    `character`.
    """
    for quality in character.metatype_qualities:
        character.improvements.remove_source(ImprovementSource.METATYPE, quality.id)
    metatype_qualities = resolve_metatype_qualities(character.metatype, QUALITIES)
    apply_quality_improvements(
        character, metatype_qualities, source_type=ImprovementSource.METATYPE
    )
    return replace(character, metatype_qualities=metatype_qualities)


def _relink_contact_selection(
    character: Character, contact_selection: ContactSelection | None
) -> Character:
    """Recompute a carried-forward contact selection against a freshly built `Character`.

    Unlike quality selection, a plain re-attach isn't correct here: `ContactSelection.free_points`/
    `karma_cost` are derived from `character.attribute_value("CHA")`, which a metatype change or an
    attribute-point change/reinterpretation (both things `submit_attributes` and
    `submit_priorities` can each trigger) can itself change. Recomputes from `contact_selection`'s
    own raw `contacts` tuple via
    `create_contact_selection` rather than trusting the old snapshot's numbers -- always safe to
    call (see `create_contact_selection`'s docstring: it never rejects a contact list that already
    passed its Connection/Loyalty-minimum check once). Returns `character` unchanged if no contact
    has ever been committed.
    """
    if contact_selection is None:
        return character
    return replace(
        character, contact_selection=create_contact_selection(character, contact_selection.contacts)
    )


def _replace_committed_qualities(character: Character, selection: QualitySelection) -> Character:
    """Swap whatever QUALITY-sourced Improvements `character.improvements` currently holds for
    `selection`'s, and re-attach `selection` as `character.quality_selection`.

    `apply_quality_improvements` only ever adds -- calling it twice for two submissions against
    the same `Character` (i.e. without an intervening `create_character` rebuild) would double up
    any quality that stayed selected across both, so previously-applied QUALITY improvements are
    removed first.
    """
    for imp in character.improvements.improvements:
        if imp.source_type == ImprovementSource.QUALITY:
            character.improvements.remove_source(ImprovementSource.QUALITY, imp.source_id)
    apply_quality_improvements(character, selection.qualities)
    return replace(character, quality_selection=selection)


def _quality_selection_context(
    character: Character | None,
    quality_ids: Iterable[str],
    *,
    error: str | None = None,
) -> dict[str, Any]:
    """Context for `_quality_selection.html`. `quality_ids` is whatever should be shown checked --
    the session's committed selection on a clean render, or the raw submitted checkbox values on
    an error-echo render, same shape as the attribute/skill contexts above.

    **WP23**: the pickable rows come from `offerable_quality_catalog(character, QUALITIES)`, not
    the module-level `MVP_QUALITIES`, so a quality this character's metatype already grants for
    free (e.g. an Elf's Low-Light Vision) never appears as something to spend karma on again.
    """
    if character is None:
        return {"character": None, "quality_error": error}
    offered = offerable_quality_catalog(character, QUALITIES)
    ids = set(quality_ids)
    rows = [{"quality": q, "selected": q.id in ids} for q in offered]
    positive_karma = sum(q.karma for q in offered if q.id in ids and q.category == "Positive")
    negative_karma = -sum(q.karma for q in offered if q.id in ids and q.category == "Negative")
    return {
        "character": character,
        "quality_rows": rows,
        "positive_karma": positive_karma,
        "negative_karma": negative_karma,
        "karma_limit": QUALITY_KARMA_LIMIT,
        "metatype_qualities": character.metatype_qualities,
        "quality_error": error,
    }


def _contacts_context(
    character: Character | None,
    contacts: tuple[Contact, ...],
    *,
    error: str | None = None,
) -> dict[str, Any]:
    """Context for `_contacts.html`. `points_spent`/`karma_cost` are computed directly from
    `Contact.points` (never by calling `create_contact_selection`, which raises on the very
    Connection/Loyalty-below-1 input an error-echo render needs to display) -- `free_points` reads
    `character.attribute_value("CHA")` fresh on every render, so it always reflects the character's
    *current* CHA even if an attribute submission changed it since contacts were last saved.
    """
    if character is None:
        return {"character": None, "contact_error": error}
    rows = [
        {
            "index": i,
            "name": contacts[i].name if i < len(contacts) else "",
            "connection": contacts[i].connection if i < len(contacts) else "",
            "loyalty": contacts[i].loyalty if i < len(contacts) else "",
            "free": contacts[i].free if i < len(contacts) else False,
            "points": contacts[i].points if i < len(contacts) else 0,
        }
        for i in range(MAX_CONTACT_ROWS)
    ]
    free_points = character.attribute_value("CHA") * FREE_CONTACT_POINTS_PER_CHARISMA
    points_spent = sum(contact.points for contact in contacts)
    karma_cost = max(0, points_spent - free_points) * KARMA_PER_EXCESS_CONTACT_POINT
    return {
        "character": character,
        "contact_rows": rows,
        "free_points": free_points,
        "points_spent": points_spent,
        "contact_karma_cost": karma_cost,
        "contact_error": error,
    }


def _resources_selection_for_display(
    letter: str, gear_names: Iterable[str], lifestyle_cost: int
) -> ResourcesSelection:
    """Recompute a `ResourcesSelection`'s nuyen totals against `letter`'s *current* budget, without
    `create_resources_selection`'s "spend must not exceed budget" check.

    WP19 needs this because `submit_priorities` now carries a committed `ResourcesSelection`
    forward unconditionally, even across a Resources-letter change -- the stored object's own
    `resources_letter`/`nuyen_budget` fields can go stale relative to `session.resources_letter`.
    `_resources_context` never hits this (it recomputes its own budget/spent numbers directly from
    `resources_letter`/`gear_names`, never trusting the stored object's fields), but
    `_character_sheet_context` reads `resources_selection.nuyen_budget`/`.nuyen_remaining` straight
    off the stored object -- so it needs a freshly-recomputed one, and needs it to not raise on an
    over-budget carry-forward the way `create_resources_selection` deliberately does.

    **WP20**: `lifestyle_cost` (the character's currently-selected `lifestyle_selection.total_cost`,
    or 0 if none yet) folds into `nuyen_remaining` the same way `create_resources_selection` folds
    it in -- passed in rather than recomputed, since this function has no reason to know about
    `chummer5.engine.lifestyle` beyond the one number it needs to share a budget with.
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
        nuyen_remaining=budget - spent - lifestyle_cost,
        lifestyle_cost=lifestyle_cost,
    )


def _resources_context(
    character: Character | None,
    resources_letter: str,
    gear_names: tuple[str, ...],
    lifestyle_cost: int,
    *,
    error: str | None = None,
) -> dict[str, Any]:
    """Context for `_resources.html`. `gear_names` is the flat, repeats-allowed name list
    `create_resources_selection` itself takes -- tallied into per-item quantities here purely for
    display.

    **WP19**: same `error`-gated re-validation as `_attribute_allocation_context` -- when `error`
    is unset, re-runs `create_resources_selection` against `resources_letter`/`gear_names` purely
    to derive `resources_budget_warning`. `submit_priorities` carries a committed gear purchase
    forward unconditionally now (see its own comment), so a Resources-letter reconfirmation that
    shrinks the nuyen budget below what's already been spent needs to surface here rather than
    silently going over. Not explicitly named in the Implementation Plan's WP19 entry (which lists
    `_priority_form_context`/`_attribute_allocation_context`/`_skill_allocation_context` as the
    three to extend) -- included anyway since gear is carried forward exactly like skill points are,
    and a stale gear purchase deserves the same explanation, not silence.

    **WP20**: `lifestyle_cost` (the character's currently-selected `lifestyle_selection.total_cost`,
    or 0 if none yet) is folded into the displayed remaining budget and the re-validation call, so
    gear and the primary Lifestyle correctly share one Resources-priority nuyen budget instead of
    each silently assuming the whole thing for itself. Not a bidirectional live update, though: this
    section's own `hx-target` only swaps `#resources`, so buying gear here doesn't refresh
    `#lifestyle`'s own displayed remaining-budget number (or vice versa) until the next full page
    render -- a deliberate, documented scope boundary (see this WP's worklog), not an oversight;
    both sections' *validation* (whether a submission is actually accepted) is always correct
    regardless, since both call the same joint `create_resources_selection` check.
    """
    if character is None:
        return {"character": None, "resources_error": error}
    counts: dict[str, int] = {}
    for name in gear_names:
        counts[name] = counts.get(name, 0) + 1
    # WP21: ~330 items instead of 5 -- grouped by category (the catalog is already sorted by
    # (category, name), so a plain groupby needs no re-sorting) rather than one long flat table, per
    # the Implementation Plan's explicit instruction. `_character_sheet_context`'s own `gear_rows`
    # (a different context key, just the *purchased* items) is unaffected -- that list is always
    # short, no grouping needed there.
    gear_groups: list[dict[str, Any]] = [
        {
            "category": category,
            "rows": [
                {
                    "item": item,
                    "quantity": counts.get(item.name, 0),
                    "subtotal": item.cost * counts.get(item.name, 0),
                }
                for item in items
            ],
        }
        for category, items in itertools.groupby(
            STARTER_GEAR_CATALOG, key=lambda item: item.category or "Other"
        )
    ]
    budget = starting_nuyen(resources_letter, PRIORITIES)
    spent = sum(int(row["subtotal"]) for group in gear_groups for row in group["rows"])
    budget_warning: str | None = None
    if error is None:
        try:
            create_resources_selection(
                resources_letter, PRIORITIES, gear_names, lifestyle_cost=lifestyle_cost
            )
        except ValueError as exc:
            budget_warning = (
                f"No longer fits since priorities were last confirmed: {exc}. "
                "Adjust the gear below to continue."
            )
    return {
        "character": character,
        "gear_groups": gear_groups,
        "nuyen_budget": budget,
        "nuyen_spent": spent,
        "nuyen_remaining": budget - spent - lifestyle_cost,
        "resources_error": error,
        "resources_budget_warning": budget_warning,
    }


def _lifestyle_context(
    character: Character | None,
    resources_letter: str,
    tier_name: str,
    months: int,
    gear_cost: int,
    *,
    error: str | None = None,
) -> dict[str, Any]:
    """Context for `_lifestyle.html`: WP20's mandatory primary-Lifestyle purchase (core rulebook,
    p. 369), drawing from the same Resources-priority nuyen budget `_resources_context` validates
    gear against. `gear_cost` is the character's *currently committed* gear spend
    (`resources_selection.nuyen_spent`, or 0 if none yet) -- passed in rather than recomputed here,
    the mirror image of `_resources_context`'s own `lifestyle_cost` parameter (see its docstring for
    why this cross-section number is threaded through rather than each section reaching into the
    other's catalog/state directly).

    Same `error`-gated re-validation pattern as `_resources_context`/`_skill_allocation_context`:
    when `error` is unset (i.e. this isn't redisplaying a submission this same request just
    rejected), re-derives whether the currently-selected tier/months still fits the combined budget,
    surfacing a distinct `lifestyle_budget_warning` rather than silently going over on the next
    render.
    """
    if character is None:
        return {
            "character": None,
            "lifestyle_options": LIFESTYLES,
            "selected_tier_name": tier_name,
            "selected_months": months,
            "min_lifestyle_months": MIN_LIFESTYLE_MONTHS,
            "max_lifestyle_months": MAX_LIFESTYLE_MONTHS,
            "lifestyle_error": error,
        }
    budget = starting_nuyen(resources_letter, PRIORITIES)
    budget_warning: str | None = None
    if error is None:
        try:
            selection = create_lifestyle_selection(tier_name, months, LIFESTYLES)
        except ValueError as exc:
            budget_warning = str(exc)
        else:
            total_spent = gear_cost + selection.total_cost
            if total_spent > budget:
                budget_warning = (
                    "No longer fits since priorities were last confirmed: gear "
                    f"({gear_cost}) + lifestyle ({selection.total_cost}) spend {total_spent} "
                    f"exceeds Resources priority {resources_letter}'s nuyen budget of {budget}. "
                    "Adjust the lifestyle below to continue."
                )
    return {
        "character": character,
        "lifestyle_options": LIFESTYLES,
        "selected_tier_name": tier_name,
        "selected_months": months,
        "min_lifestyle_months": MIN_LIFESTYLE_MONTHS,
        "max_lifestyle_months": MAX_LIFESTYLE_MONTHS,
        "nuyen_budget": budget,
        "lifestyle_error": error,
        "lifestyle_budget_warning": budget_warning,
    }


def _character_sheet_context(
    session: ChargenSession, *, error: str | None = None, info: str | None = None
) -> dict[str, Any]:
    """Context for `_character_sheet.html`: WP10's derived stats plus a read-only recap of every
    already-committed selection. Unlike the five `_*_context` builders above, there is no
    echo-the-submission variant here -- this page never redisplays invalid input, only the
    session's own last-known-good state (or `error`/`info`, set by the save/load routes below).

    `contact_selection` is recomputed here (via `create_contact_selection`), not read directly off
    `character.contact_selection` -- same reasoning as `_relink_contact_selection`: its
    `free_points`/`karma_cost` depend on `character.attribute_value("CHA")`, so recomputing from
    the committed `contacts` tuple is the only way to guarantee this always reflects the
    character's *current* CHA, even if every mutating route's own relink call were somehow missed.

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
    skill_rows = (
        [
            {"skill": skill, "rating": rating, "pool": dice_pool(character, allocation, skill)}
            for skill in MUNDANE_SKILLS
            if (rating := skill_rating(character, allocation, skill)) > 0
        ]
        if allocation is not None
        else []
    )
    quality_names = (
        [q.name for q in character.quality_selection.qualities]
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
    resources_selection = _resources_selection_for_display(
        session.resources_letter,
        committed_gear_names,
        lifestyle_selection.total_cost if lifestyle_selection is not None else 0,
    )
    gear_counts: dict[str, int] = {}
    for item in resources_selection.gear:
        gear_counts[item.name] = gear_counts.get(item.name, 0) + 1

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
        "quality_karma_cost": (
            character.quality_selection.karma_cost if character.quality_selection is not None else 0
        ),
        "contact_karma_cost": contact_selection.karma_cost,
        "initiative_value": initiative_value(character),
        "initiative_dice": initiative_dice(character),
        "physical_limit": physical_limit(character),
        "mental_limit": mental_limit(character),
        "social_limit": social_limit(character),
        "physical_cm": physical_condition_monitor(character),
        "stun_cm": stun_condition_monitor(character),
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
    return create_character_save(
        metatype_name=character.metatype.name,
        heritage_letter=session.heritage_letter,
        attributes_letter=session.attributes_letter,
        attribute_points=character.attribute_points,
        skills_letter=session.skills_letter,
        skill_points=allocation.skill_points if allocation is not None else {},
        group_points=allocation.group_points if allocation is not None else {},
        quality_ids=quality_ids,
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
    unlike `create_character`'s always-empty one (see `_relink_quality_improvements`'s docstring
    for why that matters elsewhere).
    """
    session.heritage_letter = save.heritage_letter
    session.attributes_letter = save.attributes_letter
    session.skills_letter = save.skills_letter
    session.resources_letter = save.resources_letter
    session.metatype_id = built.metatype.id
    session.character = built


def _chargen_body_context(session: ChargenSession, priority_ctx: dict[str, Any]) -> dict[str, Any]:
    """Merge the priority-form context with a clean (non-error) render of the attribute, skill,
    quality, contact, and resources sections, reflecting the session's currently committed state.
    Used by both `GET /` and a successful `POST /ui/priorities` (the places that render every
    section at once).

    **WP19**: also folds a `priority_stale_selections` flag into `priority_ctx` -- `True` if any of
    the attribute/skill/resources sections below just reported their own `*_budget_warning` (see
    those context builders), i.e. the currently-committed spend no longer fits the currently-
    confirmed priorities. Computed here, once, from the same three sub-context calls this function
    already has to make, rather than inside `_priority_form_context` itself (which would mean
    either duplicating those three `create_*` re-validation calls a second time, or restructuring
    both of its call sites to compute them first and pass the flag in) -- `_priority_form.html` is
    only ever rendered from this merged dict (see both call sites below), so it reads
    `priority_stale_selections` like any other key regardless of which function actually set it.
    """
    character = session.character
    attribute_points = character.attribute_points if character is not None else {}
    attribute_ctx = _attribute_allocation_context(character, attribute_points)
    allocation = character.skill_allocation if character is not None else None
    skill_points = allocation.skill_points if allocation is not None else {}
    group_points = allocation.group_points if allocation is not None else {}
    skill_ctx = _skill_allocation_context(
        character, session.skills_letter, skill_points, group_points
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
    resources_ctx = _resources_context(
        character, session.resources_letter, gear_names, lifestyle_cost
    )
    lifestyle_ctx = _lifestyle_context(
        character, session.resources_letter, lifestyle_tier_name, lifestyle_months, gear_cost
    )
    stale = bool(
        attribute_ctx.get("attribute_budget_warning")
        or skill_ctx.get("skill_budget_warning")
        or resources_ctx.get("resources_budget_warning")
        or lifestyle_ctx.get("lifestyle_budget_warning")
    )
    priority_ctx = {**priority_ctx, "priority_stale_selections": stale}
    return {
        **priority_ctx,
        **attribute_ctx,
        **skill_ctx,
        **quality_ctx,
        **contact_ctx,
        **lifestyle_ctx,
        **resources_ctx,
    }


def create_app() -> FastAPI:
    """Build the FastAPI app: priority-letter + metatype selection, WP14's real chargen screen."""
    app = FastAPI(title="Chummer5")
    app.state.sessions = SessionStore()
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
    templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

    def resolve_session(request: Request) -> tuple[ChargenSession, str | None]:
        """Look up this request's session by cookie, creating one if absent.

        Returns the session plus a new cookie value to set on the *actual* response the caller
        ends up returning -- not `None`, `Depends`-injected `Response`. FastAPI only merges an
        injected `Response`'s headers into the final response when the endpoint returns a plain
        value; every route here returns a `TemplateResponse` (already a `Response`) directly, and
        FastAPI substitutes that wholesale rather than merging headers onto it (confirmed by
        reading `fastapi/routing.py`'s request handler) -- so the cookie has to be set on the
        object that's actually returned.
        """
        store: SessionStore = request.app.state.sessions
        session_id = request.cookies.get(SESSION_COOKIE_NAME)
        session = store.get(session_id) if session_id else None
        if session is not None:
            return session, None
        new_session_id, session = store.create()
        return session, new_session_id

    @app.get("/", response_class=HTMLResponse)
    def index(request: Request) -> HTMLResponse:
        session, new_cookie = resolve_session(request)
        priority_ctx = _priority_form_context(
            heritage_letter=session.heritage_letter,
            attributes_letter=session.attributes_letter,
            skills_letter=session.skills_letter,
            resources_letter=session.resources_letter,
            metatype_id=session.metatype_id,
            character=session.character,
            error=None,
        )
        context = _chargen_body_context(session, priority_ctx)
        response = templates.TemplateResponse(request, "chargen.html", context)
        if new_cookie is not None:
            response.set_cookie(SESSION_COOKIE_NAME, new_cookie, httponly=True, samesite="lax")
        return response

    @app.get("/ui/metatypes", response_class=HTMLResponse)
    def metatype_options_fragment(request: Request, heritage_letter: str) -> HTMLResponse:
        heritage = PRIORITIES.heritage.get(heritage_letter)
        metatype_options = metatype_choices(heritage, METATYPES) if heritage is not None else ()
        context = {
            "metatype_options": metatype_options,
            "selected": {"metatype_id": None},
        }
        return templates.TemplateResponse(request, "_metatype_select.html", context)

    @app.post("/ui/priorities", response_class=HTMLResponse)
    def submit_priorities(
        request: Request,
        heritage_letter: str = Form(...),
        attributes_letter: str = Form(...),
        skills_letter: str = Form(...),
        resources_letter: str = Form(...),
        metatype_id: str = Form(...),
    ) -> HTMLResponse:
        session, new_cookie = resolve_session(request)
        submitted_letters = (heritage_letter, attributes_letter, skills_letter, resources_letter)
        error: str | None = None
        character = session.character

        if sorted(submitted_letters) != sorted(PRIORITY_LETTERS):
            error = (
                "Heritage, Attributes, Skills, and Resources must each use a different "
                f"priority letter ({', '.join(PRIORITY_LETTERS)}), one each."
            )
        else:
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
            metatype_id=metatype_id,
            character=character,
            error=error,
        )
        context = _chargen_body_context(session, priority_ctx)
        response = templates.TemplateResponse(request, "_chargen_body.html", context)
        if new_cookie is not None:
            response.set_cookie(SESSION_COOKIE_NAME, new_cookie, httponly=True, samesite="lax")
        return response

    @app.post("/ui/attributes", response_class=HTMLResponse)
    async def submit_attributes(request: Request) -> HTMLResponse:
        session, new_cookie = resolve_session(request)
        if session.character is None:
            context = _attribute_allocation_context(None, {})
        else:
            form = await request.form()
            attribute_points = _parse_points(form, ALLOCATABLE_ATTRIBUTES, "attr_")
            # `create_character` only needs `metatype`/`special_attribute_points` off a
            # `MetatypeChoice` (see its own docstring) -- both are already stable fields on the
            # session's committed `Character`, so there's no need to re-look-up the Heritage
            # priority/metatype catalog here the way `submit_priorities` does.
            choice = MetatypeChoice(
                metatype=session.character.metatype,
                special_attribute_points=session.character.special_attribute_points,
                karma=0,
            )
            previous = session.character
            try:
                character = create_character(
                    choice,
                    session.heritage_letter,
                    session.attributes_letter,
                    PRIORITIES,
                    attribute_points,
                )
            except ValueError as exc:
                context = _attribute_allocation_context(
                    session.character, attribute_points, error=str(exc)
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
                character = replace(
                    character,
                    skill_allocation=previous.skill_allocation,
                    resources_selection=previous.resources_selection,
                    lifestyle_selection=previous.lifestyle_selection,
                )
                session.character = character
                context = _attribute_allocation_context(character, attribute_points)
        response = templates.TemplateResponse(request, "_attribute_allocation.html", context)
        if new_cookie is not None:
            response.set_cookie(SESSION_COOKIE_NAME, new_cookie, httponly=True, samesite="lax")
        return response

    @app.post("/ui/skills", response_class=HTMLResponse)
    async def submit_skills(request: Request) -> HTMLResponse:
        session, new_cookie = resolve_session(request)
        if session.character is None:
            context = _skill_allocation_context(None, session.skills_letter, {}, {})
        else:
            form = await request.form()
            skill_points = _parse_points(form, (s.id for s in MUNDANE_SKILLS), "skill_")
            group_points = _parse_points(form, MUNDANE_SKILL_GROUPS, "group_")
            try:
                allocation = create_skill_allocation(
                    session.skills_letter, PRIORITIES, SKILLS, skill_points, group_points
                )
            except ValueError as exc:
                context = _skill_allocation_context(
                    session.character,
                    session.skills_letter,
                    skill_points,
                    group_points,
                    error=str(exc),
                )
            else:
                session.character = replace(session.character, skill_allocation=allocation)
                context = _skill_allocation_context(
                    session.character, session.skills_letter, skill_points, group_points
                )
        response = templates.TemplateResponse(request, "_skill_allocation.html", context)
        if new_cookie is not None:
            response.set_cookie(SESSION_COOKIE_NAME, new_cookie, httponly=True, samesite="lax")
        return response

    @app.post("/ui/qualities", response_class=HTMLResponse)
    async def submit_qualities(request: Request) -> HTMLResponse:
        session, new_cookie = resolve_session(request)
        if session.character is None:
            context = _quality_selection_context(None, ())
        else:
            form = await request.form()
            quality_ids = [str(value) for value in form.getlist("quality_id")]
            # WP23: validate against this character's own offerable catalog, not the raw QUALITIES
            # catalog, so a tampered/stale submission can't buy an already metatype-granted quality
            # either -- `create_quality_selection` already raises "not an MVP-offered quality id"
            # for anything not in whatever catalog it's given, so this alone is sufficient.
            offered = offerable_quality_catalog(session.character, QUALITIES)
            try:
                selection = create_quality_selection(quality_ids, offered)
            except ValueError as exc:
                context = _quality_selection_context(session.character, quality_ids, error=str(exc))
            else:
                session.character = _replace_committed_qualities(session.character, selection)
                context = _quality_selection_context(session.character, quality_ids)
        response = templates.TemplateResponse(request, "_quality_selection.html", context)
        if new_cookie is not None:
            response.set_cookie(SESSION_COOKIE_NAME, new_cookie, httponly=True, samesite="lax")
        return response

    @app.post("/ui/contacts", response_class=HTMLResponse)
    async def submit_contacts(request: Request) -> HTMLResponse:
        session, new_cookie = resolve_session(request)
        if session.character is None:
            context = _contacts_context(None, ())
        else:
            form = await request.form()
            contacts = _parse_contacts(form, MAX_CONTACT_ROWS)
            try:
                selection = create_contact_selection(session.character, contacts)
            except ValueError as exc:
                context = _contacts_context(session.character, contacts, error=str(exc))
            else:
                session.character = replace(session.character, contact_selection=selection)
                context = _contacts_context(session.character, contacts)
        response = templates.TemplateResponse(request, "_contacts.html", context)
        if new_cookie is not None:
            response.set_cookie(SESSION_COOKIE_NAME, new_cookie, httponly=True, samesite="lax")
        return response

    @app.post("/ui/resources", response_class=HTMLResponse)
    async def submit_resources(request: Request) -> HTMLResponse:
        session, new_cookie = resolve_session(request)
        if session.character is None:
            context = _resources_context(None, session.resources_letter, (), 0)
        else:
            form = await request.form()
            gear_names = _parse_gear(form, STARTER_GEAR_CATALOG)
            lifestyle_selection = session.character.lifestyle_selection
            lifestyle_cost = (
                lifestyle_selection.total_cost if lifestyle_selection is not None else 0
            )
            try:
                selection = create_resources_selection(
                    session.resources_letter,
                    PRIORITIES,
                    gear_names,
                    lifestyle_cost=lifestyle_cost,
                )
            except ValueError as exc:
                context = _resources_context(
                    session.character,
                    session.resources_letter,
                    gear_names,
                    lifestyle_cost,
                    error=str(exc),
                )
            else:
                session.character = replace(session.character, resources_selection=selection)
                context = _resources_context(
                    session.character, session.resources_letter, gear_names, lifestyle_cost
                )
        response = templates.TemplateResponse(request, "_resources.html", context)
        if new_cookie is not None:
            response.set_cookie(SESSION_COOKIE_NAME, new_cookie, httponly=True, samesite="lax")
        return response

    @app.post("/ui/lifestyle", response_class=HTMLResponse)
    async def submit_lifestyle(request: Request) -> HTMLResponse:
        session, new_cookie = resolve_session(request)
        if session.character is None:
            context = _lifestyle_context(
                None,
                session.resources_letter,
                DEFAULT_LIFESTYLE_TIER_NAME,
                DEFAULT_LIFESTYLE_MONTHS,
                0,
            )
        else:
            form = await request.form()
            tier_name = str(form.get("lifestyle_tier") or "")
            months = _parse_lifestyle_months(form)
            resources_selection = session.character.resources_selection
            gear_names = (
                tuple(item.name for item in resources_selection.gear)
                if resources_selection is not None
                else ()
            )
            gear_cost = resources_selection.nuyen_spent if resources_selection is not None else 0
            try:
                lifestyle_selection = create_lifestyle_selection(tier_name, months, LIFESTYLES)
                new_resources_selection = create_resources_selection(
                    session.resources_letter,
                    PRIORITIES,
                    gear_names,
                    lifestyle_cost=lifestyle_selection.total_cost,
                )
            except ValueError as exc:
                context = _lifestyle_context(
                    session.character,
                    session.resources_letter,
                    tier_name,
                    months,
                    gear_cost,
                    error=str(exc),
                )
            else:
                session.character = replace(
                    session.character,
                    lifestyle_selection=lifestyle_selection,
                    resources_selection=new_resources_selection,
                )
                context = _lifestyle_context(
                    session.character, session.resources_letter, tier_name, months, gear_cost
                )
        response = templates.TemplateResponse(request, "_lifestyle.html", context)
        if new_cookie is not None:
            response.set_cookie(SESSION_COOKIE_NAME, new_cookie, httponly=True, samesite="lax")
        return response

    @app.get("/character/sheet", response_class=HTMLResponse)
    def character_sheet(request: Request) -> HTMLResponse:
        session, new_cookie = resolve_session(request)
        context = _character_sheet_context(session)
        response = templates.TemplateResponse(request, "character_sheet.html", context)
        if new_cookie is not None:
            response.set_cookie(SESSION_COOKIE_NAME, new_cookie, httponly=True, samesite="lax")
        return response

    @app.get("/character/save")
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

    @app.post("/character/load", response_class=HTMLResponse)
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

    @app.post("/character/import-chum5", response_class=HTMLResponse)
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
                    info = " ".join(messages)
        context = _character_sheet_context(session, error=error, info=info)
        response = templates.TemplateResponse(request, "_character_sheet.html", context)
        if new_cookie is not None:
            response.set_cookie(SESSION_COOKIE_NAME, new_cookie, httponly=True, samesite="lax")
        return response

    return app


app = create_app()
