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
