"""Static rules data and MVP-scope catalog constants, shared by every `chummer5.web.routes` module.

**WP62**: split out of the former `chummer5.web.app` (see `spec/plan/phase-r-architecture-cleanup
.md`'s WP58 audit) -- every `load_*()` call `chummer5.data` makes once per process (Project
Overview's "parsed once at startup" rule), plus the catalog-derived constants more than one
chargen-step route module needs. Also hosts `TEMPLATES_DIR`/`templates` (the shared
`Jinja2Templates` instance) and `STATIC_DIR`, since these too have no step-specific home and every
route module needs `templates` to render its own fragment.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from fastapi.templating import Jinja2Templates
from jinja2 import pass_context
from jinja2.runtime import Context
from starlette.requests import Request

from chummer5.data.bioware import load_bioware
from chummer5.data.cyberware import load_cyberware
from chummer5.data.cyberware_subsystems import load_cyberware_entries
from chummer5.data.foci import load_foci
from chummer5.data.lifestyle import load_lifestyle_options, load_lifestyles
from chummer5.data.mentors import load_mentors
from chummer5.data.metatypes import load_metatypes
from chummer5.data.powers import load_powers
from chummer5.data.priorities import load_priorities
from chummer5.data.qualities import load_qualities
from chummer5.data.skills import Skill, load_knowledge_skills, load_skills
from chummer5.data.spells import load_spells
from chummer5.data.traditions import load_traditions
from chummer5.engine.character import Character
from chummer5.engine.lifestyle import MIN_LIFESTYLE_MONTHS
from chummer5.engine.magic import MAGICAL_SKILL_CATEGORIES, mvp_power_catalog
from chummer5.engine.qualities import MENTOR_SPIRIT_QUALITY_NAME, mvp_quality_catalog
from chummer5.engine.skills import skill_purchase_rules
from chummer5.web.i18n import (
    jinja_data_term,
    jinja_data_text,
    jinja_nuyen,
    jinja_render_message,
    jinja_translate,
    jinja_translate_plural,
)

WEB_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = WEB_DIR / "templates"
STATIC_DIR = WEB_DIR / "static"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
# WP101: the i18n key layer's one injection point -- `_("Key", ...)` in every template.
templates.env.globals["_"] = jinja_translate
templates.env.globals["_n"] = jinja_translate_plural  # WP102: `_n("Key", count, ...)`
# WP102: the one money formatter every template goes through (`{{ amount | nuyen }}`).
templates.env.filters["nuyen"] = jinja_nuyen
# WP102: `{{ value | tr }}` -- a context builder's `Message`, or an engine error's plain text.
templates.env.filters["tr"] = jinja_render_message
# WP103: `{{ skill | dterm("skills.xml") }}` -- a game-data term's display name, never its identity.
templates.env.filters["dterm"] = jinja_data_term
templates.env.filters["dtext"] = jinja_data_text  # WP103: `{{ mentor | dtext("advantage") }}`


@pass_context
def _root_relative_url_for(context: Context, name: str, /, **path_params: Any) -> str:
    """WP141: `url_for` in templates gives a root-relative path (`/static/app.css`), not
    Starlette's absolute URL. The absolute one is built from the request's own scheme and host,
    which behind Caddy is `http://` unless uvicorn trusts the proxy's headers -- on an https page
    that is mixed content the browser blocks, and outside the CSP's `'self'`."""
    request: Request = context["request"]
    path = request.url_for(name, **path_params).path
    if name == "static":
        return f"{path}?v={static_version(str(path_params['path']))}"
    return path


_STATIC_VERSIONS: dict[str, tuple[float, str]] = {}


def static_version(path: str) -> str:
    """A static file's cache-busting version: the start of its content hash. Static files are
    served without `Cache-Control`, so a browser keeps an unchanged-looking URL for as long as its
    own freshness heuristic says, and a changed stylesheet or script never reached it (found when
    the WP148 Skills strip rendered unstyled). With the hash in the URL, every change is a new URL.
    Re-hashed when the file's mtime changes, so a running dev server picks up edits."""
    file = STATIC_DIR / path
    mtime = file.stat().st_mtime
    cached = _STATIC_VERSIONS.get(path)
    if cached is None or cached[0] != mtime:
        cached = (mtime, hashlib.sha256(file.read_bytes()).hexdigest()[:12])
        _STATIC_VERSIONS[path] = cached
    return cached[1]


templates.env.globals["url_for"] = _root_relative_url_for

# Static rules data: parsed once per process, not per request (Project Overview's "parsed once at
# startup" rule for `chummer5.data` loaders).
METATYPES = load_metatypes()
PRIORITIES = load_priorities()
SKILLS = load_skills()
# WP149: legacy's example Knowledge/Language skills, for the Knowledge tab's placeholders only.
KNOWLEDGE_CATALOG = load_knowledge_skills()
QUALITIES = load_qualities()
LIFESTYLES = load_lifestyles()
LIFESTYLE_OPTIONS = load_lifestyle_options()  # WP132
# WP34 (Phase J's UI): the flat-cost, flat-Essence, Standard-grade cyberware catalog (WP31).
# **No longer what the picker offers** -- WP42 widened `_cyberware.html` to the full SR5 set below.
# Kept because it is still the WP31 flat view several test modules and fixtures read (and because
# `chummer5.data.cyberware` remains the home of the shared `<bonus>` classifier either way);
# retiring `load_cyberware()` outright is a cleanup no WP has claimed.
CYBERWARE = load_cyberware()
# WP41: WP37's full 87-row SR5 catalog, with formulas parsed and Capacity/subsystem structure
# captured. This is what every *engine* call resolves against now
# (`create_cyberware_tree_selection`, `build_character`, `import_chum5`), since
# `Character.cyberware_selection` is a purchase tree.
# CYBERWARE's ids are a subset of these, so a flat pick made from the picker above resolves here
# unchanged.
CYBERWARE_ENTRIES = load_cyberware_entries()

# WP42: the two rows of `CYBERWARE_ENTRIES` that are *engine bookkeeping*, not purchasable SR5 gear,
# despite carrying `<source>SR5</source>` like everything else. `Essence Hole` / `Essence Antihole`
# have `<page>0</page>`, `<cost>0</cost>`, `<avail>0</avail>`, a `<rating>` of **600**, and the
# phrase "essence hole" appears nowhere in the core rulebook (checked over the whole PDF -- see
# `spec/rulebooks/learnings/phase-k.md`'s WP42 entry). The legacy app creates them from code
# (`Character.IncreaseEssenceHole`) to represent Essence left behind by *removed* cyberware, a
# career-mode concept this project has no equivalent of. WP31's flat-cost filter excluded both by
# accident (their `<ess>` is `Rating * 0.01`); this list is what keeps that true now that the picker
# no longer filters on flatness.
_UNPURCHASABLE_CYBERWARE_NAMES = frozenset({"Essence Hole", "Essence Antihole"})

# WP42: what the picker offers as a *standalone* purchase -- everything above except the two
# bookkeeping rows and the 9 `<requireparent>` rows, which have no standalone mode at all
# (`create_cyberware_tree_selection` rejects one, so offering them there was a live bug: buying an
# `Ocular Drone` from WP34's picker could only ever produce an error). Those 9 are offered inside
# their parent instead, via `cyberware_plugin_choices` below. Sorted by (category, name) for the
# category-grouped `<details>` sections, exactly as `_CYBERWARE_BY_CATEGORY` was.
CYBERWARE_STANDALONE = tuple(
    sorted(
        (
            entry
            for entry in CYBERWARE_ENTRIES
            if not entry.requires_parent and entry.name not in _UNPURCHASABLE_CYBERWARE_NAMES
        ),
        key=lambda entry: (entry.category, entry.name),
    )
)

# WP42: every row installable *into* something -- a bracketed `<capacity>`, i.e. a Capacity price.
# `bundled_free` rows (`Image Link`, `Sound Link`) are excluded: they are auto-attached by their own
# parent and free, so a checkbox for one would offer a choice that isn't one. They stay in
# `CYBERWARE_STANDALONE` (WP34 offered them and the engine prices a standalone one normally), and
# the parent's own block lists them as included.
_CYBERWARE_PLUGINS = tuple(
    sorted(
        (
            entry
            for entry in CYBERWARE_ENTRIES
            if entry.is_plugin
            and not entry.bundled_free
            and entry.name not in _UNPURCHASABLE_CYBERWARE_NAMES
        ),
        key=lambda entry: (entry.category, entry.name),
    )
)

# WP42: the plugin rows each parent may hold, resolved once per parent id at import time rather than
# re-filtered per request. Keyed by the *parent's* catalog id; a row with no `<allowsubsystems>` has
# no entry. A parent's own bundled names are filtered out here too -- `Cybereyes Basic System` gets
# its `Image Link` automatically, so offering it as an installable choice would be a second way to
# ask for something already present.
CYBERWARE_PLUGIN_CHOICES = {
    parent.id: tuple(
        plugin
        for plugin in _CYBERWARE_PLUGINS
        if plugin.category in parent.allowed_subsystem_categories
        and plugin.name not in parent.bundled_subsystem_names
    )
    for parent in CYBERWARE_ENTRIES
    if parent.is_subsystem_parent
}
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
# WP149: the Knowledge tab's one table holds both kinds of row, so the two caps count together.
MAX_KNOWLEDGE_TABLE_ROWS = MAX_KNOWLEDGE_ROWS + MAX_LANGUAGE_ROWS

# MVP's regular Skills-priority point-buy UI stays mundane-only for a Mundane character -- Magical
# Active/Pseudo-Magical Active skills require being Awakened at all (not just a nonzero MAG dice
# pool term), and Resonance Active skills require being Emerged (RES stays out of scope permanently,
# per the Project Overview) -- excluded from the allocation UI for the same "excluded, not silently
# broken" reason WP2/WP3 exclude non-SR5 metatypes/qualities from their catalogs. This is a UI-layer
# curation, not an engine change: `create_skill_allocation` itself is still generic and would accept
# points on these skills if submitted directly (e.g. via a hand-crafted request).
#
# **WP61 correction**: this was originally `s.attribute not in ("MAG", "RES")` -- a plausible-
# looking but wrong proxy. Confirmed against the loaded catalog while building WP61's category
# grouping (which made the mistake visible by giving Mundane characters their own "Magical Active"
# category header): 3 of the 12 Magical/Pseudo-Magical/Resonance-categorized skills (Assensing/INT,
# Astral Combat/WIL, Arcana/LOG) use a *non*-MAG/RES linked attribute for their dice pool despite
# requiring Awakened status to use at all -- the attribute-based filter let a Mundane character buy
# all three, a real (if narrow) latent gap since WP2 first drew this line, surfaced and fixed here
# rather than left for a future WP now that the category data needed to fix it correctly
# (`Skill.category`) is already in hand for the grouping work below.
_NON_MUNDANE_SKILL_CATEGORIES = MAGICAL_SKILL_CATEGORIES | {"Resonance Active"}
MUNDANE_SKILLS = tuple(
    sorted(
        (s for s in SKILLS if s.category not in _NON_MUNDANE_SKILL_CATEGORIES),
        key=lambda s: s.name,
    )
)
MUNDANE_SKILL_GROUPS = tuple(
    sorted({s.skill_group for s in MUNDANE_SKILLS if s.skill_group is not None})
)
# WP29 note (resolved by WP61): a Magician's Talent free-skill grant could always raise a Magical
# Active skill's rating above 0 via a pure Improvement, entirely independent of this buy UI (see
# `chummer5.engine.magic.apply_magic_skill_grant_improvements`'s own docstring) -- but nothing let a
# player spend *additional* regular Skill points or leftover Karma on Magical Active skills beyond
# that grant, flagged there as a real, deliberately deferred gap pending a decision on which subset
# to offer.
#
# WP61: resolved by reusing `MAGICAL_SKILL_CATEGORIES` (the exact category filter already verified
# against the legacy `GetMagicalSkillList()` for the free-grant itself, WP25) rather than any
# narrower per-tradition/per-magic-type subset. `_offered_skills`/`_offered_skill_groups` are the
# character-scoped equivalents of `MUNDANE_SKILLS`/`MUNDANE_SKILL_GROUPS` every buy-UI call site
# now uses instead -- both return the exact Mundane-only sets unchanged when
# `character.magic_type is None`.
#
# **WP118 correction.** WP61 also claimed "SR5 doesn't restrict regular skill-point spend by
# magic type" and offered every Magical Active skill to an Adept. That read p. 69 backwards:
# "Adepts cannot use skills from any magic-related skill groups (Sorcery, Conjuring, or
# Enchanting)" and "can learn the Assensing skill only if they have the Astral Perception power".
# The rule now lives in the engine (`chummer5.engine.skills.skill_purchase_rules`), and these two
# functions hide whatever it bans -- for an Adept, and for Incompetent's group and an Uncouth
# character's Social groups too.
#
# **WP148 correction (decisions log, 2026-10-25).** The WP61 note above has Arcana needing an
# Awakened character. The user ruled otherwise: Arcana is a *Pseudo*-Magical skill a mundane
# character may learn, and legacy's `SkillsSection.cs` filter gates only "Magical Active". So a
# Mundane character is offered the Pseudo-Magical Active skills (Arcana alone in the core book);
# Magical Active skills still need an Awakened one. `MUNDANE_SKILLS` itself is unchanged: it is
# also the no-character fallback, and Arcana has no skill group, so `MUNDANE_SKILL_GROUPS` is too.
_MAGICAL_SKILLS = tuple(
    sorted((s for s in SKILLS if s.category in MAGICAL_SKILL_CATEGORIES), key=lambda s: s.name)
)
_PSEUDO_MAGICAL_SKILLS = tuple(s for s in _MAGICAL_SKILLS if s.category == "Pseudo-Magical Active")


def first_example(skill: Skill) -> str | None:
    """WP148: a skill's first suggested specialization, for an "e.g. ..." placeholder. Entries in
    brackets ("[Focus Type]") are templates, not examples, and are skipped."""
    return next((spec for spec in skill.specializations if not spec.startswith("[")), None)


def offered_skills(character: Character | None) -> tuple[Skill, ...]:
    if character is None:
        return MUNDANE_SKILLS
    candidates = tuple(
        sorted(
            MUNDANE_SKILLS
            + (_PSEUDO_MAGICAL_SKILLS if character.magic_type is None else _MAGICAL_SKILLS),
            key=lambda s: s.name,
        )
    )
    rules = skill_purchase_rules(character)  # WP118: whatever the engine would reject
    return tuple(s for s in candidates if rules.skill_blocked(s) is None)


def offered_skill_groups(character: Character | None) -> tuple[str, ...]:
    if character is None:
        return MUNDANE_SKILL_GROUPS
    rules = skill_purchase_rules(character)
    groups = {s.skill_group for s in offered_skills(character) if s.skill_group is not None}
    return tuple(sorted(g for g in groups if rules.group_blocked(g, SKILLS) is None))


# WP29: the character sheet's read-only skill list needs every skill (so a Magician's granted
# Magical Active skill shows up there too, see `_character_sheet_context`), sorted the same way
# `MUNDANE_SKILLS` already is.
ALL_SKILLS_SORTED = tuple(sorted(SKILLS, key=lambda s: s.name))
