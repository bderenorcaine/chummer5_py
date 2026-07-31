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
- `NOT_YET_SUPPORTED` -- 1 of 6 (Reflex Recorder): `<bonus><selectskill limittoattribute="BOD,AGI,
  REA,STR"><val>1</val></selectskill></bonus>` -- a *player-selected* skill bonus (any active skill
  linked to one of 4 attributes, chosen at purchase time), not a specifically-named one --
  structurally different from `<specificskill>`'s fixed-name shape, and this engine has no
  "purchase-time skill picker for a bonus" mechanism (the closest precedent, Phase I's Talent
  free-skill grant, resolves a category/xpath *filter* into a caller-supplied list, not a
  single-skill pick with no further engine support). Correctly falls through to
  `NOT_YET_SUPPORTED` rather than being silently mis-shaped as `<specificskill>`.

WP32-style Essence-floor and Improvement application is `chummer5.engine.bioware`'s job -- this
module only classifies, mirroring `chummer5.data.cyberware`'s own loader/engine split. Also mirrors
that module's "keep `NOT_YET_SUPPORTED` items in the loaded catalog" decision: Reflex Recorder's
Essence/nuyen cost is real, correctly-modeled content even though its skill bonus isn't applied --
see `chummer5.data.cyberware`'s own docstring for the full reasoning this reuses unchanged.

**WP79: `unmodeled_effect_note`, and why this module's mirror is empty.** Cyberware and bioware both
carry the field now, populated by hand from the Project Overview's "Unmodeled real effects" table
(WP56's posture: runtime code never reads a `.md` file as data). `_UNMODELED_EFFECT_NOTES` below is
this file's own mirror rather than a share of `chummer5.data.cyberware.UNMODELED_EFFECT_NOTES`,
because the two catalogs load different files with independent name spaces -- and it is **empty**,
which is a fact about the registry, not an oversight: no `bioware.xml` row is in it. Of the 6
offered rows, 5 have their whole printed effect modeled or genuinely have none, and the 6th
(`Reflex Recorder`) is deliberately *not* registry material -- its `<selectskill>` bonus is
computable by this engine and merely unimplemented, which WP77 classified as a live policy
violation for WP80 to fix rather than an accepted gap. Registering it would launder the one into
the other. The field and the dict exist so that a future bioware row that *is* registry material is
a one-line data change here, matching the other two augmentation catalogs.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from chummer5.data.cyberware import BonusSupport

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
_LIMIT_BONUS_TAGS = {
    "mentallimit": "mental_limit",
    "physicallimit": "physical_limit",
    "sociallimit": "social_limit",
}

# WP79: this file's by-name mirror of the Project Overview's "Unmodeled real effects" rows --
# deliberately empty, see the module docstring for why (no bioware row is in that table, and
# `Reflex Recorder` specifically must not be added to it).
_UNMODELED_EFFECT_NOTES: Mapping[str, str] = {}


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
    # WP79: this item's real, unmodeled SR5 effect, from _UNMODELED_EFFECT_NOTES -- None for every
    # SR5 bioware row today, deliberately. See module docstring.
    unmodeled_effect_note: str | None = None


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


def _classify_bonus(
    bonus_elem: ET.Element | None,
) -> tuple[BonusSupport, tuple[BiowareFlatBonus, ...]]:
    """Classify a `<bonus>` node -- mirrors `chummer5.data.cyberware._classify_bonus`'s "absent/
    empty is unconditionally NO_EFFECT, no name-gate needed" rule (see that module's docstring for
    why no equivalent of qualities' "empty bonus but real narrative effect" ambiguity applies here),
    but recognizes `chummer5.data.qualities`'s skill/attribute/limit flat shapes instead of
    cyberware's `<conditionmonitor>` one -- see this module's own docstring for the Enhanced
    Articulation shape that needs both a skill and a limit bonus recognized from the same node.
    """
    if bonus_elem is None or len(bonus_elem) == 0:
        return BonusSupport.NO_EFFECT, ()

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
            return BonusSupport.NOT_YET_SUPPORTED, ()
    return BonusSupport.FLAT_BONUS, tuple(flat_bonuses)


def _parse_bioware(elem: ET.Element, availability: int) -> Bioware:
    bonus_elem = elem.find("bonus")
    support, flat_bonuses = _classify_bonus(bonus_elem)
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
        unmodeled_effect_note=_UNMODELED_EFFECT_NOTES.get(name),
    )


def load_bioware(xml_path: Path = DEFAULT_BIOWARE_PATH) -> tuple[Bioware, ...]:
    """Parse `bioware.xml`, restricted to `source == "SR5"` AND flat cost AND flat Essence AND
    Availability <= 12 (6 of 23 SR5 entries; see module docstring) -- Standard grade only.
    """
    root = ET.parse(xml_path).getroot()
    biowares_elem = root.find("biowares")
    if biowares_elem is None:
        return ()
    result = []
    for b in biowares_elem.findall("bioware"):
        if b.findtext("source") != CORE_RULEBOOK_SOURCE:
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
