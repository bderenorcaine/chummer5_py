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
- `MODELED_BUT_UNCLASSIFIED` -- effects this engine *can* compute today (attribute, Initiative Dice
  and skill bonuses). Not registry material: registering them would launder a policy violation into
  an accepted gap.

**WP78 emptied most of the second bucket** (this file's `WP78_SCOPE` as written by WP77): the four
cyberware rows -- Reaction Enhancers, Wired Reflexes, Muscle Replacement, Voice Modulator -- now
classify `FLAT_BONUS` and grant real Improvements, so they no longer appear in the live
`NOT_YET_SUPPORTED` set at all and the constant naming them is gone rather than shrunk. **WP80
emptied the rest**: the bioware `Reflex Recorder`, whose `<selectskill>` is a purchase-time *player
choice* (persisted, re-validated on load, picked in the UI) rather than a fixed bonus, now
classifies `SELECT_SKILL` and grants a real Improvement against the player's own pick. So
`MODELED_BUT_UNCLASSIFIED` is empty, and the constant stays -- as an empty frozenset it is what a
future `NOT_YET_SUPPORTED` row would have to be added to, deliberately, to pass the first test
below.

**Why a test rather than the one-off check WP77's entry allowed as an alternative.** The failure
mode is a *future* catalog widening (WP42's UI, or any later `<bonus>` grammar change) quietly
adding a row to either bucket, which a one-off check run in 2026 cannot catch. The names below are
literal rather than read from the markdown table for the same reason
`chummer5.data.qualities._UNMODELED_EFFECT_NOTES` is a dict and not a parsed table -- see
`chummer5.engine.derived.unmodeled_effect_notes`' docstring: the registry is documentation, mirrored
into code by hand, never read from disk at runtime.

A new `NOT_YET_SUPPORTED` row therefore fails this file until somebody decides, deliberately, which
bucket it belongs in.

**WP79 adds the other direction to this file.** WP77's rows existed only in the Project Overview's
markdown; nothing showed them to a player. WP79 populates `unmodeled_effect_note` on both cyberware
catalogs (and, empty, on the bioware one) so the character sheet's WP56 disclosure section renders
them, and the tests at the bottom pin the correspondence *both* ways: every registered row resolves
to a note, and no unregistered row carries one -- the second being what keeps WP78's four modeled
rows, and `Reflex Recorder`, out of a table they must not be laundered into. The 6 augmentation
rows that predate WP77 (WP38/WP40's partly-modeled ones) get notes here too; they are named in
`PARTLY_MODELED_WITH_NOTES` below because no `bonus_support` value identifies them.
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

# WP77's Bucket A: a `<bonus>` that maps onto an `ImprovementType` this engine already has, still
# offered and still inert -- a live departure from the "model it in full or exclude it" policy
# rather than an accepted gap. **Empty since WP80**, for the first time since WP77 created it: WP78
# modeled the four cyberware rows and WP80 modeled `Reflex Recorder`, the last one. A future row
# lands here only as a deliberate act, with a WP named for fixing it.
MODELED_BUT_UNCLASSIFIED: frozenset[str] = frozenset()

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


def test_every_not_yet_supported_row_is_registered_or_named_as_a_known_policy_violation() -> None:
    # The whole point of this file. A row that is neither is offered, charged, mechanically silent
    # and undocumented -- exactly the state WP77 existed to end.
    assert _not_yet_supported_names() == REGISTERED_UNMODELED | MODELED_BUT_UNCLASSIFIED


def test_the_two_buckets_are_disjoint() -> None:
    # WP78's acceptance criteria ask that every row it reclassifies "has been removed from WP77's
    # registry rows or was never in them" -- this is that check, and the four rows it modeled were
    # never in `REGISTERED_UNMODELED` to begin with, which is what kept the fix to one bucket.
    assert not REGISTERED_UNMODELED & MODELED_BUT_UNCLASSIFIED


def test_the_audited_split_is_now_10_cyberware_and_no_bioware() -> None:
    # WP77 re-ran WP41's audit rather than trusting its counts and got 14 + 1, split 10 registry /
    # 5 computable. WP78 modeled 4 of the 5 computable ones (all cyberware) and WP80 the 5th (the
    # one bioware row), so no bioware row is NOT_YET_SUPPORTED at all any more and the registry side
    # is untouched. Pinned as numbers so a catalog change that shifts them is visible as more than a
    # name-set diff above.
    cyberware = [e for e in CYBERWARE_ENTRIES if e.bonus_support is BonusSupport.NOT_YET_SUPPORTED]
    bioware = [b for b in BIOWARE if b.bonus_support is BonusSupport.NOT_YET_SUPPORTED]
    assert (len(cyberware), len(bioware)) == (10, 0)
    assert (len(REGISTERED_UNMODELED), len(MODELED_BUT_UNCLASSIFIED)) == (10, 0)


def test_the_rows_wp78_modeled_are_gone_from_both_buckets_and_grant_real_improvements() -> None:
    # WP78's own acceptance criterion, standing as a regression test: a row that regressed to
    # NOT_YET_SUPPORTED (a `<bonus>` grammar change, a data update) would be silently inert again.
    modeled = {"Reaction Enhancers", "Wired Reflexes", "Muscle Replacement", "Voice Modulator"}
    assert not modeled & (REGISTERED_UNMODELED | MODELED_BUT_UNCLASSIFIED)
    by_name = {e.name: e for e in CYBERWARE_ENTRIES}
    for name in modeled:
        assert by_name[name].bonus_support is BonusSupport.FLAT_BONUS
        assert by_name[name].flat_bonuses != ()


def test_registry_rows_split_5_offered_in_the_ui_and_5_import_only() -> None:
    # The `Kind` column's reachability marker, checked against the catalog the picker actually
    # renders (WP31's flat 60) rather than asserted in prose.
    offered = {c.name for c in FLAT_CYBERWARE} | {b.name for b in BIOWARE}
    assert REGISTERED_UNMODELED & offered == REGISTERED_AND_OFFERED_IN_UI
    assert len(REGISTERED_UNMODELED - offered) == 5


# --- WP79: the notes that make the registry visible to a player ----------------------------------

# The 6 augmentation rows that were already in the Project Overview's registry before WP77, from
# WP38 (cyberlimb Customization/Enhancement) and WP40 (the four conditional limit bonuses). Their
# effect is *partly* modeled, so they need a note too -- and it must read as the unmodeled
# remainder, not as "this does nothing." Named here rather than derived, because there is no
# `bonus_support` value that identifies them: two are NO_EFFECT and one is CONDITIONAL_BONUS.
PARTLY_MODELED_WITH_NOTES = frozenset(
    {
        "Customized Agility",
        "Customized Strength",
        "Enhanced Agility",
        "Enhanced Strength",
        "Vision Enhancement",
        "Audio Enhancement",
        "Spatial Recognizer",
        "Hydraulic Jacks",
    }
)

# WP95's registry row, and a third bucket because it fits neither of the two above. `Control Rig`
# carries **no `<bonus>` node at all**, so it classifies `NO_EFFECT` rather than
# `NOT_YET_SUPPORTED` -- which is precisely why WP77's audit, a sweep of the `NOT_YET_SUPPORTED`
# bucket, never saw it despite it being UI-reachable since WP42 and costing a full point of Essence
# at rating 1. Its entire printed effect (p. 266) is an in-play limit bonus on a *vehicle*, so
# nothing about it is computable here and none of it is modeled: unlike
# `PARTLY_MODELED_WITH_NOTES`, its note is a bare gap, not a remainder.
#
# The standing lesson, worth more than the row: `NOT_YET_SUPPORTED` identifies rows whose `<bonus>`
# the loader could not parse, **not** rows whose effect this engine does not model. A row with no
# `<bonus>` is invisible to that sweep. Any future audit has to enumerate `NO_EFFECT` rows against
# the book too.
FULLY_UNMODELED_WITHOUT_A_BONUS_NODE = frozenset({"Control Rig"})


def test_every_registered_row_resolves_to_a_note_in_both_cyberware_catalogs() -> None:
    # WP79's acceptance criterion. Both catalogs, because they are two views of the same rows and a
    # note that reached only one of them would be a mirror that had already drifted -- the exact
    # failure the single shared `UNMODELED_EFFECT_NOTES` constant exists to make impossible.
    entries = {e.name: e for e in CYBERWARE_ENTRIES}
    flat = {c.name: c for c in FLAT_CYBERWARE}
    for name in REGISTERED_UNMODELED:
        assert entries[name].unmodeled_effect_note, name
        if name in flat:  # 5 of the 10 are import-only and absent from WP31's flat catalog
            assert flat[name].unmodeled_effect_note == entries[name].unmodeled_effect_note, name


def test_partly_modeled_registry_rows_carry_a_note_naming_what_is_modeled() -> None:
    # WP79's "their note is the unmodeled remainder, not 'this does nothing'" requirement, pinned
    # as something checkable: each of these says, in words, that part of the effect *is* applied.
    entries = {e.name: e for e in CYBERWARE_ENTRIES}
    for name in PARTLY_MODELED_WITH_NOTES:
        note = entries[name].unmodeled_effect_note
        assert note, name
        assert "modeled" in note, name


def test_no_row_outside_the_registry_carries_a_note() -> None:
    # The other half of the invariant: a note is a claim that the Project Overview's table has a row
    # for this item, so an unregistered one would be documentation with no source. In particular
    # WP78's four newly-modeled rows must have none -- registering them would launder a live policy
    # violation into an accepted gap, which is the distinction this whole file exists to keep.
    named = REGISTERED_UNMODELED | PARTLY_MODELED_WITH_NOTES | FULLY_UNMODELED_WITHOUT_A_BONUS_NODE
    for entry in CYBERWARE_ENTRIES:
        assert (entry.unmodeled_effect_note is not None) == (entry.name in named), entry.name


def test_control_rig_is_registered_despite_carrying_no_bonus_node() -> None:
    # WP95. The row itself, and the reason it was missed: `NO_EFFECT`, not `NOT_YET_SUPPORTED`, so
    # neither bucket above would ever have contained it and the two constants' union test passes
    # without it. It is UI-reachable (WP42's full-catalog picker) and costs a full Essence point at
    # rating 1, which is what makes the silence expensive.
    entries = {e.name: e for e in CYBERWARE_ENTRIES}
    control_rig = entries["Control Rig"]
    assert control_rig.bonus_support is BonusSupport.NO_EFFECT
    assert control_rig.raw_bonus is None
    assert control_rig.unmodeled_effect_note
    # Not a remainder: nothing of its effect is applied, so it must not claim otherwise.
    assert "modeled" not in control_rig.unmodeled_effect_note
    assert not FULLY_UNMODELED_WITHOUT_A_BONUS_NODE & (
        REGISTERED_UNMODELED | MODELED_BUT_UNCLASSIFIED | PARTLY_MODELED_WITH_NOTES
    )


def test_no_bioware_row_carries_a_note_and_reflex_recorder_is_modeled_instead() -> None:
    # `chummer5.data.bioware`'s own mirror is deliberately empty: no bioware row is in the registry,
    # and `Reflex Recorder` specifically must never be added to it -- WP80 models it, which is the
    # remedy the policy asks for, and a note would launder that fix into an accepted gap.
    assert all(b.unmodeled_effect_note is None for b in BIOWARE)
    reflex_recorder = next(b for b in BIOWARE if b.name == "Reflex Recorder")
    assert reflex_recorder.unmodeled_effect_note is None
    assert reflex_recorder.bonus_support is BonusSupport.SELECT_SKILL
    assert reflex_recorder.select_skill_bonus is not None


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
