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
`NOT_YET_SUPPORTED` set at all and the constant naming them is gone rather than shrunk. **One row
survives**, the bioware `Reflex Recorder`, whose `<selectskill>` is a purchase-time *player choice*
(persisted, re-validated on load, picked in the UI) rather than a fixed bonus -- WP78 ruled that its
own WP, **WP80**, for the same reason WP55 was one for `SELECT_TEXT` qualities.

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

# WP77's Bucket A, as it stands after WP78 modeled the four cyberware rows: a `<bonus>` that maps
# onto an `ImprovementType` this engine already has, still offered and still inert. A live departure
# from the "model it in full or exclude it" policy rather than an accepted gap -- WP80 is the fix,
# and this row is deliberately not being excluded in the meantime (it has shipped in the bioware
# picker since WP45 and is real content in `Barrett.chum5`'s import positive case).
MODELED_BUT_UNCLASSIFIED = frozenset(
    {
        "Reflex Recorder",  # bioware; `<selectskill>` is a player choice -- see this file's header
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


def test_every_not_yet_supported_row_is_registered_or_named_as_a_known_policy_violation() -> None:
    # The whole point of this file. A row that is neither is offered, charged, mechanically silent
    # and undocumented -- exactly the state WP77 existed to end.
    assert _not_yet_supported_names() == REGISTERED_UNMODELED | MODELED_BUT_UNCLASSIFIED


def test_the_two_buckets_are_disjoint() -> None:
    # WP78's acceptance criteria ask that every row it reclassifies "has been removed from WP77's
    # registry rows or was never in them" -- this is that check, and the four rows it modeled were
    # never in `REGISTERED_UNMODELED` to begin with, which is what kept the fix to one bucket.
    assert not REGISTERED_UNMODELED & MODELED_BUT_UNCLASSIFIED


def test_the_audited_split_is_now_10_cyberware_plus_1_bioware() -> None:
    # WP77 re-ran WP41's audit rather than trusting its counts and got 14 + 1, split 10 registry /
    # 5 computable. WP78 modeled 4 of the 5 computable ones (all cyberware), so the cyberware count
    # drops by exactly 4 and the registry side is untouched. Pinned as numbers so a catalog change
    # that shifts them is visible as more than a name-set diff above.
    cyberware = [e for e in CYBERWARE_ENTRIES if e.bonus_support is BonusSupport.NOT_YET_SUPPORTED]
    bioware = [b for b in BIOWARE if b.bonus_support is BonusSupport.NOT_YET_SUPPORTED]
    assert (len(cyberware), len(bioware)) == (10, 1)
    assert (len(REGISTERED_UNMODELED), len(MODELED_BUT_UNCLASSIFIED)) == (10, 1)


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
