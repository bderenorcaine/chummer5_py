"""Loader for `legacy/Chummer/data/cyberware.xml`, restricted to SR5 core-rulebook content, flat
cost, flat Essence, Standard grade only (WP31 -- Phase J's first content WP, following WP30's
Essence-tracking prerequisite).

Of `cyberware.xml`'s 362 entries, 87 carry `source == "SR5"`. Grade is not offered at all this
phase (Phase J intro) -- `<cost>`/`<ess>` are consumed directly as Standard-grade values, with no
`<grades>` multiplier applied. Beyond that, this loader further restricts to items whose `<cost>`
is a bare integer literal and whose `<ess>` is a bare (optionally fractional) decimal literal --
mirroring `chummer5.data.gear`'s identical "flat, not a formula" filter for WP21's gear catalog.
Confirmed directly against the XML (not assumed from the Implementation Plan's own pre-stated
count): 60 of the 87 SR5 entries pass both filters. The other 27 carry a `Rating * N`/
`FixedValues(...)`/compound-arithmetic formula in `<cost>` and/or `<ess>` (e.g. Wired Reflexes'
`FixedValues(2,3,5)`
Essence cost) -- the legacy engine resolves those at read time against a purchased rating; this
loader does not evaluate rules-language expressions, mirroring WP21's own gear-formula exclusion.
None of the 60 flat items carry a `<rating>` tag at all (checked directly), confirming they are
genuinely single-purchase items with no rating dimension to resolve in the first place -- simpler
than WP27's powers, which needed a rating multiplier despite being flat-PP-cost.

`<bonus>` nodes are classified with a 3-way `BonusSupport` scheme mirroring
`chummer5.data.qualities.BonusSupport` (not `chummer5.data.powers.BonusSupport`, which deliberately
has no `NO_EFFECT` member) -- a genuinely new `BonusSupport` Enum per module, not an import shared
across `qualities`/`powers`/`cyberware`, since each module's own docstring already documents why its
membership differs (WP27's docstring explains why powers has no `NO_EFFECT`; this one explains why
cyberware's `NO_EFFECT` needs no name-gate, unlike qualities'). Verified directly against every one
of the 60 flat items' raw `<bonus>` node:

- `NO_EFFECT` -- an empty/absent `<bonus>` (42 of 60: pure Essence/nuyen cost, no other effect at
  all). Unlike `chummer5.data.qualities.BonusSupport.NO_EFFECT`, no name-gate is needed here: an
  empty `<bonus>` on a piece of cyberware already means literally nothing beyond its Essence/nuyen
  cost -- there's no equivalent of a quality's "empty `<bonus>` but a real in-play narrative effect"
  ambiguity WP22 had to individually verify away, because cyberware's own narrative/mechanical
  effects (if any) always show up as a real `<bonus>` child.
- `FLAT_BONUS` -- 8 of 60, all Cyberlimb-category items (Obvious/Synthetic Full Arm, Torso, Skull;
  Obvious/Synthetic Full Leg) whose `<bonus>` reduces, after stripping `<disablequality>` (see next
  bullet), to exactly one `<conditionmonitor><physical>1</physical></conditionmonitor>` child --
  maps directly onto the existing `ImprovementType.PHYSICAL_CM`, the same type WP10 already wired
  into `chummer5.engine.derived.physical_condition_monitor`. Every one of these 8 carries the
  identical value (`1`), confirmed directly rather than assumed.
- **A verified-inert bonus child, `<disablequality>`, is stripped before classification rather than
  disqualifying the item to `NOT_YET_SUPPORTED`.** 6 of the 60 flat items (the same 8 Cyberlimb
  FLAT_BONUS items above, minus the 2 that carry *only* `<conditionmonitor>`, plus 4 more --
  Obvious/Synthetic Foot and Lower Leg -- whose `<bonus>` is *only* `<disablequality>Celerity
  </disablequality>`, no `<conditionmonitor>` at all) name-disable the Celerity quality (SR5's
  running-speed-boost metagenic quality) while that limb is installed. Verified moot for this
  engine's actual offered scope, not assumed: `Celerity` is `source == "RF"` (not `SR5` -- excluded
  from `mvp_quality_catalog` on source grounds alone) and additionally gated behind a `<required>`
  of Changeling-SURGE qualities in the raw data, so it is categorically unreachable by any character
  this engine can build regardless of this loader's own scope. Concretely: after stripping
  `<disablequality>` children, the 2 Full-Leg items reduce to a bare `<conditionmonitor>` (still
  `FLAT_BONUS`) and the 4 Foot/Lower-Leg items reduce to nothing at all (`NO_EFFECT`, the same
  bucket as a genuinely empty `<bonus>`) -- 8 `FLAT_BONUS` + 4 of these = the 12 Cyberlimb items
  that carry *any* `<bonus>` at all, out of 16 total flat Cyberlimb entries.
- `CONDITIONAL_BONUS` (WP40 -- Phase K) -- a `<limitmodifier>` whose `<condition>` is one of the
  four named conditions `chummer5.engine.improvements.ImprovementCondition` compiles (see below).
  Exactly 1 of the 60 flat items: **Spatial Recognizer**, which WP31 classified `NOT_YET_SUPPORTED`
  purely because nothing could express "only during this kind of test" yet. WP39 built that
  primitive, so this is now real, modeled content rather than a documented gap. The other three
  conditional items (Vision Enhancement, Audio Enhancement, Hydraulic Jacks) are rating-scaled and
  therefore outside this loader's flat-only scope entirely -- they reach the engine through
  `chummer5.data.cyberware_subsystems`, which shares `classify_bonus` verbatim, so this one
  classifier covers all four.
- `NOT_YET_SUPPORTED` -- the remaining 5: Smartlink (`<smartlink>2</smartlink>` -- no smartlink/
  called-shot mechanic modeled), Damper (`<sonicresist>2</sonicresist>` -- no sonic-attack
  resistance modeled), and the 3 Bone Lacing variants (`<armor>`/`<damageresistance>`/
  `<unarmeddv>`/`<unarmeddvphysical>` -- an armor/unarmed-combat bundle, no combat system in this
  engine's scope). Each individually confirmed to have a real, non-Essence/non-nuyen mechanical
  effect, not shape-matched by accident.

**The four supported conditions are a whitelist of confirmed real `<condition>` strings, not a
condition language** -- mirroring this module's own "classify known, named shapes" posture for
`<bonus>` generally, and WP39's identical decision one layer up (`ImprovementCondition` is an Enum
with one member per confirmed shape). `_SUPPORTED_BONUS_CONDITIONS` below is the complete set of
`<condition>` values appearing anywhere in the SR5 cyberware rows -- verified by enumeration, so
"whitelist" costs no coverage today; an unrecognized one falls through to `NOT_YET_SUPPORTED`
exactly as an unrecognized `<bonus>` child already does. The condition key is carried through as
its **verbatim legacy string**, not as an engine enum: this module is the data layer and does not
import from `chummer5.engine`, the same split `CyberwareFlatBonus.target_kind`'s string already
uses (`chummer5.engine.cyberware` owns both string -> enum maps).

WP32 is what actually turns `FLAT_BONUS` items into real `Improvement` records (mirroring
`chummer5.engine.qualities.apply_quality_improvements`'s shape) -- this module only classifies.
`NOT_YET_SUPPORTED` items are still loaded (unlike qualities'/powers' catalogs, which exclude them
from what a player can pick): a piece of cyberware's fundamental content *is* its Essence/nuyen
cost, with `<bonus>` a secondary, sometimes-absent effect on top -- so WP32/WP34 remain free to
offer Bone Lacing (Titanium) for purchase (real fixture data confirms multiple curated mundane
characters own it) while simply not applying its unmodeled armor/damage-resistance bonus, the same
"purchase is real, secondary effect is dropped and documented" posture `chummer5.data.gear` already
established for gear generally (no engine-side bonus modeling for any gear item at all). This is a
deliberate
difference from `chummer5.data.qualities`'s "never partially apply, so exclude entirely" rule --
recorded here because it is a real, considered choice, not an oversight: a quality's entire content
*is* its bonus (nothing to buy otherwise), while cyberware's Essence/nuyen cost stands on its own as
real, correctly-modeled content even when its bonus doesn't.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from pathlib import Path

# legacy/Chummer/data/cyberware.xml, resolved relative to this file (not cwd).
DEFAULT_CYBERWARE_PATH = (
    Path(__file__).resolve().parents[3] / "legacy" / "Chummer" / "data" / "cyberware.xml"
)

# MVP content scope: only entries carrying this <source> tag are loaded. See "MVP content scope" in
# Implementation Plan.md.
CORE_RULEBOOK_SOURCE = "SR5"

# A bare (optionally negative) integer literal, e.g. "1000" -- not "Rating * 1000" or
# "FixedValues(...)". Mirrors chummer5.data.gear's identical flat-cost filter.
_FLAT_INT_RE = re.compile(r"-?\d+")
# A bare (optionally negative, optionally fractional) decimal literal, e.g. "0.2" or "1.5" -- not
# "Rating * 0.3" or "FixedValues(2,3,5)". Essence costs, unlike cost, are routinely fractional.
_FLAT_DECIMAL_RE = re.compile(r"-?\d+(\.\d+)?")

# The one <bonus> child tag verified moot for this engine's actual offered scope -- see module
# docstring's "verified-inert bonus child" paragraph. Stripped before classification rather than
# treated as a real, unmodeled effect.
_VERIFIED_INERT_BONUS_TAGS = frozenset({"disablequality"})

# <limitmodifier><limit>X</limit> -> CyberwareConditionalBonus.target_kind. Only Mental and
# Physical occur in the SR5 cyberware rows (verified by enumeration); a `Social` one would fall
# through to NOT_YET_SUPPORTED rather than being mapped on the assumption it works the same way.
_LIMIT_TARGET_KINDS = {"Mental": "mental_limit", "Physical": "physical_limit"}

# <limitmodifier><value>Rating</value>: the bonus is the purchased Rating, not a literal. The only
# non-literal value shape in the SR5 rows.
_RATING_VALUE = "Rating"

# Every <condition> string appearing in the SR5 cyberware rows, verified by enumeration (WP39's
# learnings entry has the item/limit/condition/English-text table). A whitelist, not a parser --
# see module docstring.
_SUPPORTED_BONUS_CONDITIONS = frozenset(
    {
        "LimitCondition_SkillsActivePerceptionVisual",  # Vision Enhancement
        "LimitCondition_SkillsActivePerceptionHearing",  # Audio Enhancement
        "LimitCondition_SkillsActivePerceptionSpatialRecognizer",  # Spatial Recognizer
        "LimitCondition_CyberwareHydraulicJacks",  # Hydraulic Jacks
    }
)


class BonusSupport(Enum):
    """Whether/how a cyberware item's `<bonus>` node was parsed. See module docstring for the 4
    values -- WP31's 3-way scheme mirroring `chummer5.data.qualities.BonusSupport` (not
    `chummer5.data.powers.BonusSupport`'s 2-way one), plus WP40's `CONDITIONAL_BONUS`, which no
    other catalog module has because no other catalog has a bonus that applies only during a
    specific kind of test.
    """

    FLAT_BONUS = "flat_bonus"
    CONDITIONAL_BONUS = "conditional_bonus"
    NO_EFFECT = "no_effect"
    NOT_YET_SUPPORTED = "not_yet_supported"


@dataclass(frozen=True)
class CyberwareFlatBonus:
    """One unconditional, flat point bonus produced by a cyberware item.

    `target_kind` is only ever `"physical_cm"` so far (the Cyberlimb condition-monitor bonus) --
    see module docstring. `value` is the flat point value (always `1` among today's real entries,
    but not hardcoded as such, mirroring `chummer5.data.qualities.FlatBonus`'s own shape).
    """

    target_kind: str
    value: int


@dataclass(frozen=True)
class CyberwareConditionalBonus:
    """One point bonus that applies only during a specific kind of test (WP40).

    `target_kind` is `"mental_limit"` or `"physical_limit"` -- the `<limitmodifier><limit>` value,
    mapped to an `ImprovementType` by `chummer5.engine.cyberware`, the same way
    `CyberwareFlatBonus.target_kind` already is.

    `value` is `None` when the bonus is the item's own purchased Rating
    (`<value>Rating</value>` -- Vision/Audio Enhancement, Hydraulic Jacks) rather than a literal
    (`<value>2</value>` -- Spatial Recognizer). Use `resolve_value(rating)` rather than reading the
    field directly; a `None` here is "ask the purchase," not "no bonus."

    `condition` is the verbatim legacy `<condition>` key (e.g.
    `"LimitCondition_SkillsActivePerceptionVisual"`), which `chummer5.engine.cyberware` maps to an
    `ImprovementCondition` -- see the module docstring for why the data layer keeps the string.
    """

    target_kind: str
    value: int | None
    condition: str

    def resolve_value(self, rating: int) -> int:
        """This bonus's magnitude for a purchase at `rating`."""
        return rating if self.value is None else self.value


@dataclass(frozen=True)
class Cyberware:
    id: str
    name: str
    category: str
    cost: int
    essence_cost: Decimal
    source: str
    page: int
    bonus_support: BonusSupport
    flat_bonuses: tuple[CyberwareFlatBonus, ...]  # populated only when bonus_support is FLAT_BONUS
    # populated only when bonus_support is CONDITIONAL_BONUS (WP40)
    conditional_bonuses: tuple[CyberwareConditionalBonus, ...]
    raw_bonus: str | None  # serialized <bonus> element, kept for future parser work; None if absent


def _is_flat_cost(text: str | None) -> bool:
    return text is not None and _FLAT_INT_RE.fullmatch(text) is not None


def _is_flat_essence(text: str | None) -> bool:
    return text is not None and _FLAT_DECIMAL_RE.fullmatch(text) is not None


def _is_flat_physical_cm_bonus(elem: ET.Element) -> bool:
    physical = elem.find("physical")
    if physical is None or len(physical) != 0:
        return False
    return {child.tag for child in elem} == {"physical"} and physical.text is not None


def _parse_conditional_limit_bonus(elem: ET.Element) -> CyberwareConditionalBonus | None:
    """Parse a `<limitmodifier>` child, or return `None` if it isn't a shape WP40 supports.

    The supported shape is exactly `<limit>` + `<value>` + `<condition>`, with a mapped limit, a
    whitelisted condition, and a value that is either the literal string `Rating` or a bare
    integer. Anything else -- an extra child, an unmapped limit, an unknown condition, an
    arithmetic value -- returns `None`, which sends the whole item to `NOT_YET_SUPPORTED`.
    """
    if {child.tag for child in elem} != {"limit", "value", "condition"}:
        return None

    target_kind = _LIMIT_TARGET_KINDS.get(elem.findtext("limit", "").strip())
    condition = elem.findtext("condition", "").strip()
    raw_value = elem.findtext("value", "").strip()
    if target_kind is None or condition not in _SUPPORTED_BONUS_CONDITIONS:
        return None

    if raw_value == _RATING_VALUE:
        value = None
    elif _FLAT_INT_RE.fullmatch(raw_value) is not None:
        value = int(raw_value)
    else:
        return None
    return CyberwareConditionalBonus(target_kind=target_kind, value=value, condition=condition)


def classify_bonus(
    bonus_elem: ET.Element | None,
) -> tuple[BonusSupport, tuple[CyberwareFlatBonus, ...], tuple[CyberwareConditionalBonus, ...]]:
    """Classify a `<bonus>` node, extracting flat and conditional bonuses when every remaining
    child is a supported shape. `<disablequality>` children are stripped first (see module
    docstring) -- an item whose `<bonus>` is empty, absent, or reduces to nothing after that
    stripping is `NO_EFFECT`; a single unsupported remaining child marks the whole item
    `NOT_YET_SUPPORTED` (mirrors `chummer5.data.qualities._classify_bonus`'s "never partially
    classify" rule for the bonus itself, independent of WP31's own "still load NOT_YET_SUPPORTED
    items" catalog-inclusion choice -- see module docstring).

    An item carrying **any** supported conditional bonus is `CONDITIONAL_BONUS`, even if it also
    carries a flat one; both tuples are populated either way, so a caller applies what it finds
    rather than branching on the support value. No SR5 row actually mixes the two (each of the four
    conditional items' `<bonus>` is a single `<limitmodifier>`), so this is a rule chosen for the
    mixed case rather than one any current row exercises -- said out loud because "which support
    value wins" would otherwise be invisible guesswork for whoever hits the first mixed row.

    Public (unlike `chummer5.data.qualities`/`powers`/`mentors`' identically-named private
    classifiers) because WP37's `chummer5.data.cyberware_subsystems` reads the *same* rows out of
    the *same* file and so shares this grammar verbatim -- see that module's docstring for why it
    reuses this rather than re-implementing it the way `chummer5.data.bioware` had to.
    """
    if bonus_elem is None or len(bonus_elem) == 0:
        return BonusSupport.NO_EFFECT, (), ()

    children = [child for child in bonus_elem if child.tag not in _VERIFIED_INERT_BONUS_TAGS]
    if not children:
        return BonusSupport.NO_EFFECT, (), ()

    flat_bonuses = []
    conditional_bonuses = []
    for child in children:
        if child.tag == "conditionmonitor" and _is_flat_physical_cm_bonus(child):
            flat_bonuses.append(
                CyberwareFlatBonus(
                    target_kind="physical_cm",
                    value=int(child.findtext("physical", "0")),
                )
            )
            continue
        if child.tag == "limitmodifier":
            conditional = _parse_conditional_limit_bonus(child)
            if conditional is not None:
                conditional_bonuses.append(conditional)
                continue
        return BonusSupport.NOT_YET_SUPPORTED, (), ()

    support = BonusSupport.CONDITIONAL_BONUS if conditional_bonuses else BonusSupport.FLAT_BONUS
    return support, tuple(flat_bonuses), tuple(conditional_bonuses)


def _parse_cyberware(elem: ET.Element) -> Cyberware:
    bonus_elem = elem.find("bonus")
    support, flat_bonuses, conditional_bonuses = classify_bonus(bonus_elem)
    raw_bonus = (
        ET.tostring(bonus_elem, encoding="unicode").strip() if bonus_elem is not None else None
    )
    return Cyberware(
        id=elem.findtext("id", ""),
        name=elem.findtext("name", ""),
        category=elem.findtext("category", ""),
        cost=int(elem.findtext("cost", "0")),
        essence_cost=Decimal(elem.findtext("ess", "0")),
        source=elem.findtext("source", ""),
        page=int(elem.findtext("page", "0")),
        bonus_support=support,
        flat_bonuses=flat_bonuses,
        conditional_bonuses=conditional_bonuses,
        raw_bonus=raw_bonus,
    )


def load_cyberware(xml_path: Path = DEFAULT_CYBERWARE_PATH) -> tuple[Cyberware, ...]:
    """Parse `cyberware.xml`, restricted to `source == "SR5"` AND flat cost AND flat Essence (60
    of 87 SR5 entries) -- Standard grade only, per the Implementation Plan's Phase J intro.
    """
    root = ET.parse(xml_path).getroot()
    cyberwares_elem = root.find("cyberwares")
    if cyberwares_elem is None:
        return ()
    return tuple(
        _parse_cyberware(c)
        for c in cyberwares_elem.findall("cyberware")
        if c.findtext("source") == CORE_RULEBOOK_SOURCE
        and _is_flat_cost(c.findtext("cost"))
        and _is_flat_essence(c.findtext("ess"))
    )


def count_by_support(cyberware: Iterable[Cyberware]) -> Mapping[BonusSupport, int]:
    """Count cyberware items per `BonusSupport` value, so the supported/unsupported split is
    visible.
    """
    counts = Counter(c.bonus_support for c in cyberware)
    return {support: counts[support] for support in BonusSupport}
