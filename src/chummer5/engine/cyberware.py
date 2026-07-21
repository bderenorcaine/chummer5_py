"""Cyberware selection & Improvement application (Phase J, WP32).

Composes WP30's Essence mechanism (`chummer5.engine.derived.essence`/`BASE_ESSENCE`) with WP31's
flat-cost, flat-Essence, Standard-grade cyberware catalog (`chummer5.data.cyberware`) and WP6's
`Character` into a buildable cyberware purchase -- mirrors `chummer5.engine.qualities`'s
`create_*_selection`/`apply_*_improvements` shape.

**Nuyen: the same shared Resources-priority budget gear and Lifestyle already draw from --
confirmed, not assumed.** The core rulebook's "Step Six: Spend Your Resources" (p. 94) names
"Cyberware and Bioware" as one of its own subsections, on the same page as the gear/Lifestyle intro
text WP20 already cited for their own shared-budget finding ("This Priority Level determines the
amount of money that characters will have to spend on the gear they'll use ... as well as a place
to crash") -- Cyberware and Bioware is not a separate pool, it's the next subsection of the same
Step Six nuyen figure. `create_cyberware_selection` therefore takes `nuyen_budget` as a plain
parameter -- the caller's responsibility to resolve (typically the Resources letter's nuyen budget
minus whatever gear/Lifestyle already spent), mirroring `chummer5.engine.magic
.create_magic_attribute_points`'s `other_special_attribute_points_spent` parameter for a second
selection validated against one shared budget, rather than this module reaching into
`chummer5.engine.resources.ResourcesSelection` itself. WP34 (the cyberware UI) is where an actual
three-way gear+Lifestyle+cyberware joint budget gets threaded through the web layer -- this module
stays decoupled from `chummer5.engine.resources` even then; `ResourcesSelection`/`create_resources_
selection` gained a `cyberware_cost` parameter instead (mirroring `lifestyle_cost`'s own shape), so
the joint check still lives in one place without either engine module importing the other.

**Duplicate purchases are legal -- confirmed against real fixture data, not assumed.**
`Barrett.chum5` and `Bastion.chum5` (2 of the Phase J intro's 8 real cyberware-bearing fixtures)
each carry two of the same bilateral Cyberlimb item (Barrett: two `Synthetic Full Arm`, two
`Synthetic Full Leg`; Bastion: two `Obvious Full Arm`, two `Obvious Full Leg`) -- a runner with a
matched pair of cyberlimbs is an entirely ordinary SR5 build, not an edge case to reject.
`create_cyberware_selection` allows repeats, mirroring `chummer5.engine.resources
.create_resources_selection`'s identical "repeats allowed" gear-name handling -- unlike
`chummer5.engine.qualities.create_quality_selection`'s one-of-each rule, which qualities need but
cyberware categorically doesn't.

**Essence floor: verified against both the rulebook and the legacy engine, not assumed as "no floor
at all".** Core rulebook p. 51 ("ESSENCE (ESS)"): Essence "acts as a cap on the amount of
alterations you can adopt. When it's gone, it doesn't come back." The legacy engine's own
character-creation validity gate goes further and pins down the exact boundary:
`CharacterCreate.cs`'s `CheckCharacterValidity` has a dedicated "Check if the character's Essence
is above 0" block that rejects the build (`Message_InvalidEssenceExcess`, "{0} over the Essence
limit") whenever resulting Essence would be `<= 0` -- strictly positive, not merely non-negative.
`create_cyberware_selection` enforces the same floor at selection time (rather than only at a
later, separate "is this character still valid" pass this project hasn't built).

**WP45 widens the floor check with `other_essence_spent`.** Through WP44, cyberware was the only
Essence-reducing source this project modeled, so comparing this selection's own Essence cost
against `chummer5.engine.derived.BASE_ESSENCE` directly was equivalent to checking the character's
resulting `essence()` -- flagged in this module's own WP32-era docstring as something "a future WP
that adds a second Essence-reducing source (bioware, if ever built) would need to widen ... to take
the character's pre-purchase Essence as an input instead." WP45 is that widening: `other_essence_
spent` defaults to `Decimal(0)` (every pre-WP45 call site, unaffected), and a caller building both
selections passes the *other* one's already-resolved `essence_spent` in, mirroring `chummer5.engine
.magic.create_magic_attribute_points`'s `other_special_attribute_points_spent` parameter for the
same "two selections, one shared budget, resolved by the caller" shape. `chummer5.engine.bioware
.create_bioware_selection` is the mirror image, taking cyberware's `essence_spent` the same way --
see that module's own docstring for the fixed evaluation order (cyberware first, unaware of
bioware; bioware second, aware of cyberware) this project settled on.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal

from chummer5.data.cyberware import Cyberware
from chummer5.engine.character import Character
from chummer5.engine.derived import BASE_ESSENCE
from chummer5.engine.improvements import Improvement, ImprovementSource, ImprovementType

# CyberwareFlatBonus.target_kind -> ImprovementType. Only one kind exists in WP31's catalog today
# (the Cyberlimb condition-monitor bonus) -- see chummer5.data.cyberware's module docstring.
_TARGET_KIND_TO_IMPROVEMENT_TYPE = {
    "physical_cm": ImprovementType.PHYSICAL_CM,
}

# Every ImprovementType this module produces resolves against a single, character-wide total (there
# is only one Essence pool, one Physical CM per character) -- the same _GLOBAL_TARGET sentinel
# chummer5.engine.derived already resolves both of these against.
_GLOBAL_TARGET = ""


@dataclass(frozen=True)
class CyberwareSelection:
    """A validated set of purchased cyberware items and their combined nuyen/Essence cost.

    `items` may contain the same `Cyberware` more than once -- see module docstring for why
    duplicate purchases (e.g. a matched pair of cyberlimbs) are legal, unlike a quality/power pick.
    """

    items: tuple[Cyberware, ...]
    nuyen_budget: int
    nuyen_spent: int
    essence_spent: Decimal


def create_cyberware_selection(
    item_ids: Iterable[str],
    catalog: Iterable[Cyberware],
    nuyen_budget: int,
    *,
    other_essence_spent: Decimal = Decimal(0),
) -> CyberwareSelection:
    """Build a `CyberwareSelection`, validating nuyen spend and the Essence floor together.

    Validates: every id resolves against `catalog`; total nuyen cost doesn't exceed `nuyen_budget`
    (the caller's own responsibility to resolve -- see module docstring); total Essence cost, plus
    `other_essence_spent` (WP45 -- another selection's already-resolved Essence cost sharing the
    same pool, e.g. bioware; `Decimal(0)` for every pre-WP45 caller), leaves strictly-positive
    Essence remaining, per the rulebook/legacy-validity floor cited in the module docstring.
    Duplicate ids are allowed -- see module docstring. Does not require the full nuyen budget to be
    spent, mirroring every other `create_*` function in this engine.
    """
    by_id = {item.id: item for item in catalog}
    ids = list(item_ids)

    unknown = sorted({item_id for item_id in ids if item_id not in by_id})
    if unknown:
        raise ValueError(f"not a cyberware catalog id: {unknown}")

    selected = tuple(by_id[item_id] for item_id in ids)

    nuyen_spent = sum(item.cost for item in selected)
    if nuyen_spent > nuyen_budget:
        raise ValueError(
            f"cyberware spend {nuyen_spent} exceeds the nuyen budget of {nuyen_budget}"
        )

    essence_spent = sum((item.essence_cost for item in selected), Decimal(0))
    if essence_spent + other_essence_spent >= BASE_ESSENCE:
        raise ValueError(
            f"cyberware Essence cost {essence_spent} would leave no Essence remaining "
            f"(total Essence cost, including {other_essence_spent} already spent elsewhere, must "
            f"stay below {BASE_ESSENCE})"
        )

    return CyberwareSelection(
        items=selected,
        nuyen_budget=nuyen_budget,
        nuyen_spent=nuyen_spent,
        essence_spent=essence_spent,
    )


def apply_cyberware_improvements(character: Character, selection: CyberwareSelection) -> None:
    """Add every purchased item's Essence cost (always) and `FLAT_BONUS`es (if any) to
    `character.improvements`.

    Mirrors `chummer5.engine.qualities.apply_quality_improvements`'s shape, with one addition none
    of the prior `apply_*_improvements` functions needed: **every** selected item grants an
    `ESSENCE` Improvement unconditionally (`essence_value=-item.essence_cost`), not just items with
    a recognized `<bonus>` -- Essence cost is real content for all 60 catalog items, `FLAT_BONUS`
    for only 8 of them (see `chummer5.data.cyberware`'s module docstring).

    `source_id` is the item's own catalog id -- **not** made unique per purchase when the same item
    is bought twice (see module docstring's "duplicate purchases are legal" paragraph). This means
    `ImprovementIndex.remove_source(ImprovementSource.CYBERWARE, item.id)` retracts every copy of a
    repeated item at once, not one at a time. This project has no chargen-time "remove a single
    cyberware purchase, keep its twin" use case (unlike a quality/power, which is always bought at
    most once), so this is a deliberate, harmless simplification, not an oversight.
    """
    for item in selection.items:
        character.improvements.add(
            Improvement(
                improvement_type=ImprovementType.ESSENCE,
                target=_GLOBAL_TARGET,
                value=0,
                source_type=ImprovementSource.CYBERWARE,
                source_id=item.id,
                essence_value=-item.essence_cost,
            )
        )
        for flat_bonus in item.flat_bonuses:
            character.improvements.add(
                Improvement(
                    improvement_type=_TARGET_KIND_TO_IMPROVEMENT_TYPE[flat_bonus.target_kind],
                    target=_GLOBAL_TARGET,
                    value=flat_bonus.value,
                    source_type=ImprovementSource.CYBERWARE,
                    source_id=item.id,
                )
            )
