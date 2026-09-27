"""Loader for `legacy/Chummer/data/bioware.xml`, restricted to SR5 core-rulebook content, flat cost,
flat Essence, low-Availability, Standard grade only (WP45 -- Phase L, reusing Phase J's Essence
mechanism directly).

Of `bioware.xml`'s 213 entries, 23 carry `source == "SR5"`. Grade is not offered at all (mirrors
`chummer5.data.cyberware`'s own Standard-grade-only scope) -- `<cost>`/`<ess>` are consumed directly
as Standard-grade values. Beyond that, this loader restricts to items whose `<cost>` is a bare
integer literal and whose `<ess>` is a bare (optionally fractional) decimal literal -- the identical
"flat, not a formula" filter `chummer5.data.cyberware`/`chummer5.data.gear` already use. Confirmed
directly against the XML (not assumed from the Implementation Plan's own pre-stated count): 8 of the
23 SR5 entries pass both filters, matching the Plan's own figure. The other 15 carry a
`Rating * N` cost/Essence formula (e.g. Cerebral Booster's `Rating * 31500` cost, `Rating * 0.2`
Essence) -- this loader does not evaluate rules-language expressions, mirroring `chummer5.data
.cyberware`'s identical exclusion.

**A 4th filter beyond cyberware's own two: Availability <= 12.** Per the Project Overview's
2026-07-21 ruling ("any new catalog ... should simply exclude items with Availability > 12"),
applied here from day one since this is new-enough content to build the simplification in rather
than retrofitting it (unlike WP21's gear catalog or WP31's cyberware catalog, neither of which
filters by Availability at all -- see that ruling's own text for why those two are flagged, not
fixed). `<avail>` is a bare integer optionally suffixed with a legality code letter (`F`orbidden/
`R`estricted, e.g. `"18F"`/`"20R"`) for every one of the 8 flat items -- no `Rating`-scaled
Availability formula to resolve, since a `Rating`-scaled item was already excluded by the cost/
Essence filters above. Of the 8 flat SR5 items, 2 exceed 12 (Pain Editor at 18F, Suprathyroid Gland
at 20R) and are excluded, leaving **6** offerable items: Cat's Eyes, Enhanced Articulation, Platelet
Factories, Reflex Recorder, Skin Pocket, Sleep Regulator.

**`BonusSupport` is reused directly from `chummer5.data.cyberware`, not redefined** -- per the
Implementation Plan's own explicit instruction to "confirm ... whether the existing type already
generalizes cleanly" before adding a new one. Checked directly: cyberware's 3-way scheme
(`FLAT_BONUS`/`NO_EFFECT`/`NOT_YET_SUPPORTED`) describes bioware's own `<bonus>` shapes with no
gaps, so a fresh Enum here would just be a duplicate of the same 3 names -- unlike WP31's own
decision to give cyberware a fresh Enum rather than reuse `chummer5.data.qualities`' one (there, the
two modules' real membership differed in a documented way; here it doesn't).

Every one of the 6 flat items' raw `<bonus>` node was read directly (not shape-matched by
assumption):

- `NO_EFFECT` -- 4 of 6 (Cat's Eyes, Platelet Factories, Skin Pocket, Sleep Regulator): no `<bonus>`
  element at all. Each has a real, narrative-only SR5 effect this engine's scope doesn't model
  (low-light vision, faster healing, a hidden storage pocket, reduced sleep need respectively) --
  verified moot the same way `chummer5.data.cyberware` verified its own bonus-less items: a `grep`
  of the legacy C# for by-name special-casing of any of the 4 turned up nothing, confirming there is
  no hidden hardcoded mechanical hook an empty `<bonus>` might be masking.
- `FLAT_BONUS` -- 1 of 6 (Enhanced Articulation): `<bonus><physicallimit>1</physicallimit>
  <specificskill><name>Escape Artist</name><bonus>1</bonus></specificskill></bonus>` -- two
  *different* flat-bonus shapes in one node, both already-recognized ones (mirrors `chummer5.data
  .qualities`'s own `<physicallimit>`/`<specificskill>` classification exactly, reused here rather
  than reinvented, since the raw shapes are identical to what qualities' `<bonus>` grammar already
  produces). `BiowareFlatBonus` therefore needs a `target_name` field (unlike `chummer5.data
  .cyberware.CyberwareFlatBonus`, which never needed one -- its only flat shape, the Cyberlimb
  condition-monitor bonus, has nothing to name) -- mirrors `chummer5.data.qualities.FlatBonus`'s
  shape instead.
- `SELECT_SKILL` (WP80; `NOT_YET_SUPPORTED` from WP45 until then) -- 1 of 6 (Reflex Recorder):
  `<bonus><selectskill limittoattribute="BOD,AGI,REA,STR"><val>1</val></selectskill></bonus>` -- a
  *player-selected* skill bonus (any active skill linked to one of 4 attributes, chosen at purchase
  time), not a specifically-named one -- structurally different from `<specificskill>`'s fixed-name
  shape. See the WP80 section below.

**WP80: `<selectskill>` is a purchase-time player choice, so it is its own `BonusSupport` value.**
`SELECT_SKILL` (added to the shared `chummer5.data.cyberware.BonusSupport`) mirrors
`chummer5.data.qualities.BonusSupport.SELECT_TEXT` exactly: the catalog records *that* a pick is
required and what it is allowed to be, never the pick itself -- which belongs to the purchase
(`chummer5.engine.bioware.BiowarePurchase.chosen_skill`), persisted per purchase rather than per
catalog row, because SR5 explicitly contemplates buying several ("Multiple recorders may be taken
for multiple skills, but you can't implant two reflex recorders for the same skill", p. 460).

Classified by *shape*, not by name (unlike `qualities`' `_VERIFIED_SELECT_TEXT_NAMES` gate): a
`<selectskill>` carrying a `limittoattribute` filter and exactly one `<val>` child has one
unambiguous reading, whereas `<selecttext>`'s meaning genuinely varies per quality. A
`<selectskill>` *without* `limittoattribute`, or with any other child, still falls through to
`NOT_YET_SUPPORTED` -- an unfiltered or otherwise-shaped pick is a different mechanic, not this one.
Verified by enumeration: `Reflex Recorder` is the only SR5-sourced row in either augmentation
catalog whose `<bonus>` contains a `<selectskill>` at all (no SR5 `cyberware.xml` row does).

The printed effect is a **Rating** bonus, not a dice-pool one -- p. 460: "The reflex recorder adds
1 to the Rating of a specific skill linked to a Physical attribute." So `chummer5.engine.bioware`
routes it through `ImprovementType.SKILL`, this engine's established skill-rating route, rather than
needing the pool-modifier primitive WP78's worklog flagged as a possibility. (The `.chum5` corpus'
own copy of this bonus carries a `<!-- Hero Lab says this is not RAW <applytorating>True -->`
comment; the rulebook sentence above settles it in favour of a rating bonus.) See
`spec/decisions-log.md`, 2026-07-31, for the one consequence that leaves open: `skill_rating`
clamps to `MAX_SKILL_RATING_CREATE`, so this bonus does nothing on a skill already at 6.

WP32-style Essence-floor and Improvement application is `chummer5.engine.bioware`'s job -- this
module only classifies, mirroring `chummer5.data.cyberware`'s own loader/engine split. Also mirrors
that module's "keep `NOT_YET_SUPPORTED` items in the loaded catalog" decision: Reflex Recorder's
Essence/nuyen cost is real, correctly-modeled content even though its skill bonus isn't applied --
see `chummer5.data.cyberware`'s own docstring for the full reasoning this reuses unchanged.

**Not modeled, and deliberately not enforced: "Reflex recorder bioware is incompatible with
skillwires cyberware" (p. 460).** Cross-catalog incompatibility is a validation mechanism this
engine has never had (nothing checks a bioware purchase against a cyberware one beyond the shared
Essence/nuyen pools), and the rule has no computable consequence here: `Skillwires` grants nothing
at all in this engine (it is one of WP77's registered "Unmodeled real effects" rows), so allowing
both changes no derived number. `bioware.xml` carries no `<forbidden>` node for `Reflex Recorder`
either, so the legacy engine does not enforce it either. Recorded rather than silently skipped.

**WP79: `unmodeled_effect_note`, and why this module's mirror is empty.** Cyberware and bioware both
carry the field now, populated by hand from the Project Overview's "Unmodeled real effects" table
(WP56's posture: runtime code never reads a `.md` file as data). `_UNMODELED_EFFECT_NOTES` below is
this file's own mirror rather than a share of `chummer5.data.cyberware.UNMODELED_EFFECT_NOTES`,
because the two catalogs load different files with independent name spaces -- and it is **empty**,
which is a fact about the registry, not an oversight: no `bioware.xml` row is in it. Of the 6
offered rows, 5 have their whole printed effect modeled or genuinely have none, and the 6th
(`Reflex Recorder`) is deliberately *not* registry material -- its `<selectskill>` bonus is
computable by this engine, which WP77 classified as a live policy violation for WP80 to fix rather
than an accepted gap (and WP80 did: it is modeled now). Registering it would have laundered the one
into the other. The field and the dict exist so that a future bioware row that *is* registry
material is a one-line data change here, matching the other two augmentation catalogs.

**WP128: the 15 rated rows are offered.** Every one prices both cost and Essence as `Rating * N`
(pp. 459-461 print them the same way), so `_parse_rated_bioware` stores the two
`chummer5.data.cyberware_formula` formulas and resolves them per purchase (`cost_at`, `essence_at`).
Its `<avail>` is kept raw for WP126's cap (`availability_at`). Their `<bonus>` nodes go through
cyberware's shared `classify_bonus`, not this module's flat classifier: they are Rating-valued and
carry the same `unique`/`precedence` dedup groups (Muscle Toner's `unique="muscle"`, the Synaptic
Booster's `precedence="0"`, Orthoskin's `group="0"`). The in-play halves -- toxin and disease
resistance, healing, unarmed damage, the pheromones' smell-range dice, the adrenaline pump -- are
registry rows (`_UNMODELED_EFFECT_NOTES`), and their `<bonus>` children are stripped as
`REGISTERED_UNMODELED_BONUS_TAGS`. `incompatible_names` joins each row's `<forbidden>` with the
book's own "cannot be combined" rules (`_INCOMPATIBLE_NAMES`). Pain Editor (18F) and Suprathyroid
Gland (20R) stay out: flat, and over Availability 12, which WP126's ruling leaves alone.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from chummer5.data.cyberware import (
    CONDITIONAL_SKILL_GROUP,
    BonusSupport,
    CyberwareFlatBonus,
    classify_bonus,
)
from chummer5.data.cyberware_formula import (
    CyberwareFormula,
    FormulaKind,
    parse_cyberware_formula,
)
from chummer5.data.gear import availability_at_rating

# legacy/Chummer/data/bioware.xml, resolved relative to this file (not cwd).
DEFAULT_BIOWARE_PATH = (
    Path(__file__).resolve().parents[3] / "legacy" / "Chummer" / "data" / "bioware.xml"
)

# MVP content scope: only entries carrying this <source> tag are loaded. See "MVP content scope" in
# Implementation Plan.md.
CORE_RULEBOOK_SOURCE = "SR5"

# Mirrors chummer5.data.cyberware/gear's identical flat-cost/flat-Essence filters.
_FLAT_INT_RE = re.compile(r"-?\d+")
_FLAT_DECIMAL_RE = re.compile(r"-?\d+(\.\d+)?")

# A bare leading integer, optionally followed by a legality-code letter (F/R/...) and/or other
# trailing text -- e.g. "18F", "20R", "4". Every one of the 8 flat SR5 bioware items' <avail> is
# this shape (no Rating-scaled Availability formula among them -- see module docstring).
_AVAIL_RE = re.compile(r"-?\d+")

# Project Overview's 2026-07-21 ruling: exclude Availability > 12 from any new catalog rather than
# tracking an Availability budget as its own resource.
MAX_AVAILABILITY = 12

# The two <bonus> child shapes MVP treats as "flat", reused verbatim from chummer5.data.qualities'
# identical grammar (the raw XML shapes are the same grammar, just appearing in a different data
# file) -- see module docstring's Enhanced Articulation citation.
_FLAT_SKILL_FIELDS = frozenset({"name", "bonus"})
_FLAT_ATTRIBUTE_FIELDS = frozenset({"name", "val"})
# WP80: the one shape a <selectskill> node is accepted in -- a single <val> child, plus a
# limittoattribute filter as an attribute. Anything else falls through to NOT_YET_SUPPORTED.
_SELECT_SKILL_FIELDS = frozenset({"val"})
_LIMIT_TO_ATTRIBUTE = "limittoattribute"
_LIMIT_BONUS_TAGS = {
    "mentallimit": "mental_limit",
    "physicallimit": "physical_limit",
    "sociallimit": "social_limit",
}

# WP79: this file's by-name mirror of the Project Overview's "Unmodeled real effects" rows. Empty
# until WP128 offered the rated rows (and `Reflex Recorder` must still never be in it). Each entry
# condenses the printed effect (pp. 459-461) this engine has no test or state for.
_UNMODELED_EFFECT_NOTES: Mapping[str, str] = {
    "Adrenaline Pump": (
        "When triggered (a Free Action, or a failed Composure Test): ignore injury modifiers and "
        "Stun unconsciousness, and add its Rating to STR/AGI/REA/WIL for Rating x 1D6 Combat "
        "Turns, then take that many boxes of Stun; 1 hour to recharge (p. 459)."
    ),
    "Bone Density Augmentation": (
        "Unarmed attacks deal Physical damage, (STR + Rating - 1)P (p. 460 table). Its Body dice "
        "for damage resistance are computed."
    ),
    "Pathogenic Defense": "Adds its Rating to Disease Resistance Tests (p. 459).",
    "Symbiotes": (
        "Adds its Rating to healing tests (Physical and Stun); needs (Rating x 200)¥ a month of "
        "special food unless the Lifestyle is High or better (p. 460)."
    ),
    "Tailored Pheromones": (
        "Adds its Rating to Acting and Influence skill-group tests, only against someone within "
        "conversation range who can smell you (p. 460). Its Social limit bonus is computed."
    ),
    "Toxin Extractor": "Adds its Rating to all Toxin Resistance Tests (p. 460).",
    "Tracheal Filter": (
        "Adds its Rating to Toxin Resistance Tests against inhalation vectors (p. 460)."
    ),
}

# WP128: the `<bonus>` children the registry rows above cover, stripped before classification so
# the computed siblings can apply (the same device as `chummer5.data.cyberware
# .REGISTERED_UNMODELED_BONUS_TAGS`). A test pins that each row carrying one has a note.
REGISTERED_UNMODELED_BONUS_TAGS = frozenset(
    {
        "unarmeddv",
        "unarmeddvphysical",
        "pathogencontactresist",
        "pathogeningestionresist",
        "pathogeninhalationresist",
        "pathogeninjectionresist",
        "toxincontactresist",
        "toxiningestionresist",
        "toxininhalationresist",
        "toxininjectionresist",
        "stuncmrecovery",
        "physicalcmrecovery",
        CONDITIONAL_SKILL_GROUP,
    }
)

# WP128: what the book says each rated row can't be combined with, beyond its own `<forbidden>`
# (which covers Bone Density vs. Bone Lacing, Orthoskin vs. Dermal Plating, and Damage
# Compensators vs. High Pain Tolerance). p. 459: Muscle Augmentation and Muscle Toner are each
# "incompatible with augmentations that increase" their attribute, "including the muscle
# replacements cyberware" -- not with each other. p. 461: the Synaptic Booster "cannot be combined
# with any other form of Reaction or Initiative enhancement".
_INCOMPATIBLE_NAMES: Mapping[str, tuple[str, ...]] = {
    "Muscle Augmentation": ("Muscle Replacement",),
    "Muscle Toner": ("Muscle Replacement",),
    "Synaptic Booster": ("Wired Reflexes", "Reaction Enhancers", "Improved Reflexes"),
}


@dataclass(frozen=True)
class BiowareFlatBonus:
    """One unconditional, flat point bonus to a skill, attribute, or Inherent Limit -- mirrors
    `chummer5.data.qualities.FlatBonus`'s shape (including `target_name`, empty for the 3 limit
    kinds) rather than `chummer5.data.cyberware.CyberwareFlatBonus`'s narrower one -- see module
    docstring for why bioware's own flat shapes need a name field cyberware's never did.
    """

    target_kind: str  # "skill", "attribute", "mental_limit", "physical_limit", or "social_limit"
    target_name: str
    value: int


@dataclass(frozen=True)
class BiowareSelectSkillBonus:
    """A flat bonus to *one active skill the player picks at purchase time* (WP80).

    `value` is the bonus's magnitude (`<val>`, always 1 in the SR5 catalog); `limit_to_attributes`
    is the `limittoattribute` filter's attribute codes (`("BOD", "AGI", "REA", "STR")` -- SR5's four
    Physical attributes), which is the *only* restriction on what the player may pick. The pick
    itself is never stored here: it belongs to the purchase, not the catalog row -- see the module
    docstring, and `chummer5.engine.bioware.BiowarePurchase.chosen_skill` for where it lives.
    """

    value: int
    limit_to_attributes: tuple[str, ...]


@dataclass(frozen=True)
class Bioware:
    id: str
    name: str
    category: str
    cost: int
    essence_cost: Decimal
    availability: int
    source: str
    page: int
    bonus_support: BonusSupport
    flat_bonuses: tuple[BiowareFlatBonus, ...]  # populated only when bonus_support is FLAT_BONUS
    raw_bonus: str | None  # serialized <bonus> element, kept for future parser work; None if absent
    # WP80: populated only when bonus_support is SELECT_SKILL -- the purchase-time skill pick this
    # item requires, and the filter that pick must satisfy. None for every other row.
    select_skill_bonus: BiowareSelectSkillBonus | None = None
    # WP79: this item's real, unmodeled SR5 effect, from _UNMODELED_EFFECT_NOTES.
    unmodeled_effect_note: str | None = None
    # WP128: a rated row. `cost`/`essence_cost`/`availability` above then hold its rating-1
    # values; read `cost_at`/`essence_at`/`availability_at` for a purchase. `rated_bonuses` are its
    # Rating-valued bonuses (the cyberware shape, resolved at the purchased rating).
    max_rating: int | None = None
    cost_formula: CyberwareFormula | None = None
    essence_formula: CyberwareFormula | None = None
    raw_availability: str | None = None
    rated_bonuses: tuple[CyberwareFlatBonus, ...] = ()
    # WP128: cyberware, quality and power names this row can't be combined with.
    incompatible_names: tuple[str, ...] = ()

    @property
    def is_rated(self) -> bool:
        return self.max_rating is not None

    def cost_at(self, rating: int) -> int:
        if self.cost_formula is None:
            return self.cost
        return int(self.cost_formula.resolve(rating=rating))

    def essence_at(self, rating: int) -> Decimal:
        if self.essence_formula is None:
            return self.essence_cost
        return self.essence_formula.resolve(rating=rating)

    def availability_at(self, rating: int) -> int:
        if self.raw_availability is None:
            return self.availability
        value = availability_at_rating(self.raw_availability, rating)
        return self.availability if value is None else value


def _is_flat_cost(text: str | None) -> bool:
    return text is not None and _FLAT_INT_RE.fullmatch(text) is not None


def _is_flat_essence(text: str | None) -> bool:
    return text is not None and _FLAT_DECIMAL_RE.fullmatch(text) is not None


def _parse_availability(text: str | None) -> int | None:
    if text is None:
        return None
    match = _AVAIL_RE.match(text)
    return int(match.group()) if match is not None else None


def _is_flat_skill_bonus(elem: ET.Element) -> bool:
    return {child.tag for child in elem} == _FLAT_SKILL_FIELDS


def _is_flat_attribute_bonus(elem: ET.Element) -> bool:
    return {child.tag for child in elem} == _FLAT_ATTRIBUTE_FIELDS


def _select_skill_bonus(elem: ET.Element) -> BiowareSelectSkillBonus | None:
    """WP80: `<selectskill limittoattribute="BOD,AGI,REA,STR"><val>1</val></selectskill>` ->
    `BiowareSelectSkillBonus`, or `None` for any other `<selectskill>` shape (an unfiltered pick, or
    one carrying children this module doesn't recognize) -- see the module docstring for why the
    filter is required rather than defaulted to "any skill".
    """
    codes = tuple(
        code.strip() for code in elem.get(_LIMIT_TO_ATTRIBUTE, "").split(",") if code.strip()
    )
    if not codes or {child.tag for child in elem} != _SELECT_SKILL_FIELDS:
        return None
    return BiowareSelectSkillBonus(value=int(elem.findtext("val", "0")), limit_to_attributes=codes)


def _classify_bonus(
    bonus_elem: ET.Element | None,
) -> tuple[BonusSupport, tuple[BiowareFlatBonus, ...], BiowareSelectSkillBonus | None]:
    """Classify a `<bonus>` node -- mirrors `chummer5.data.cyberware._classify_bonus`'s "absent/
    empty is unconditionally NO_EFFECT, no name-gate needed" rule (see that module's docstring for
    why no equivalent of qualities' "empty bonus but real narrative effect" ambiguity applies here),
    but recognizes `chummer5.data.qualities`'s skill/attribute/limit flat shapes instead of
    cyberware's `<conditionmonitor>` one -- see this module's own docstring for the Enhanced
    Articulation shape that needs both a skill and a limit bonus recognized from the same node.

    **WP80**: a lone `<selectskill>` child classifies `SELECT_SKILL` and returns the third element
    of this tuple instead of any flat bonus. It is deliberately not mixable with the flat shapes --
    no SR5 row combines them, and "half a node is a player pick, half isn't" is exactly the
    partial classification `classify_bonus`'s all-or-nothing rule exists to prevent.
    """
    if bonus_elem is None or len(bonus_elem) == 0:
        return BonusSupport.NO_EFFECT, (), None

    if len(bonus_elem) == 1 and bonus_elem[0].tag == "selectskill":
        select_skill = _select_skill_bonus(bonus_elem[0])
        if select_skill is None:
            return BonusSupport.NOT_YET_SUPPORTED, (), None
        return BonusSupport.SELECT_SKILL, (), select_skill

    flat_bonuses = []
    for child in bonus_elem:
        if child.tag == "specificskill" and _is_flat_skill_bonus(child):
            flat_bonuses.append(
                BiowareFlatBonus(
                    target_kind="skill",
                    target_name=child.findtext("name", ""),
                    value=int(child.findtext("bonus", "0")),
                )
            )
        elif child.tag == "specificattribute" and _is_flat_attribute_bonus(child):
            flat_bonuses.append(
                BiowareFlatBonus(
                    target_kind="attribute",
                    target_name=child.findtext("name", ""),
                    value=int(child.findtext("val", "0")),
                )
            )
        elif child.tag in _LIMIT_BONUS_TAGS and len(child) == 0 and child.text is not None:
            flat_bonuses.append(
                BiowareFlatBonus(
                    target_kind=_LIMIT_BONUS_TAGS[child.tag],
                    target_name="",
                    value=int(child.text),
                )
            )
        else:
            return BonusSupport.NOT_YET_SUPPORTED, (), None
    return BonusSupport.FLAT_BONUS, tuple(flat_bonuses), None


def _parse_bioware(elem: ET.Element, availability: int) -> Bioware:
    bonus_elem = elem.find("bonus")
    support, flat_bonuses, select_skill_bonus = _classify_bonus(bonus_elem)
    raw_bonus = (
        ET.tostring(bonus_elem, encoding="unicode").strip() if bonus_elem is not None else None
    )
    name = elem.findtext("name", "")
    return Bioware(
        id=elem.findtext("id", ""),
        name=name,
        category=elem.findtext("category", ""),
        cost=int(elem.findtext("cost", "0")),
        essence_cost=Decimal(elem.findtext("ess", "0")),
        availability=availability,
        source=elem.findtext("source", ""),
        page=int(elem.findtext("page", "0")),
        bonus_support=support,
        flat_bonuses=flat_bonuses,
        raw_bonus=raw_bonus,
        select_skill_bonus=select_skill_bonus,
        unmodeled_effect_note=_UNMODELED_EFFECT_NOTES.get(name),
    )


def _rating_times(text: str | None) -> CyberwareFormula | None:
    formula = parse_cyberware_formula(text or "")
    return formula if formula is not None and formula.kind is FormulaKind.RATING_TIMES else None


def _forbidden_names(elem: ET.Element) -> tuple[str, ...]:
    return tuple(
        node.text.strip()
        for node in elem.findall("forbidden/oneof/*")
        if node.tag in ("cyberware", "bioware", "quality") and node.text
    )


def _parse_rated_bioware(elem: ET.Element) -> Bioware | None:
    """WP128: a `<rating>` row whose cost and Essence are both `Rating * N`, or `None`. Every one of
    the 15 SR5 rated rows is that shape (pp. 459-461 print them the same way)."""
    cost = _rating_times(elem.findtext("cost"))
    essence = _rating_times(elem.findtext("ess"))
    raw_availability = elem.findtext("avail")
    max_rating = elem.findtext("rating")
    if cost is None or essence is None or raw_availability is None or max_rating is None:
        return None
    availability = availability_at_rating(raw_availability, 1)
    if availability is None or availability > MAX_AVAILABILITY:
        return None
    bonus_elem = elem.find("bonus")
    support, rated_bonuses, conditional = classify_bonus(
        bonus_elem, registered_tags=REGISTERED_UNMODELED_BONUS_TAGS
    )
    if conditional:
        return None  # no rated SR5 row has one; refuse rather than drop it
    name = elem.findtext("name", "")
    return Bioware(
        id=elem.findtext("id", ""),
        name=name,
        category=elem.findtext("category", ""),
        cost=int(cost.resolve(rating=1)),
        essence_cost=essence.resolve(rating=1),
        availability=availability,
        source=elem.findtext("source", ""),
        page=int(elem.findtext("page", "0")),
        bonus_support=support,
        flat_bonuses=(),
        raw_bonus=(
            ET.tostring(bonus_elem, encoding="unicode").strip() if bonus_elem is not None else None
        ),
        unmodeled_effect_note=_UNMODELED_EFFECT_NOTES.get(name),
        max_rating=int(max_rating),
        cost_formula=cost,
        essence_formula=essence,
        raw_availability=raw_availability,
        rated_bonuses=rated_bonuses,
        incompatible_names=_forbidden_names(elem) + _INCOMPATIBLE_NAMES.get(name, ()),
    )


def load_bioware(xml_path: Path = DEFAULT_BIOWARE_PATH) -> tuple[Bioware, ...]:
    """Parse `bioware.xml`, restricted to `source == "SR5"` AND flat cost AND flat Essence AND
    Availability <= 12 (6 of 23 SR5 entries; see module docstring) -- Standard grade only.

    **WP128** adds the 15 rated SR5 rows (`_parse_rated_bioware`), after the flat ones: all 21
    offerable rows. (Pain Editor and Suprathyroid Gland stay out: flat, and over Availability 12.)
    """
    root = ET.parse(xml_path).getroot()
    biowares_elem = root.find("biowares")
    if biowares_elem is None:
        return ()
    result = []
    for b in biowares_elem.findall("bioware"):
        if b.findtext("source") != CORE_RULEBOOK_SOURCE:
            continue
        if b.find("rating") is not None:
            rated = _parse_rated_bioware(b)
            if rated is not None:
                result.append(rated)
            continue
        if not (_is_flat_cost(b.findtext("cost")) and _is_flat_essence(b.findtext("ess"))):
            continue
        availability = _parse_availability(b.findtext("avail"))
        if availability is None or availability > MAX_AVAILABILITY:
            continue
        result.append(_parse_bioware(b, availability))
    return tuple(result)


def count_by_support(bioware: Iterable[Bioware]) -> Mapping[BonusSupport, int]:
    """Count bioware items per `BonusSupport` value, so the supported/unsupported split is
    visible."""
    counts = Counter(b.bonus_support for b in bioware)
    return {support: counts[support] for support in BonusSupport}
