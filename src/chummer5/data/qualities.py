"""Loader for `legacy/Chummer/data/qualities.xml`, restricted to SR5 core-rulebook content.

MVP's "core rulebook only" scope (see `Project Overview.md`) narrows the file's 803 `<quality>`
entries to the 96 with `source == "SR5"`. `<bonus>` nodes are a mini-language mirroring the general
Improvement bonus grammar the legacy engine parses (metatype bonuses, notoriety shifts,
category-wide skill bonuses, select-a-target choices, ...); MVP does not implement that general
parser. Instead, each in-scope quality's `<bonus>` is classified as one of three `BonusSupport`
values:

- `FLAT_BONUS` — an unconditional, flat point bonus to one or more specifically-named skills,
  attributes, (since WP22) Inherent Limits, or (since WP49) the native-language limit — the shapes
  simple enough to feed directly into WP5's Improvement engine without a condition/selection
  sub-parser.
- `NO_EFFECT` (WP22) — a verified-inert quality: an empty `<bonus/>` node *and* individually
  confirmed, via the rulebook text and a `grep` of the legacy C# for by-name special-casing,
  to produce no computed value anywhere this engine's scope reaches (combat/Matrix/vehicle/
  perception mechanics MVP doesn't model). Deliberately name-gated (`_VERIFIED_NO_EFFECT_NAMES`),
  not "any empty `<bonus/>` qualifies" — several other empty-`<bonus/>` SR5 qualities
  (Human-Looking, the Insomnia pair, ...) are excluded from *this* list because they need a
  different kind of engine support (a metatype-gate check, a mutual-exclusion check) that WP22
  didn't build, not because their bonus is unverified. See `spec/worklogs/WP22.md` and
  `spec/rulebooks/learnings.md`'s WP22 entry for the full per-quality research.
- `NOT_YET_SUPPORTED` — everything else.

WP8 offers only `FLAT_BONUS` qualities to the player; WP22 widens that to `FLAT_BONUS` and
`NO_EFFECT` (see `chummer5.engine.qualities.mvp_quality_catalog`). `NOT_YET_SUPPORTED` qualities
are excluded from the offered list rather than silently applied with their bonus dropped. See
`spec/worklogs/WP3.md`.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

# legacy/Chummer/data/qualities.xml, resolved relative to this file (not cwd).
DEFAULT_QUALITIES_PATH = (
    Path(__file__).resolve().parents[3] / "legacy" / "Chummer" / "data" / "qualities.xml"
)

# MVP content scope: only entries carrying this <source> tag are loaded. See "MVP content scope" in
# Implementation Plan.md.
CORE_RULEBOOK_SOURCE = "SR5"

# The two <bonus> child shapes MVP treats as "flat": a bare name + unconditional numeric value, with
# no other fields (no <condition>, no <max>/<min> range changes, no category/select machinery).
_FLAT_SKILL_FIELDS = frozenset({"name", "bonus"})
_FLAT_ATTRIBUTE_FIELDS = frozenset({"name", "val"})

# WP22 Tranche 1: the Indomitable trio's <bonus> is a single bare-numeric leaf tag (e.g.
# <mentallimit>1</mentallimit>, no children, no <condition>) -- flat in the same sense as
# <specificskill>/<specificattribute> above, just untargeted (there's only one Mental/Physical/
# Social Limit per character). Maps to the FlatBonus.target_kind values
# `chummer5.engine.qualities._TARGET_KIND_TO_IMPROVEMENT_TYPE` resolves against the derived-stats
# global sentinel target (see `chummer5.engine.derived._GLOBAL_TARGET`).
#
# WP49 adds `nativelanguagelimit` (Bilingual's own `<bonus>`, verified to be the identical
# bare-numeric-leaf shape -- see spec/rulebooks/learnings.md's WP49 entry): a Plan-stated "already
# offered" claim turned out to be wrong (Bilingual was actually `NOT_YET_SUPPORTED` before this WP),
# so classifying it here is what makes it FLAT_BONUS -- and therefore offerable at all -- for the
# first time.
_GLOBAL_BONUS_TAGS = {
    "mentallimit": "mental_limit",
    "physicallimit": "physical_limit",
    "sociallimit": "social_limit",
    "nativelanguagelimit": "native_language_limit",
}

# WP22 Tranche 2: SR5 qualities individually verified (rulebook text + a `grep` of the legacy C#
# for by-name special-casing, both turning up nothing) to have zero mechanical effect this engine's
# scope ever computes -- Gearhead/Juryrigger (vehicle/repair mechanics, no vehicles in MVP), Guts
# (fear-test resistance, no such test), Natural Hardening (Matrix-attack resistance, no Matrix in
# MVP), Low-Light Vision/Thermographic Vision (lighting-condition perception, not modeled),
# Simsense Vertigo (AR/VR/simsense dice-pool penalty, no such test), Unsteady Hands (called-shot
# penalty, no combat system). See spec/rulebooks/learnings.md's WP22 entry for the citations. Every
# one of these has an
# empty `<bonus/>` node in the real data, but this set is name-gated rather than "any empty <bonus/>
# qualifies" -- see the module docstring for why (other empty-`<bonus/>` qualities need different,
# not-yet-built engine support, not a NO_EFFECT verdict).
_VERIFIED_NO_EFFECT_NAMES = frozenset(
    {
        "Gearhead",
        "Guts",
        "Juryrigger",
        "Natural Hardening",
        "Low-Light Vision",
        "Thermographic Vision",
        "Simsense Vertigo",
        "Unsteady Hands",
    }
)


class BonusSupport(Enum):
    """Whether/how a quality's `<bonus>` node was parsed. See module docstring for the 3 values."""

    FLAT_BONUS = "flat_bonus"
    NO_EFFECT = "no_effect"
    NOT_YET_SUPPORTED = "not_yet_supported"


@dataclass(frozen=True)
class FlatBonus:
    """One unconditional, flat point bonus to a skill, attribute, or (WP22) Inherent Limit.

    `target_name` is the specifically-named skill/attribute for those two kinds; for the 3
    limit kinds (`"mental_limit"`/`"physical_limit"`/`"social_limit"`) it's `""` — there's only one
    of each per character, so there's nothing to name (mirrors `chummer5.engine.derived`'s own
    `_GLOBAL_TARGET` sentinel for the same reason).
    """

    target_kind: str  # "skill", "attribute", "mental_limit", "physical_limit", or "social_limit"
    target_name: str
    value: int


@dataclass(frozen=True)
class Quality:
    id: str
    name: str
    category: str  # "Positive" or "Negative"
    karma: int  # negative for Negative-category qualities, per the source data's sign convention
    limit: str | None  # raw string: a count, "True"/"False", or a formula like "{arm} - 1"
    source: str
    page: int
    bonus_support: BonusSupport
    flat_bonuses: tuple[FlatBonus, ...]  # populated only when bonus_support is FLAT_BONUS
    raw_bonus: str | None  # serialized <bonus> element, kept for future parser work; None if absent


def _is_flat_skill_bonus(elem: ET.Element) -> bool:
    return {child.tag for child in elem} == _FLAT_SKILL_FIELDS


def _is_flat_attribute_bonus(elem: ET.Element) -> bool:
    return {child.tag for child in elem} == _FLAT_ATTRIBUTE_FIELDS


def _classify_bonus(
    name: str,
    bonus_elem: ET.Element | None,
) -> tuple[BonusSupport, tuple[FlatBonus, ...]]:
    """Classify a `<bonus>` node, extracting flat bonuses when every child is a flat shape.

    A single unsupported child (or an empty/absent `<bonus>`) marks the whole quality
    `NOT_YET_SUPPORTED` — MVP never partially applies a quality's effects — unless `name` is
    one of WP22's individually-verified `_VERIFIED_NO_EFFECT_NAMES`, in which case it's
    `NO_EFFECT` instead.
    """
    if name in _VERIFIED_NO_EFFECT_NAMES:
        return BonusSupport.NO_EFFECT, ()
    if bonus_elem is None or len(bonus_elem) == 0:
        return BonusSupport.NOT_YET_SUPPORTED, ()

    flat_bonuses = []
    for child in bonus_elem:
        if child.tag == "specificskill" and _is_flat_skill_bonus(child):
            flat_bonuses.append(
                FlatBonus(
                    target_kind="skill",
                    target_name=child.findtext("name", ""),
                    value=int(child.findtext("bonus", "0")),
                )
            )
        elif child.tag == "specificattribute" and _is_flat_attribute_bonus(child):
            flat_bonuses.append(
                FlatBonus(
                    target_kind="attribute",
                    target_name=child.findtext("name", ""),
                    value=int(child.findtext("val", "0")),
                )
            )
        elif child.tag in _GLOBAL_BONUS_TAGS and len(child) == 0 and child.text is not None:
            flat_bonuses.append(
                FlatBonus(
                    target_kind=_GLOBAL_BONUS_TAGS[child.tag],
                    target_name="",
                    value=int(child.text),
                )
            )
        else:
            return BonusSupport.NOT_YET_SUPPORTED, ()
    return BonusSupport.FLAT_BONUS, tuple(flat_bonuses)


def _parse_quality(elem: ET.Element) -> Quality:
    bonus_elem = elem.find("bonus")
    support, flat_bonuses = _classify_bonus(elem.findtext("name", ""), bonus_elem)
    raw_bonus = (
        ET.tostring(bonus_elem, encoding="unicode").strip() if bonus_elem is not None else None
    )
    return Quality(
        id=elem.findtext("id", ""),
        name=elem.findtext("name", ""),
        category=elem.findtext("category", ""),
        karma=int(elem.findtext("karma", "0")),
        limit=elem.findtext("limit"),
        source=elem.findtext("source", ""),
        page=int(elem.findtext("page", "0")),
        bonus_support=support,
        flat_bonuses=flat_bonuses,
        raw_bonus=raw_bonus,
    )


def load_qualities(xml_path: Path = DEFAULT_QUALITIES_PATH) -> tuple[Quality, ...]:
    """Parse `qualities.xml`, restricted to `source == "SR5"` entries (96 of 803)."""
    root = ET.parse(xml_path).getroot()
    qualities_elem = root.find("qualities")
    if qualities_elem is None:
        return ()
    return tuple(
        _parse_quality(q)
        for q in qualities_elem.findall("quality")
        if q.findtext("source") == CORE_RULEBOOK_SOURCE
    )


def count_by_support(qualities: Iterable[Quality]) -> Mapping[BonusSupport, int]:
    """Count qualities per `BonusSupport` value, so the supported/unsupported split is visible."""
    counts = Counter(q.bonus_support for q in qualities)
    return {support: counts[support] for support in BonusSupport}
