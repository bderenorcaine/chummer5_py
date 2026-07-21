"""Bioware selection & Improvement application (Phase L, WP45).

Composes `chummer5.engine.derived.essence`/`BASE_ESSENCE` (WP30) with WP45's flat-cost,
flat-Essence, low-Availability, Standard-grade bioware catalog (`chummer5.data.bioware`) and WP6's
`Character` into a buildable bioware purchase -- mirrors `chummer5.engine.cyberware`'s
`create_*_selection`/`apply_*_improvements` shape almost exactly, since this WP reuses Phase J's
Essence/nuyen-budget/Improvement-application machinery directly rather than inventing a second one
(per the Implementation Plan's own framing of this WP).

**A new module, not folded into `chummer5.engine.cyberware`.** Considered both, per the Plan's own
"decide & document which" prompt. Chose a separate module for the same reason `chummer5.engine
.lifestyle`/`chummer5.engine.cyberware` are already separate from `chummer5.engine.resources`: each
is its own SR5 chargen decision (cyberware and bioware are named as two distinct catalogs in the
rulebook's own "Cyberware and Bioware" Step Six subsection, not one merged list) with its own
catalog/dataclass, even though all three ultimately share one nuyen budget and (cyberware/bioware
specifically) one Essence pool. Folding bioware's ~6 items into `chummer5.engine.cyberware` would
only save one file at the cost of conflating two catalogs `chummer5.data` already keeps separate.

**Nuyen and Essence: the same shared pools cyberware already draws from/reduces -- confirmed, not
assumed.** `chummer5.engine.cyberware`'s own module docstring already cites the core rulebook's
"Step Six: Spend Your Resources" (p. 94) naming "Cyberware and Bioware" as one combined subsection
-- so nuyen is the identical shared budget, `nuyen_budget` taken as a plain parameter the same way.
Essence is the same single pool too (checked directly against the legacy engine's own
`Character.Essence()`, which sums cyberware and bioware Essence costs together with no separate
tracking -- see `chummer5.engine.improvements.ImprovementIndex.resolve_essence`'s own docstring,
already written with this in mind: "an Essence cost is a plain sum of whatever cyberware/bioware was
actually bought").

**Evaluation order: cyberware first (unaware of bioware), bioware second (aware of cyberware) --
a fixed, documented convention, not an arbitrary choice.** Both `create_cyberware_selection`/
`create_bioware_selection` take an `other_essence_spent`/nuyen-budget parameter representing the
*other* selection's already-resolved spend (mirroring `chummer5.engine.magic
.create_magic_attribute_points`'s `other_special_attribute_points_spent` shape). Every caller in
this project (`chummer5.io.save_format.build_character`, `chummer5.web.app`'s combined cyberware+
bioware section) resolves cyberware first with `other_essence_spent` at its default (`Decimal(0)`),
then bioware second, passing cyberware's own `essence_spent`/leftover nuyen in. This means a
combination that only becomes invalid once *both* are counted together is always caught -- on the
second (bioware) call -- even though the first (cyberware) call alone couldn't have known about it;
it is never silently missed by either call passing without the other.

**Duplicate purchases are allowed, mirroring cyberware -- though unlike cyberware, no real fixture
confirms this is an ordinary SR5 purchase pattern for bioware specifically.** None of this project's
own curated corpus's real Bioware purchases (see Log/worklog) are duplicates of the same item, so
this is a consistency choice (one `create_*_selection` shape across cyberware/bioware/gear, all of
which allow repeats) rather than a separately-verified rule the way cyberware's own duplicate-
cyberlimb-pair finding was.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal

from chummer5.data.bioware import Bioware
from chummer5.engine.character import Character
from chummer5.engine.derived import BASE_ESSENCE
from chummer5.engine.improvements import Improvement, ImprovementSource, ImprovementType

# BiowareFlatBonus.target_kind -> ImprovementType, mirroring chummer5.engine.qualities's identical
# mapping (bioware's own flat shapes are qualities' skill/attribute/limit grammar, reused verbatim
# -- see chummer5.data.bioware's module docstring).
_TARGET_KIND_TO_IMPROVEMENT_TYPE = {
    "attribute": ImprovementType.ATTRIBUTE,
    "skill": ImprovementType.SKILL,
    "mental_limit": ImprovementType.MENTAL_LIMIT,
    "physical_limit": ImprovementType.PHYSICAL_LIMIT,
    "social_limit": ImprovementType.SOCIAL_LIMIT,
}

# The 3 limit kinds resolve against a single, character-wide total -- the same _GLOBAL_TARGET
# sentinel chummer5.engine.derived/chummer5.engine.cyberware already resolve ESSENCE/PHYSICAL_CM
# against. Skill/attribute bonuses use the bonus's own target_name instead (see apply_bioware_
# improvements below).
_GLOBAL_TARGET = ""


@dataclass(frozen=True)
class BiowareSelection:
    """A validated set of purchased bioware items and their combined nuyen/Essence cost.

    `items` may contain the same `Bioware` more than once -- see module docstring for why duplicate
    purchases are allowed (a consistency choice, not a separately-verified rule the way cyberware's
    own was).
    """

    items: tuple[Bioware, ...]
    nuyen_budget: int
    nuyen_spent: int
    essence_spent: Decimal


def create_bioware_selection(
    item_ids: Iterable[str],
    catalog: Iterable[Bioware],
    nuyen_budget: int,
    *,
    other_essence_spent: Decimal = Decimal(0),
) -> BiowareSelection:
    """Build a `BiowareSelection`, validating nuyen spend and the (shared) Essence floor together.

    Validates: every id resolves against `catalog`; total nuyen cost doesn't exceed `nuyen_budget`
    (the caller's own responsibility to resolve, mirroring `chummer5.engine.cyberware
    .create_cyberware_selection`); total Essence cost, plus `other_essence_spent` (typically
    cyberware's own already-resolved `essence_spent` -- see module docstring for the fixed
    evaluation order), leaves strictly-positive Essence remaining. Duplicate ids are allowed -- see
    module docstring. Does not require the full nuyen budget to be spent, mirroring every other
    `create_*` function in this engine.
    """
    by_id = {item.id: item for item in catalog}
    ids = list(item_ids)

    unknown = sorted({item_id for item_id in ids if item_id not in by_id})
    if unknown:
        raise ValueError(f"not a bioware catalog id: {unknown}")

    selected = tuple(by_id[item_id] for item_id in ids)

    nuyen_spent = sum(item.cost for item in selected)
    if nuyen_spent > nuyen_budget:
        raise ValueError(f"bioware spend {nuyen_spent} exceeds the nuyen budget of {nuyen_budget}")

    essence_spent = sum((item.essence_cost for item in selected), Decimal(0))
    if essence_spent + other_essence_spent >= BASE_ESSENCE:
        raise ValueError(
            f"bioware Essence cost {essence_spent} would leave no Essence remaining "
            f"(total Essence cost, including {other_essence_spent} already spent elsewhere, must "
            f"stay below {BASE_ESSENCE})"
        )

    return BiowareSelection(
        items=selected,
        nuyen_budget=nuyen_budget,
        nuyen_spent=nuyen_spent,
        essence_spent=essence_spent,
    )


def apply_bioware_improvements(character: Character, selection: BiowareSelection) -> None:
    """Add every purchased item's Essence cost (always) and `FLAT_BONUS`es (if any) to
    `character.improvements`, under `ImprovementSource.BIOWARE` -- mirrors `chummer5.engine
    .cyberware.apply_cyberware_improvements`'s shape exactly, including granting an unconditional
    `ESSENCE` Improvement for every item (even `NOT_YET_SUPPORTED` ones, e.g. Reflex Recorder) and
    sharing one `source_id` (the item's own catalog id) across duplicate purchases of the same item.
    """
    for item in selection.items:
        character.improvements.add(
            Improvement(
                improvement_type=ImprovementType.ESSENCE,
                target=_GLOBAL_TARGET,
                value=0,
                source_type=ImprovementSource.BIOWARE,
                source_id=item.id,
                essence_value=-item.essence_cost,
            )
        )
        for flat_bonus in item.flat_bonuses:
            character.improvements.add(
                Improvement(
                    improvement_type=_TARGET_KIND_TO_IMPROVEMENT_TYPE[flat_bonus.target_kind],
                    target=flat_bonus.target_name,
                    value=flat_bonus.value,
                    source_type=ImprovementSource.BIOWARE,
                    source_id=item.id,
                )
            )
