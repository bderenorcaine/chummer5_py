"""WP33/WP45: confirms `chummer5.io.legacy_import`'s itemized cyberware and bioware blocking checks
against real per-item data in the Phase J intro's 8 real cyberware-bearing fixtures (`BLUE`,
`Barrett`, `Bastion`, `Blindfire`, `Fuzzy-chargen`, `Gentle Earthquake`, `Monomax (approved) 3`,
`SCSi`).

None of these 8 is `buildmethod == Priority` (all `SumtoTen` -- see the Phase J intro and
`tests/integration/test_cyberware_fixtures.py`'s identical precedent). **WP44** widened
`import_chum5`'s build-method gate to accept `SumtoTen` too (see
`chummer5.io.legacy_import`'s own docstring), so build method alone no longer rejects these 8 --
each is still rejected, but on its own real cyberware/bioware content (confirmed directly: every
one of these 8 also carries at least one rating-scaled/non-Standard-grade cyberware or bioware item
this project's two catalogs can't represent). This file confirms the itemized reasons `import_chum5`
raises for that real content are the specific, per-item ones WP33/WP45 introduce (rating-scaled/
non-Standard-grade/non-SR5/high-Availability cyberware or bioware), not the old blanket "character
has cyberware/bioware" message -- and that a real Standard-grade flat item (Bastion's/Blindfire's
own Datajack, Bastion's own Smartlink, **Barrett's own Reflex Recorder/Sleep Regulator/Platelet
Factories bioware** -- see `spec/worklogs/WP45.md` for the correction this last one makes to the
Implementation Plan's own "no fixture carries real bioware" claim) is correctly *not* itemized as
rejected.

**WP41** extends all of that to nested `<children>`, which WP33 did not parse at all. The catalog
also widens here, from WP31's 60 flat rows to WP37's full 87-row SR5 set, so "rating-scaled" stops
being a rejection reason at either level -- a `Cybereyes Basic System` and the `Vision Enhancement`
installed in it are both real, resolvable content now. The two new tests at the bottom cover the
acceptance criteria's two halves against real fixture data: `Fuzzy-chargen`'s cybereyes subtree,
where *every* child resolves and the resolved Capacity/nuyen/Essence math is hand-checked against
p. 454's eyeware table; and `Barrett`/`BLUE`, where an unresolvable child is itemized by name
*naming its parent*, rather than being silently dropped (which would leave the parent's Capacity
spend understated rather than merely incomplete).
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from tests.fixtures.mundane_chum5 import mundane_fixture_path

from chummer5.data.bioware import load_bioware
from chummer5.data.cyberware_subsystems import load_cyberware_entries
from chummer5.data.lifestyle import load_lifestyles
from chummer5.data.metatypes import load_metatypes
from chummer5.data.priorities import load_priorities
from chummer5.data.qualities import load_qualities
from chummer5.data.skills import load_skills
from chummer5.engine.cyberware_subsystems import create_cyberware_tree_selection
from chummer5.io.legacy_chum5 import LegacyCyberware, load_chum5
from chummer5.io.legacy_import import (
    UnsupportedLegacyCharacterError,
    _augmentation_reasons,
    _cyberware_purchase_requests,
    import_chum5,
)

METATYPES = load_metatypes()
PRIORITIES = load_priorities()
SKILLS = load_skills()
QUALITIES = load_qualities()
LIFESTYLES = load_lifestyles()
CYBERWARE = load_cyberware_entries()
BIOWARE = load_bioware()

_CYBERWARE_BEARING_FIXTURES = (
    "BLUE.chum5",
    "Barrett.chum5",
    "Bastion.chum5",
    "Blindfire.chum5",
    "Fuzzy-chargen.chum5",
    "Gentle Earthquake.chum5",
    "Monomax (approved) 3.chum5",
    "SCSi.chum5",
)


def _reasons(fixture_name: str) -> tuple[str, ...]:
    with pytest.raises(UnsupportedLegacyCharacterError) as exc_info:
        import_chum5(
            mundane_fixture_path(fixture_name),
            metatypes=METATYPES,
            priorities=PRIORITIES,
            skills=SKILLS,
            qualities=QUALITIES,
            lifestyles=LIFESTYLES,
            cyberware=CYBERWARE,
            bioware=BIOWARE,
        )
    return exc_info.value.reasons


@pytest.mark.parametrize("fixture_name", _CYBERWARE_BEARING_FIXTURES)
def test_every_cyberware_bearing_fixture_is_rejected_with_itemized_reasons(
    fixture_name: str,
) -> None:
    """Every one of the 8 is SumtoTen-built (accepted since WP44) but still carries real,
    unsupported cyberware or bioware content per the Phase J intro -- the itemized reasons must
    appear distinctly, confirming WP33/WP45's classification logic actually runs and reports
    correctly even though nothing here can reach a full successful import (see module docstring).
    Build method itself is deliberately *not* asserted as a reason here anymore -- WP44 widened the
    gate, so it may or may not appear depending on whether some *other* WP44 check (e.g. a missing
    priority letter) also fires for this fixture.
    """
    reasons = _reasons(fixture_name)
    # Every one of these 8 fixtures carries real, unsupported cyberware or bioware content per the
    # Phase J intro -- at least one itemized reason for it must appear regardless of build method.
    assert any("out of scope" in r for r in reasons)


def test_bastions_standard_grade_flat_items_are_not_itemized_as_rejected() -> None:
    """Bastion's real Smartlink + Datajack purchases (both Standard grade, both in WP31's flat
    catalog) must not appear among the itemized rejection reasons -- only her real Used-grade
    Cyberlimbs and bioware content should (all 4 of her real Bioware items -- Cerebral Booster
    (rating-scaled), Cerebellum Booster/Adapsin/Genetic Optimization (non-SR5-sourced), Platelet
    Factories (Used grade) -- are themselves rejected, unlike Barrett's own bioware below).
    """
    reasons = _reasons("Bastion.chum5")
    assert not any("'Smartlink'" in r for r in reasons)
    assert not any("'Datajack'" in r for r in reasons)
    assert any("'Obvious Full Arm'" in r for r in reasons)  # bought at Used grade -- rejected
    assert any("'Platelet Factories'" in r and "bioware" in r for r in reasons)


def test_blindfires_standard_grade_datajack_is_not_itemized_as_rejected() -> None:
    reasons = _reasons("Blindfire.chum5")
    assert not any("'Datajack'" in r for r in reasons)
    assert any("'Obvious Full Arm'" in r for r in reasons)  # bought at Used grade -- rejected


def test_barretts_standard_grade_flat_bioware_is_not_itemized_as_rejected() -> None:
    """WP45's own positive case: `Barrett.chum5` carries 3 real Standard-grade, SR5-sourced,
    flat-cost-and-Essence bioware items (Reflex Recorder, Sleep Regulator, Platelet Factories) that
    resolve against the WP45 catalog -- none of these 3 may appear among the itemized rejection
    reasons, even though Barrett still carries other, genuinely unsupported content (her real
    Mnemonic Enhancer bioware is rating-scaled; her real cyberware purchases are covered by
    `tests/integration/test_cyberware_fixtures.py`).
    """
    reasons = _reasons("Barrett.chum5")
    assert not any("'Reflex Recorder'" in r for r in reasons)
    assert not any("'Sleep Regulator'" in r for r in reasons)
    assert not any("'Platelet Factories'" in r for r in reasons)
    assert any("'Mnemonic Enhancer'" in r and "rating-scaled" in r for r in reasons)


# --- WP41: nested <children> ----------------------------------------------------------------------

CYBERWARE_BY_NAME = {entry.name: entry for entry in CYBERWARE}
BIOWARE_BY_NAME = {item.name: item for item in BIOWARE}


def _top_level_item(fixture_name: str, item_name: str) -> LegacyCyberware:
    legacy = load_chum5(mundane_fixture_path(fixture_name))
    return next(item for item in legacy.cyberware if item.name == item_name)


def test_fuzzys_cybereyes_subtree_imports_with_hand_checked_capacity_and_essence() -> None:
    """The acceptance criteria's positive half, against real nested fixture data.

    `Fuzzy-chargen.chum5` buys a Rating 1 `Cybereyes Basic System` at Standard grade with three
    children -- `Image Link`, `Smartlink`, `Flare Compensation` -- and unlike every other nested
    purchase in the corpus, *all three* are SR5-sourced and Standard grade, so the whole subtree
    resolves. Every number below is the printed p. 454 eyeware table:

    - cybereyes Rating 1: 4,000 nuyen, 0.2 Essence, Capacity **4** (the parent's budget);
    - `Image Link`: bundled with the basic system (`[*]`), so free in all three currencies;
    - `Smartlink` `[3]` at 4,000 nuyen and `Flare Compensation` `[1]` at 1,000 nuyen, both charging
      **Capacity, not Essence** (p. 456's dual-costing rule) -- 4 of 4 Capacity, exactly full.
    """
    cybereyes = _top_level_item("Fuzzy-chargen.chum5", "Cybereyes Basic System")
    assert [child.name for child in cybereyes.children] == [
        "Image Link",
        "Smartlink",
        "Flare Compensation",
    ]
    assert (
        _augmentation_reasons([cybereyes], CYBERWARE_BY_NAME, BIOWARE_BY_NAME, parent_name=None)
        == []
    )

    selection = create_cyberware_tree_selection(
        _cyberware_purchase_requests([cybereyes], CYBERWARE_BY_NAME),
        CYBERWARE,
        nuyen_budget=1_000_000,
    )
    (purchase,) = selection.purchases
    assert purchase.rating == 1
    assert selection.nuyen_spent == 4000 + 4000 + 1000
    assert selection.essence_spent == Decimal("0.2")
    assert purchase.capacity_budget == Decimal(4)
    assert purchase.capacity_spent == Decimal(4)
    assert purchase.capacity_remaining == Decimal(0)

    by_name = {plugin.item.name: plugin for plugin in purchase.plugins}
    assert by_name["Image Link"].bundled
    assert by_name["Image Link"].nuyen_cost == 0
    assert by_name["Smartlink"].capacity_cost == Decimal(3)
    assert by_name["Flare Compensation"].capacity_cost == Decimal(1)
    # Dual costing: a plugin contributes zero Essence, however much it costs standalone.
    assert all(plugin.essence_cost == Decimal(0) for plugin in purchase.plugins)


def test_barretts_synthetic_full_arm_itemizes_every_one_of_its_six_children() -> None:
    """The acceptance criteria's negative half. Barrett's first `Synthetic Full Arm` carries 6 real
    children; the whole limb is `Used` grade, which is still blocking (see this module's docstring
    and `spec/worklogs/WP33.md` for why a non-Standard grade can't be read as Standard). WP33 would
    have produced exactly one reason for this limb -- WP41 produces **seven**, one per node, each
    naming the parent it was installed in, so nothing is dropped without being reported.
    """
    arm = _top_level_item("Barrett.chum5", "Synthetic Full Arm")
    reasons = _augmentation_reasons([arm], CYBERWARE_BY_NAME, BIOWARE_BY_NAME, parent_name=None)
    assert len(reasons) == 7
    assert any("'Synthetic Full Arm' (Used grade):" in r for r in reasons)
    for child in arm.children:
        assert any(
            f"'{child.name}' (Used grade) installed in 'Synthetic Full Arm'" in r for r in reasons
        ), child.name


def test_blues_standard_grade_limb_itemizes_only_its_non_sr5_child() -> None:
    """The sharpest version of "itemized, not silently dropped": BLUE's `Obvious Full Leg` and 3 of
    its 4 children are Standard-grade SR5 content that resolves cleanly, and only the 4th
    (`Retractable Climbing Claws (Feet)`, `CF`-sourced) is out of scope. Dropping it silently would
    understate the limb's real Capacity spend; the import reports exactly that one node instead.
    """
    leg = _top_level_item("BLUE.chum5", "Obvious Full Leg")
    reasons = _augmentation_reasons([leg], CYBERWARE_BY_NAME, BIOWARE_BY_NAME, parent_name=None)
    assert reasons == [
        "cannot import 'Retractable Climbing Claws (Feet)' (Standard grade) installed in "
        "'Obvious Full Leg': non-Standard-grade or non-SR5 cyberware is out of scope"
    ]
    assert {child.name for child in leg.children} == {
        "Customized Agility",
        "Customized Strength",
        "Armor",
        "Retractable Climbing Claws (Feet)",
    }
