"""Cross-checks `chummer5.data.bioware`/`chummer5.engine.bioware` (WP45) against real per-item
`<ess>`/`<cost>` data in `Barrett.chum5` -- 1 of the 6 curated mundane fixtures confirmed to carry
real Bioware content (`Barrett`, `Bastion`, `Blindfire`, `Fuzzy-chargen`, `Gentle Earthquake`,
`SCSi`; see `spec/worklogs/WP45.md` for the correction this makes to the Implementation Plan's own
"no fixture carries real bioware" claim). `Barrett.chum5` is used here specifically because it's the
one fixture whose real Bioware purchases include 3 *Standard*-grade, flat-cost-and-Essence items
this project's catalog actually offers (Reflex Recorder, Sleep Regulator, Platelet Factories) --
the other 5 fixtures' real Bioware content is either rating-scaled, non-SR5-sourced, or bought at a
non-Standard grade (see `tests/integration/test_cyberware_import_fixtures.py` for the itemized
per-fixture rejection reasons).

None of the 6 is `buildmethod == Priority` (all `SumtoTen`, out of MVP scope for *building* a
character -- see `tests/fixtures/README.md`'s corpus split), and
`chummer5.io.legacy_chum5.LegacyCyberware` doesn't distinguish real per-item grade beyond what
`chummer5.io.legacy_import`'s own itemized check already exercises. So this file reads Barrett's
raw `<cyberwares><cyberware improvementsource="Bioware">` elements directly with
`xml.etree.ElementTree`, mirroring `tests/integration/test_cyberware_fixtures.py`'s identical
"read the raw XML by hand where the fixture can't be built yet" precedent.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from decimal import Decimal

from tests.fixtures.mundane_chum5 import mundane_fixture_path

from chummer5.data.bioware import load_bioware
from chummer5.data.metatypes import load_metatypes
from chummer5.data.priorities import load_priorities
from chummer5.engine.bioware import apply_bioware_improvements, create_bioware_selection
from chummer5.engine.character import create_character, metatype_choices
from chummer5.engine.derived import BASE_ESSENCE, essence, physical_limit

BIOWARE = load_bioware()
BIOWARE_BY_NAME = {b.name: b for b in BIOWARE}
METATYPES = load_metatypes()
PRIORITIES = load_priorities()

# The confirmed flat-cost-and-Essence Bioware subset that actually appears, at Standard grade,
# unmodified by a rating formula, in Barrett.chum5's real purchases.
_CONFIRMED_FLAT_NAMES = frozenset({"Reflex Recorder", "Sleep Regulator", "Platelet Factories"})


def _raw_bioware(fixture_name: str) -> list[tuple[str, str, str, str]]:
    """Top-level `<cyberware improvementsource="Bioware">` entries as (name, ess text, cost text,
    grade) -- a direct `xml.etree.ElementTree` read, see module docstring for why.
    """
    root = ET.parse(mundane_fixture_path(fixture_name)).getroot()
    cyberwares = root.find(".//cyberwares")
    assert cyberwares is not None
    return [
        (
            cw.findtext("name", ""),
            cw.findtext("ess", ""),
            cw.findtext("cost", ""),
            cw.findtext("grade", ""),
        )
        for cw in cyberwares.findall("cyberware")
        if cw.findtext("improvementsource") == "Bioware"
    ]


def test_barrett_has_all_three_confirmed_flat_items() -> None:
    names = {name for name, _, _, _ in _raw_bioware("Barrett.chum5")}
    assert _CONFIRMED_FLAT_NAMES <= names


def test_confirmed_flat_items_essence_and_cost_match_the_catalog_exactly() -> None:
    """For every real purchase in Barrett.chum5 whose name is in the confirmed flat subset, the
    fixture's own raw `<ess>`/`<cost>` match this WP45 catalog's `essence_cost`/`cost` exactly, and
    the purchase really is Standard grade (unlike Bastion's own Platelet Factories, bought at Used
    grade -- see `tests/integration/test_cyberware_import_fixtures.py`).
    """
    checked = 0
    for name, ess_text, cost_text, grade in _raw_bioware("Barrett.chum5"):
        if name not in _CONFIRMED_FLAT_NAMES:
            continue
        assert grade == "Standard", f"{name}: expected Standard grade, got {grade!r}"
        catalog_item = BIOWARE_BY_NAME[name]
        assert catalog_item.essence_cost == Decimal(ess_text), f"{name} essence mismatch"
        assert catalog_item.cost == int(cost_text), f"{name} cost mismatch"
        checked += 1
    assert checked == len(_CONFIRMED_FLAT_NAMES)


def test_barretts_real_bioware_purchase_reduces_essence_on_a_hand_built_character() -> None:
    """Composes WP45's catalog + selection/apply against a hand-built `Character` (Barrett isn't
    `Priority`-built, so it can't be constructed by `create_character` from its own real priority
    letters -- mirrors `test_cyberware_fixtures.py`'s identical "verify by hand where the fixture
    itself can't be built" precedent).
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
    base_essence = essence(character)
    assert base_essence == Decimal(BASE_ESSENCE)

    item_ids = [BIOWARE_BY_NAME[name].id for name in _CONFIRMED_FLAT_NAMES]
    selection = create_bioware_selection(item_ids, BIOWARE, nuyen_budget=1_000_000)
    expected_essence = sum(
        (BIOWARE_BY_NAME[name].essence_cost for name in _CONFIRMED_FLAT_NAMES), Decimal(0)
    )
    assert selection.essence_spent == expected_essence

    apply_bioware_improvements(character, selection)

    assert essence(character) == base_essence - expected_essence


def test_reflex_recorder_sleep_regulator_platelet_factories_hand_checked() -> None:
    # Reflex Recorder (Cultured, NOT_YET_SUPPORTED -- a player-selected skill bonus this engine
    # doesn't model); Sleep Regulator/Platelet Factories (both Basic/Cultured, NO_EFFECT --
    # narrative sleep/healing effects, verified moot per chummer5.data.bioware's own docstring).
    reflex_recorder = BIOWARE_BY_NAME["Reflex Recorder"]
    assert reflex_recorder.essence_cost == Decimal("0.1")
    assert reflex_recorder.cost == 14000
    assert reflex_recorder.flat_bonuses == ()

    sleep_regulator = BIOWARE_BY_NAME["Sleep Regulator"]
    assert sleep_regulator.essence_cost == Decimal("0.1")
    assert sleep_regulator.cost == 12000

    platelet_factories = BIOWARE_BY_NAME["Platelet Factories"]
    assert platelet_factories.essence_cost == Decimal("0.2")
    assert platelet_factories.cost == 17000


def test_reflex_recorder_purchase_costs_essence_but_applies_no_flat_bonus() -> None:
    """A NOT_YET_SUPPORTED item (Reflex Recorder) still costs real Essence when purchased -- only
    its (unmodeled) player-selected skill bonus is dropped, mirroring `test_cyberware_fixtures.py`'s
    identical Smartlink test.
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
    reflex_recorder_id = BIOWARE_BY_NAME["Reflex Recorder"].id
    selection = create_bioware_selection([reflex_recorder_id], BIOWARE, nuyen_budget=100000)
    apply_bioware_improvements(character, selection)

    assert essence(character) == Decimal(BASE_ESSENCE) - Decimal("0.1")
    assert character.improvements.improvements[0].improvement_type.name == "ESSENCE"
    assert len(character.improvements.improvements) == 1  # no FLAT_BONUS Improvement added


def test_enhanced_articulation_flat_bonus_raises_physical_limit_on_a_hand_built_character() -> None:
    """No curated fixture buys Enhanced Articulation (the one real `FLAT_BONUS` bioware item) --
    confirms the mechanism directly, mirroring `test_cyberware_fixtures.py`'s own Cyberlimb test
    for the equivalent case.
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
    base_limit = physical_limit(character)
    item_id = BIOWARE_BY_NAME["Enhanced Articulation"].id
    selection = create_bioware_selection([item_id], BIOWARE, nuyen_budget=100000)
    apply_bioware_improvements(character, selection)

    assert physical_limit(character) == base_limit + 1
