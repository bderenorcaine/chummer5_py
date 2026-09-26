"""Cyberware `<bonus>` -> `Improvement` translation (Phase J, WP32; narrowed to this one job by
WP41).

**What this module used to be, and why it isn't any more.** WP32 built the whole flat cyberware
purchase here -- `CyberwareSelection`, `create_cyberware_selection`, `apply_cyberware_improvements`
-- composing WP30's Essence mechanism with WP31's flat-cost/flat-Essence/Standard-grade catalog.
Phase K then built the real thing: `chummer5.engine.cyberware_subsystems` (WP38/WP40) models a
purchase *tree*, where a cyberlimb/cybereye/cyberear holds plugins that charge its Capacity instead
of the character's Essence, and a flat purchase is simply a zero-plugin tree. WP41 retyped
`Character.cyberware_selection` onto that tree and migrated every call site (save/load, legacy
import, the web routes), which left WP32's three flat symbols with no constructor and no consumer.
They are **retired**, not deprecated-in-place: `Character` has exactly one cyberware field, so
leaving behind a second selection builder whose output could never be attached to a character would
be a trap, not a convenience. Every rule they enforced (nuyen budget, the strictly-positive Essence
floor shared with `other_essence_spent`, duplicate purchases being legal) is enforced by
`create_cyberware_tree_selection` verbatim -- see that module's docstring for the citations, which
were researched here and are not repeated.

What stays here is `cyberware_bonus_improvements`: the `<bonus>` -> `Improvement` translation, plus
the two string -> enum maps it needs. It lives in this module rather than in
`cyberware_subsystems` because it is the engine-side mirror of the data layer's own single shared
classifier (`chummer5.data.cyberware.classify_bonus`, which both catalogs call) -- one classifier,
one translator, both keyed off `chummer5.data.cyberware`'s vocabulary.
"""

from __future__ import annotations

from collections.abc import Iterable

from chummer5.data.cyberware import CyberwareConditionalBonus, CyberwareFlatBonus
from chummer5.engine.improvements import (
    Improvement,
    ImprovementCondition,
    ImprovementSource,
    ImprovementType,
)

# CyberwareFlatBonus/CyberwareConditionalBonus.target_kind -> ImprovementType. `physical_cm` is
# WP31's Cyberlimb condition-monitor bonus; the two Limit kinds are WP40's conditional bonuses;
# `attribute`/`skill`/`initiative_dice` are WP78's.
# See chummer5.data.cyberware's module docstring for why the data layer names these as strings.
_TARGET_KIND_TO_IMPROVEMENT_TYPE = {
    "physical_cm": ImprovementType.PHYSICAL_CM,
    "mental_limit": ImprovementType.MENTAL_LIMIT,
    "physical_limit": ImprovementType.PHYSICAL_LIMIT,
    "attribute": ImprovementType.ATTRIBUTE,
    "skill": ImprovementType.SKILL,
    "initiative_dice": ImprovementType.INITIATIVE_DICE,
    # WP109: Bone Lacing, Dermal Plating and the cyberlimb Armor enhancement.
    "armor": ImprovementType.ARMOR,
    "damage_resistance": ImprovementType.DAMAGE_RESISTANCE,
}

# The legacy <condition> key -> WP39's compiled predicate. One entry per member of
# `chummer5.data.cyberware._SUPPORTED_BONUS_CONDITIONS`; a key with no entry here is a bug rather
# than a fall-through, since the data layer already refused to classify anything else.
_CONDITION_KEY_TO_CONDITION = {
    "LimitCondition_SkillsActivePerceptionVisual": ImprovementCondition.PERCEPTION_VISUAL_ONLY,
    "LimitCondition_SkillsActivePerceptionHearing": ImprovementCondition.PERCEPTION_HEARING_ONLY,
    "LimitCondition_SkillsActivePerceptionSpatialRecognizer": (
        ImprovementCondition.PERCEPTION_SOUND_SOURCE_ONLY
    ),
    "LimitCondition_CyberwareHydraulicJacks": ImprovementCondition.JUMPING_OR_SPRINTING_ONLY,
}

# The character-wide ImprovementTypes this module produces (Physical CM, the two Limits, Initiative
# Dice) resolve against a single total -- the same _GLOBAL_TARGET sentinel chummer5.engine.derived
# already resolves them against. WP78's `attribute`/`skill` kinds are the first per-target ones
# here; their target is the bonus's own `target_name`, which the data layer leaves as exactly this
# empty string for every character-wide kind, so one expression covers both cases.
_GLOBAL_TARGET = ""


def cyberware_bonus_improvements(
    *,
    item_id: str,
    item_name: str,
    flat_bonuses: Iterable[CyberwareFlatBonus],
    conditional_bonuses: Iterable[CyberwareConditionalBonus],
    rating: int,
) -> tuple[Improvement, ...]:
    """Build the `Improvement`s one purchased cyberware item's `<bonus>` grants, at `rating`.

    Shared with `chummer5.engine.cyberware_subsystems` (WP40), which imports it rather than
    re-deriving the two string -> enum maps above -- the data layer already shares one classifier
    across both catalogs (`chummer5.data.cyberware.classify_bonus`), so the engine sharing one
    translator is the matching half of that split. Essence is *not* built here: a standalone
    purchase and a plugin are priced differently in Essence (see `chummer5.engine
    .cyberware_subsystems`' dual-costing section), so each caller owns that record.

    `rating` resolves a `Rating`-valued bonus, flat (WP78) or conditional (WP40). WP31's flat
    catalog has no rating dimension at all (none of its 60 rows carries a `<rating>` tag), so its
    caller would pass 1 -- and no row in it carries a `Rating`-valued bonus of either kind
    (verified by enumeration: all four `Rating`-valued rows are rating-scaled in `<cost>` or
    `<ess>` too, which is exactly what excludes them from that catalog).

    `unique_name` (WP78) is carried through from the data layer unchanged, so SR5's "these two
    augmentations don't stack" rules land on `ImprovementIndex.resolve`'s existing highest-wins
    dedup pass rather than needing a second mechanism.
    """
    improvements = [
        Improvement(
            improvement_type=_TARGET_KIND_TO_IMPROVEMENT_TYPE[flat_bonus.target_kind],
            target=flat_bonus.target_name,
            value=flat_bonus.resolve_value(rating),
            source_type=ImprovementSource.CYBERWARE,
            source_id=item_id,
            rating=rating,
            unique_name=flat_bonus.unique_name,
        )
        for flat_bonus in flat_bonuses
    ]
    for conditional in conditional_bonuses:
        condition = _CONDITION_KEY_TO_CONDITION.get(conditional.condition)
        if condition is None:
            raise ValueError(
                f"{item_name}: <condition> {conditional.condition!r} has no ImprovementCondition "
                f"(chummer5.data.cyberware classified it as supported -- the two whitelists have "
                f"drifted apart)"
            )
        improvements.append(
            Improvement(
                improvement_type=_TARGET_KIND_TO_IMPROVEMENT_TYPE[conditional.target_kind],
                target=_GLOBAL_TARGET,
                value=conditional.resolve_value(rating),
                source_type=ImprovementSource.CYBERWARE,
                source_id=item_id,
                rating=rating,
                condition=condition,
            )
        )
    return tuple(improvements)
