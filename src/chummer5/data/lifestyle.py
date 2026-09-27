"""Loader for `legacy/Chummer/data/lifestyles.xml`, restricted to the 6 real SR5 starting tiers.

`lifestyles.xml` has 12 raw `<lifestyle>` entries; 9 carry `source == "SR5"` (see WP20's worklog for
the full count). Of those 9, 3 are not valid *starting* Lifestyle choices and are excluded here
(the same "excluded, not silently dropped" MVP content-scope pattern WP2/WP3/WP6 already established
for out-of-scope metatypes/qualities):

- `"ID ERROR. Re-add life style to fix"` — a data-migration placeholder, not a real tier (confirmed
  by name, and by its nonsensical `lp=0`/`cost=1` pairing, unlike every real tier's coherent
  cost/LP progression).
- `"Hospitalized, Basic"` / `"Hospitalized, Intensive"` — core rulebook, p. 369: "Characters cannot
  own this lifestyle. They only pay for it until they get well or go broke" — a temporary condition
  applied during play, not a choice offered at character creation.

The remaining 6 (Street/Squatter/Low/Medium/High/Luxury) are exactly the tiers in the core
rulebook's own "Lifestyle Costs Table" (p. 94) and "Lifestyle" section (p. 369) — see
`spec/rulebooks/learnings.md`'s WP20 entry for the full rulebook/legacy-code cross-check, including
why the `<cost>` field is a *monthly* rate rather than a pre-multiplied total.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

# legacy/Chummer/data/lifestyles.xml, resolved relative to this file (not cwd).
DEFAULT_LIFESTYLES_PATH = (
    Path(__file__).resolve().parents[3] / "legacy" / "Chummer" / "data" / "lifestyles.xml"
)

# MVP content scope: only entries carrying this <source> tag are loaded. See "MVP content scope" in
# Implementation Plan.md.
CORE_RULEBOOK_SOURCE = "SR5"

# The 6 real starting-lifestyle tiers a character can select as their primary Lifestyle at
# character creation. See module docstring for why the other 3 SR5-sourced entries are excluded.
STARTING_TIER_NAMES = ("Street", "Squatter", "Low", "Medium", "High", "Luxury")


@dataclass(frozen=True)
class LifestyleTier:
    """One of the 6 starting-Lifestyle tiers offered as a character's primary Lifestyle."""

    name: str
    monthly_cost: int
    source: str
    page: int


def _parse_tier(elem: ET.Element) -> LifestyleTier:
    return LifestyleTier(
        name=elem.findtext("name", ""),
        monthly_cost=int(elem.findtext("cost", "0")),
        source=elem.findtext("source", ""),
        page=int(elem.findtext("page", "0")),
    )


def load_lifestyles(xml_path: Path = DEFAULT_LIFESTYLES_PATH) -> tuple[LifestyleTier, ...]:
    """Parse `lifestyles.xml`, restricted to the 6 real SR5 starting tiers (see module
    docstring)."""
    root = ET.parse(xml_path).getroot()
    lifestyles_elem = root.find("lifestyles")
    if lifestyles_elem is None:
        return ()
    tiers = []
    for elem in lifestyles_elem.findall("lifestyle"):
        if elem.findtext("source") != CORE_RULEBOOK_SOURCE:
            continue
        if elem.findtext("name") not in STARTING_TIER_NAMES:
            continue
        tiers.append(_parse_tier(elem))
    return tuple(tiers)


# WP132: the five core Lifestyle Options (p. 370). `lifestyles.xml` files them as lifestyle
# `<qualities>` alongside the four DocWagon contracts (category "Contracts", sold as gear since
# WP21) -- only the Positive/Negative ones are options. Their `<lp>` values are Run Faster's
# Lifestyle Points, not core, and are ignored.
LIFESTYLE_OPTION_CATEGORIES = ("Positive", "Negative")

# p. 370's in-play effects, which nothing here resolves ("Unmodeled real effects" rows).
_OPTION_EFFECT_NOTES = {
    "Special Work Area": (
        "Skill checks relevant to the setting have their Limit increased by 2 when performed in "
        "this space (p. 370)."
    ),
    "Extra Secure": (
        "High Threat Response and other security response rolls are made at one level better "
        "than the area would normally be (p. 370)."
    ),
    "Obscure/Difficult to Find": (
        "Sneaking checks in the vicinity (the owner excluded) are made at -2 (p. 370)."
    ),
    "Cramped": (
        "Skill checks tied to Logic have their Limit reduced by 2 (minimum 1) when performed in "
        "this space (p. 370)."
    ),
    "Dangerous Area": (
        "High Threat Response and similar security responses are made as if the area were one "
        "level lower (p. 370)."
    ),
}


@dataclass(frozen=True)
class LifestyleOption:
    """One core Lifestyle Option (WP132, p. 370): a percent of the lifestyle's cost (Cramped
    -10, Dangerous Area -20, Obscure +10, Extra Secure +20) or a flat monthly amount (Special Work
    Area +1,000). `repeatable` options (Special Work Area) name what each one is, in `text`."""

    id: str
    name: str
    cost_percent: int
    flat_cost: int
    repeatable: bool
    source: str
    page: int
    unmodeled_effect_note: str | None = None


def _parse_option(elem: ET.Element) -> LifestyleOption:
    percent = elem.findtext("multiplier") or elem.findtext("multiplierbaseonly") or "0"
    name = elem.findtext("name", "")
    return LifestyleOption(
        id=elem.findtext("id", ""),
        name=name,
        cost_percent=int(percent),
        flat_cost=int(elem.findtext("cost") or "0"),
        repeatable=elem.find("allowmultiple") is not None,
        source=elem.findtext("source", ""),
        page=int(elem.findtext("page", "0")),
        unmodeled_effect_note=_OPTION_EFFECT_NOTES.get(name),
    )


def load_lifestyle_options(xml_path: Path = DEFAULT_LIFESTYLES_PATH) -> tuple[LifestyleOption, ...]:
    """The five SR5 Lifestyle Options (WP132)."""
    root = ET.parse(xml_path).getroot()
    return tuple(
        _parse_option(elem)
        for elem in root.findall("qualities/quality")
        if elem.findtext("source") == CORE_RULEBOOK_SOURCE
        and elem.findtext("category") in LIFESTYLE_OPTION_CATEGORIES
    )
