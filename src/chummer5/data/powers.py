"""Loader for `legacy/Chummer/data/powers.xml`, restricted to SR5 core-rulebook content (WP27).

Mirrors `chummer5.data.qualities`'s "classify each `<bonus>` node, offer only the flat shapes"
method, with one real difference from that precedent (confirmed by reading every SR5 power's raw
`<bonus>` node directly): **every power's bonus value is the literal token `"Rating"`, not a
hardcoded int.** `chummer5.data.qualities.FlatBonus.value` can be a plain `int` because a quality's
bonus is fixed the moment the quality is picked; a power's bonus scales with the rating actually
purchased (SR5 core rulebook p.308: "For each level of this power..."), so `PowerFlatBonus`
deliberately carries no `value` field at all -- `chummer5.engine.magic.apply_power_improvements`
resolves `value = the purchased pick's own rating` at apply time instead (every verified
`FLAT_BONUS` power below has a per-level magnitude of exactly 1, i.e. the literal "Rating" token
*is* the resolved multiplier, so no further per-level scaling is needed beyond that).

**The trap this WP was built around, caught before implementation (Implementation Plan's WP27
intro):** `<selectattribute>` is not a single shape. Improved Physical Attribute's `<bonus>` is
`<selectattribute><attribute>...</attribute>...<val>Rating</val></selectattribute>` -- a real,
permanent, rating-scaled attribute bonus, target chosen from a fixed eligible list. Attribute
Boost's `<bonus>` uses the *same* `selectattribute` tag, with the *same* list of eligible
attributes, but **no `<val>` child at all** -- because its real effect (rulebook p.309, "Attribute
Boost") is "make a Magic + Attribute Boost Rating Test; each hit raises the attribute by 1 until the
boost ends, then take Drain" -- a temporary, test-gated, Drain-costing effect, not a permanent
bonus. The classifier below (`_is_select_attribute_flat_bonus`) checks for that `<val>` child
specifically, not just the `selectattribute` tag, so Attribute Boost correctly falls through to
`NOT_YET_SUPPORTED` rather than being silently misapplied as a flat attribute bonus. See
`spec/worklogs/WP27.md` for the full per-power research this classification was checked against,
including a second power (Voice Control) confirmed via the rulebook text to be a genuine
`FLAT_BONUS` candidate the Implementation Plan's own WP27 entry didn't name.

**No `NO_EFFECT` value exists in this module's `BonusSupport`, unlike `chummer5.data.qualities`'s**.
Every SR5 power with an empty/absent `<bonus>` (Light Body, Missile Parry, Traceless Walk, Wall
Running) was individually checked against the rulebook text (per this WP's own "don't assume an
empty `<bonus>` means inert" caution) and turned out to have a real, in-play mechanical effect this
engine's combat-free, test-free scope doesn't model -- none qualified as verified-inert the way
WP22 found 8 qualities to be. Adding an always-zero-count enum member would just be unused
scaffolding (see the Project Overview's own "add it when a WP actually needs one" principle), so it
isn't added here; a future WP that finds a genuinely inert power should add it then, the same way
WP22 added `NO_EFFECT` to `chummer5.data.qualities` only once it had a real member to put in it.

Deliberately deferred, not defaulted into `FLAT_BONUS` or `NOT_YET_SUPPORTED` by a shape-matching
accident: **Improved Ability (skill)** (rulebook p.309) is shape-recognizable as a flat skill bonus
(`<selectskill minimumrating="1"><val>Rating</val>...`), but its real rule needs two things this
loader doesn't check -- the target skill must already be known at rating >= 1, and the achievable
improvement is capped at "your current skill level x 1.5, rounded up," a formula with no equivalent
anywhere else in this engine. Classified `NOT_YET_SUPPORTED` here rather than half-implementing the
cap; see `spec/worklogs/WP27.md` for the full reasoning.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from pathlib import Path

# legacy/Chummer/data/powers.xml, resolved relative to this file (not cwd).
DEFAULT_POWERS_PATH = (
    Path(__file__).resolve().parents[3] / "legacy" / "Chummer" / "data" / "powers.xml"
)

# MVP content scope: only entries carrying this <source> tag are loaded. See "MVP content scope" in
# Implementation Plan.md.
CORE_RULEBOOK_SOURCE = "SR5"

# The 3 Inherent-Limit bonus tags, mirroring chummer5.data.qualities's identical mapping for the
# Indomitable trio -- Improved Potential (Social/Mental/Physical) uses the exact same 3 tags, each a
# bare leaf holding the literal text "Rating" (confirmed in the raw XML; levels=False for all 3, so
# the resolved rating -- and thus the value -- is always exactly 1, per chummer5.engine.magic).
_LIMIT_BONUS_TAGS = {
    "mentallimit": "mental_limit",
    "physicallimit": "physical_limit",
    "sociallimit": "social_limit",
}


class BonusSupport(Enum):
    """Whether/how a power's `<bonus>` node was parsed. See module docstring for why there's no
    `NO_EFFECT` value here, unlike `chummer5.data.qualities.BonusSupport`.
    """

    FLAT_BONUS = "flat_bonus"
    NOT_YET_SUPPORTED = "not_yet_supported"


@dataclass(frozen=True)
class PowerFlatBonus:
    """One rating-scaled point bonus to a skill, attribute, or Inherent Limit.

    `target_kind` is `"skill"` (a fixed, named skill -- e.g. Enhanced Perception's Perception/
    Assensing), `"select_attribute"` (the purchaser picks one attribute from `attribute_options` at
    selection time -- Improved Physical Attribute), or one of the 3 Inherent-Limit kinds (a bare
    per-character total, `target_name` is `""`, mirroring `chummer5.data.qualities.FlatBonus`'s
    identical convention). No `value` field -- see module docstring for why.
    """

    target_kind: str
    target_name: str
    attribute_options: tuple[str, ...]  # only for "select_attribute"; () otherwise


@dataclass(frozen=True)
class Power:
    id: str
    name: str
    points: Decimal  # PP cost per level (levels=True) or the single flat PP cost (levels=False)
    levels: bool  # whether rating (and cost) scales past 1
    limit: int  # max rating (levels=True) or max purchases (always 1 for every FLAT_BONUS power)
    source: str
    page: int
    bonus_support: BonusSupport
    flat_bonuses: tuple[PowerFlatBonus, ...]  # populated only when bonus_support is FLAT_BONUS
    raw_bonus: str | None  # serialized <bonus> element, kept for future parser work; None if absent


def _is_flat_skill_bonus(elem: ET.Element) -> bool:
    return {child.tag for child in elem} == {"name", "bonus"} and elem.findtext("bonus") == "Rating"


def _is_select_attribute_flat_bonus(elem: ET.Element) -> bool:
    """Improved Physical Attribute's shape: any number of `<attribute>` options plus exactly one
    `<val>Rating</val>` child. Attribute Boost shares the `<attribute>` options but has no `<val>`
    child at all -- see module docstring's "trap" paragraph -- so it fails this check and falls
    through to `NOT_YET_SUPPORTED`.
    """
    tags = [child.tag for child in elem]
    if tags.count("val") != 1:
        return False
    if {tag for tag in tags if tag != "val"} != {"attribute"}:
        return False
    return elem.findtext("val") == "Rating"


def _classify_bonus(
    bonus_elem: ET.Element | None,
) -> tuple[BonusSupport, tuple[PowerFlatBonus, ...]]:
    """Classify a `<bonus>` node, extracting flat bonuses when every child is a flat shape.

    A single unsupported child (or an empty/absent `<bonus>`) marks the whole power
    `NOT_YET_SUPPORTED` -- MVP never partially applies a power's effects, mirroring
    `chummer5.data.qualities._classify_bonus`'s identical rule. Unlike that function, there's no
    name-gate for a verified-inert case -- see module docstring for why.
    """
    if bonus_elem is None or len(bonus_elem) == 0:
        return BonusSupport.NOT_YET_SUPPORTED, ()

    flat_bonuses = []
    for child in bonus_elem:
        if child.tag == "specificskill" and _is_flat_skill_bonus(child):
            flat_bonuses.append(
                PowerFlatBonus(
                    target_kind="skill",
                    target_name=child.findtext("name", ""),
                    attribute_options=(),
                )
            )
        elif child.tag == "selectattribute" and _is_select_attribute_flat_bonus(child):
            options = tuple(a.text or "" for a in child.findall("attribute"))
            flat_bonuses.append(
                PowerFlatBonus(
                    target_kind="select_attribute",
                    target_name="",
                    attribute_options=options,
                )
            )
        elif child.tag in _LIMIT_BONUS_TAGS and len(child) == 0 and child.text == "Rating":
            flat_bonuses.append(
                PowerFlatBonus(
                    target_kind=_LIMIT_BONUS_TAGS[child.tag],
                    target_name="",
                    attribute_options=(),
                )
            )
        else:
            return BonusSupport.NOT_YET_SUPPORTED, ()
    return BonusSupport.FLAT_BONUS, tuple(flat_bonuses)


def _parse_power(elem: ET.Element) -> Power:
    bonus_elem = elem.find("bonus")
    support, flat_bonuses = _classify_bonus(bonus_elem)
    raw_bonus = (
        ET.tostring(bonus_elem, encoding="unicode").strip() if bonus_elem is not None else None
    )
    return Power(
        id=elem.findtext("id", ""),
        name=elem.findtext("name", ""),
        points=Decimal(elem.findtext("points", "0")),
        levels=elem.findtext("levels") == "True",
        limit=int(elem.findtext("limit", "1")),
        source=elem.findtext("source", ""),
        page=int(elem.findtext("page", "0")),
        bonus_support=support,
        flat_bonuses=flat_bonuses,
        raw_bonus=raw_bonus,
    )


def load_powers(xml_path: Path = DEFAULT_POWERS_PATH) -> tuple[Power, ...]:
    """Parse `powers.xml`, restricted to `source == "SR5"` entries (28 of 109)."""
    root = ET.parse(xml_path).getroot()
    powers_elem = root.find("powers")
    if powers_elem is None:
        return ()
    return tuple(
        _parse_power(p)
        for p in powers_elem.findall("power")
        if p.findtext("source") == CORE_RULEBOOK_SOURCE
    )


def count_by_support(powers: Iterable[Power]) -> Mapping[BonusSupport, int]:
    """Count powers per `BonusSupport` value, so the supported/unsupported split is visible."""
    counts = Counter(p.bonus_support for p in powers)
    return {support: counts[support] for support in BonusSupport}
