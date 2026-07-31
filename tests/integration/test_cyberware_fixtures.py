"""Cross-checks `chummer5.data.cyberware` (WP31's flat catalog) against the real
per-item `<ess>`/`<cost>` data in 6 of the Phase J intro's 8 real cyberware-bearing fixtures --
`BLUE`, `Barrett`, `Bastion`, `Blindfire`, `Monomax (approved) 3`, `Gentle Earthquake` (`SCSi` and
`Fuzzy-chargen` are the other 2, not used here since neither is needed to cover the confirmed flat
subset below).

None of these 8 fixtures is `buildmethod == Priority` (they're all `SumtoTen`, out of MVP scope for
*building* a character -- see `tests/fixtures/README.md`'s corpus split), and
`chummer5.io.legacy_chum5.LegacyCharacter` doesn't parse per-item cyberware fields at all yet (only
the boolean `has_cyberware` -- that's WP33's job). So this file reads each fixture's raw
`<cyberwares><cyberware>` elements directly with `xml.etree.ElementTree`, mirroring
`tests/integration/test_magic_fixtures.py`'s identical "read the raw XML by hand where the fixture
can't be built/imported yet" precedent (used there for Miko's `<spells>`/Wesson's `<powers>`).

Only the top-level `<cyberware>` elements are read here. Each Cyberlimb's nested `<children>`
are Phase K's subject, covered by `tests/integration/test_cyberware_tree_fixtures.py` (WP38) and
`tests/integration/test_cyberware_import_fixtures.py` (WP41) instead. Per the Phase J intro, only
a modest, specific subset of real purchases across these fixtures are flat-cost-and-Essence items
this project's WP31 catalog actually includes: Datajack, the Cyberlimb variants, Smartlink, and
Bone Lacing (Titanium) -- this file checks exactly that subset, not every raw cyberware entry (most
of the rest are Rating-scaled or non-SR5-sourced, out of WP31's own scope already).

**A fixture's stored `<ess>`/`<cost>` are the catalog's flat, un-grade-adjusted values, confirmed
directly**: several of these purchases were actually bought at `Used`/`Alphaware` grade in their
respective fixtures (e.g. Bastion's `Obvious Full Arm` is `grade=Used`), yet the stored `<ess>`/
`<cost>` numbers match the Standard-grade catalog values exactly (1 Essence / 15000 nuyen), not a
grade-multiplied number (`Used` would be Essence x1.25, cost x0.75 -- confirmed against
`cyberware.xml`'s own `<grades>` table). This means comparing this WP31/32 Standard-grade-only
catalog against these fixtures' raw fields is valid *regardless* of which real grade was actually
purchased -- the grade multiplier is applied elsewhere (a computed `TotalESS`/`TotalCost`
property), never baked into the stored per-item field itself.

**WP41** retired WP32's flat `create_cyberware_selection`/`apply_cyberware_improvements` (see
`chummer5.engine.cyberware`'s own docstring for why), so the two purchase-composing tests below now
go through `chummer5.engine.cyberware_subsystems`' purchase tree instead -- each flat item as a
zero-plugin leaf, which is exactly what the retired pair produced. The *catalog* assertions are
unchanged: WP31's `load_cyberware()` is still what this file's flat subset is checked against, and
its ids are a subset of WP37's wider catalog, so the same rows are being priced either way.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from decimal import Decimal

from tests.fixtures.mundane_chum5 import mundane_fixture_path

from chummer5.data.cyberware import load_cyberware
from chummer5.data.cyberware_subsystems import load_cyberware_entries
from chummer5.data.metatypes import load_metatypes
from chummer5.data.priorities import load_priorities
from chummer5.engine.character import create_character, metatype_choices
from chummer5.engine.cyberware_subsystems import (
    CyberwarePurchaseRequest,
    apply_cyberware_tree_improvements,
    create_cyberware_tree_selection,
)
from chummer5.engine.derived import BASE_ESSENCE, essence, physical_condition_monitor

CYBERWARE = load_cyberware()
CYBERWARE_BY_NAME = {c.name: c for c in CYBERWARE}
# WP41: the same rows, as the purchase tree's own catalog type -- ids are shared, so a flat pick
# resolves identically in both.
ENTRIES = load_cyberware_entries()
ENTRIES_BY_NAME = {entry.name: entry for entry in ENTRIES}
METATYPES = load_metatypes()
PRIORITIES = load_priorities()

# The confirmed flat-cost-and-Essence subset that actually appears, unmodified by a rating formula,
# across these fixtures' real purchases (Implementation Plan's Phase J intro).
_CONFIRMED_FLAT_NAMES = frozenset(
    {
        "Datajack",
        "Smartlink",
        "Bone Lacing (Titanium)",
        "Obvious Full Arm",
        "Obvious Full Leg",
        "Obvious Torso",
        "Obvious Skull",
        "Synthetic Full Arm",
        "Synthetic Full Leg",
        "Synthetic Torso",
        "Synthetic Skull",
    }
)

_FIXTURES = (
    "BLUE.chum5",
    "Barrett.chum5",
    "Bastion.chum5",
    "Blindfire.chum5",
    "Monomax (approved) 3.chum5",
    "Gentle Earthquake.chum5",
)


def _raw_cyberware(fixture_name: str) -> list[tuple[str, str, str]]:
    """Top-level `<cyberware>` entries only (not nested `<children>`) as (name, ess text, cost
    text) -- a direct `xml.etree.ElementTree` read, see module docstring for why.
    """
    root = ET.parse(mundane_fixture_path(fixture_name)).getroot()
    cyberwares = root.find(".//cyberwares")
    assert cyberwares is not None
    return [
        (cw.findtext("name", ""), cw.findtext("ess", ""), cw.findtext("cost", ""))
        for cw in cyberwares.findall("cyberware")
    ]


def test_every_fixture_has_at_least_one_confirmed_flat_item() -> None:
    for fixture_name in _FIXTURES:
        names = {name for name, _, _ in _raw_cyberware(fixture_name)}
        assert names & _CONFIRMED_FLAT_NAMES, f"{fixture_name}: no confirmed flat item found"


def test_confirmed_flat_items_essence_and_cost_match_the_catalog_exactly() -> None:
    """For every real purchase across these 6 fixtures whose name is in the confirmed flat
    subset, the fixture's own raw `<ess>`/`<cost>` match this WP31 catalog's `essence_cost`/`cost`
    exactly -- regardless of which real grade the item was actually bought at (see module
    docstring).
    """
    checked = 0
    for fixture_name in _FIXTURES:
        for name, ess_text, cost_text in _raw_cyberware(fixture_name):
            if name not in _CONFIRMED_FLAT_NAMES:
                continue
            catalog_item = CYBERWARE_BY_NAME[name]
            assert catalog_item.essence_cost == Decimal(ess_text), (
                f"{fixture_name}: {name} essence mismatch"
            )
            assert catalog_item.cost == int(cost_text), f"{fixture_name}: {name} cost mismatch"
            checked += 1
    # 6 fixtures, each with at least one confirmed item (per the test above) -- sanity floor.
    assert checked >= len(_FIXTURES)


def test_bastions_two_cyberlimb_pairs_raise_physical_condition_monitor_and_reduce_essence() -> None:
    """Bastion.chum5 really does buy two `Obvious Full Arm` + two `Obvious Full Leg` (confirmed via
    `_raw_cyberware` above) -- composes the catalog + WP38's purchase tree against a hand-built
    `Character` (Bastion isn't `Priority`-built, so it can't be constructed by `create_character`
    from its own real priority letters -- this proves the mechanism using its real *item* data on an
    arbitrarily-chosen priority-built shell instead, mirroring `test_magic_fixtures.py`'s identical
    "verify by hand where the fixture itself can't be built" precedent).
    """
    raw = _raw_cyberware("Bastion.chum5")
    bastion_cyberlimb_names = [
        name for name, _, _ in raw if name in ("Obvious Full Arm", "Obvious Full Leg")
    ]
    assert bastion_cyberlimb_names == [
        "Obvious Full Leg",
        "Obvious Full Arm",
        "Obvious Full Arm",
        "Obvious Full Leg",
    ]

    heritage = PRIORITIES.heritage["A"]
    human_choice = next(
        c for c in metatype_choices(heritage, METATYPES) if c.metatype.name == "Human"
    )
    character = create_character(
        metatype_choice=human_choice,
        heritage_letter="A",
        attributes_letter="B",
        priorities=PRIORITIES,
        attribute_points={},
    )
    base_cm = physical_condition_monitor(character)
    base_essence = essence(character)
    assert base_essence == Decimal(BASE_ESSENCE)

    selection = create_cyberware_tree_selection(
        [
            CyberwarePurchaseRequest(item_id=ENTRIES_BY_NAME[name].id)
            for name in bastion_cyberlimb_names
        ],
        ENTRIES,
        nuyen_budget=1_000_000,
    )
    assert selection.nuyen_spent == 15000 * 2 + 15000 * 2
    assert selection.essence_spent == Decimal("4")

    apply_cyberware_tree_improvements(character, selection)

    assert physical_condition_monitor(character) == base_cm + 4
    assert essence(character) == base_essence - Decimal("4")


def test_datajack_and_smartlink_essence_costs_hand_checked() -> None:
    # Datajack (Headware, NO_EFFECT): appears flat-cost/flat-Essence in BLUE/Barrett/Bastion/
    # Blindfire/Monomax. Smartlink (Eyeware, NOT_YET_SUPPORTED): appears in Barrett/Bastion/
    # Gentle Earthquake -- still loaded per WP31 (a cyberware item's Essence/nuyen cost is real
    # content even when its bonus isn't, see chummer5.data.cyberware's module docstring), just
    # contributes no FLAT_BONUS Improvement.
    datajack = CYBERWARE_BY_NAME["Datajack"]
    assert datajack.essence_cost == Decimal("0.1")
    assert datajack.cost == 1000
    assert datajack.flat_bonuses == ()

    smartlink = CYBERWARE_BY_NAME["Smartlink"]
    assert smartlink.essence_cost == Decimal("0.2")
    assert smartlink.cost == 4000
    assert smartlink.flat_bonuses == ()


def test_smartlink_purchase_costs_essence_but_applies_no_flat_bonus() -> None:
    """A NOT_YET_SUPPORTED item (Smartlink) still costs real Essence when purchased -- only its
    (unmodeled) smartlink bonus is dropped, mirroring WP8/WP22's "excluded effect, not excluded
    purchase" pattern for cyberware specifically (chummer5.data.cyberware's own documented
    divergence from qualities'/powers' "exclude entirely" rule).
    """
    heritage = PRIORITIES.heritage["A"]
    human_choice = next(
        c for c in metatype_choices(heritage, METATYPES) if c.metatype.name == "Human"
    )
    character = create_character(
        metatype_choice=human_choice,
        heritage_letter="A",
        attributes_letter="B",
        priorities=PRIORITIES,
        attribute_points={},
    )
    smartlink_id = ENTRIES_BY_NAME["Smartlink"].id
    selection = create_cyberware_tree_selection(
        [CyberwarePurchaseRequest(item_id=smartlink_id)], ENTRIES, nuyen_budget=100000
    )
    apply_cyberware_tree_improvements(character, selection)

    assert essence(character) == Decimal(BASE_ESSENCE) - Decimal("0.2")
    assert character.improvements.improvements[0].improvement_type.name == "ESSENCE"
    assert len(character.improvements.improvements) == 1  # no FLAT_BONUS Improvement added
