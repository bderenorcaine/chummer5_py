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

WP34 adds a third new fragment/route, `POST /ui/cyberware` (`chummer5.engine.cyberware`'s
`create_cyberware_selection`/`apply_cyberware_improvements`), for Phase J's cyberware purchase --
another new peer section alongside Resources and Lifestyle, not folded into `_resources.html`/
`submit_resources`, mirroring WP20's own "Lifestyle gets its own section despite sharing a budget"
choice (see `_cyberware_context`'s docstring for why). All three sections now share one nuyen
budget: `chummer5.engine.resources.create_resources_selection` gained a `cyberware_cost` parameter
alongside `lifestyle_cost`, so the joint over-budget check is a genuine three-way one, and
`_resources_context`/`_lifestyle_context`/`_cyberware_context` each take the other two sections'
already-committed cost as a plain `int` (the same cross-section wiring `_chargen_body_context`
already does for gear/Lifestyle, now extended to all three). Unlike quality/contact Improvements, a
cyberware purchase's `source_id` is the item's own catalog id shared across every duplicate
purchase (see `chummer5.engine.cyberware`'s own docstring), so `_replace_committed_cyberware`
removes by *distinct* id, not once per purchased unit. `submit_priorities`'s `dataclasses.replace`-
in-place carries a committed `cyberware_selection` forward automatically, same as `lifestyle_
selection`; `submit_attributes` needed one explicit addition (`_relink_cyberware_selection`,
mirroring `_relink_quality_improvements`'s shape, since it still rebuilds via `create_character()`
fresh). `_character_sheet_context` gains the character's current Essence
(`chummer5.engine.derived.essence`, replacing the fixed "6" no character before this WP could ever
move away from) and a purchased-cyberware list.

WP24 retires "Talent forced to E" as a hardcoded assumption: the priority form gains a 5th letter
selector (Talent, alongside Heritage/Attributes/Skills/Resources), and `submit_priorities` validates
a 5-way A-E permutation instead of a 4-way A-D one. This is deliberately zero new player-visible
capability -- Talent's chosen *letter* is now real, session-held state
(`chummer5.web.session.ChargenSession.talent_letter`), but its *option* still resolves
unconditionally to `priorities.mundane_talent()` (letter E's own "Mundane" entry) regardless of
which letter was picked, since no other letter's Talent list even contains a Mundane option (see
`_priority_form_context`'s docstring). `Character` gains no `talent_letter` field of its own in
this WP -- nothing on `Character` reads it yet, the same reason `skills_letter`/`resources_letter`
never got one either; WP25 adds it once real archetype selection needs to look the letter up
against `priorities.talent`.

WP44 adds a second build method, Sum-to-Ten, alongside WP14's Priority (bijection) rule -- a radio
selector in `_priority_form.html` picks which validity rule `submit_priorities` applies to the same
5 letter dropdowns (no new controls needed: Sum-to-Ten already allows any of the 5 dropdowns' A-E
range per category, it just doesn't require them to be *distinct*). `ChargenSession.build_method`
holds the pending choice the same "pre-`Character` UI state" way `talent_letter` does (see that
class's own docstring) -- `Character` needs no field for it, since neither `create_character` nor
`build_character` ever validated the letter *assignment*'s shape to begin with (only
`submit_priorities` did, and still does). `_priority_form_context` always computes a live
`sum_to_ten_total` (never raises on an off-target combination, only on a malformed letter -- see
`chummer5.engine.build_method.sum_to_ten_total`'s own docstring), displayed only when Sum-to-Ten is
the selected method.

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
from decimal import Decimal
from pathlib import Path
from types import MappingProxyType
from typing import Any

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.datastructures import FormData, UploadFile

from chummer5.data.bioware import Bioware, load_bioware
from chummer5.data.cyberware import Cyberware, load_cyberware
from chummer5.data.foci import Focus, load_foci
from chummer5.data.knowledge import KNOWLEDGE_CATEGORIES, SUGGESTED_LANGUAGES
from chummer5.data.lifestyle import load_lifestyles
from chummer5.data.mentors import MentorSpiritArchetype, load_mentors
from chummer5.data.metatypes import load_metatypes
from chummer5.data.powers import Power, load_powers
from chummer5.data.priorities import load_priorities
from chummer5.data.qualities import load_qualities
from chummer5.data.skills import load_skills
from chummer5.data.spells import load_spells
from chummer5.data.traditions import load_traditions
from chummer5.engine.bioware import (
    BiowareSelection,
    apply_bioware_improvements,
    create_bioware_selection,
)
from chummer5.engine.build_method import (
    PRIORITY_BUILD_METHOD,
    SUM_TO_TEN_BUILD_METHOD,
    SUM_TO_TEN_TARGET,
    SUPPORTED_BUILD_METHODS,
    sum_to_ten_total,
    validate_sum_to_ten_total,
)
from chummer5.engine.character import (
    ALLOCATABLE_ATTRIBUTES,
    PRIMARY_ATTRIBUTES,
    SPECIAL_ATTRIBUTES,
    Character,
    MetatypeChoice,
    create_character,
    metatype_choices,
)
from chummer5.engine.cyberware import (
    CyberwareSelection,
    apply_cyberware_improvements,
    create_cyberware_selection,
)
from chummer5.engine.derived import (
    BASE_ESSENCE,
    drain_resistance,
    essence,
    initiative_dice,
    initiative_value,
    mental_limit,
    physical_condition_monitor,
    physical_limit,
    social_limit,
    stun_condition_monitor,
)
from chummer5.engine.foci import (
    CHARGEN_FORCE_CAP_MULTIPLIER,
    FociSelection,
    apply_foci_improvements,
    create_foci_selection,
)
from chummer5.engine.improvements import ImprovementIndex, ImprovementSource
from chummer5.engine.knowledge import (
    KnowledgeSkillPick,
    LanguageSkillPick,
    create_knowledge_selection,
    free_knowledge_points,
    native_language_limit,
)
from chummer5.engine.lifestyle import (
    MAX_LIFESTYLE_MONTHS,
    MIN_LIFESTYLE_MONTHS,
    create_lifestyle_selection,
)
from chummer5.engine.magic import (
    MAGIC_SKILL_GRANT_SOURCE_ID,
    MagicSelection,
    PowerSelection,
    apply_magic_skill_grant_improvements,
    apply_power_improvements,
    create_magic_attribute_points,
    create_magic_selection,
    create_power_selection,
    create_spell_selection,
    magic_skill_grant_eligible_skills,
    mvp_power_catalog,
    offered_talent_options,
)
from chummer5.engine.qualities import (
    MENTOR_SPIRIT_QUALITY_NAME,
    QUALITY_KARMA_LIMIT,
    QualitySelection,
    apply_mentor_spirit_improvements,
    apply_quality_improvements,
    create_quality_selection,
    mvp_quality_catalog,
    offerable_quality_catalog,
    resolve_metatype_qualities,
)
from chummer5.engine.resources import (
    FREE_CONTACT_POINTS_PER_CHARISMA,
    KARMA_PER_EXCESS_CONTACT_POINT,
    MAX_KARMA_TO_NUYEN,
    STARTER_GEAR_CATALOG,
    Contact,
    ContactSelection,
    ResourcesSelection,
    StarterGearItem,
    available_nuyen,
    create_contact_selection,
    create_resources_selection,
    karma_to_nuyen,
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
from chummer5.engine.spirits import create_bound_spirit_selection, offered_spirit_types
from chummer5.io.legacy_import import (
    UnsupportedLegacyCharacterError,
    import_chum5,
)
from chummer5.io.save_format import (
    DEFAULT_TALENT_CODENAME,
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
# WP34 (Phase J's UI): the flat-cost, flat-Essence, Standard-grade cyberware catalog (WP31).
CYBERWARE = load_cyberware()
# WP45: the flat-cost, flat-Essence, low-Availability, Standard-grade bioware catalog.
BIOWARE = load_bioware()
# WP47: the Rating-scaled SR5 Foci catalog (32 items, 7 rulebook categories).
FOCI = load_foci()
# WP29 (Phase I's UI): Talent/tradition/spell/power catalogs, loaded once like every other
# `chummer5.data` catalog above.
TRADITIONS = load_traditions()
SPELLS = load_spells()
POWERS = load_powers()
# WP48: the 16 SR5 Mentor Spirit archetypes.
MENTORS = load_mentors()

# The MVP-offered quality catalog (see chummer5.engine.qualities): 3 FLAT_BONUS qualities, all
# Positive. Computed once, mirroring MUNDANE_SKILLS/MUNDANE_SKILL_GROUPS below.
MVP_QUALITIES = mvp_quality_catalog(QUALITIES)

# WP48: the Mentor Spirit quality itself, looked up once by name -- used by `submit_qualities` to
# recognize whether it's among the submitted quality_id checkboxes (see that route's own comment).
MENTOR_SPIRIT_QUALITY = next(q for q in QUALITIES if q.name == MENTOR_SPIRIT_QUALITY_NAME)

# The MVP-offered Adept Power catalog (see chummer5.engine.magic): 6 FLAT_BONUS powers.
MVP_POWERS = mvp_power_catalog(POWERS)

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

# WP46: same fixed-row precedent as MAX_CONTACT_ROWS, sized generously above any SR5-core
# metatype's plausible Charisma (the real cap `create_bound_spirit_selection` enforces).
MAX_BOUND_SPIRIT_ROWS = 10

# WP49: same fixed-row precedent as MAX_CONTACT_ROWS/MAX_BOUND_SPIRIT_ROWS -- generously sized
# above any SR5-core metatype's plausible (INT+LOG)*2 budget at 1 point per row.
MAX_KNOWLEDGE_ROWS = 12
MAX_LANGUAGE_ROWS = 4

# MVP's regular Skills-priority point-buy UI stays mundane-only even after WP29 -- a Mundane
# character's MAG/RES are always 0 and can never be raised in chargen (RES/Resonance stays out of
# scope permanently, per the Project Overview), and the 12 skills linked to those attributes
# (Alchemy, Summoning, Compiling, ...) would show a permanently-crippled dice pool (rating + 0, and
# none of them allow defaulting) if offered here for a Mundane build -- excluded from the
# allocation UI for the same "excluded, not silently broken" reason WP2/WP3 exclude non-SR5
# metatypes/qualities from their catalogs. This is a UI-layer curation, not an engine change:
# `create_skill_allocation` itself is still generic and would accept points on these skills if
# submitted directly (e.g. via a hand-crafted request). **WP29 note**: a Magician's Talent
# free-skill grant can still raise a Magical Active skill's rating above 0 via a pure Improvement,
# entirely independent of this buy UI (see `chummer5.engine.magic
# .apply_magic_skill_grant_improvements`'s own docstring) -- widening `MUNDANE_SKILLS` itself so a
# Magician/Adept could spend *additional* Skills-priority points on Magical Active skills beyond
# that grant is a real, deliberately deferred follow-on (see this WP's worklog), not something this
# constant's exclusion silently breaks.
_MAGIC_ATTRIBUTES = ("MAG", "RES")
MUNDANE_SKILLS = tuple(
    sorted((s for s in SKILLS if s.attribute not in _MAGIC_ATTRIBUTES), key=lambda s: s.name)
)
MUNDANE_SKILL_GROUPS = tuple(
    sorted({s.skill_group for s in MUNDANE_SKILLS if s.skill_group is not None})
)
# WP29: the character sheet's read-only skill list needs every skill (so a Magician's granted
# Magical Active skill shows up there too, see `_character_sheet_context`), sorted the same way
# `MUNDANE_SKILLS` already is.
ALL_SKILLS_SORTED = tuple(sorted(SKILLS, key=lambda s: s.name))


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


def _parse_specializations(form: FormData, keys: Iterable[str], prefix: str) -> dict[str, str]:
    """Read `{prefix}{key}` fields off a submitted form into a sparse `{key: name}` dict (WP50).

    Sparse the same way `_parse_points` is: a blank/absent field means "no specialization for this
    skill", not an error -- `create_skill_allocation`'s own validation is what rejects a genuinely
    invalid nonblank entry (unbought skill, group-purchased skill, budget overspend).
    """
    specializations: dict[str, str] = {}
    for key in keys:
        raw = form.get(f"{prefix}{key}")
        if raw is None:
            continue
        name = str(raw).strip()
        if name:
            specializations[key] = name
    return specializations


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


def _parse_bound_spirits(form: FormData, max_rows: int) -> tuple[tuple[str, int], ...]:
    """Read up to `max_rows` bound-spirit rows off a submitted form into `(spirit_type, services)`
    pairs -- mirrors `_parse_contacts`'s identical fixed-row shape. Any row whose spirit-type field
    is blank is skipped entirely; a malformed services value is treated as 0 rather than dropping
    the row, the same "let the engine validate what it's already responsible for" choice `_parse_
    contacts` makes for Connection/Loyalty (`create_bound_spirit_selection`'s own "services must be
    at least 1" check is what rejects a 0 here).
    """
    picks = []
    for i in range(max_rows):
        spirit_type = str(form.get(f"spirit_type_{i}") or "").strip()
        if not spirit_type:
            continue
        try:
            services = int(str(form.get(f"spirit_services_{i}", "0")))
        except ValueError:
            services = 0
        picks.append((spirit_type, services))
    return tuple(picks)


def _parse_knowledge_skills(form: FormData, max_rows: int) -> tuple[KnowledgeSkillPick, ...]:
    """Read up to `max_rows` Knowledge-skill rows off a submitted form -- mirrors
    `_parse_contacts`'s identical fixed-row shape. Any row whose name field is blank is skipped
    entirely; a malformed rating is treated as 0 rather than dropping the row
    (`create_knowledge_selection`'s own 1-6 range check is what rejects a 0, the same "let the
    engine validate what it's already responsible for" choice `_parse_contacts` makes for
    Connection/Loyalty).
    """
    picks = []
    for i in range(max_rows):
        name = str(form.get(f"knowledge_name_{i}") or "").strip()
        if not name:
            continue
        category = str(form.get(f"knowledge_category_{i}") or "")
        try:
            rating = int(str(form.get(f"knowledge_rating_{i}", "0")))
        except ValueError:
            rating = 0
        picks.append(KnowledgeSkillPick(name=name, category=category, rating=rating))
    return tuple(picks)


def _parse_languages(form: FormData, max_rows: int) -> tuple[LanguageSkillPick, ...]:
    """Read up to `max_rows` Language-skill rows off a submitted form -- same shape as
    `_parse_knowledge_skills` above, plus a `native` checkbox.
    """
    picks = []
    for i in range(max_rows):
        name = str(form.get(f"language_name_{i}") or "").strip()
        if not name:
            continue
        native = form.get(f"language_native_{i}") is not None
        try:
            rating = int(str(form.get(f"language_rating_{i}", "0")))
        except ValueError:
            rating = 0
        picks.append(LanguageSkillPick(name=name, rating=rating, native=native))
    return tuple(picks)


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


def _parse_cyberware(form: FormData, catalog: Iterable[Cyberware]) -> tuple[str, ...]:
    """Expand each cyberware item's submitted quantity into that many repeats of its id -- mirrors
    `_parse_gear`'s identical shape, keyed by catalog id (not name): `create_cyberware_selection`'s
    own `item_ids` parameter takes ids, and repeats are legal purchases (a matched pair of
    cyberlimbs -- see `chummer5.engine.cyberware`'s module docstring), not an error to reject.
    """
    ids: list[str] = []
    for item in catalog:
        raw = form.get(f"cyberware_{item.id}")
        try:
            quantity = int(str(raw)) if raw is not None else 0
        except ValueError:
            quantity = 0
        ids.extend([item.id] * max(quantity, 0))
    return tuple(ids)


def _parse_bioware(form: FormData, catalog: Iterable[Bioware]) -> tuple[str, ...]:
    """Expand each bioware item's submitted quantity into that many repeats of its id -- mirrors
    `_parse_cyberware`'s identical shape, keyed by `bioware_{id}` form fields instead of
    `cyberware_{id}` ones.
    """
    ids: list[str] = []
    for item in catalog:
        raw = form.get(f"bioware_{item.id}")
        try:
            quantity = int(str(raw)) if raw is not None else 0
        except ValueError:
            quantity = 0
        ids.extend([item.id] * max(quantity, 0))
    return tuple(ids)


def _parse_foci(form: FormData, catalog: Iterable[Focus]) -> tuple[tuple[str, int], ...]:
    """Read a submitted Force per Foci catalog item into `(focus_id, force)` pairs -- unlike
    `_parse_cyberware`/`_parse_bioware`'s quantity-per-item shape, this UI offers at most one bonded
    pick per catalog item (Force 0 means "not bonded"), a deliberate simplification: no real fixture
    exercises `create_foci_selection`'s own "bond two of the same item" allowance, and a
    quantity-of-Force-N picker would need a second dimension (how many, at what Force each) no other
    section's UI has needed yet. An unparseable or non-positive Force is treated as "not bonded",
    the same robustness clamp `_parse_gear` already applies to a bad quantity.
    """
    picks: list[tuple[str, int]] = []
    for item in catalog:
        raw = form.get(f"focus_force_{item.id}")
        try:
            force = int(str(raw)) if raw is not None else 0
        except ValueError:
            force = 0
        if force > 0:
            picks.append((item.id, force))
    return tuple(picks)


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


def _display_karma_to_nuyen(karma_converted: int) -> int:
    """`karma_to_nuyen`, clamped to the valid 0-10 range first, so a context builder can compute a
    display number for an *out-of-range* submitted value (echoed back alongside a rejection
    message) without that computation itself raising -- `create_resources_selection`'s own call to
    the un-clamped `karma_to_nuyen` is what actually rejects it; this is purely for rendering.
    """
    return karma_to_nuyen(max(0, min(karma_converted, MAX_KARMA_TO_NUYEN)))


def _parse_karma_converted(form: FormData) -> int:
    """Read `karma_converted` off a submitted form (WP43), clamping an unparseable or negative
    value to 0 -- the same "let the engine validate what it's already responsible for" choice
    `_parse_gear`/`_parse_lifestyle_months` make. `karma_to_nuyen`'s own 0-10 range check is what
    rejects anything above the cap, not this parser.
    """
    raw = form.get("karma_converted")
    try:
        value = int(str(raw)) if raw is not None else 0
    except ValueError:
        value = 0
    return max(value, 0)


def _parse_power_picks(
    form: FormData, catalog: Iterable[Power]
) -> tuple[tuple[str, int, str | None], ...]:
    """Read `power_rating_{id}`/`power_attribute_{id}` fields off a submitted form into
    `create_power_selection`'s own `(power_id, rating, selected_attribute)` triple shape (WP29).

    A rating of 0 (the default for a power the player didn't touch) means "not purchased" -- the
    same "absence means 0" convention `_parse_points` already established -- so it's simply omitted
    from the result rather than passed through as an invalid `rating < 1` pick.
    """
    picks: list[tuple[str, int, str | None]] = []
    for power in catalog:
        raw_rating = form.get(f"power_rating_{power.id}")
        try:
            rating = int(str(raw_rating)) if raw_rating is not None else 0
        except ValueError:
            rating = 0
        if rating <= 0:
            continue
        raw_attribute = form.get(f"power_attribute_{power.id}")
        selected_attribute = str(raw_attribute) if raw_attribute else None
        picks.append((power.id, rating, selected_attribute))
    return tuple(picks)


def _attribute_allocation_context(
    character: Character | None,
    attribute_points: Mapping[str, int],
    magic_points: int = 0,
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

    **Post-WP29 correction**: `magic_points` -- Special Attribute Points spent raising MAG beyond
    `character.magic_rating` -- is a *separate* parameter from `attribute_points`, not one more key
    inside it: `create_character` itself only ever validates `ALLOCATABLE_ATTRIBUTES` (still just
    the primary 8 + EDG; see `chummer5.engine.character.Character`'s own docstring correction for
    why MAG's allocatability is character-specific, not a fixed global set `create_character` could
    validate unconditionally). When `character.magic_type is not None`, a `"MAG"` row is appended
    to `attribute_rows` with the *same* shape every other row has (`code`/`minimum`/`maximum`/
    `points`/`value`) -- `_attribute_allocation.html` needs no template branching to render it,
    since `row.minimum`/`row.maximum` already give it the correct `max="{{ row.maximum -
    row.minimum }}"` headroom on the numeric input. Absent entirely for Mundane/uncommitted-Talent
    characters, mirroring the legacy `MAGEnabled` flag's "not just zero, not allocatable at all"
    gating.

    **WP19**: when `error` is unset (a clean render, not an echo of a submission this same request
    just rejected), re-runs `create_character` (and, when applicable, `create_magic_attribute_
    points`) against `character`'s own current metatype/heritage/attributes/Talent state and
    `attribute_points`/`magic_points`, purely to derive `attribute_budget_warning` from whatever
    `ValueError` either raises (discarding the exception itself, not its message) --
    `submit_priorities` no longer resets a carried-forward spend that no longer fits a
    just-reconfirmed letter/metatype (see its own comment), so this is what surfaces that fact,
    freshly, on every render for as long as it stays true. Distinct from `attribute_error` (sourced
    from a `ValueError` raised by *this specific request's* submission, never stored) so a template
    can style "you just typed something invalid" differently from "this was fine when you entered
    it, but a priority change since then broke it."
    """
    if character is None:
        return {"character": None, "attribute_error": error}
    display = replace(
        character,
        attribute_points=MappingProxyType(dict(attribute_points)),
        magic_attribute_points=magic_points,
    )
    primary_budget = PRIORITIES.attributes[character.attributes_letter].points
    primary_spent = sum(attribute_points.get(code, 0) for code in PRIMARY_ATTRIBUTES)
    special_spent = sum(attribute_points.get(code, 0) for code in SPECIAL_ATTRIBUTES) + magic_points
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
    if character.magic_type is not None:
        rows.append(
            {
                "code": "MAG",
                "minimum": character.magic_rating,
                "maximum": display.attribute_range("MAG").maximum,
                "points": magic_points,
                "value": display.attribute_value("MAG"),
            }
        )
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
            if character.magic_type is not None:
                create_magic_attribute_points(
                    character.magic_type,
                    magic_points,
                    character.magic_rating,
                    character.attribute_range("MAG").maximum,
                    character.special_attribute_points,
                    attribute_points.get("EDG", 0),
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
    specializations: Mapping[str, str] = MappingProxyType({}),
    *,
    error: str | None = None,
) -> dict[str, Any]:
    """Context for `_skill_allocation.html`. Same echo-the-submission shape as the attribute
    context above; `skill_points`/`group_points`/`specializations` feed a throwaway
    `SkillAllocation` used purely for display (rating/dice-pool preview), independent of whether
    the submission actually validated.

    **WP19**: same `error`-gated re-validation as `_attribute_allocation_context` -- when `error`
    is unset, re-runs `create_skill_allocation` against `skills_letter`/`skill_points`/
    `group_points`/`specializations` purely to derive `skill_budget_warning`. See that function's
    docstring for why this needs to be re-derived fresh on every render rather than decided once at
    submission time.

    **WP50**: `skill_rows["pool"]` relies on `dice_pool`'s own default (whether `skill.id` is in
    `allocation.specializations`) rather than passing `specialized=` explicitly here.
    """
    if character is None:
        return {"character": None, "skill_error": error}
    allocation = SkillAllocation(
        skill_points=MappingProxyType(dict(skill_points)),
        group_points=MappingProxyType(dict(group_points)),
        specializations=MappingProxyType(dict(specializations)),
    )
    budget = skill_point_budget(skills_letter, PRIORITIES)
    skill_rows = [
        {
            "skill": skill,
            "points": allocation.skill_points.get(skill.id, 0),
            "specialization": allocation.specializations.get(skill.id, ""),
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
            create_skill_allocation(
                skills_letter, PRIORITIES, SKILLS, skill_points, group_points, specializations
            )
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
        "skills_remaining": (
            budget.skills - sum(allocation.skill_points.values()) - len(allocation.specializations)
        ),
        "skill_budget_warning": budget_warning,
        "groups_budget": budget.skill_groups,
        "groups_remaining": budget.skill_groups - sum(allocation.group_points.values()),
        "max_skill_rating": MAX_SKILL_RATING_CREATE,
        "skill_error": error,
    }


def _knowledge_selection_context(
    character: Character | None,
    knowledge_skills: tuple[KnowledgeSkillPick, ...],
    languages: tuple[LanguageSkillPick, ...],
    *,
    error: str | None = None,
) -> dict[str, Any]:
    """Context for `_knowledge_skills.html`. Same echo-the-submission/re-validate-fresh shape as
    `_skill_allocation_context` -- `knowledge_skills`/`languages` feed a throwaway echo of the
    submission regardless of whether it actually validated; when `error` is unset, re-runs
    `create_knowledge_selection` purely to detect whether an attribute edit since the last commit
    shrank INT/LOG below what's already spent (WP19-style "no longer fits" staleness), the same
    re-derive-fresh-on-every-render precedent every other carried-forward selection follows.
    """
    if character is None:
        return {"character": None, "knowledge_error": error}
    knowledge_rows = [
        {
            "index": i,
            "name": knowledge_skills[i].name if i < len(knowledge_skills) else "",
            "category": knowledge_skills[i].category if i < len(knowledge_skills) else "",
            "rating": knowledge_skills[i].rating if i < len(knowledge_skills) else "",
        }
        for i in range(MAX_KNOWLEDGE_ROWS)
    ]
    language_rows = [
        {
            "index": i,
            "name": languages[i].name if i < len(languages) else "",
            "rating": languages[i].rating if i < len(languages) else "",
            "native": languages[i].native if i < len(languages) else False,
        }
        for i in range(MAX_LANGUAGE_ROWS)
    ]
    free_points = free_knowledge_points(character)
    points_spent = sum(k.rating for k in knowledge_skills) + sum(
        la.rating for la in languages if not la.native
    )
    budget_warning: str | None = None
    if error is None:
        try:
            create_knowledge_selection(character, knowledge_skills, languages)
        except ValueError as exc:
            budget_warning = (
                f"No longer fits since attributes were last confirmed: {exc}. "
                "Adjust the entries below to continue."
            )
    return {
        "character": character,
        "knowledge_rows": knowledge_rows,
        "language_rows": language_rows,
        "knowledge_categories": KNOWLEDGE_CATEGORIES,
        "suggested_languages": SUGGESTED_LANGUAGES,
        "knowledge_free_points": free_points,
        "knowledge_points_spent": points_spent,
        "native_language_limit": native_language_limit(character),
        "max_skill_rating": MAX_SKILL_RATING_CREATE,
        "knowledge_budget_warning": budget_warning,
        "knowledge_error": error,
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

    **WP48**: also re-applies `quality_selection.mentor_spirit`'s `MENTOR_SPIRIT`-sourced
    Improvements when present, for the identical reason -- a fresh `create_character()` call's
    empty index has nothing to remove, so this is always a pure add, never a double-application.

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
    if quality_selection.mentor_spirit is not None:
        apply_mentor_spirit_improvements(character, quality_selection.mentor_spirit)
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


def _remove_adept_power_improvements(character: Character) -> None:
    """Remove every currently-held `ADEPT_POWER`-sourced Improvement from `character.improvements`.

    Each purchased power is its own source instance (`source_id` is the power's own id, per
    `apply_power_improvements`), so retracting "every power this character has" means one
    `remove_source` call per distinct id, not a single shared one the way the Talent free-skill
    grant's `MAGIC_SKILL_GRANT_SOURCE_ID` is. `character.improvements.improvements` is a snapshot
    tuple (see `ImprovementIndex`), so it's safe to iterate while `remove_source` mutates the
    underlying list -- the same pattern `_replace_committed_qualities` below already uses for
    `QUALITY`-sourced Improvements.
    """
    for imp in character.improvements.improvements:
        if imp.source_type == ImprovementSource.ADEPT_POWER:
            character.improvements.remove_source(ImprovementSource.ADEPT_POWER, imp.source_id)


def _relink_magic_selection(
    character: Character, talent_letter: str, previous: Character
) -> Character:
    """Re-apply a carried-forward Talent selection's free-skill-grant Improvements (and a carried-
    forward Adept power selection's Improvements) onto a freshly built `Character`, and re-attach
    `magic_type`/`magic_rating`/`tradition`/`magic_granted_skill_ids`/`spell_selection`/
    `power_selection` themselves.

    Mirrors `_relink_quality_improvements`/`_relink_metatype_qualities`: `create_character()`
    always starts every one of those fields at its Mundane/unset default and a brand-new, empty
    `ImprovementIndex` (see that function's docstring) -- `submit_attributes` is the one route that
    still rebuilds this way (WP19 left it that way; see its own worklog), so without this helper a
    Magician/Adept's entire Talent selection would silently reset to Mundane on the very next
    attribute-point edit.

    Re-derives the Talent selection via `create_magic_selection` (using `talent_letter` -- the
    session's *current* one, not necessarily whatever letter was in effect when `previous` was
    built) rather than trusting `previous`'s own snapshot, the same "recompute, don't just
    re-attach" reasoning `_relink_contact_selection` already uses -- `Character` has no field for
    the free-skill grant's *rating* (only the granted skill *ids*), so the rating has to be
    re-resolved from the matched Talent option regardless. Safe to call unconditionally: a no-op if
    `previous.magic_type is None` (still Mundane, nothing to carry).
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


def _replace_committed_powers(character: Character, selection: PowerSelection) -> Character:
    """Swap whatever `ADEPT_POWER`-sourced Improvements `character.improvements` currently holds
    for `selection`'s, and re-attach `selection` as `character.power_selection` -- mirrors
    `_replace_committed_qualities`'s identical shape.
    """
    _remove_adept_power_improvements(character)
    apply_power_improvements(character, selection)
    return replace(character, power_selection=selection)


def _relink_cyberware_selection(
    character: Character, cyberware_selection: CyberwareSelection | None
) -> Character:
    """Re-apply a carried-forward cyberware selection's Essence/bonus Improvements onto a freshly
    built `Character`, and re-attach the selection itself -- mirrors `_relink_quality_
    improvements`'s identical shape (a fresh `create_character()` call always starts `cyberware_
    selection` at `None` and `improvements` empty; see that function's own docstring). Load-bearing
    only for `submit_attributes`, the one route still rebuilding via `create_character()` fresh.
    """
    if cyberware_selection is None:
        return character
    apply_cyberware_improvements(character, cyberware_selection)
    return replace(character, cyberware_selection=cyberware_selection)


def _replace_committed_cyberware(character: Character, selection: CyberwareSelection) -> Character:
    """Swap whatever `CYBERWARE`-sourced Improvements `character.improvements` currently holds for
    `selection`'s, and re-attach `selection` as `character.cyberware_selection` -- mirrors
    `_replace_committed_qualities`'s identical shape, with one difference: removes by each
    *distinct* previously-purchased item id, not once per purchased unit.
    `ImprovementIndex.remove_source` already retracts every Improvement a given source id granted
    at once, and a repeated purchase of the same item shares one `source_id` (the item's own
    catalog id -- see `chummer5.engine.cyberware`'s own "duplicate purchases share one source_id"
    docstring), so removing that id once already clears every copy.
    """
    if character.cyberware_selection is not None:
        for item_id in {item.id for item in character.cyberware_selection.items}:
            character.improvements.remove_source(ImprovementSource.CYBERWARE, item_id)
    apply_cyberware_improvements(character, selection)
    return replace(character, cyberware_selection=selection)


def _relink_bioware_selection(
    character: Character, bioware_selection: BiowareSelection | None
) -> Character:
    """Re-apply a carried-forward bioware selection's Essence/bonus Improvements onto a freshly
    built `Character`, and re-attach the selection itself -- mirrors `_relink_cyberware_selection`'s
    identical shape. Load-bearing only for `submit_attributes`, the one route still rebuilding via
    `create_character()` fresh.
    """
    if bioware_selection is None:
        return character
    apply_bioware_improvements(character, bioware_selection)
    return replace(character, bioware_selection=bioware_selection)


def _replace_committed_bioware(character: Character, selection: BiowareSelection) -> Character:
    """Swap whatever `BIOWARE`-sourced Improvements `character.improvements` currently holds for
    `selection`'s, and re-attach `selection` as `character.bioware_selection` -- mirrors
    `_replace_committed_cyberware`'s identical shape, including removing by each *distinct*
    previously-purchased item id rather than once per purchased unit.
    """
    if character.bioware_selection is not None:
        for item_id in {item.id for item in character.bioware_selection.items}:
            character.improvements.remove_source(ImprovementSource.BIOWARE, item_id)
    apply_bioware_improvements(character, selection)
    return replace(character, bioware_selection=selection)


def _relink_foci_selection(character: Character, foci_selection: FociSelection | None) -> Character:
    """Re-apply a carried-forward Foci selection's `FLAT_BONUS` skill Improvements onto a freshly
    built `Character`, and re-attach the selection itself -- mirrors `_relink_bioware_selection`'s
    identical shape. Load-bearing only for `submit_attributes`, the one route still rebuilding via
    `create_character()` fresh.
    """
    if foci_selection is None:
        return character
    apply_foci_improvements(character, foci_selection)
    return replace(character, foci_selection=foci_selection)


def _replace_committed_foci(character: Character, selection: FociSelection) -> Character:
    """Swap whatever `FOCUS`-sourced Improvements `character.improvements` currently holds for
    `selection`'s, and re-attach `selection` as `character.foci_selection` -- mirrors
    `_replace_committed_cyberware`'s identical shape, including removing by each *distinct*
    previously-bonded item id rather than once per bonded unit.
    """
    if character.foci_selection is not None:
        for item_id in {pick.focus.id for pick in character.foci_selection.picks}:
            character.improvements.remove_source(ImprovementSource.FOCUS, item_id)
    apply_foci_improvements(character, selection)
    return replace(character, foci_selection=selection)


def _remove_foci_improvements(character: Character) -> None:
    """Retract every `FOCUS`-sourced Improvement -- mirrors `_remove_adept_power_improvements`'s
    identical shape, used by `_replace_committed_talent` (a Talent change invalidates whatever
    Magic-rating-dependent Foci selection was already committed, the same reasoning that WP applies
    to `bound_spirit_selection`/`power_selection`).
    """
    if character.foci_selection is None:
        return
    for item_id in {pick.focus.id for pick in character.foci_selection.picks}:
        character.improvements.remove_source(ImprovementSource.FOCUS, item_id)


def _strip_mentor_spirit_selection(
    character: Character, quality_selection: QualitySelection | None
) -> QualitySelection | None:
    """Drop just the Mentor Spirit quality and archetype pick from an already-committed
    `QualitySelection`, keeping every other quality intact (WP48), used by
    `_replace_committed_talent` below.

    Unlike spell/power/spirit/Foci selections, which `_replace_committed_talent` resets to `None`
    wholesale on any Talent change, `quality_selection` as a whole can't be reset that way -- it
    also holds every magic-*independent* quality the player picked (Catlike, Indomitable, ...),
    which a Talent change has no reason to discard. But a Mentor Spirit pick specifically *is*
    Talent-dependent (its `gated_choice` is resolved from `magic_type`, and the quality stops being
    offered at all once `magic_type` becomes `None`), so it needs the same "reset on any Talent
    (re)confirmation" treatment those other selections get, applied surgically instead of wholesale.
    Removes `MENTOR_SPIRIT`-sourced Improvements as a side effect; `QUALITY`-sourced ones for the
    remaining qualities are left untouched (`apply_quality_improvements` was never called twice for
    them, so there's nothing to remove before a no-op re-add would be needed). Returns
    `quality_selection` unchanged if nothing was ever committed, or if it never included Mentor
    Spirit in the first place.
    """
    if quality_selection is None or quality_selection.mentor_spirit is None:
        return quality_selection
    character.improvements.remove_source(
        ImprovementSource.MENTOR_SPIRIT, quality_selection.mentor_spirit.archetype.id
    )
    remaining_ids = [
        q.id for q in quality_selection.qualities if q.name != MENTOR_SPIRIT_QUALITY_NAME
    ]
    offered = offerable_quality_catalog(character, QUALITIES)
    return create_quality_selection(remaining_ids, offered)


def _replace_committed_qualities(character: Character, selection: QualitySelection) -> Character:
    """Swap whatever QUALITY-/MENTOR_SPIRIT-sourced Improvements `character.improvements` currently
    holds for `selection`'s, and re-attach `selection` as `character.quality_selection`.

    `apply_quality_improvements`/`apply_mentor_spirit_improvements` only ever add -- calling either
    twice for two submissions against the same `Character` (i.e. without an intervening
    `create_character` rebuild) would double up anything that stayed selected across both, so
    previously-applied Improvements of both kinds are removed first. `MENTOR_SPIRIT` is removed
    unconditionally (a no-op when nothing was ever picked) rather than only when `selection
    .mentor_spirit is None`, since a *changed* archetype pick also needs its old Improvements gone
    before the new ones are applied (WP48).
    """
    for imp in character.improvements.improvements:
        if imp.source_type in (ImprovementSource.QUALITY, ImprovementSource.MENTOR_SPIRIT):
            character.improvements.remove_source(imp.source_type, imp.source_id)
    apply_quality_improvements(character, selection.qualities)
    if selection.mentor_spirit is not None:
        apply_mentor_spirit_improvements(character, selection.mentor_spirit)
    return replace(character, quality_selection=selection)


def _quality_selection_context(
    character: Character | None,
    quality_ids: Iterable[str],
    *,
    mentor_spirit_archetype_id: str | None = None,
    mentor_spirit_general_choice_id: str | None = None,
    error: str | None = None,
) -> dict[str, Any]:
    """Context for `_quality_selection.html`. `quality_ids` is whatever should be shown checked --
    the session's committed selection on a clean render, or the raw submitted checkbox values on
    an error-echo render, same shape as the attribute/skill contexts above.

    **WP23**: the pickable rows come from `offerable_quality_catalog(character, QUALITIES)`, not
    the module-level `MVP_QUALITIES`, so a quality this character's metatype already grants for
    free (e.g. an Elf's Low-Light Vision) never appears as something to spend karma on again --
    also what makes Mentor Spirit itself appear as a row at all for a magic-active character (WP48).

    **WP48**: `mentor_spirit_archetype_id`/`mentor_spirit_general_choice_id` follow the identical
    "explicit override on echo/submit, fall back to the committed selection otherwise" shape --
    `None` (the default, used by the main chargen-body render) falls back to `character
    .quality_selection.mentor_spirit`; `submit_qualities` always passes an explicit value (possibly
    `None`, meaning "no archetype picked"), which must win even when it differs from what's
    committed. `mentor_spirit_offered` gates whether `_quality_selection.html` even shows the
    archetype picker at all -- mirrors `offerable_quality_catalog`'s own `character.magic_type is
    not None` gate for Mentor Spirit itself, so the picker never appears for a build where the
    quality isn't even offered.
    """
    if character is None:
        return {"character": None, "quality_error": error}
    offered = offerable_quality_catalog(character, QUALITIES)
    ids = set(quality_ids)
    rows = [{"quality": q, "selected": q.id in ids} for q in offered]
    positive_karma = sum(q.karma for q in offered if q.id in ids and q.category == "Positive")
    negative_karma = -sum(q.karma for q in offered if q.id in ids and q.category == "Negative")

    committed_pick = (
        character.quality_selection.mentor_spirit
        if character.quality_selection is not None
        else None
    )
    if mentor_spirit_archetype_id is None and committed_pick is not None:
        mentor_spirit_archetype_id = committed_pick.archetype.id
        if mentor_spirit_general_choice_id is None:
            mentor_spirit_general_choice_id = committed_pick.general_choice.id
    selected_archetype: MentorSpiritArchetype | None = next(
        (a for a in MENTORS if a.id == mentor_spirit_archetype_id), None
    )

    return {
        "character": character,
        "quality_rows": rows,
        "positive_karma": positive_karma,
        "negative_karma": negative_karma,
        "karma_limit": QUALITY_KARMA_LIMIT,
        "metatype_qualities": character.metatype_qualities,
        "mentor_spirit_offered": character.magic_type is not None,
        "mentor_spirit_archetypes": MENTORS,
        "selected_mentor_spirit_archetype_id": mentor_spirit_archetype_id,
        "selected_mentor_spirit_archetype": selected_archetype,
        "selected_mentor_spirit_general_choice_id": mentor_spirit_general_choice_id,
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
    `_resources_context` never hits this (it recomputes its own budget/spent numbers directly from
    `resources_letter`/`gear_names`, never trusting the stored object's fields), but
    `_character_sheet_context` reads `resources_selection.nuyen_budget`/`.nuyen_remaining` straight
    off the stored object -- so it needs a freshly-recomputed one, and needs it to not raise on an
    over-budget carry-forward the way `create_resources_selection` deliberately does.

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
            + _display_karma_to_nuyen(karma_converted)
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


def _resources_context(
    character: Character | None,
    resources_letter: str,
    gear_names: tuple[str, ...],
    lifestyle_cost: int,
    cyberware_cost: int,
    bioware_cost: int,
    karma_converted: int = 0,
    foci_cost: int = 0,
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

    **WP34**: `cyberware_cost` (the character's currently-selected `cyberware_selection.nuyen_
    spent`, or 0 if none yet) folds in the same way, extending the shared-budget check from gear+
    Lifestyle to gear+Lifestyle+cyberware.

    **WP45**: `bioware_cost` folds in the same way, extending the shared-budget check to
    gear+Lifestyle+cyberware+bioware.

    **WP43**: `karma_converted` (this same submission's Karma-to-Nuyen amount, or the character's
    currently-committed one when redisplaying a clean render) tops up the budget the re-validation
    call and the displayed remaining-nuyen number both use.

    **WP47**: `foci_cost` folds in the same way, extending the shared-budget check to
    gear+Lifestyle+cyberware+bioware+Foci.
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
                resources_letter,
                PRIORITIES,
                gear_names,
                lifestyle_cost=lifestyle_cost,
                cyberware_cost=cyberware_cost,
                bioware_cost=bioware_cost,
                karma_converted=karma_converted,
                foci_cost=foci_cost,
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
        "nuyen_remaining": (
            budget
            + _display_karma_to_nuyen(karma_converted)
            - spent
            - lifestyle_cost
            - cyberware_cost
            - bioware_cost
            - foci_cost
        ),
        "karma_converted": karma_converted,
        "max_karma_to_nuyen": MAX_KARMA_TO_NUYEN,
        "karma_to_nuyen_amount": _display_karma_to_nuyen(karma_converted),
        "resources_error": error,
        "resources_budget_warning": budget_warning,
    }


def _lifestyle_context(
    character: Character | None,
    resources_letter: str,
    tier_name: str,
    months: int,
    gear_cost: int,
    cyberware_cost: int,
    bioware_cost: int,
    karma_converted: int = 0,
    foci_cost: int = 0,
    *,
    error: str | None = None,
) -> dict[str, Any]:
    """Context for `_lifestyle.html`: WP20's mandatory primary-Lifestyle purchase (core rulebook,
    p. 369), drawing from the same Resources-priority nuyen budget `_resources_context` validates
    gear against. `gear_cost` is the character's *currently committed* gear spend
    (`resources_selection.nuyen_spent`, or 0 if none yet) -- passed in rather than recomputed here,
    the mirror image of `_resources_context`'s own `lifestyle_cost` parameter (see its docstring for
    why this cross-section number is threaded through rather than each section reaching into the
    other's catalog/state directly). **WP34** adds `cyberware_cost` the same way (the character's
    currently-selected `cyberware_selection.nuyen_spent`, or 0 if none yet), extending the shared
    budget from two sections to three. **WP45** adds `bioware_cost` the same way, extending the
    shared budget to four sections. **WP43** adds `karma_converted` the same way (the
    character's currently-committed `resources_selection.karma_converted`, or 0 if none yet),
    topping up the budget rather than spending from it -- see `chummer5.engine.resources`'s module
    docstring. **WP47** adds `foci_cost` the same way, extending the shared budget to five sections.

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
    budget = starting_nuyen(resources_letter, PRIORITIES) + _display_karma_to_nuyen(karma_converted)
    budget_warning: str | None = None
    if error is None:
        try:
            selection = create_lifestyle_selection(tier_name, months, LIFESTYLES)
        except ValueError as exc:
            budget_warning = str(exc)
        else:
            total_spent = (
                gear_cost + selection.total_cost + cyberware_cost + bioware_cost + foci_cost
            )
            if total_spent > budget:
                parts = [f"gear ({gear_cost})", f"lifestyle ({selection.total_cost})"]
                if cyberware_cost:
                    parts.append(f"cyberware ({cyberware_cost})")
                if bioware_cost:
                    parts.append(f"bioware ({bioware_cost})")
                if foci_cost:
                    parts.append(f"foci ({foci_cost})")
                budget_warning = (
                    f"No longer fits since priorities were last confirmed: {' + '.join(parts)} "
                    f"spend {total_spent} exceeds Resources priority {resources_letter}'s nuyen "
                    f"budget of {budget}. Adjust the lifestyle below to continue."
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


# Sorted by (category, name) for the picker's category-grouped `<details>` sections, mirroring
# `STARTER_GEAR_CATALOG`'s own sort -- unlike that catalog, `load_cyberware()`'s XML-document order
# already groups most categories consecutively but not perfectly (Cyber Implant Weapon and Cyber
# Implant Weapon Accessory interleave at the end of the file), so a plain `itertools.groupby` over
# `CYBERWARE` directly would produce spurious duplicate groups. Computed once at import time, not
# per-request.
_CYBERWARE_BY_CATEGORY = tuple(sorted(CYBERWARE, key=lambda item: (item.category, item.name)))
# Same reasoning, applied to WP45's much smaller bioware catalog (2 categories, Basic/Cultured).
_BIOWARE_BY_CATEGORY = tuple(sorted(BIOWARE, key=lambda item: (item.category, item.name)))
# Same reasoning, applied to WP47's Foci catalog (7 rulebook categories, not a gear.xml field --
# see chummer5.data.foci's own docstring for how focus_category is derived).
_FOCI_BY_CATEGORY = tuple(sorted(FOCI, key=lambda item: (item.focus_category, item.name)))


def _catalog_groups(
    item_ids: tuple[str, ...],
    catalog_by_category: tuple[Any, ...],
    by_id: dict[str, Any],
) -> list[dict[str, Any]]:
    """Build category-grouped `<details>` rows for a quantity-per-item picker -- shared by the
    cyberware and bioware halves of `_cyberware_context` (WP45), mirroring `_resources_context`'s
    WP21 shape.
    """
    counts: dict[str, int] = {}
    for item_id in item_ids:
        counts[item_id] = counts.get(item_id, 0) + 1
    return [
        {
            "category": category,
            "rows": [
                {
                    "item": item,
                    "quantity": counts.get(item.id, 0),
                    "subtotal": item.cost * counts.get(item.id, 0),
                }
                for item in items
            ],
        }
        for category, items in itertools.groupby(
            catalog_by_category, key=lambda item: item.category
        )
    ]


def _cyberware_context(
    character: Character | None,
    resources_letter: str,
    item_ids: tuple[str, ...],
    bioware_item_ids: tuple[str, ...],
    gear_cost: int,
    lifestyle_cost: int,
    karma_converted: int = 0,
    foci_cost: int = 0,
    *,
    error: str | None = None,
) -> dict[str, Any]:
    """Context for `_cyberware.html` (WP34, widened by WP45): Phase J's cyberware purchase, plus
    Phase L's bioware purchase folded into the same section.

    **A new peer section, not folded into `_resources.html`'s gear picker** -- mirrors WP20's own
    explicit "Lifestyle gets its own section despite sharing a budget" choice (see that WP's
    worklog for the full reasoning). SR5 frames "buy gear" and "install cyberware/bioware" as
    distinct chargen decisions with different validation rules (an Essence floor here, not just a
    nuyen cap), and cramming these catalogs into `_resources_context` would make that one context
    builder responsible for unrelated catalogs. Shares the same Resources-priority nuyen budget as
    gear/Lifestyle though -- `gear_cost`/`lifestyle_cost` are those two sections' currently-
    committed spend, threaded through the same cross-section wiring `_resources_context`/
    `_lifestyle_context` already use for each other (see their docstrings). **WP43** adds
    `karma_converted` the same way, topping up the budget rather than spending from it. **WP47**
    adds `foci_cost` the same way, extending the shared budget to five sections.

    **WP45: bioware folds into this same section rather than getting its own** -- unlike Lifestyle
    (its own distinct rulebook chargen step), the rulebook's own Step Six groups "Cyberware and
    Bioware" as one combined subsection (see `chummer5.engine.cyberware`'s module docstring for the
    citation), both catalogs are tiny/near-identical in shape (nuyen + Essence, no other validation
    rule), and they share one Essence pool that has to be checked jointly regardless -- cramming a
    second, near-duplicate section into the UI would only fragment one shared decision. Evaluation
    order is fixed and documented in `chummer5.engine.bioware`'s module docstring: cyberware is
    resolved first (unaware of bioware), bioware second (aware of cyberware's own nuyen/Essence
    spend) -- so a combination only invalid once both are counted together is always caught, on the
    bioware call.

    Same `error`-gated re-validation pattern as `_resources_context`/`_lifestyle_context`: when
    `error` is unset, re-derives whether the currently-selected items still fit the combined budget
    (and the shared Essence floor `create_cyberware_selection`/`create_bioware_selection` enforce),
    surfacing a distinct `cyberware_budget_warning` rather than silently going over/under on the
    next render.
    """
    if character is None:
        return {"character": None, "cyberware_error": error}
    cyberware_by_id = {item.id: item for item in CYBERWARE}
    bioware_by_id = {item.id: item for item in BIOWARE}
    cyberware_groups = _catalog_groups(item_ids, _CYBERWARE_BY_CATEGORY, cyberware_by_id)
    bioware_groups = _catalog_groups(bioware_item_ids, _BIOWARE_BY_CATEGORY, bioware_by_id)
    budget = starting_nuyen(resources_letter, PRIORITIES) + _display_karma_to_nuyen(karma_converted)
    nuyen_available = budget - gear_cost - lifestyle_cost - foci_cost
    cyberware_spent = sum(
        int(row["subtotal"]) for group in cyberware_groups for row in group["rows"]
    )
    bioware_spent = sum(int(row["subtotal"]) for group in bioware_groups for row in group["rows"])
    spent = cyberware_spent + bioware_spent
    cyberware_essence_spent = sum(
        (cyberware_by_id[item_id].essence_cost for item_id in item_ids), Decimal(0)
    )
    bioware_essence_spent = sum(
        (bioware_by_id[item_id].essence_cost for item_id in bioware_item_ids), Decimal(0)
    )
    essence_spent = cyberware_essence_spent + bioware_essence_spent
    budget_warning: str | None = None
    if error is None:
        try:
            cyberware_selection = create_cyberware_selection(item_ids, CYBERWARE, nuyen_available)
            create_bioware_selection(
                bioware_item_ids,
                BIOWARE,
                nuyen_available - cyberware_selection.nuyen_spent,
                other_essence_spent=cyberware_selection.essence_spent,
            )
        except ValueError as exc:
            budget_warning = (
                f"No longer fits since priorities were last confirmed: {exc}. "
                "Adjust cyberware/bioware below to continue."
            )
    return {
        "character": character,
        "cyberware_groups": cyberware_groups,
        "bioware_groups": bioware_groups,
        "nuyen_available": nuyen_available,
        "nuyen_spent": spent,
        "nuyen_remaining": nuyen_available - spent,
        "essence_spent": essence_spent,
        "essence_remaining": BASE_ESSENCE - essence_spent,
        "cyberware_error": error,
        "cyberware_budget_warning": budget_warning,
    }


def _default_talent_codename(talent_letter: str) -> str:
    """The codename a fresh (or not-yet-visited) Talent section pre-fills for `talent_letter` --
    its first offered option (`"Mundane"` at letter E, since no other A-D letter offers one -- see
    `chummer5.web.session`'s own docstring), the same "starts at a legal, harmless default"
    precedent `DEFAULT_LIFESTYLE_TIER_NAME` et al. already set.
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
    error-echo render, mirroring `_quality_selection_context`'s identical `quality_ids` parameter.

    **WP19-style staleness re-validation**: when `error` is unset and a Talent selection is already
    committed (`character.magic_type is not None`), re-runs `create_magic_selection` against the
    *current* `talent_letter` purely to derive `talent_budget_warning` -- a priorities
    reconfirmation can change which letter Talent sits on, or which options that letter even offers,
    the same way it can shrink an attribute/skill/resources budget (see `_attribute_allocation_
    context`'s identical pattern).
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


def _spell_selection_context(
    character: Character | None,
    talent_letter: str,
    spell_ids: Iterable[str],
    *,
    error: str | None = None,
) -> dict[str, Any]:
    """Context for `_spell_selection.html` (WP29): WP26's `create_spell_selection` reaching the
    browser, gated to Magician only (see `_chargen_body.html`'s own gating note). `spell_ids` is
    whatever should be shown checked, same echo-the-submission shape as `_quality_selection_
    context`'s `quality_ids`.
    """
    if character is None:
        return {"character": None, "spell_error": error}
    if character.magic_type != "Magician":
        return {"character": character, "spell_error": error}
    magician_option = next(
        (o for o in offered_talent_options(talent_letter, PRIORITIES) if o.codename == "Magician"),
        None,
    )
    budget = (magician_option.spells or 0) if magician_option is not None else 0
    ids = set(spell_ids)
    rows = [{"spell": spell, "selected": spell.id in ids} for spell in SPELLS]
    return {
        "character": character,
        "spell_rows": rows,
        "spell_budget": budget,
        "spells_selected": len(ids),
        "spells_remaining": budget - len(ids),
        "spell_error": error,
    }


def _power_selection_context(
    character: Character | None,
    picks: Iterable[tuple[str, int, str | None]],
    *,
    error: str | None = None,
) -> dict[str, Any]:
    """Context for `_power_selection.html` (WP29): WP27's `create_power_selection` reaching the
    browser, gated to Adept only. `picks` is whatever should be shown filled in -- the character's
    own committed `power_selection.picks` on a clean render, or the raw submitted `(power_id,
    rating, selected_attribute)` triples on an error-echo render.
    """
    if character is None:
        return {"character": None, "power_error": error}
    if character.magic_type != "Adept":
        return {"character": character, "power_error": error}
    picked = {power_id: (rating, attribute) for power_id, rating, attribute in picks}
    rows = []
    spent = Decimal(0)
    for power in MVP_POWERS:
        rating, selected_attribute = picked.get(power.id, (0, None))
        select_attribute_bonus = next(
            (fb for fb in power.flat_bonuses if fb.target_kind == "select_attribute"), None
        )
        rows.append(
            {
                "power": power,
                "rating": rating,
                "selected_attribute": selected_attribute,
                "attribute_options": (
                    select_attribute_bonus.attribute_options
                    if select_attribute_bonus is not None
                    else ()
                ),
            }
        )
        if rating > 0:
            spent += power.points * rating
    budget = character.power_points
    return {
        "character": character,
        "power_rows": rows,
        "power_point_budget": budget,
        "power_points_spent": spent,
        "power_points_remaining": budget - spent,
        "power_error": error,
    }


def _spirit_selection_context(
    character: Character | None,
    picks: Iterable[tuple[str, int]],
    *,
    error: str | None = None,
) -> dict[str, Any]:
    """Context for `_spirit_selection.html` (WP46): `create_bound_spirit_selection` reaching the
    browser, gated to Magician only (mirrors `_spell_selection_context`'s identical gating note --
    Adepts/Mundane never cast or conjure, see `chummer5.engine.spirits`'s module docstring).
    `picks` is whatever should be shown filled in, same echo-the-submission shape as `_spell_
    selection_context`'s `spell_ids`.

    `karma_budget` is `character.karma_remaining` (WP51's unified ledger) with Bound Spirits' own
    currently-committed cost added back in -- `karma_remaining` already has it subtracted out
    (it's part of the sum), but re-validating a *new* Bound Spirit pick needs the budget as it would
    be with nothing yet committed to this section, the same way every other section's re-validation
    excludes its own prior commitment. Recomputed fresh on every render (not read off a stored
    total), so it always reflects the character's *current* karma spend -- including Foci's, read
    directly off `character.foci_selection` rather than threaded through as a parameter (pre-WP51,
    callers had to pass this by hand; now it's just part of the same `character` already passed in).

    **WP19-style staleness re-validation**: when `error` is unset and a Bound Spirit selection is
    already committed, re-runs `create_bound_spirit_selection` against the *current* character/
    budget purely to derive `spirit_budget_warning` -- an attribute edit (CHA) or a Talent change
    (MAG, tradition) can each shrink what was previously a valid selection, the same way a
    priorities reconfirmation can for every other carried-forward selection (see `_talent_
    selection_context`'s identical pattern).
    """
    if character is None:
        return {"character": None, "spirit_error": error}
    if character.magic_type != "Magician":
        return {"character": character, "spirit_error": error}
    offered = offered_spirit_types(character.tradition) if character.tradition is not None else ()
    own_committed_cost = (
        character.bound_spirit_selection.karma_cost
        if character.bound_spirit_selection is not None
        else 0
    )
    karma_budget = character.karma_remaining + own_committed_cost
    entries = list(picks)
    rows = [
        {
            "index": i,
            "spirit_type": entries[i][0] if i < len(entries) else "",
            "services": entries[i][1] if i < len(entries) else 0,
        }
        for i in range(MAX_BOUND_SPIRIT_ROWS)
    ]
    karma_spent = sum(services for _, services in entries)
    budget_warning: str | None = None
    if error is None and character.bound_spirit_selection is not None:
        committed_picks = [
            (spirit.spirit_type, spirit.services)
            for spirit in character.bound_spirit_selection.spirits
        ]
        try:
            create_bound_spirit_selection(committed_picks, character, karma_budget)
        except ValueError as exc:
            budget_warning = (
                f"No longer fits since priorities/attributes were last confirmed: {exc}. "
                "Reconfirm Bound Spirits below to continue."
            )
    return {
        "character": character,
        "spirit_rows": rows,
        "offered_spirit_types": offered,
        "max_bound_spirits": character.attribute_value("CHA"),
        "spirit_force": character.attribute_value("MAG"),
        "spirit_karma_budget": karma_budget,
        "spirit_karma_spent": karma_spent,
        "spirit_karma_remaining": karma_budget - karma_spent,
        "spirit_error": error,
        "spirit_budget_warning": budget_warning,
    }


def _foci_selection_context(
    character: Character | None,
    resources_letter: str,
    picks: Iterable[tuple[str, int]],
    gear_cost: int,
    lifestyle_cost: int,
    cyberware_cost: int,
    bioware_cost: int,
    karma_converted: int = 0,
    *,
    error: str | None = None,
) -> dict[str, Any]:
    """Context for `_foci_selection.html` (WP47): `create_foci_selection` reaching the browser,
    gated to any magic-active character (Magician or Adept -- see `chummer5.engine.foci`'s own
    docstring for why this is looser than Bound Spirits' Magician-only gate). `picks` is whatever
    should be shown filled in, the same echo-the-submission shape as `_spirit_selection_context`'s
    `picks`.

    **Nuyen**: shares the same Step Six pool gear/Lifestyle/cyberware/bioware already draw from --
    `gear_cost`/`lifestyle_cost`/`cyberware_cost`/`bioware_cost` are those sections' currently
    committed spend, the same cross-section wiring `_cyberware_context` already uses for its own
    four terms, now extended to five.

    **Karma**: `karma_budget` is `character.karma_remaining` (WP51's unified ledger) with Foci's own
    currently-committed cost added back in -- the same "exclude this section's own prior
    commitment" shape `_spirit_selection_context`'s own `karma_budget` uses, mirrored here. Bound
    Spirits' current commitment is read directly off `character.bound_spirit_selection` (part of
    `karma_remaining`'s own sum) rather than threaded through as a parameter, the same
    simplification WP51 made possible on the Bound Spirits side.

    **WP19-style staleness re-validation**: when `error` is unset and a Foci selection is already
    committed, re-runs `create_foci_selection` against the *current* character/budgets purely to
    derive `foci_budget_warning` -- an attribute edit (MAG) or a Talent change can each shrink what
    was previously a valid selection.
    """
    if character is None:
        return {"character": None, "foci_error": error}
    if character.magic_type is None:
        return {"character": character, "foci_error": error}

    entries = list(picks)
    by_id = {item.id: item for item in FOCI}
    force_by_id = dict(entries)
    foci_groups = [
        {
            "category": category,
            "rows": [
                {
                    "item": item,
                    "force": force_by_id.get(item.id, 0),
                    "subtotal": force_by_id.get(item.id, 0) * item.cost_per_force,
                }
                for item in items
            ],
        }
        for category, items in itertools.groupby(
            _FOCI_BY_CATEGORY, key=lambda item: item.focus_category
        )
    ]

    nuyen_available = (
        starting_nuyen(resources_letter, PRIORITIES)
        + _display_karma_to_nuyen(karma_converted)
        - gear_cost
        - lifestyle_cost
        - cyberware_cost
        - bioware_cost
    )
    nuyen_spent = sum(int(row["subtotal"]) for group in foci_groups for row in group["rows"])
    own_committed_cost = (
        character.foci_selection.karma_cost if character.foci_selection is not None else 0
    )
    karma_budget = character.karma_remaining + own_committed_cost
    karma_spent = sum(
        force * by_id[focus_id].bonding_karma_per_force for focus_id, force in entries
    )
    budget_warning: str | None = None
    if error is None:
        try:
            create_foci_selection(entries, character, FOCI, nuyen_available, karma_budget)
        except ValueError as exc:
            budget_warning = (
                f"No longer fits since priorities/attributes were last confirmed: {exc}. "
                "Adjust Foci below to continue."
            )
    return {
        "character": character,
        "foci_groups": foci_groups,
        "foci_nuyen_available": nuyen_available,
        "foci_nuyen_spent": nuyen_spent,
        "foci_nuyen_remaining": nuyen_available - nuyen_spent,
        "foci_karma_budget": karma_budget,
        "foci_karma_spent": karma_spent,
        "foci_karma_remaining": karma_budget - karma_spent,
        "foci_max_count": character.attribute_value("MAG"),
        "foci_max_total_force": character.attribute_value("MAG") * CHARGEN_FORCE_CAP_MULTIPLIER,
        "foci_error": error,
        "foci_budget_warning": budget_warning,
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
    skill_rows = (
        [
            {
                "skill": skill,
                "rating": rating,
                "specialization": allocation.specializations.get(skill.id, ""),
                "pool": dice_pool(character, allocation, skill),
            }
            for skill in ALL_SKILLS_SORTED
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
        "knowledge_skill_rows": (
            [
                {"name": pick.name, "category": pick.category, "rating": pick.rating}
                for pick in character.knowledge_selection.knowledge_skills
            ]
            if character.knowledge_selection is not None
            else []
        ),
        "language_rows": (
            [
                {"name": pick.name, "rating": pick.rating, "native": pick.native}
                for pick in character.knowledge_selection.languages
            ]
            if character.knowledge_selection is not None
            else []
        ),
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


def _chargen_body_context(session: ChargenSession, priority_ctx: dict[str, Any]) -> dict[str, Any]:
    """Merge the priority-form context with a clean (non-error) render of the attribute, skill,
    quality, contact, lifestyle, cyberware, and resources sections, reflecting the session's
    currently committed state. Used by both `GET /` and a successful `POST /ui/priorities` (the
    places that render every section at once).

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
    attribute_ctx = _attribute_allocation_context(character, attribute_points, magic_points)
    allocation = character.skill_allocation if character is not None else None
    skill_points = allocation.skill_points if allocation is not None else {}
    group_points = allocation.group_points if allocation is not None else {}
    specializations = allocation.specializations if allocation is not None else {}
    skill_ctx = _skill_allocation_context(
        character, session.skills_letter, skill_points, group_points, specializations
    )
    knowledge_selection = character.knowledge_selection if character is not None else None
    knowledge_skills = (
        knowledge_selection.knowledge_skills if knowledge_selection is not None else ()
    )
    languages = knowledge_selection.languages if knowledge_selection is not None else ()
    knowledge_ctx = _knowledge_selection_context(character, knowledge_skills, languages)
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

    @app.get("/ui/metatypes", response_class=HTMLResponse)
    def metatype_options_fragment(request: Request, heritage_letter: str) -> HTMLResponse:
        heritage = PRIORITIES.heritage.get(heritage_letter)
        metatype_options = metatype_choices(heritage, METATYPES) if heritage is not None else ()
        context = {
            "metatype_options": metatype_options,
            "selected": {"metatype_id": None},
        }
        return templates.TemplateResponse(request, "_metatype_select.html", context)

    @app.get("/ui/talent-options", response_class=HTMLResponse)
    def talent_options_fragment(
        request: Request, talent_letter: str, talent_codename: str
    ) -> HTMLResponse:
        """WP29: mirrors `metatype_options_fragment` above -- refreshes the tradition dropdown and
        free-skill-grant checkboxes inside `_talent_selection.html` when the player picks a
        different Talent codename, without a full-page/full-body round trip. Unlike the metatype
        fragment, this one is triggered by the codename radio group *inside* `_talent_selection
        .html` itself, not by the Talent letter selector in `_priority_form.html` -- changing the
        letter there only takes effect (and refreshes which codenames are even offered) once the
        priority form is actually submitted, the same "no live cross-section refresh" scope
        boundary WP20 already documented for gear/Lifestyle.
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

    @app.post("/ui/priorities", response_class=HTMLResponse)
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

    @app.post("/ui/attributes", response_class=HTMLResponse)
    async def submit_attributes(request: Request) -> HTMLResponse:
        session, new_cookie = resolve_session(request)
        if session.character is None:
            context = _attribute_allocation_context(None, {})
        else:
            form = await request.form()
            attribute_points = _parse_points(form, ALLOCATABLE_ATTRIBUTES, "attr_")
            previous = session.character
            # Post-WP29 correction: MAG's own points (when allocatable at all -- see this section's
            # own comment below) are parsed and validated separately from `attribute_points`, since
            # `create_character` only ever validates `ALLOCATABLE_ATTRIBUTES` -- see `chummer5
            # .engine.character.Character`'s docstring correction for why MAG's allocatability is
            # character-specific rather than a fixed global set.
            magic_points = (
                _parse_points(form, ("MAG",), "attr_").get("MAG", 0)
                if previous.magic_type is not None
                else 0
            )
            # `create_character` only needs `metatype`/`special_attribute_points` off a
            # `MetatypeChoice` (see its own docstring) -- both are already stable fields on the
            # session's committed `Character`, so there's no need to re-look-up the Heritage
            # priority/metatype catalog here the way `submit_priorities` does.
            choice = MetatypeChoice(
                metatype=previous.metatype,
                special_attribute_points=previous.special_attribute_points,
                karma=0,
            )
            try:
                character = create_character(
                    choice,
                    session.heritage_letter,
                    session.attributes_letter,
                    PRIORITIES,
                    attribute_points,
                )
                if previous.magic_type is not None:
                    magic_points = create_magic_attribute_points(
                        previous.magic_type,
                        magic_points,
                        previous.magic_rating,
                        previous.attribute_range("MAG").maximum,
                        previous.special_attribute_points,
                        attribute_points.get("EDG", 0),
                    )
            except ValueError as exc:
                context = _attribute_allocation_context(
                    session.character, attribute_points, magic_points, error=str(exc)
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
                # WP29: same reasoning -- Talent/tradition/free-skill-grant Improvements, and the
                # Adept power selection's own Improvements, need re-landing on this fresh index too,
                # or a Magician/Adept would silently reset to Mundane on the next attribute edit.
                # `magic_points` is *not* carried from `previous` here -- it's this same request's
                # own freshly-validated submission (the Attributes form is where MAG points are
                # spent, echoing whatever was already committed unless just edited).
                character = _relink_magic_selection(character, session.talent_letter, previous)
                # WP34: cyberware's Essence/bonus Improvements need the same re-landing as
                # quality/metatype/Talent above -- a fresh `create_character()` call always starts
                # `cyberware_selection` at `None` and `improvements` empty (see `_relink_cyberware_
                # selection`'s own docstring).
                character = _relink_cyberware_selection(character, previous.cyberware_selection)
                # WP45: bioware's Essence/bonus Improvements need the identical re-landing.
                character = _relink_bioware_selection(character, previous.bioware_selection)
                # WP47: Foci's FLAT_BONUS skill Improvements need the identical re-landing.
                character = _relink_foci_selection(character, previous.foci_selection)
                character = replace(
                    character,
                    skill_allocation=previous.skill_allocation,
                    resources_selection=previous.resources_selection,
                    lifestyle_selection=previous.lifestyle_selection,
                    magic_attribute_points=magic_points,
                    # WP46: carried forward by plain reference, same as lifestyle_selection above --
                    # a bound spirit has no Improvement to re-land (see chummer5.engine.spirits'
                    # module docstring), so there's no relink helper needed, just a plain carry.
                    # `_spirit_selection_context`'s own WP19-style re-validation is what surfaces a
                    # "no longer fits" warning if this attribute edit shrank CHA/MAG below what was
                    # already committed.
                    bound_spirit_selection=previous.bound_spirit_selection,
                    # WP49: same plain-carry treatment -- Knowledge/Language has no Improvement of
                    # its own to re-land either (it only *consumes* Bilingual's
                    # NATIVE_LANGUAGE_LIMIT, already re-landed by `_relink_quality_improvements`
                    # above). `_knowledge_selection_context`'s own WP19-style re-validation surfaces
                    # a "no longer fits" warning if this attribute edit shrank INT/LOG below what
                    # was already spent.
                    knowledge_selection=previous.knowledge_selection,
                )
                session.character = character
                context = _attribute_allocation_context(character, attribute_points, magic_points)
        response = templates.TemplateResponse(request, "_attribute_allocation.html", context)
        if new_cookie is not None:
            response.set_cookie(SESSION_COOKIE_NAME, new_cookie, httponly=True, samesite="lax")
        return response

    @app.post("/ui/talent", response_class=HTMLResponse)
    async def submit_talent(request: Request) -> HTMLResponse:
        session, new_cookie = resolve_session(request)
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
        response = templates.TemplateResponse(request, "_talent_selection.html", context)
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
            specializations = _parse_specializations(form, (s.id for s in MUNDANE_SKILLS), "spec_")
            try:
                allocation = create_skill_allocation(
                    session.skills_letter,
                    PRIORITIES,
                    SKILLS,
                    skill_points,
                    group_points,
                    specializations,
                )
            except ValueError as exc:
                context = _skill_allocation_context(
                    session.character,
                    session.skills_letter,
                    skill_points,
                    group_points,
                    specializations,
                    error=str(exc),
                )
            else:
                session.character = replace(session.character, skill_allocation=allocation)
                context = _skill_allocation_context(
                    session.character,
                    session.skills_letter,
                    skill_points,
                    group_points,
                    specializations,
                )
        response = templates.TemplateResponse(request, "_skill_allocation.html", context)
        if new_cookie is not None:
            response.set_cookie(SESSION_COOKIE_NAME, new_cookie, httponly=True, samesite="lax")
        return response

    @app.post("/ui/knowledge", response_class=HTMLResponse)
    async def submit_knowledge(request: Request) -> HTMLResponse:
        session, new_cookie = resolve_session(request)
        if session.character is None:
            context = _knowledge_selection_context(None, (), ())
        else:
            form = await request.form()
            knowledge_skills = _parse_knowledge_skills(form, MAX_KNOWLEDGE_ROWS)
            languages = _parse_languages(form, MAX_LANGUAGE_ROWS)
            try:
                selection = create_knowledge_selection(
                    session.character, knowledge_skills, languages
                )
            except ValueError as exc:
                context = _knowledge_selection_context(
                    session.character, knowledge_skills, languages, error=str(exc)
                )
            else:
                session.character = replace(session.character, knowledge_selection=selection)
                context = _knowledge_selection_context(
                    session.character, knowledge_skills, languages
                )
        response = templates.TemplateResponse(request, "_knowledge_skills.html", context)
        if new_cookie is not None:
            response.set_cookie(SESSION_COOKIE_NAME, new_cookie, httponly=True, samesite="lax")
        return response

    @app.post("/ui/spells", response_class=HTMLResponse)
    async def submit_spells(request: Request) -> HTMLResponse:
        session, new_cookie = resolve_session(request)
        if session.character is None or session.character.magic_type != "Magician":
            context = _spell_selection_context(session.character, session.talent_letter, ())
        else:
            form = await request.form()
            spell_ids = [str(v) for v in form.getlist("spell_id")]
            magician_option = next(
                (
                    o
                    for o in offered_talent_options(session.talent_letter, PRIORITIES)
                    if o.codename == "Magician"
                ),
                None,
            )
            budget = (magician_option.spells or 0) if magician_option is not None else 0
            try:
                selection = create_spell_selection(spell_ids, SPELLS, budget)
            except ValueError as exc:
                context = _spell_selection_context(
                    session.character, session.talent_letter, spell_ids, error=str(exc)
                )
            else:
                session.character = replace(session.character, spell_selection=selection)
                context = _spell_selection_context(
                    session.character, session.talent_letter, spell_ids
                )
        response = templates.TemplateResponse(request, "_spell_selection.html", context)
        if new_cookie is not None:
            response.set_cookie(SESSION_COOKIE_NAME, new_cookie, httponly=True, samesite="lax")
        return response

    @app.post("/ui/powers", response_class=HTMLResponse)
    async def submit_powers(request: Request) -> HTMLResponse:
        session, new_cookie = resolve_session(request)
        if session.character is None or session.character.magic_type != "Adept":
            context = _power_selection_context(session.character, ())
        else:
            form = await request.form()
            picks = _parse_power_picks(form, MVP_POWERS)
            try:
                selection = create_power_selection(picks, POWERS, session.character.power_points)
            except ValueError as exc:
                context = _power_selection_context(session.character, picks, error=str(exc))
            else:
                session.character = _replace_committed_powers(session.character, selection)
                context = _power_selection_context(session.character, picks)
        response = templates.TemplateResponse(request, "_power_selection.html", context)
        if new_cookie is not None:
            response.set_cookie(SESSION_COOKIE_NAME, new_cookie, httponly=True, samesite="lax")
        return response

    @app.post("/ui/spirits", response_class=HTMLResponse)
    async def submit_spirits(request: Request) -> HTMLResponse:
        session, new_cookie = resolve_session(request)
        if session.character is None or session.character.magic_type != "Magician":
            context = _spirit_selection_context(session.character, ())
        else:
            form = await request.form()
            picks = _parse_bound_spirits(form, MAX_BOUND_SPIRIT_ROWS)
            character = session.character
            # WP51: budget excludes Bound Spirits' own currently-committed cost (about to be
            # replaced by this submission) -- see _spirit_selection_context's own docstring for why
            # this is `karma_remaining` with that one term added back in.
            own_committed_cost = (
                character.bound_spirit_selection.karma_cost
                if character.bound_spirit_selection is not None
                else 0
            )
            karma_budget = character.karma_remaining + own_committed_cost
            try:
                selection = create_bound_spirit_selection(picks, character, karma_budget)
            except ValueError as exc:
                context = _spirit_selection_context(character, picks, error=str(exc))
            else:
                session.character = replace(character, bound_spirit_selection=selection)
                context = _spirit_selection_context(session.character, picks)
        response = templates.TemplateResponse(request, "_spirit_selection.html", context)
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
            # WP48: the archetype/general-choice fields are only meaningful when Mentor Spirit
            # itself is checked -- forced to None otherwise, so unchecking the quality never
            # requires also clearing a stale dropdown just to avoid "an archetype was picked
            # without the Mentor Spirit quality" (create_quality_selection's own guard against an
            # orphaned pick, meant for a tampered/stale request, not this ordinary UI interaction).
            mentor_spirit_archetype_id: str | None = None
            mentor_spirit_general_choice_id: str | None = None
            if MENTOR_SPIRIT_QUALITY.id in quality_ids:
                raw_archetype_id = str(form.get("mentor_spirit_archetype_id") or "")
                mentor_spirit_archetype_id = raw_archetype_id or None
                raw_general_choice_id = str(form.get("mentor_spirit_general_choice_id") or "")
                mentor_spirit_general_choice_id = raw_general_choice_id or None
            # WP23: validate against this character's own offerable catalog, not the raw QUALITIES
            # catalog, so a tampered/stale submission can't buy an already metatype-granted quality
            # either -- `create_quality_selection` already raises "not an MVP-offered quality id"
            # for anything not in whatever catalog it's given, so this alone is sufficient.
            offered = offerable_quality_catalog(session.character, QUALITIES)
            try:
                selection = create_quality_selection(
                    quality_ids,
                    offered,
                    magic_type=session.character.magic_type,
                    mentor_catalog=MENTORS,
                    mentor_spirit_archetype_id=mentor_spirit_archetype_id,
                    mentor_spirit_general_choice_id=mentor_spirit_general_choice_id,
                )
            except ValueError as exc:
                context = _quality_selection_context(
                    session.character,
                    quality_ids,
                    mentor_spirit_archetype_id=mentor_spirit_archetype_id,
                    mentor_spirit_general_choice_id=mentor_spirit_general_choice_id,
                    error=str(exc),
                )
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
            context = _resources_context(None, session.resources_letter, (), 0, 0, 0, 0)
        else:
            form = await request.form()
            gear_names = _parse_gear(form, STARTER_GEAR_CATALOG)
            karma_converted = _parse_karma_converted(form)
            lifestyle_selection = session.character.lifestyle_selection
            lifestyle_cost = (
                lifestyle_selection.total_cost if lifestyle_selection is not None else 0
            )
            cyberware_selection = session.character.cyberware_selection
            cyberware_cost = (
                cyberware_selection.nuyen_spent if cyberware_selection is not None else 0
            )
            bioware_selection = session.character.bioware_selection
            bioware_cost = bioware_selection.nuyen_spent if bioware_selection is not None else 0
            try:
                selection = create_resources_selection(
                    session.resources_letter,
                    PRIORITIES,
                    gear_names,
                    lifestyle_cost=lifestyle_cost,
                    cyberware_cost=cyberware_cost,
                    bioware_cost=bioware_cost,
                    karma_converted=karma_converted,
                )
            except ValueError as exc:
                context = _resources_context(
                    session.character,
                    session.resources_letter,
                    gear_names,
                    lifestyle_cost,
                    cyberware_cost,
                    bioware_cost,
                    karma_converted,
                    error=str(exc),
                )
            else:
                session.character = replace(session.character, resources_selection=selection)
                context = _resources_context(
                    session.character,
                    session.resources_letter,
                    gear_names,
                    lifestyle_cost,
                    cyberware_cost,
                    bioware_cost,
                    karma_converted,
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
                0,
                0,
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
            karma_converted = (
                resources_selection.karma_converted if resources_selection is not None else 0
            )
            cyberware_selection = session.character.cyberware_selection
            cyberware_cost = (
                cyberware_selection.nuyen_spent if cyberware_selection is not None else 0
            )
            bioware_selection = session.character.bioware_selection
            bioware_cost = bioware_selection.nuyen_spent if bioware_selection is not None else 0
            try:
                lifestyle_selection = create_lifestyle_selection(tier_name, months, LIFESTYLES)
                new_resources_selection = create_resources_selection(
                    session.resources_letter,
                    PRIORITIES,
                    gear_names,
                    lifestyle_cost=lifestyle_selection.total_cost,
                    cyberware_cost=cyberware_cost,
                    bioware_cost=bioware_cost,
                    karma_converted=karma_converted,
                )
            except ValueError as exc:
                context = _lifestyle_context(
                    session.character,
                    session.resources_letter,
                    tier_name,
                    months,
                    gear_cost,
                    cyberware_cost,
                    bioware_cost,
                    karma_converted,
                    error=str(exc),
                )
            else:
                session.character = replace(
                    session.character,
                    lifestyle_selection=lifestyle_selection,
                    resources_selection=new_resources_selection,
                )
                context = _lifestyle_context(
                    session.character,
                    session.resources_letter,
                    tier_name,
                    months,
                    gear_cost,
                    cyberware_cost,
                    bioware_cost,
                    karma_converted,
                )
        response = templates.TemplateResponse(request, "_lifestyle.html", context)
        if new_cookie is not None:
            response.set_cookie(SESSION_COOKIE_NAME, new_cookie, httponly=True, samesite="lax")
        return response

    @app.post("/ui/cyberware", response_class=HTMLResponse)
    async def submit_cyberware(request: Request) -> HTMLResponse:
        session, new_cookie = resolve_session(request)
        if session.character is None:
            context = _cyberware_context(None, session.resources_letter, (), (), 0, 0, 0)
        else:
            form = await request.form()
            item_ids = _parse_cyberware(form, CYBERWARE)
            bioware_item_ids = _parse_bioware(form, BIOWARE)
            resources_selection = session.character.resources_selection
            gear_names = (
                tuple(item.name for item in resources_selection.gear)
                if resources_selection is not None
                else ()
            )
            gear_cost = resources_selection.nuyen_spent if resources_selection is not None else 0
            karma_converted = (
                resources_selection.karma_converted if resources_selection is not None else 0
            )
            lifestyle_selection = session.character.lifestyle_selection
            lifestyle_cost = (
                lifestyle_selection.total_cost if lifestyle_selection is not None else 0
            )
            # WP47: Foci's own committed nuyen cost shares this same pool now too.
            foci_selection = session.character.foci_selection
            foci_cost = foci_selection.nuyen_cost if foci_selection is not None else 0
            nuyen_available = available_nuyen(
                session.resources_letter, PRIORITIES, karma_converted
            ) - (gear_cost + lifestyle_cost + foci_cost)
            try:
                # Fixed evaluation order (chummer5.engine.bioware's own docstring): cyberware
                # first, unaware of bioware; bioware second, aware of cyberware's own nuyen/Essence
                # spend -- so a combination only invalid once both are counted together is always
                # caught, on the bioware call.
                selection = create_cyberware_selection(item_ids, CYBERWARE, nuyen_available)
                bioware_selection = create_bioware_selection(
                    bioware_item_ids,
                    BIOWARE,
                    nuyen_available - selection.nuyen_spent,
                    other_essence_spent=selection.essence_spent,
                )
                new_resources_selection = create_resources_selection(
                    session.resources_letter,
                    PRIORITIES,
                    gear_names,
                    lifestyle_cost=lifestyle_cost,
                    cyberware_cost=selection.nuyen_spent,
                    bioware_cost=bioware_selection.nuyen_spent,
                    karma_converted=karma_converted,
                    foci_cost=foci_cost,
                )
            except ValueError as exc:
                context = _cyberware_context(
                    session.character,
                    session.resources_letter,
                    item_ids,
                    bioware_item_ids,
                    gear_cost,
                    lifestyle_cost,
                    karma_converted,
                    foci_cost,
                    error=str(exc),
                )
            else:
                session.character = _replace_committed_cyberware(session.character, selection)
                session.character = _replace_committed_bioware(session.character, bioware_selection)
                session.character = replace(
                    session.character, resources_selection=new_resources_selection
                )
                context = _cyberware_context(
                    session.character,
                    session.resources_letter,
                    item_ids,
                    bioware_item_ids,
                    gear_cost,
                    lifestyle_cost,
                    karma_converted,
                    foci_cost,
                )
        response = templates.TemplateResponse(request, "_cyberware.html", context)
        if new_cookie is not None:
            response.set_cookie(SESSION_COOKIE_NAME, new_cookie, httponly=True, samesite="lax")
        return response

    @app.post("/ui/foci", response_class=HTMLResponse)
    async def submit_foci(request: Request) -> HTMLResponse:
        session, new_cookie = resolve_session(request)
        if session.character is None or session.character.magic_type is None:
            context = _foci_selection_context(
                session.character, session.resources_letter, (), 0, 0, 0, 0
            )
        else:
            form = await request.form()
            picks = _parse_foci(form, FOCI)
            character = session.character
            resources_selection = character.resources_selection
            gear_cost = resources_selection.nuyen_spent if resources_selection is not None else 0
            karma_converted = (
                resources_selection.karma_converted if resources_selection is not None else 0
            )
            lifestyle_selection = character.lifestyle_selection
            lifestyle_cost = (
                lifestyle_selection.total_cost if lifestyle_selection is not None else 0
            )
            cyberware_selection = character.cyberware_selection
            cyberware_cost = (
                cyberware_selection.nuyen_spent if cyberware_selection is not None else 0
            )
            bioware_selection = character.bioware_selection
            bioware_cost = bioware_selection.nuyen_spent if bioware_selection is not None else 0
            nuyen_available = available_nuyen(
                session.resources_letter, PRIORITIES, karma_converted
            ) - (gear_cost + lifestyle_cost + cyberware_cost + bioware_cost)
            # WP51: budget excludes Foci's own currently-committed cost (about to be replaced by
            # this submission) -- see _foci_selection_context's own docstring for why this is
            # `karma_remaining` with that one term added back in.
            own_committed_cost = (
                character.foci_selection.karma_cost if character.foci_selection is not None else 0
            )
            karma_budget = character.karma_remaining + own_committed_cost
            try:
                selection = create_foci_selection(
                    picks, character, FOCI, nuyen_available, karma_budget
                )
                new_resources_selection = create_resources_selection(
                    session.resources_letter,
                    PRIORITIES,
                    tuple(
                        item.name
                        for item in (
                            resources_selection.gear if resources_selection is not None else ()
                        )
                    ),
                    lifestyle_cost=lifestyle_cost,
                    cyberware_cost=cyberware_cost,
                    bioware_cost=bioware_cost,
                    karma_converted=karma_converted,
                    foci_cost=selection.nuyen_cost,
                )
            except ValueError as exc:
                context = _foci_selection_context(
                    character,
                    session.resources_letter,
                    picks,
                    gear_cost,
                    lifestyle_cost,
                    cyberware_cost,
                    bioware_cost,
                    karma_converted,
                    error=str(exc),
                )
            else:
                session.character = _replace_committed_foci(character, selection)
                session.character = replace(
                    session.character, resources_selection=new_resources_selection
                )
                context = _foci_selection_context(
                    session.character,
                    session.resources_letter,
                    picks,
                    gear_cost,
                    lifestyle_cost,
                    cyberware_cost,
                    bioware_cost,
                    karma_converted,
                )
        response = templates.TemplateResponse(request, "_foci_selection.html", context)
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

    return app


app = create_app()
