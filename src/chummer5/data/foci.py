"""Loader for the `Foci` category of `legacy/Chummer/data/gear.xml` (Phase M, WP47).

Of `gear.xml`'s 116 `category == "Foci"` entries, 32 carry `source == "SR5"`. Unlike every prior
"flat-cost" catalog this project has built (`chummer5.data.gear`/`cyberware`/`bioware`), **every
one of these 32 items is Rating-scaled, not flat** -- confirmed directly, not assumed: each
`<cost>` is `"Rating * N"` (N in `{3000, 4000, 5000, 7000, 9000, 18000}` depending on the item)
and each `<avail>` is `"(Rating * M)R"` (M in `{3, 4}`), where `Rating` is the Force the player
chooses at bonding time (core rulebook, "Foci", p. 317: "Foci have a Force rating that measures
their power"). This loader therefore does not filter by flat-cost the way `chummer5.data.gear`
does -- there is nothing flat to find among these 32 -- it instead exposes each item's **linear
multiplier** (`cost_per_force`/`availability_per_force`), a single-int-times-Force formula simple
enough to resolve without a general rating-formula evaluator, per the Implementation Plan's own
WP47 framing.

**Availability can't be filtered at load time the way `chummer5.data.bioware` filters it.** The
Implementation Plan's own WP47 text says to filter "Availability <= 12" in the loader, mirroring
bioware's static per-item cutoff -- checked directly and found not to apply here: bioware's
`<avail>` values are bare integers (no Force/Rating dependency), so a static per-item cutoff is
meaningful; every focus's Availability scales with the Force the player picks *at chargen time*,
not a fixed catalog property. Applying "Availability > 12 is excluded" to a Rating-scaled value
can only be done once a specific Force is chosen, so this project's 2026-07-21 Availability ruling
is enforced instead in `chummer5.engine.foci.create_foci_selection`, per-pick, at the Force the
player actually chose -- not a loader-level exclusion. This is a correction to the Plan's own
pre-implementation wording, the same kind of "verify rather than trust the Plan's own draft
phrasing" finding WP44 made for Sum-to-Ten's rule; see `spec/rulebooks/learnings.md`'s WP47 entry.

**The 7 rulebook focus categories (core rulebook, "Focus Types", p. 318) are not a `gear.xml`
field** -- every one of these 32 entries carries the bare `category == "Foci"`, with no
sub-category tag at all. `_FOCUS_CATEGORY_BY_NAME`/`_focus_category` classify each item by its own
name instead, verified individually against the rulebook's own per-category prose (p. 317-319,
"FOCUS TYPES"): Enchanting (Alchemical, Disenchanting), Metamagic (Centering, Flexible Signature,
Masking, Spell Shaping), Power (Power Focus), Qi (Qi Focus), Spirit (Summoning, Banishing,
Binding), Weapon (Weapon Focus) are each matched by exact name; every remaining name follows the
uniform `"<Type> Focus, <Category>"` shape (20 items: Counterspelling/Ritual Spellcasting/
Spellcasting/Sustaining x the 5 spell categories) and is recognized by the comma alone -- no other
focus name contains one. `BONDING_KARMA_PER_FORCE` is the Focus Table itself (p. 318): Enchanting/
Metamagic/Weapon Foci bond at Force x3, Power Foci at Force x6, Qi/Spell/Spirit Foci at Force x2.

**`<bonus>` classification -- every one of the 32 items individually checked against the
rulebook's own "Focus Types" prose, not shape-matched by accident.** Two verified-inert selection
tags are stripped before classification (mirroring `chummer5.data.cyberware`'s
`<disablequality>`-stripping precedent): `<selecttradition/>` (a focus's own tradition affinity --
moot for a chargen engine with no Test-resolution system, since every remaining item whose *only*
other child is this one has its real rulebook effect land entirely on a Test type --
Counterspelling/Ritual Spellcasting/Sustaining Tests, an Initiation-grade modifier for Centering/
Flexible Signature/Masking/Spell Shaping -- this engine has no equivalent computed value for at
all) and `<selecttext>` (Summoning/Banishing/Binding Focus's spirit-category pick -- moot for the
identical reason: their real effect targets Summoning/Banishing/Binding Tests, and Bound Spirits,
WP46, deliberately models no dice-pool/Test resolution whatsoever). After stripping, an empty
`<bonus>` is `NO_EFFECT`; a lone `<specificskill>` whose `<bonus>` child is the literal token
`"Rating"` (mirrors `chummer5.data.powers`'s identical "value scales with the purchased rating,
not a stored int" shape) is `FLAT_BONUS`; anything else is `NOT_YET_SUPPORTED`. This resolves to:

- `FLAT_BONUS` (2 of 32) -- Alchemical Focus (`<specificskill><name>Alchemy</name><bonus>Rating
  </bonus></specificskill>`), Disenchanting Focus (same shape, Disenchanting). Both skills are
  real, SR5-core, `Magical Active` entries in `chummer5.data.skills` already.
- `NO_EFFECT` (22 of 32) -- the 4 Metamagic foci, all 15 non-Spellcasting Spell foci
  (Counterspelling/Ritual Spellcasting/Sustaining x5 categories), and the 3 Spirit foci: each
  reduces to nothing after stripping the one inert selection child it carries -- see above for why
  their real, rulebook-described effect is verified moot for this engine's scope regardless.
- `NOT_YET_SUPPORTED` (8 of 32) -- Power Focus (`<skillattribute>`, a blanket bonus to every
  MAG-linked skill test, not a single named skill -- no existing Improvement mechanism for that
  shape); Qi Focus (`<selectpowers>`, an Adept-power-selection mechanism at purchase time); the 5
  Spellcasting foci (`<spellcategory>` with a `<condition>` child -- this engine's `Improvement`
  has no condition field at all, the same gap Phase K's pre-research already flagged for Vision
  Enhancement); Weapon Focus (`<weaponspecificdice>`, no weapon/combat dice-pool system modeled).

`chummer5.engine.foci` is what actually turns `FLAT_BONUS` items into real `Improvement`s -- this
module only classifies, mirroring every prior `chummer5.data.*` loader's loader/engine split.
`NOT_YET_SUPPORTED`/`NO_EFFECT` items are still loaded and purchasable (a focus's fundamental
content is its Force-scaled nuyen/Karma cost, same "purchase is real even when the bonus isn't
applied"
posture `chummer5.data.cyberware`'s own docstring already established).
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

DEFAULT_GEAR_PATH = Path(__file__).resolve().parents[3] / "legacy" / "Chummer" / "data" / "gear.xml"

# MVP content scope: only entries carrying this <source> tag are loaded. See "MVP content scope" in
# Implementation Plan.md.
CORE_RULEBOOK_SOURCE = "SR5"

# "Rating * N" (cost) / "(Rating * N)..." (avail) -- the linear-in-Force multiplier every one of the
# 32 SR5 Foci entries uses for both fields (see module docstring).
_COST_RE = re.compile(r"Rating\s*\*\s*(\d+)")
_AVAIL_RE = re.compile(r"\(Rating\s*\*\s*(\d+)\)")

# Every SR5 focus's raw <rating> field (its maximum purchasable Force) -- confirmed uniform across
# all 32 entries. Kept as a named constant rather than parsed per-item since it never varies; a
# future book adding a focus with a different cap would need this loader revisited anyway (it isn't
# the binding constraint for any legal chargen build -- see chummer5.engine.foci's own docstring).
FOCUS_MAX_RATING = 18

# The rulebook's 7 focus categories (core rulebook, "Focus Types", p. 318) -- classified by name,
# not a gear.xml field (none exists). See module docstring for the per-item verification below.
_FOCUS_CATEGORY_BY_NAME = {
    "Alchemical Focus": "Enchanting",
    "Disenchanting Focus": "Enchanting",
    "Centering Focus": "Metamagic",
    "Flexible Signature Focus": "Metamagic",
    "Masking Focus": "Metamagic",
    "Spell Shaping Focus": "Metamagic",
    "Power Focus": "Power",
    "Qi Focus": "Qi",
    "Summoning Focus": "Spirit",
    "Banishing Focus": "Spirit",
    "Binding Focus": "Spirit",
    "Weapon Focus": "Weapon",
}

# Focus Table, core rulebook p. 318 -- bonding cost in Karma per point of Force.
BONDING_KARMA_PER_FORCE = {
    "Enchanting": 3,
    "Metamagic": 3,
    "Power": 6,
    "Qi": 2,
    "Spell": 2,
    "Spirit": 2,
    "Weapon": 3,
}

# See module docstring's "<bonus> classification" paragraph for why both are verified moot (their
# real rulebook effect targets a Test-resolution mechanic this engine doesn't model at all) rather
# than treated as a real, unmodeled effect.
_VERIFIED_INERT_BONUS_TAGS = frozenset({"selecttradition", "selecttext"})


def _focus_category(name: str) -> str:
    """One of the 7 rulebook focus categories for `name` -- see module docstring. Every non-Spell
    name is matched exactly (`_FOCUS_CATEGORY_BY_NAME`); every Spell-category focus follows the
    uniform `"<Type> Focus, <Category>"` shape and is the only naming pattern among these 32 items
    that contains a comma, so that alone is a safe discriminator. Raises `KeyError` for a name
    this session's per-item classification didn't cover -- a real data-integrity signal if
    `gear.xml` ever adds an SR5 focus this loader hasn't been taught about, not an expected edge
    case.
    """
    if "," in name:
        return "Spell"
    return _FOCUS_CATEGORY_BY_NAME[name]


class BonusSupport(Enum):
    """Whether/how a focus's `<bonus>` node was parsed. A fresh 3-way enum, not reused from
    `chummer5.data.qualities`/`cyberware`/`bioware` (each has `NO_EFFECT`, matching this module's
    own need, but their `FLAT_BONUS` value is a stored int -- WP47's is the literal token
    `"Rating"`, resolved against the purchased Force at apply time, the same shape
    `chummer5.data.powers.BonusSupport.FLAT_BONUS` has) nor from `powers` directly (which has no
    `NO_EFFECT` at all -- see that module's own docstring for why it doesn't need one; this one
    does, per the module docstring's 22-item `NO_EFFECT` bucket above).
    """

    FLAT_BONUS = "flat_bonus"
    NO_EFFECT = "no_effect"
    NOT_YET_SUPPORTED = "not_yet_supported"


@dataclass(frozen=True)
class FocusFlatBonus:
    """One skill bonus scaling 1:1 with the bonded focus's own Force -- mirrors `chummer5.data.
    powers.PowerFlatBonus`'s "no stored value, resolved against the purchased pick" shape exactly
    (the only verified `FLAT_BONUS` shape here, Alchemical/Disenchanting Focus's `<specificskill>`,
    is the identical grammar `chummer5.data.qualities`/`bioware` already recognize, just with a
    `"Rating"`-token value instead of a fixed int -- see module docstring).
    """

    target_kind: str  # always "skill" so far
    target_name: str


@dataclass(frozen=True)
class Focus:
    id: str
    name: str
    focus_category: str  # one of the 7 rulebook categories, see module docstring
    cost_per_force: int
    availability_per_force: int
    bonding_karma_per_force: int
    source: str
    page: int
    bonus_support: BonusSupport
    flat_bonuses: tuple[FocusFlatBonus, ...]  # populated only when bonus_support is FLAT_BONUS
    raw_bonus: str | None  # serialized <bonus> element, kept for future parser work; None if absent


def _is_flat_skill_bonus(elem: ET.Element) -> bool:
    return {child.tag for child in elem} == {"name", "bonus"} and elem.findtext("bonus") == "Rating"


def _classify_bonus(
    bonus_elem: ET.Element | None,
) -> tuple[BonusSupport, tuple[FocusFlatBonus, ...]]:
    """Classify a `<bonus>` node -- strips `_VERIFIED_INERT_BONUS_TAGS` first (see module
    docstring), then applies the same "empty is NO_EFFECT, one recognized flat shape is
    FLAT_BONUS, anything else is NOT_YET_SUPPORTED" rule `chummer5.data.cyberware._classify_bonus`
    already established.
    """
    if bonus_elem is None or len(bonus_elem) == 0:
        return BonusSupport.NO_EFFECT, ()

    children = [child for child in bonus_elem if child.tag not in _VERIFIED_INERT_BONUS_TAGS]
    if not children:
        return BonusSupport.NO_EFFECT, ()

    if (
        len(children) == 1
        and children[0].tag == "specificskill"
        and _is_flat_skill_bonus(children[0])
    ):
        return (
            BonusSupport.FLAT_BONUS,
            (FocusFlatBonus(target_kind="skill", target_name=children[0].findtext("name", "")),),
        )
    return BonusSupport.NOT_YET_SUPPORTED, ()


def _parse_focus(elem: ET.Element) -> Focus:
    name = elem.findtext("name", "")
    cost_match = _COST_RE.search(elem.findtext("cost", ""))
    avail_match = _AVAIL_RE.search(elem.findtext("avail", ""))
    assert cost_match is not None and avail_match is not None  # guaranteed for all 32 SR5 entries
    category = _focus_category(name)
    bonus_elem = elem.find("bonus")
    support, flat_bonuses = _classify_bonus(bonus_elem)
    raw_bonus = (
        ET.tostring(bonus_elem, encoding="unicode").strip() if bonus_elem is not None else None
    )
    return Focus(
        id=elem.findtext("id", ""),
        name=name,
        focus_category=category,
        cost_per_force=int(cost_match.group(1)),
        availability_per_force=int(avail_match.group(1)),
        bonding_karma_per_force=BONDING_KARMA_PER_FORCE[category],
        source=elem.findtext("source", ""),
        page=int(elem.findtext("page", "0")),
        bonus_support=support,
        flat_bonuses=flat_bonuses,
        raw_bonus=raw_bonus,
    )


def load_foci(xml_path: Path = DEFAULT_GEAR_PATH) -> tuple[Focus, ...]:
    """Parse `gear.xml`'s `Foci` category, restricted to `source == "SR5"` (32 of 116 entries)."""
    root = ET.parse(xml_path).getroot()
    gears_elem = root.find("gears")
    if gears_elem is None:
        return ()
    return tuple(
        _parse_focus(g)
        for g in gears_elem.findall("gear")
        if g.findtext("category") == "Foci" and g.findtext("source") == CORE_RULEBOOK_SOURCE
    )


def count_by_support(foci: Iterable[Focus]) -> Mapping[BonusSupport, int]:
    """Count foci per `BonusSupport` value, so the supported/unsupported split is visible."""
    counts = Counter(f.bonus_support for f in foci)
    return {support: counts[support] for support in BonusSupport}
