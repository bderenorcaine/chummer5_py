"""Static rules data and MVP-scope catalog constants, shared by every `chummer5.web.routes` module.

**WP62**: split out of the former `chummer5.web.app` (see `spec/plan/phase-r-architecture-cleanup
.md`'s WP58 audit) -- every `load_*()` call `chummer5.data` makes once per process (Project
Overview's "parsed once at startup" rule), plus the catalog-derived constants more than one
chargen-step route module needs. Also hosts `TEMPLATES_DIR`/`templates` (the shared
`Jinja2Templates` instance) and `STATIC_DIR`, since these too have no step-specific home and every
route module needs `templates` to render its own fragment.
"""

from __future__ import annotations

from pathlib import Path

from fastapi.templating import Jinja2Templates

from chummer5.data.bioware import load_bioware
from chummer5.data.cyberware import load_cyberware
from chummer5.data.cyberware_subsystems import load_cyberware_entries
from chummer5.data.foci import load_foci
from chummer5.data.lifestyle import load_lifestyles
from chummer5.data.mentors import load_mentors
from chummer5.data.metatypes import load_metatypes
from chummer5.data.powers import load_powers
from chummer5.data.priorities import load_priorities
from chummer5.data.qualities import load_qualities
from chummer5.data.skills import Skill, load_skills
from chummer5.data.spells import load_spells
from chummer5.data.traditions import load_traditions
from chummer5.engine.character import Character
from chummer5.engine.lifestyle import MIN_LIFESTYLE_MONTHS
from chummer5.engine.magic import MAGICAL_SKILL_CATEGORIES, mvp_power_catalog
from chummer5.engine.qualities import MENTOR_SPIRIT_QUALITY_NAME, mvp_quality_catalog

WEB_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = WEB_DIR / "templates"
STATIC_DIR = WEB_DIR / "static"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# Static rules data: parsed once per process, not per request (Project Overview's "parsed once at
# startup" rule for `chummer5.data` loaders).
METATYPES = load_metatypes()
PRIORITIES = load_priorities()
SKILLS = load_skills()
QUALITIES = load_qualities()
LIFESTYLES = load_lifestyles()
# WP34 (Phase J's UI): the flat-cost, flat-Essence, Standard-grade cyberware catalog (WP31).
# Still what the picker in `_cyberware.html` *offers* -- WP42 is the WP that widens the UI to
# rating-scaled items and plugin installation.
CYBERWARE = load_cyberware()
# WP41: WP37's full 87-row SR5 catalog, with formulas parsed and Capacity/subsystem structure
# captured. This is what every *engine* call resolves against now
# (`create_cyberware_tree_selection`, `build_character`, `import_chum5`), since
# `Character.cyberware_selection` is a purchase tree.
# CYBERWARE's ids are a subset of these, so a flat pick made from the picker above resolves here
# unchanged.
CYBERWARE_ENTRIES = load_cyberware_entries()
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
# narrower per-tradition/per-magic-type subset -- SR5 doesn't restrict regular skill-point spend by
# magic type or tradition, only the free grant is restricted, and an Adept's MAG > 0 makes these
# skills just as functional (not "permanently crippled") as they are for a Magician. Applies
# identically to both. `_offered_skills`/`_offered_skill_groups` are the character-scoped
# equivalents of `MUNDANE_SKILLS`/`MUNDANE_SKILL_GROUPS` every buy-UI call site now uses instead --
# both return the exact Mundane-only sets unchanged when `character.magic_type is None`.
_MAGICAL_SKILLS = tuple(
    sorted((s for s in SKILLS if s.category in MAGICAL_SKILL_CATEGORIES), key=lambda s: s.name)
)


def offered_skills(character: Character | None) -> tuple[Skill, ...]:
    if character is None or character.magic_type is None:
        return MUNDANE_SKILLS
    return tuple(sorted(MUNDANE_SKILLS + _MAGICAL_SKILLS, key=lambda s: s.name))


def offered_skill_groups(character: Character | None) -> tuple[str, ...]:
    if character is None or character.magic_type is None:
        return MUNDANE_SKILL_GROUPS
    return tuple(
        sorted({s.skill_group for s in offered_skills(character) if s.skill_group is not None})
    )


# WP29: the character sheet's read-only skill list needs every skill (so a Magician's granted
# Magical Active skill shows up there too, see `_character_sheet_context`), sorted the same way
# `MUNDANE_SKILLS` already is.
ALL_SKILLS_SORTED = tuple(sorted(SKILLS, key=lambda s: s.name))
