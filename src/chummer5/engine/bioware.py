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
cyberlimb-pair finding was. **WP80 turns it into a verified one for `Reflex Recorder`
specifically** -- p. 460: "Multiple recorders may be taken for multiple skills, but you can't
implant two reflex recorders for the same skill" -- which is also the first SR5 rule this engine
has that constrains *which* duplicates are legal, rather than whether duplicates are.

**WP80: a purchase is a `BiowarePurchaseRequest`, not a bare id, because one row needs a player
choice.** `Reflex Recorder`'s `<bonus>` is a `<selectskill>` (see `chummer5.data.bioware`'s
docstring): the catalog says a pick is required and what it may be, and the *purchase* carries the
pick. Two consequences worth stating once:

- **Per purchase, not per catalog row.** The pick can't live in a `{item_id: skill}` mapping the
  way WP55's former `QualitySelection.quality_text` did, because bioware can be bought repeatedly
  (WP107 later moved quality text onto per-instance `QualityPick`s for the same reason) -- and
  p. 460 explicitly contemplates buying several recorders for several skills (`cyberware.xml`'s
  own LCD-sourced implant packages bundle two, forced to `Locksmith` and `Pistols`).
  Hence `BiowarePurchase`, one per bought unit.
- **A bare id is still accepted** wherever no choice is involved: `create_bioware_selection` takes
  `Iterable[str | BiowarePurchaseRequest]` and reads a plain string as "this item, no player
  choice." That is a total, well-defined meaning rather than a placeholder (5 of the 6 offered rows
  have no choice to make), so it keeps every pre-WP80 caller correct instead of rewriting them into
  a shape carrying a permanent `chosen_skill=None`. An id for a row that *does* require a pick is
  rejected, loudly, by the same validation a `BiowarePurchaseRequest(chosen_skill=None)` hits.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass, replace
from decimal import Decimal

from chummer5.data.bioware import Bioware
from chummer5.data.grades import STANDARD_GRADE, implant_grade
from chummer5.data.skills import Skill
from chummer5.engine.character import Character
from chummer5.engine.cyberware import cyberware_bonus_improvements
from chummer5.engine.derived import BASE_ESSENCE
from chummer5.engine.improvements import Improvement, ImprovementSource, ImprovementType
from chummer5.engine.resources import MAX_AVAILABILITY

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
class BiowarePurchaseRequest:
    """One requested bioware purchase (WP80): a catalog id, plus the player's skill pick for the
    rows that need one (`Reflex Recorder`; `None` for every other row).

    The unresolved, persistable half of a purchase -- exactly what `chummer5.io.save_format
    .CharacterSave.bioware_purchases` stores and what a web form/legacy import produces, mirroring
    `chummer5.engine.cyberware_subsystems.CyberwarePurchaseRequest`'s identical split between a
    request and its resolved form.
    """

    item_id: str
    chosen_skill: str | None = None
    grade: str = STANDARD_GRADE  # WP127: Standard, Alphaware or Used (p. 451)
    rating: int = 1  # WP128: a rated row's purchased rating; 1 for every flat row


@dataclass(frozen=True)
class BiowarePurchase:
    """One resolved bioware purchase: the catalog row, and the player's pick if it needed one.

    WP127: `grade` scales `nuyen_cost` and `essence_cost` (p. 451); read those, not the catalog
    row's own Standard-grade `cost`/`essence_cost`.
    """

    item: Bioware
    chosen_skill: str | None = None
    grade: str = STANDARD_GRADE
    rating: int = 1  # WP128

    @property
    def nuyen_cost(self) -> int:
        return implant_grade(self.grade).nuyen(self.item.cost_at(self.rating))

    @property
    def essence_cost(self) -> Decimal:
        return self.item.essence_at(self.rating) * implant_grade(self.grade).essence_multiplier


@dataclass(frozen=True)
class BiowareSelection:
    """A validated set of purchased bioware items and their combined nuyen/Essence cost.

    `purchases` may contain the same `Bioware` more than once -- see module docstring for why
    duplicate purchases are allowed (a consistency choice, not a separately-verified rule the way
    cyberware's own was) and for the one SR5 rule constraining *which* duplicates are legal.

    `items` is the purchased rows without their picks, kept as a property (WP80) so every consumer
    that only wants "what did this character buy" -- the character sheet's recap,
    `chummer5.engine.derived.unmodeled_effect_notes`, the web layer's Improvement swap -- reads
    the same way it did before purchases grew a second field.
    """

    purchases: tuple[BiowarePurchase, ...]
    nuyen_budget: int
    nuyen_spent: int
    essence_spent: Decimal

    @property
    def items(self) -> tuple[Bioware, ...]:
        return tuple(purchase.item for purchase in self.purchases)

    def to_requests(self) -> tuple[BiowarePurchaseRequest, ...]:
        """The persistable inverse of `create_bioware_selection`'s input (WP80) -- mirrors
        `chummer5.engine.cyberware_subsystems.CyberwareTreeSelection.to_requests`."""
        return tuple(
            BiowarePurchaseRequest(
                item_id=purchase.item.id,
                chosen_skill=purchase.chosen_skill,
                grade=purchase.grade,
                rating=purchase.rating,
            )
            for purchase in self.purchases
        )


def select_skill_choices(item: Bioware, skills: Iterable[Skill]) -> tuple[Skill, ...]:
    """Every active skill a `SELECT_SKILL` row's pick may legally be (WP80), name-sorted.

    `()` for a row with no pick to make. The row's `limittoattribute` filter is the only restriction
    SR5 states (p. 460: "a specific skill linked to a Physical attribute"), so this deliberately
    does *not* narrow further -- an untrained skill is a legal pick (the recorder raises its Rating
    from 0 to 1), and so are the three Exotic skills, which the filter itself doesn't exclude.

    Shared by the browser picker and `chummer5.io.legacy_import`, so "what may be chosen" and "what
    is accepted" can't drift apart.
    """
    bonus = item.select_skill_bonus
    if bonus is None:
        return ()
    return tuple(
        sorted(
            (skill for skill in skills if skill.attribute in bonus.limit_to_attributes),
            key=lambda skill: skill.name,
        )
    )


def augmentation_names(character: Character, cyberware_names: Iterable[str] = ()) -> frozenset[str]:
    """The names a bioware row's `incompatible_names` is checked against (WP128): `cyberware_names`
    (the cyberware tree being committed with it), plus the character's qualities and adept
    powers."""
    names = set(cyberware_names)
    if character.quality_selection is not None:
        names |= {pick.quality.name for pick in character.quality_selection.qualities}
    if character.power_selection is not None:
        names |= {pick.power.name for pick in character.power_selection.picks}
    return frozenset(names)


def purchased_grades(selection: BiowareSelection | None) -> frozenset[tuple[str, str]]:
    """Every `(item id, grade)` the character already has (WP127) -- `availability_exempt`."""
    if selection is None:
        return frozenset()
    return frozenset((p.item.id, p.grade) for p in selection.purchases)


def bioware_grade_offered(item: Bioware, grade: str) -> bool:
    """Whether `item` may be newly bought at `grade` (WP127): its Availability, shifted by the
    grade, stays within 12 (at rating 1, for a rated row). The offered catalog is already within
    12 at Standard grade."""
    if grade == STANDARD_GRADE:
        return True
    return item.availability + implant_grade(grade).availability_modifier <= MAX_AVAILABILITY


def bioware_rating_maximum(item: Bioware, grade: str = STANDARD_GRADE) -> int:
    """The highest rating `item` may be newly bought at (WP128): its printed maximum, lowered to
    stay within Availability 12 at `grade` (WP126's cap) -- Muscle Toner `(Rating x 5)R` stops at
    2. 1 for a flat row."""
    if item.max_rating is None:
        return 1
    modifier = implant_grade(grade).availability_modifier
    fitting = [
        rating
        for rating in range(1, item.max_rating + 1)
        if item.availability_at(rating) + modifier <= MAX_AVAILABILITY
    ]
    return max(fitting, default=1)


def _checked_rating(item: Bioware, rating: int) -> int:
    maximum = item.max_rating or 1
    if not 1 <= rating <= maximum:
        raise ValueError(f"{item.name}: rating {rating} is outside its range 1-{maximum}")
    return rating


def _as_request(purchase: str | BiowarePurchaseRequest) -> BiowarePurchaseRequest:
    """A bare catalog id means "this item, no player choice" -- see module docstring (WP80)."""
    return BiowarePurchaseRequest(item_id=purchase) if isinstance(purchase, str) else purchase


def _resolve_chosen_skill(
    item: Bioware, chosen_skill: str | None, skills_by_name: Mapping[str, Skill]
) -> str | None:
    """Validate one purchase's skill pick against its catalog row (WP80).

    Returns the pick to store (`None` for a row that needs none). Raises `ValueError` when a row
    that requires a pick has none, when a row that requires none has one (the "don't silently
    ignore a stale/tampered field" rule `create_quality_selection` applies to a pick's text), or
    when the pick isn't an active skill whose linked attribute passes the row's own
    `limittoattribute` filter.
    """
    bonus = item.select_skill_bonus
    if bonus is None:
        if chosen_skill is not None:
            raise ValueError(
                f"a skill was chosen for {item.name!r}, which has no skill to choose: "
                f"{chosen_skill!r}"
            )
        return None
    if chosen_skill is None or not chosen_skill.strip():
        raise ValueError(f"{item.name} requires a chosen skill")
    name = chosen_skill.strip()
    skill = skills_by_name.get(name)
    if skill is None:
        raise ValueError(f"not an active skill: {name!r}")
    if skill.attribute not in bonus.limit_to_attributes:
        raise ValueError(
            f"{item.name}: {skill.name} is linked to {skill.attribute}, not one of "
            f"{', '.join(bonus.limit_to_attributes)}"
        )
    return name


def bioware_disabled(character: Character) -> bool:
    """Whether the character may hold no bioware (WP117): Sensitive System."""
    return character.improvements.resolve(ImprovementType.BIOWARE_DISABLED, "") > 0


def create_bioware_selection(
    purchases: Iterable[str | BiowarePurchaseRequest],
    catalog: Iterable[Bioware],
    nuyen_budget: int,
    *,
    other_essence_spent: Decimal = Decimal(0),
    skills: Iterable[Skill] = (),
    bioware_disabled: bool = False,
    availability_exempt: AbstractSet[tuple[str, str]] | None = None,
    other_augmentations: AbstractSet[str] = frozenset(),
) -> BiowareSelection:
    """Build a `BiowareSelection`, validating nuyen spend and the (shared) Essence floor together.

    Validates: every id resolves against `catalog`; total nuyen cost doesn't exceed `nuyen_budget`
    (the caller's own responsibility to resolve, mirroring `chummer5.engine.cyberware
    .create_cyberware_selection`); total Essence cost, plus `other_essence_spent` (typically
    cyberware's own already-resolved `essence_spent` -- see module docstring for the fixed
    evaluation order), leaves strictly-positive Essence remaining. Duplicate ids are allowed -- see
    module docstring. Does not require the full nuyen budget to be spent, mirroring every other
    `create_*` function in this engine.

    **WP80**: each purchase may be a bare id or a `BiowarePurchaseRequest` (see module docstring).
    A `BonusSupport.SELECT_SKILL` row (`Reflex Recorder`) additionally requires a `chosen_skill`
    that resolves against `skills` and passes its own `limittoattribute` filter, and no two such
    purchases may name the same skill (p. 460: "you can't implant two reflex recorders for the same
    skill"). `skills` defaults to `()` -- the same "a caller with nothing to resolve passes
    nothing" shape `build_character`'s own optional catalogs use -- so buying a row that needs a
    pick without supplying a skill catalog fails as an unresolvable pick rather than silently
    skipping the check.

    **WP117**: `bioware_disabled` (Sensitive System, see `bioware_disabled()`) rejects any purchase.

    **WP127**: each request's `grade` scales its nuyen and Essence (p. 451). With
    `availability_exempt` set (the web route passes `purchased_grades` of what the character
    already has), a new pick whose grade's Availability shift takes the item over 12 is rejected
    -- an Alphaware row printed at 11. `None` (save loading, legacy import) skips the check, as
    WP126's cyberware cap does.

    **WP128**: a rated row's request names its `rating` (1 to the row's maximum, and within
    Availability 12 at its grade for a new pick); a rated row is bought at most once -- a second
    Cerebral Booster is a higher rating, not a second implant. `other_augmentations` is the
    character's cyberware, quality and power names: a row whose `incompatible_names` meets it is
    rejected (Orthoskin with Dermal Plating, a Synaptic Booster with Wired Reflexes, ...).
    """
    by_id = {item.id: item for item in catalog}
    requests = [_as_request(purchase) for purchase in purchases]
    if requests and bioware_disabled:
        # WP117, p. 83: "Bioware implants [...] are rejected by the character's body."
        raise ValueError("Sensitive System: the character's body rejects every bioware implant")

    unknown = sorted({r.item_id for r in requests if r.item_id not in by_id})
    if unknown:
        raise ValueError(f"not a bioware catalog id: {unknown}")

    skills_by_name = {skill.name: skill for skill in skills}
    resolved = tuple(
        BiowarePurchase(
            item=by_id[r.item_id],
            chosen_skill=_resolve_chosen_skill(by_id[r.item_id], r.chosen_skill, skills_by_name),
            grade=implant_grade(r.grade).name,
            rating=_checked_rating(by_id[r.item_id], r.rating),
        )
        for r in requests
    )
    rated_seen: set[str] = set()
    names = {purchase.item.name for purchase in resolved}
    for purchase in resolved:
        item = purchase.item
        if item.is_rated:
            if item.id in rated_seen:
                raise ValueError(f"{item.name} is bought once, at the rating wanted")
            rated_seen.add(item.id)
        clash = sorted(set(item.incompatible_names) & (set(other_augmentations) | names))
        if clash:
            raise ValueError(f"{item.name} can't be combined with {', '.join(clash)}")
    if availability_exempt is not None:
        for purchase in resolved:
            if (purchase.item.id, purchase.grade) in availability_exempt:
                continue
            if not bioware_grade_offered(purchase.item, purchase.grade):
                raise ValueError(
                    f"{purchase.item.name}: {purchase.grade} grade is over Availability 12 at "
                    "character creation"
                )
            maximum = bioware_rating_maximum(purchase.item, purchase.grade)
            if purchase.rating > maximum:
                raise ValueError(
                    f"{purchase.item.name}: rating {purchase.rating} is over Availability 12 at "
                    f"character creation (the highest at {purchase.grade} grade is {maximum})"
                )

    # p. 460: multiple recorders are legal, one per skill. Checked per (item, skill) rather than per
    # skill overall, since the rule is about implanting two of *the same* item for one skill.
    picks_seen: set[tuple[str, str]] = set()
    for purchase in resolved:
        if purchase.chosen_skill is None:
            continue
        pick = (purchase.item.id, purchase.chosen_skill)
        if pick in picks_seen:
            raise ValueError(
                f"two {purchase.item.name} purchases both chose {purchase.chosen_skill} -- "
                "only one per skill is allowed"
            )
        picks_seen.add(pick)

    nuyen_spent = sum(purchase.nuyen_cost for purchase in resolved)
    if nuyen_spent > nuyen_budget:
        raise ValueError(f"bioware spend {nuyen_spent} exceeds the nuyen budget of {nuyen_budget}")

    essence_spent = sum((purchase.essence_cost for purchase in resolved), Decimal(0))
    if essence_spent + other_essence_spent >= BASE_ESSENCE:
        raise ValueError(
            f"bioware Essence cost {essence_spent} would leave no Essence remaining "
            f"(total Essence cost, including {other_essence_spent} already spent elsewhere, must "
            f"stay below {BASE_ESSENCE})"
        )

    return BiowareSelection(
        purchases=resolved,
        nuyen_budget=nuyen_budget,
        nuyen_spent=nuyen_spent,
        essence_spent=essence_spent,
    )


def apply_bioware_improvements(character: Character, selection: BiowareSelection) -> None:
    """Add every purchased item's Essence cost (always), its `FLAT_BONUS`es (if any) and its
    `SELECT_SKILL` bonus against the player's own pick (WP80) to `character.improvements`, under
    `ImprovementSource.BIOWARE` -- mirrors `chummer5.engine.cyberware
    .apply_cyberware_improvements`'s shape exactly, including granting an unconditional `ESSENCE`
    Improvement for every item (even
    `NOT_YET_SUPPORTED` ones) and sharing one `source_id` (the item's own catalog id) across
    duplicate purchases of the same item.

    Two `Reflex Recorder`s sharing that one `source_id` is correct rather than a collision: they
    target *different* skills (`create_bioware_selection` rejects two picking the same one), so
    they resolve independently, and `ImprovementIndex.remove_source` still retracts both at once --
    which is exactly what the web layer's own "swap this source's Improvements" step wants.
    """
    for purchase in selection.purchases:
        item = purchase.item
        character.improvements.add(
            Improvement(
                improvement_type=ImprovementType.ESSENCE,
                target=_GLOBAL_TARGET,
                value=0,
                source_type=ImprovementSource.BIOWARE,
                source_id=item.id,
                essence_value=-purchase.essence_cost,  # WP127: at its grade
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
        # WP128: a rated row's Rating-valued bonuses, through cyberware's translator (the same
        # classifier produced them), re-sourced as bioware.
        for improvement in cyberware_bonus_improvements(
            item_id=item.id,
            item_name=item.name,
            flat_bonuses=item.rated_bonuses,
            conditional_bonuses=(),
            rating=purchase.rating,
        ):
            character.improvements.add(replace(improvement, source_type=ImprovementSource.BIOWARE))
        # WP80: the SELECT_SKILL bonus, aimed at the player's own pick. p. 460 says the recorder
        # "adds 1 to the Rating of a specific skill", so this is ImprovementType.SKILL (a rating
        # bonus), not a dice-pool modifier -- see chummer5.data.bioware's docstring.
        if item.select_skill_bonus is not None and purchase.chosen_skill is not None:
            character.improvements.add(
                Improvement(
                    improvement_type=ImprovementType.SKILL,
                    target=purchase.chosen_skill,
                    value=item.select_skill_bonus.value,
                    source_type=ImprovementSource.BIOWARE,
                    source_id=item.id,
                )
            )
