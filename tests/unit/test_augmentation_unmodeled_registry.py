"""WP77: pins every `NOT_YET_SUPPORTED` augmentation row to one of the two buckets that WP's audit
split them into, so the gap it closed cannot silently reopen.

The gap: a cyberware/bioware row whose `<bonus>` classifies `NOT_YET_SUPPORTED` is still offered
(WP31/WP45's deliberate "the Essence/nuyen cost is real content on its own" choice, see
`chummer5.data.cyberware`'s docstring) and grants nothing. That is only acceptable under the Project
Overview's 2026-07-24 policy when the unmodeled effect is genuinely outside this engine's scope
*and* recorded in its "Unmodeled real effects" registry. WP77's audit found both cases in the same
`NOT_YET_SUPPORTED` bucket, and this file is what keeps them apart:

- `REGISTERED_UNMODELED` -- effects this engine has no representation of at all (armor totals,
  attack tests, skillsofts, toxin resistance). Registry rows, added to the Project Overview by WP77.
- `WP78_SCOPE` -- effects this engine *can* compute today (attribute, Initiative Dice and skill
  bonuses). Not registry material: registering them would launder a policy violation into an
  accepted gap. WP78 is the WP that models them.

**Why a test rather than the one-off check WP77's entry allowed as an alternative.** The failure
mode is a *future* catalog widening (WP42's UI, or any later `<bonus>` grammar change) quietly
adding a row to either bucket, which a one-off check run in 2026 cannot catch. The names below are
literal rather than read from the markdown table for the same reason
`chummer5.data.qualities._UNMODELED_EFFECT_NOTES` is a dict and not a parsed table -- see
`chummer5.engine.derived.unmodeled_effect_notes`' docstring: the registry is documentation, mirrored
into code by hand, never read from disk at runtime.

A new `NOT_YET_SUPPORTED` row therefore fails this file until somebody decides, deliberately, which
bucket it belongs in.
"""

from __future__ import annotations

from chummer5.data.bioware import load_bioware
from chummer5.data.cyberware import BonusSupport, load_cyberware
from chummer5.data.cyberware_subsystems import load_cyberware_entries

CYBERWARE_ENTRIES = load_cyberware_entries()  # all 87 SR5 rows (WP37) -- the engine's catalog
FLAT_CYBERWARE = load_cyberware()  # the 60 flat rows the browser picker offers (WP31)
BIOWARE = load_bioware()  # the 6 offered bioware rows (WP45)

# The 10 rows WP77 added to the Project Overview's "Unmodeled real effects" table, as 8 table rows
# (Bone Lacing's 3 variants share one, differing only in magnitude -- the same grouping the registry
# already uses for `Customized Agility / Customized Strength`).
REGISTERED_UNMODELED = frozenset(
    {
        "Bone Lacing (Plastic)",
        "Bone Lacing (Aluminum)",
        "Bone Lacing (Titanium)",
        "Smartlink",
        "Damper",
        "Dermal Plating",
        "Armor",  # the Cyberlimb Enhancement, not a gear/armor item
        "Internal Air Tank",
        "Skillwires",
        "Skilljack",
    }
)

# WP77's Bucket A: a `<bonus>` that maps onto an `ImprovementType` this engine already has
# (`ATTRIBUTE`, `INITIATIVE_DICE`, `SKILL`). Offered and inert today, which is a live departure from
# the "model it in full or exclude it" policy rather than an accepted gap -- WP78 is the fix, and
# these are deliberately not being excluded in the meantime.
WP78_SCOPE = frozenset(
    {
        "Reaction Enhancers",
        "Wired Reflexes",
        "Muscle Replacement",
        "Voice Modulator",
        "Reflex Recorder",  # bioware, and the one of the 5 the shipped UI offers
    }
)

# Of the registered rows, the ones a player can buy from the browser today. The rest are reachable
# only by importing a legacy `.chum5` (WP41 widened import to all 87 rows) -- a distinction the
# registry's `Kind` column now records, because the two are not the same severity.
REGISTERED_AND_OFFERED_IN_UI = frozenset(
    {
        "Bone Lacing (Plastic)",
        "Bone Lacing (Aluminum)",
        "Bone Lacing (Titanium)",
        "Smartlink",
        "Damper",
    }
)


def _not_yet_supported_names() -> frozenset[str]:
    # Both catalogs, since `BonusSupport` is shared between them (WP45 reused cyberware's Enum
    # rather than defining a bioware one) and the policy this file pins is shared too.
    cyberware = {
        e.name for e in CYBERWARE_ENTRIES if e.bonus_support is BonusSupport.NOT_YET_SUPPORTED
    }
    bioware = {b.name for b in BIOWARE if b.bonus_support is BonusSupport.NOT_YET_SUPPORTED}
    return frozenset(cyberware | bioware)


def test_every_not_yet_supported_row_is_registered_or_named_in_wp78s_scope() -> None:
    # The whole point of this file. A row that is neither is offered, charged, mechanically silent
    # and undocumented -- exactly the state WP77 existed to end.
    assert _not_yet_supported_names() == REGISTERED_UNMODELED | WP78_SCOPE


def test_the_two_buckets_are_disjoint() -> None:
    # WP78's acceptance criteria ask that every row it reclassifies "has been removed from WP77's
    # registry rows or was never in them" -- this is that check, standing in advance.
    assert not REGISTERED_UNMODELED & WP78_SCOPE


def test_the_audited_split_is_still_14_cyberware_plus_1_bioware() -> None:
    # WP77 re-ran WP41's audit rather than trusting its counts; this pins the result so a catalog
    # change that shifts them is visible as a number, not just as a name-set diff above.
    cyberware = [e for e in CYBERWARE_ENTRIES if e.bonus_support is BonusSupport.NOT_YET_SUPPORTED]
    bioware = [b for b in BIOWARE if b.bonus_support is BonusSupport.NOT_YET_SUPPORTED]
    assert (len(cyberware), len(bioware)) == (14, 1)
    assert (len(REGISTERED_UNMODELED), len(WP78_SCOPE)) == (10, 5)


def test_registry_rows_split_5_offered_in_the_ui_and_5_import_only() -> None:
    # The `Kind` column's reachability marker, checked against the catalog the picker actually
    # renders (WP31's flat 60) rather than asserted in prose. Bucket A's `Reflex Recorder` is
    # offered too, but it is not a registry row -- see this module's docstring.
    offered = {c.name for c in FLAT_CYBERWARE} | {b.name for b in BIOWARE}
    assert REGISTERED_UNMODELED & offered == REGISTERED_AND_OFFERED_IN_UI
    assert len(REGISTERED_UNMODELED - offered) == 5


def test_registered_rows_carry_no_partially_classified_bonus() -> None:
    # "Registered" means the effect is documented as absent, so the loader must also be carrying no
    # partial bonus for these rows -- a half-applied bonus would be worse than none, and is what the
    # "never partially classify" rule in `classify_bonus` exists to prevent.
    for entry in CYBERWARE_ENTRIES:
        if entry.name in REGISTERED_UNMODELED:
            assert entry.flat_bonuses == ()
            assert entry.conditional_bonuses == ()
            # ... but the raw node is kept, so WP78-style work can still read what was skipped.
            assert entry.raw_bonus is not None
