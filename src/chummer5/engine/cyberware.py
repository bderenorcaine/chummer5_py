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
# WP31's Cyberlimb condition-monitor bonus; the two Limit kinds are WP40's conditional bonuses.
# See chummer5.data.cyberware's module docstring for why the data layer names these as strings.
_TARGET_KIND_TO_IMPROVEMENT_TYPE = {
    "physical_cm": ImprovementType.PHYSICAL_CM,
    "mental_limit": ImprovementType.MENTAL_LIMIT,
    "physical_limit": ImprovementType.PHYSICAL_LIMIT,
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

# Every ImprovementType this module produces resolves against a single, character-wide total (there
# is only one Essence pool, one Physical CM per character) -- the same _GLOBAL_TARGET sentinel
# chummer5.engine.derived already resolves both of these against.
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

    `rating` resolves a `<value>Rating</value>` conditional bonus. WP31's flat catalog has no
    rating dimension at all (none of its 60 rows carries a `<rating>` tag), so its caller passes
    1 -- and a rating-scaled conditional bonus appearing there would be data drift, which
    `apply_cyberware_improvements` rejects rather than silently applying as +1.
    """
    improvements = [
        Improvement(
            improvement_type=_TARGET_KIND_TO_IMPROVEMENT_TYPE[flat_bonus.target_kind],
            target=_GLOBAL_TARGET,
            value=flat_bonus.value,
            source_type=ImprovementSource.CYBERWARE,
            source_id=item_id,
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
