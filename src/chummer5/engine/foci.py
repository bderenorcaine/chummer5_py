"""Foci: bonding purchase, nuyen/Karma budget, and the FLAT_BONUS skill bonus (Phase M, WP47).

Composes WP47's `chummer5.data.foci` catalog with WP6's `Character` into a buildable
focus-bonding purchase. **A new module, not folded into `chummer5.engine.magic`** -- mirrors
`chummer5.engine.spirits`'s own precedent (WP46): `magic.py` already covers Magic
type/rating/tradition, the Talent free-skill grant, spells, and powers, and Foci is its own
self-contained SR5 chargen decision.

**Gate: any magic-active character, not Magician-only.** Unlike Bound Spirits (Magician-only,
since conjuring is what makes spirit types offered at all -- see `chummer5.engine.spirits`'s own
docstring), bonding a focus only requires being Awakened at all (core rulebook, "Foci", p. 317:
"you can't bond foci unless you're Awakened") -- an Adept can bond a focus exactly as legally as
a Magician, even though most focus categories' real bonus targets a Magician-only test this
engine doesn't compute anyway (see `chummer5.data.foci`'s own docstring for the per-category
breakdown). `create_foci_selection` therefore gates on `character.magic_type is not None`, not
`is "Magician"`.

**Two caps, both real and both enforced together -- not just the chargen-specific one.** Core
rulebook p. 317 states the *general/lifetime* rule ("You can't bond more foci than your Magic
attribute, and the maximum Force of all your bonded foci can't exceed your Magic x 5"); Step
Seven's own Additional Purchases table (p. 98) narrows the *total-Force* half specifically "at
character creation" to Magic x 2 -- the tighter number this WP must use (see the Implementation
Plan's own WP47 intro for why reading only the general rule would be a real, documented trap).
The *count* cap (<= Magic rating) is not overridden by that same table and is not
chargen-specific, so it still applies unchanged. `create_foci_selection` enforces both:
`len(picks) <= character.attribute_value("MAG")` and `total_force <= character.attribute_value
("MAG") * CHARGEN_FORCE_CAP_MULTIPLIER`.

**Availability >12 exclusion applied per-pick, not per-catalog-item.** See `chummer5.data.foci`'s
own docstring for why a static loader-level cutoff can't work here (every item's Availability
scales with the Force chosen at bonding time). `create_foci_selection` rejects a pick whose
`force * availability_per_force` exceeds `MAX_AVAILABILITY`, applying this project's 2026-07-21
Availability ruling at the one point it can actually be checked -- against the specific Force a
player picked, not a fixed catalog value.

**Karma shares the same pool Bound Spirits draws from -- `Character.karma_remaining` (Phase O's
unified ledger, WP51).** Both are Karma-costing Magic-only chargen extras. Neither
`create_bound_spirit_selection` nor `create_foci_selection` chains into the other's own call the
way `create_bioware_selection` takes cyberware's `essence_spent` directly -- each just takes a
caller-resolved `karma_budget: int`. That still leaves two different contexts with two different
correct answers for who resolves in what order:

- **A one-shot reconstruction from scratch (`chummer5.io.save_format.build_character`) needs a
  fixed order**, the same reason cyberware/bioware do: both selections are being validated for
  the first time together, so *something* has to go first. Bound Spirits resolves first, unaware
  of Foci (unchanged from WP46 -- its own `karma_budget` call doesn't gain a `foci_karma_cost`
  term); Foci resolves second, aware of Bound Spirits' own already-computed `karma_cost`. This is
  the only way to guarantee the *combined* spend never exceeds the pool -- computing each
  against an unreserved budget independently would let both "fit" on their own while jointly
  overspending.
- **Interactive re-validation of an already-committed selection (the web layer's per-section
  `_X_selection_context` staleness check) is symmetric instead**, since both selections already
  have a fixed, known cost at render time: `_spirit_selection_context` reads
  `character.foci_selection.karma_cost` and `_foci_selection_context` reads
  `character.bound_spirit_selection.karma_cost`, each accounting for the other's *current*
  commitment the same way the nuyen budget's gear/Lifestyle/cyberware/bioware sections already
  read each other's committed spend.

**Nuyen shares the same Step Six pool gear/Lifestyle/cyberware/bioware already draw from.** Step
Seven's own Additional Purchases table lists "Bond Foci" nuyen cost as "Variable; see p. 318" --
p. 318's Focus Table is the *Karma* bonding cost, not nuyen; a focus's nuyen cost is its own
`<cost>` (`chummer5.data.foci.Focus.cost_per_force * force`), paid like any other Step Six
purchase -- `chummer5.engine.resources.create_resources_selection` gains a `foci_cost` parameter
alongside `cyberware_cost`/`bioware_cost`, the same "fold into the one joint over-budget check"
shape every prior Step Six purchase already has.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from chummer5.data.foci import FOCUS_MAX_RATING, BonusSupport, Focus
from chummer5.engine.character import Character
from chummer5.engine.improvements import Improvement, ImprovementSource, ImprovementType

# Step Seven's own Additional Purchases table (p. 98): "Maximum total Force of all foci that can
# be bonded at character creation is equal to character's Magic Rating x 2" -- the
# *chargen-specific* total-Force cap, tighter than the general/lifetime "Magic x 5" rule (p. 317).
# See module docstring.
CHARGEN_FORCE_CAP_MULTIPLIER = 2

# Project Overview's 2026-07-21 ruling: exclude Availability > 12 from any new catalog. Applied here
# per-pick (force * availability_per_force), not per-catalog-item -- see chummer5.data.foci's module
# docstring for why a static loader-level cutoff can't work for a Rating-scaled Availability.
MAX_AVAILABILITY = 12

_TARGET_KIND_TO_IMPROVEMENT_TYPE = {
    "skill": ImprovementType.SKILL,
}


@dataclass(frozen=True)
class FocusPick:
    """One bonded focus: which catalog item, at what Force (player-chosen, unlike Bound Spirits'
    fixed-to-Magic Force -- a focus's Force is whatever the player pays nuyen/Karma for, capped as
    above)."""

    focus: Focus
    force: int


@dataclass(frozen=True)
class FociSelection:
    """A validated set of bonded foci and their combined nuyen/Karma cost."""

    picks: tuple[FocusPick, ...]
    nuyen_cost: int
    karma_cost: int
    nuyen_budget: int
    karma_budget: int


def create_foci_selection(
    picks: Iterable[tuple[str, int]],
    character: Character,
    catalog: Iterable[Focus],
    nuyen_budget: int,
    karma_budget: int,
) -> FociSelection:
    """Build a `FociSelection`, validating `picks` (`(focus_id, force)` pairs) together.

    Validates: an empty `picks` is always fine, for any character (mirrors
    `create_bound_spirit_selection`'s identical "no gate until there's actually something to
    check" shape); non-empty `picks` requires `character.magic_type is not None` (Magician or
    Adept -- see module docstring for why this is looser than Bound Spirits' Magician-only gate);
    every `focus_id` resolves against `catalog`; every `force` is between 1 and
    `chummer5.data.foci.FOCUS_MAX_RATING`; the number of picks doesn't exceed
    `character.attribute_value("MAG")`; the summed Force doesn't exceed Magic x
    `CHARGEN_FORCE_CAP_MULTIPLIER`; each pick's resolved Availability (`force *
    availability_per_force`) doesn't exceed `MAX_AVAILABILITY`; and the summed nuyen/Karma cost
    each stay within their own budget. Does not require either budget fully spent, or every
    Charisma/Magic slot filled, mirroring every other `create_*` function in this engine. Bonding
    two foci of the same catalog item (at the same or different Force) is allowed -- no rulebook
    rule forbids it, the same "repeats allowed" default `chummer5.engine.{cyberware,bioware}`
    already use.
    """
    entries = list(picks)
    if not entries:
        return FociSelection(
            picks=(),
            nuyen_cost=0,
            karma_cost=0,
            nuyen_budget=nuyen_budget,
            karma_budget=karma_budget,
        )

    if character.magic_type is None:
        raise ValueError(
            "Foci can only be bonded by a magically active (Magician or Adept) character"
        )

    by_id = {f.id: f for f in catalog}
    unknown = sorted({focus_id for focus_id, _ in entries if focus_id not in by_id})
    if unknown:
        raise ValueError(f"not a Foci catalog id: {unknown}")

    max_count = character.attribute_value("MAG")
    if len(entries) > max_count:
        raise ValueError(f"{len(entries)} foci selected, exceeding the Magic limit of {max_count}")

    force_cap = max_count * CHARGEN_FORCE_CAP_MULTIPLIER
    resolved: list[FocusPick] = []
    total_force = 0
    nuyen_cost = 0
    karma_cost = 0
    for focus_id, force in entries:
        focus = by_id[focus_id]
        if force < 1 or force > FOCUS_MAX_RATING:
            raise ValueError(
                f"{focus.name!r}: Force must be between 1 and {FOCUS_MAX_RATING}, got {force}"
            )
        availability = force * focus.availability_per_force
        if availability > MAX_AVAILABILITY:
            raise ValueError(
                f"{focus.name!r} at Force {force}: Availability {availability} exceeds "
                f"{MAX_AVAILABILITY}"
            )
        resolved.append(FocusPick(focus=focus, force=force))
        total_force += force
        nuyen_cost += force * focus.cost_per_force
        karma_cost += force * focus.bonding_karma_per_force

    if total_force > force_cap:
        raise ValueError(
            f"total bonded Force {total_force} exceeds the character-creation cap of {force_cap} "
            f"(Magic {max_count} x {CHARGEN_FORCE_CAP_MULTIPLIER})"
        )
    if nuyen_cost > nuyen_budget:
        raise ValueError(f"Foci nuyen cost {nuyen_cost} exceeds the nuyen budget of {nuyen_budget}")
    if karma_cost > karma_budget:
        raise ValueError(f"Foci Karma cost {karma_cost} exceeds the Karma budget of {karma_budget}")

    return FociSelection(
        picks=tuple(resolved),
        nuyen_cost=nuyen_cost,
        karma_cost=karma_cost,
        nuyen_budget=nuyen_budget,
        karma_budget=karma_budget,
    )


def apply_foci_improvements(character: Character, selection: FociSelection) -> None:
    """Add every bonded focus's `FLAT_BONUS` skill bonus (if any) to `character.improvements`,
    under `ImprovementSource.FOCUS` -- mirrors `chummer5.engine.magic.apply_power_improvements`'s
    "value is the purchased pick's own magnitude, not a stored int" shape: `value` is always
    `pick.force` (the literal `"Rating"` token in the raw data resolves to the bonded Force, per
    `chummer5.data.foci`'s own docstring). `source_id` is the focus's own catalog id, so two
    bonded copies of the same item (at possibly different Force) would collide under
    `ImprovementIndex.remove_source` -- acceptable here for the same reason
    `chummer5.engine.cyberware`'s duplicate-purchase precedent already accepts sharing one
    `source_id` across repeats (removal always retracts every copy at once, never partially).
    """
    for pick in selection.picks:
        if pick.focus.bonus_support != BonusSupport.FLAT_BONUS:
            continue
        for flat_bonus in pick.focus.flat_bonuses:
            character.improvements.add(
                Improvement(
                    improvement_type=_TARGET_KIND_TO_IMPROVEMENT_TYPE[flat_bonus.target_kind],
                    target=flat_bonus.target_name,
                    value=pick.force,
                    source_type=ImprovementSource.FOCUS,
                    source_id=pick.focus.id,
                )
            )
