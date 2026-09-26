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

**`NO_EFFECT` (WP119).** WP27 found no verified-inert power and so added no `NO_EFFECT` value. Phase
X offers powers whose whole effect is in play anyway, with a registry note, following the
2026-07-24 policy: WP119 added the value for Critical Strike, Enhanced Accuracy and Killing Hands,
name-gated like the qualities' (`_VERIFIED_NO_EFFECT_NAMES`).

**Improved Ability (skill)** (rulebook p.309) was deferred by WP27, because its rule needs the
target skill already known at rating >= 1 and caps the improvement ("current skill level x 1.5,
rounded up"). WP119 offers it: `chummer5.engine.magic.power_max_rating` applies the cap, and
`create_power_selection` checks the skill is known when the caller has the skill ratings.

**`<limit>` is an instance count, not a level cap (WP119 correction).** Levels are capped by the
Magic rating and `<maxlevels>` (p. 308); `<limit>` says how many times a repeatable power may be
bought, each for a different target. See `Power.limit`.
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
    # WP119: a power whose whole effect is in play (Critical Strike's +1 DV, ...), offered with an
    # `unmodeled_effect_note`. Name-gated, as for qualities.
    NO_EFFECT = "no_effect"
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
    # WP119: the dedup group, as for cyberware (`"precedence0"`: Improved Reflexes' Initiative
    # dice and Reaction don't combine with wired reflexes, p. 310).
    unique_name: str | None = None


@dataclass(frozen=True)
class Power:
    id: str
    name: str
    points: Decimal  # PP cost per level (levels=True) or the single flat PP cost (levels=False)
    levels: bool  # whether rating (and cost) scales past 1
    # WP119 correction: how many *instances* may be bought (Critical Strike 100, once per skill),
    # not the level cap -- see `max_levels`. WP27 read it as the level cap.
    limit: int
    source: str
    page: int
    bonus_support: BonusSupport
    flat_bonuses: tuple[PowerFlatBonus, ...]  # populated only when bonus_support is FLAT_BONUS
    raw_bonus: str | None  # serialized <bonus> element, kept for future parser work; None if absent
    # WP118: the power's in-play effect this engine doesn't compute (the Project Overview registry),
    # mirroring `chummer5.data.qualities.Quality.unmodeled_effect_note`.
    unmodeled_effect_note: str | None = None
    # WP119: `<maxlevels>` (0: none beyond the Magic rating, p. 308) and `<extrapointcost>` (a flat
    # PP charge on top of `points x rating` -- Improved Reflexes' 1.5/2.5/3.5, p. 310).
    max_levels: int = 0
    extra_point_cost: Decimal = Decimal(0)
    # WP119: what each instance names (`PowerPick.target`), or None: "attribute" (from
    # `target_options`) or "skill" (from `target_options` if given, else any skill of
    # `target_skill_categories` not in `target_excluded`). `target_minimum_rating` is the rating
    # the named skill must already have (Improved Ability: "You need to know the skill").
    target_kind: str | None = None
    target_options: tuple[str, ...] = ()
    target_skill_categories: tuple[str, ...] = ()
    target_excluded: tuple[str, ...] = ()
    target_minimum_rating: int = 0
    # WP119: qualities this power can't be held with (`<forbidden><oneof><quality>`) -- Pain
    # Resistance and High Pain Tolerance.
    forbidden_qualities: tuple[str, ...] = ()

    @property
    def repeatable(self) -> bool:
        """Several instances, each with its own target (WP119)."""
        return self.limit > 1 and self.target_kind is not None


# WP118: the registry text for offered powers with an in-play part. WP119/WP120 add the rest.
_UNMODELED_EFFECT_NOTES: Mapping[str, str] = {
    # WP119
    "Critical Strike": (
        "+1 DV on attacks with the chosen melee skill (p. 309) -- no attack or damage resolution "
        "exists. The chosen skill is recorded."
    ),
    "Enhanced Accuracy (skill)": (
        "+1 Accuracy for weapons used with the chosen Combat skill (p. 309) -- no weapon or "
        "Accuracy representation exists. The chosen skill is recorded."
    ),
    "Killing Hands": (
        "Unarmed attacks may deal Physical instead of Stun damage, and count as magical against "
        "critters' magical defenses (p. 310) -- no unarmed-combat or damage resolution exists."
    ),
    # WP120
    "Adrenaline Boost": (
        "+2 Initiative Score per level for the current Combat Turn, then Drain equal to the level "
        "at the start of the next (p. 308) -- no Initiative or Drain resolution exists."
    ),
    "Attribute Boost": (
        "A Magic + level Test whose hits raise the chosen attribute's dice pools (not its limit "
        "or Initiative) for twice as many Combat Turns, then Drain equal to the level (p. 309) -- "
        "no test or Drain resolution exists, so the attribute on the sheet is not raised. The "
        "chosen attribute is recorded."
    ),
    "Combat Sense": (
        "+1 die per level on defense tests against ranged and melee attacks, and a Perception Test "
        "before a possible surprise (p. 309) -- no combat or surprise resolution exists."
    ),
    "Danger Sense": (
        "+1 die per level on Surprise Tests (p. 309) -- no surprise resolution exists."
    ),
    "Improved Sense": (
        "The chosen sense improvement -- low-light or thermographic vision, directional sense, "
        "improved tactile, perfect pitch, human scale, ... (p. 310) -- no Perception or sensory "
        "resolution exists. The chosen sense is recorded."
    ),
    "Kinesics": (
        "+1 die per level to resist Social Tests and tests to read the character's emotions, such "
        "as Judge Intentions (p. 310) -- no Social test resolution exists."
    ),
    "Light Body": (
        "Adds its level to Agility for jump distance, +1 die per level on the Gymnastics Test to "
        "jump, and shortens a fall by its level in meters (p. 310) -- no movement or falling "
        "resolution exists."
    ),
    "Missile Parry": (
        "+1 die per level to defend against thrown weapons and slow missiles, catching one on net "
        "hits (p. 310) -- no combat resolution exists."
    ),
    "Natural Immunity": (
        "+1 die per level on tests to resist toxins and disease (p. 311) -- no toxin/pathogen "
        "resistance subsystem exists."
    ),
    "Rapid Healing": (
        "+1 die per level to Body for Healing Tests, and to any test to heal the character (p. "
        "311) -- no healing resolution exists."
    ),
    "Spell Resistance": (
        "+1 die per level on Resistance Tests against spells, rituals, alchemical preparations "
        "and Innate Spell (p. 311) -- no spell resolution exists."
    ),
    "Traceless Walk": (
        "Moving without visible traces or contact noise: -4 dice to hearing-based Perception "
        "against the character, no ground sensors tripped, -2 to Track Tests (p. 311) -- no "
        "stealth or Perception resolution exists."
    ),
    "Wall Running": (
        "A Running + Strength [Magic] Test to run up (or, with a Sprint, across) a wall (p. 311) "
        "-- no movement resolution exists."
    ),
    "Mystic Armor": (
        "Its Armor also protects against damage in astral combat (p. 310) -- no astral combat "
        "exists. (Its +1 Armor per level is applied.)"
    ),
    "Pain Resistance": (
        "+2 dice per level on tests to withstand pain from torture, magic or illness (p. 311) -- "
        "no such test exists. (Its wound-modifier offset is applied.)"
    ),
    "Astral Perception": (
        "Seeing into the astral plane while dual-natured, and so able to attack astral forms "
        "(p. 309; astral perception, p. 312) -- no astral resolution exists. (Its unlocking of "
        "the Assensing skill is applied.)"
    ),
}


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


# WP119: powers whose whole effect is in play, offered with a note (`BonusSupport.NO_EFFECT`).
_VERIFIED_NO_EFFECT_NAMES = frozenset(
    {
        "Critical Strike",
        "Enhanced Accuracy (skill)",
        "Killing Hands",
        # WP120: the rest of the core list. Attribute Boost is here, not a flat attribute bonus:
        # its boost is a Magic + Rating Test's hits, in play, with Drain after (p. 309; the
        # 2026-07-19 decisions-log entry), so it must never raise the attribute on the sheet.
        "Adrenaline Boost",
        "Attribute Boost",
        "Combat Sense",
        "Danger Sense",
        "Improved Sense",
        "Kinesics",
        "Light Body",
        "Missile Parry",
        "Natural Immunity",
        "Rapid Healing",
        "Spell Resistance",
        "Traceless Walk",
        "Wall Running",
    }
)

# WP119: the rulebook's non-stacking rule for Improved Reflexes (p. 310: "the increase cannot be
# combined with other technological or magical increases to Initiative") covers its Reaction too,
# not just the Initiative dice the data marks `precedence="0"`.
_RULEBOOK_UNIQUE_NAMES: Mapping[str, str] = {"Improved Reflexes": "precedence0"}

# WP119: bare `Rating` leaves -> target kinds.
_RATING_LEAF_TAGS = {"armor": "armor", "initiativepass": "initiative_dice"}


def _classify_bonus(
    bonus_elem: ET.Element | None,
    name: str = "",
) -> tuple[BonusSupport, tuple[PowerFlatBonus, ...]]:
    """Classify a `<bonus>` node, extracting flat bonuses when every child is a flat shape.

    A single unsupported child (or an empty/absent `<bonus>`) marks the whole power
    `NOT_YET_SUPPORTED` -- MVP never partially applies a power's effects, mirroring
    `chummer5.data.qualities._classify_bonus`'s identical rule. Unlike that function, there's no
    name-gate for a verified-inert case -- see module docstring for why.
    """
    if name in _VERIFIED_NO_EFFECT_NAMES:
        return BonusSupport.NO_EFFECT, ()
    if bonus_elem is None or len(bonus_elem) == 0:
        return BonusSupport.NOT_YET_SUPPORTED, ()

    unique = _RULEBOOK_UNIQUE_NAMES.get(name)
    flat_bonuses = []
    for child in bonus_elem:
        if child.tag == "disablequality":
            # WP119: Improved Reflexes switches off Lightning Reflexes, a non-core quality.
            continue
        if child.tag in _RATING_LEAF_TAGS and len(child) == 0 and child.text == "Rating":
            precedence = child.get("precedence")
            flat_bonuses.append(
                PowerFlatBonus(
                    target_kind=_RATING_LEAF_TAGS[child.tag],
                    target_name="",
                    attribute_options=(),
                    unique_name=unique or (f"precedence{precedence}" if precedence else None),
                )
            )
        elif (
            child.tag == "specificattribute"
            and {c.tag for c in child} == {"name", "val"}
            and child.findtext("val") == "Rating"
        ):
            flat_bonuses.append(
                PowerFlatBonus(
                    target_kind="attribute",
                    target_name=child.findtext("name", ""),
                    attribute_options=(),
                    unique_name=unique,
                )
            )
        elif (
            child.tag == "conditionmonitor"
            and [c.tag for c in child] == ["thresholdoffset"]
            and child.findtext("thresholdoffset") == "Rating"
        ):
            # WP119: Pain Resistance -- one ignored wound box per level on both tracks (p. 311).
            flat_bonuses.append(
                PowerFlatBonus(
                    target_kind="cm_threshold_offset", target_name="", attribute_options=()
                )
            )
        elif child.tag == "selectskill" and child.findtext("val") == "Rating":
            # WP119: Improved Ability -- +Rating to the chosen skill's rating (p. 309).
            flat_bonuses.append(
                PowerFlatBonus(target_kind="skill", target_name="", attribute_options=())
            )
        elif child.tag == "specificskill" and _is_flat_skill_bonus(child):
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
        elif child.tag == "unlockskills" and child.get("name") and len(child) == 0:
            # WP118: Astral Perception's `<unlockskills name="Assensing">` -- the one gate on an
            # Adept learning Assensing (p. 69).
            flat_bonuses.append(
                PowerFlatBonus(
                    target_kind="unlock_skill",
                    target_name=child.get("name", ""),
                    attribute_options=(),
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


def _parse_target(bonus_elem: ET.Element | None) -> dict[str, object]:
    """WP119: what an instance of the power names, from its `<bonus>`'s select-a-thing node."""
    if bonus_elem is None:
        return {}
    attributes = bonus_elem.find("selectattribute")
    if attributes is not None:
        return {
            "target_kind": "attribute",
            "target_options": tuple(a.text or "" for a in attributes.findall("attribute")),
        }
    categories = bonus_elem.find("weaponcategorydv/selectcategory")
    if categories is not None:
        # Critical Strike: "Unarmed Combat, Clubs, Blades, Astral Combat, or a particular Exotic
        # Melee weapon skill" (p. 309) -- the categories are skill names.
        return {
            "target_kind": "skill",
            "target_options": tuple(c.text or "" for c in categories.findall("category")),
        }
    select_skill = bonus_elem.find(".//selectskill")
    if select_skill is not None:
        listed = tuple(c.text or "" for c in select_skill.findall("skillcategories/category"))
        category = select_skill.get("skillcategory")
        excluded = select_skill.get("excludeskill")
        return {
            "target_kind": "skill",
            "target_skill_categories": listed or ((category,) if category else ()),
            "target_excluded": (excluded,) if excluded else (),
            "target_minimum_rating": int(select_skill.get("minimumrating", "0")),
        }
    if bonus_elem.find("selecttext") is not None:
        return {"target_kind": "text"}
    return {}


def _parse_power(elem: ET.Element) -> Power:
    bonus_elem = elem.find("bonus")
    support, flat_bonuses = _classify_bonus(bonus_elem, elem.findtext("name", ""))
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
        unmodeled_effect_note=_UNMODELED_EFFECT_NOTES.get(elem.findtext("name", "")),
        max_levels=int(elem.findtext("maxlevels", "0")),
        extra_point_cost=Decimal(elem.findtext("extrapointcost", "0")),
        forbidden_qualities=tuple(
            q.text for q in elem.findall("forbidden/oneof/quality") if q.text
        ),
        **_parse_target(bonus_elem),  # type: ignore[arg-type]
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
