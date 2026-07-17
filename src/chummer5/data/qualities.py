"""Loader for `legacy/Chummer/data/qualities.xml`, restricted to SR5 core-rulebook content.

MVP's "core rulebook only" scope (see `Project Overview.md`) narrows the file's 803 `<quality>`
entries to the 96 with `source == "SR5"`. `<bonus>` nodes are a mini-language mirroring the general
Improvement bonus grammar the legacy engine parses (metatype bonuses, notoriety shifts,
category-wide skill bonuses, select-a-target choices, ...); MVP does not implement that general
parser. Instead,
each in-scope quality's `<bonus>` is classified as `FLAT_BONUS` — an unconditional, flat point bonus
to one or more specifically-named skills or attributes, the one shape simple enough to feed directly
into WP5's Improvement engine without a condition/selection sub-parser — or `NOT_YET_SUPPORTED`.
WP8 offers only `FLAT_BONUS` qualities to the player; `NOT_YET_SUPPORTED` ones are excluded from the
offered list rather than silently applied with their bonus dropped. See `spec/worklogs/WP3.md`.
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


class BonusSupport(Enum):
    """Whether a quality's `<bonus>` node was parsed into `Quality.flat_bonuses`."""

    FLAT_BONUS = "flat_bonus"
    NOT_YET_SUPPORTED = "not_yet_supported"


@dataclass(frozen=True)
class FlatBonus:
    """One unconditional, flat point bonus to a specifically-named skill or attribute."""

    target_kind: str  # "skill" or "attribute"
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
    bonus_elem: ET.Element | None,
) -> tuple[BonusSupport, tuple[FlatBonus, ...]]:
    """Classify a `<bonus>` node, extracting flat bonuses when every child is a flat shape.

    A single unsupported child (or an empty/absent `<bonus>`) marks the whole quality
    `NOT_YET_SUPPORTED` — MVP never partially applies a quality's effects.
    """
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
        else:
            return BonusSupport.NOT_YET_SUPPORTED, ()
    return BonusSupport.FLAT_BONUS, tuple(flat_bonuses)


def _parse_quality(elem: ET.Element) -> Quality:
    bonus_elem = elem.find("bonus")
    support, flat_bonuses = _classify_bonus(bonus_elem)
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
