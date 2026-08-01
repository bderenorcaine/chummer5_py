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
from dataclasses import replace
from decimal import Decimal

from tests.fixtures.mundane_chum5 import mundane_fixture_path

from chummer5.data.bioware import load_bioware
from chummer5.data.metatypes import load_metatypes
from chummer5.data.priorities import load_priorities
from chummer5.data.skills import load_skills
from chummer5.engine.bioware import (
    BiowarePurchaseRequest,
    apply_bioware_improvements,
    create_bioware_selection,
)
from chummer5.engine.character import create_character, metatype_choices
from chummer5.engine.derived import BASE_ESSENCE, essence, physical_limit
from chummer5.engine.skills import (
    MAX_SKILL_RATING_CREATE,
    create_skill_allocation,
    dice_pool,
    natural_skill_rating,
    skill_rating,
)

BIOWARE = load_bioware()
BIOWARE_BY_NAME = {b.name: b for b in BIOWARE}
METATYPES = load_metatypes()
PRIORITIES = load_priorities()
SKILLS = load_skills()

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


def _barrett_reflex_recorder_extra() -> str:
    """WP80: the skill Barrett's own Reflex Recorder was bought for, read straight out of the
    fixture's `<extra>` rather than hardcoded -- the same element `chummer5.io.legacy_import`
    imports it from.
    """
    root = ET.parse(mundane_fixture_path("Barrett.chum5")).getroot()
    cyberwares = root.find(".//cyberwares")
    assert cyberwares is not None
    return next(
        cw.findtext("extra", "")
        for cw in cyberwares.findall("cyberware")
        if cw.findtext("name") == "Reflex Recorder"
    )


BARRETT_REFLEX_RECORDER_SKILL = _barrett_reflex_recorder_extra()


def _human_character():
    heritage = PRIORITIES.heritage["A"]
    human_choice = next(
        c for c in metatype_choices(heritage, METATYPES) if c.metatype.name == "Human"
    )
    return create_character(
        metatype_choice=human_choice,
        heritage_letter="A",
        attributes_letter="B",
        priorities=PRIORITIES,
        attribute_points={},
    )


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

    # WP80: Reflex Recorder is among these 3, and now needs its own purchase-time skill pick --
    # Barrett's real one, `<extra>Longarms</extra>`.
    requests = [
        BiowarePurchaseRequest(
            item_id=BIOWARE_BY_NAME[name].id,
            chosen_skill=BARRETT_REFLEX_RECORDER_SKILL if name == "Reflex Recorder" else None,
        )
        for name in _CONFIRMED_FLAT_NAMES
    ]
    selection = create_bioware_selection(requests, BIOWARE, nuyen_budget=1_000_000, skills=SKILLS)
    expected_essence = sum(
        (BIOWARE_BY_NAME[name].essence_cost for name in _CONFIRMED_FLAT_NAMES), Decimal(0)
    )
    assert selection.essence_spent == expected_essence

    apply_bioware_improvements(character, selection)

    assert essence(character) == base_essence - expected_essence


def test_reflex_recorder_sleep_regulator_platelet_factories_hand_checked() -> None:
    # Reflex Recorder (Cultured, SELECT_SKILL since WP80 -- a player-selected skill bonus);
    # Sleep Regulator/Platelet Factories (both Basic/Cultured, NO_EFFECT --
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


def test_barretts_real_reflex_recorder_raises_exactly_the_skill_she_chose() -> None:
    """WP80's acceptance criterion against real fixture content: `Barrett.chum5` stores
    `<extra>Longarms</extra>` on her Reflex Recorder, so the purchase must raise Longarms' rating
    (and through it its dice pool) by exactly 1 -- p. 460: "adds 1 to the Rating of a specific skill
    linked to a Physical attribute" -- and no other skill's.

    Read out of the fixture rather than hardcoded, so a corpus change can't quietly pass.
    """
    assert BARRETT_REFLEX_RECORDER_SKILL == "Longarms"
    character = _human_character()
    longarms = next(s for s in SKILLS if s.name == BARRETT_REFLEX_RECORDER_SKILL)
    allocation = create_skill_allocation(
        "C", PRIORITIES, SKILLS, skill_points={longarms.id: 3}, group_points={}
    )
    character = replace(character, skill_allocation=allocation)
    assert skill_rating(character, allocation, longarms) == 3

    selection = create_bioware_selection(
        [
            BiowarePurchaseRequest(
                item_id=BIOWARE_BY_NAME["Reflex Recorder"].id,
                chosen_skill=BARRETT_REFLEX_RECORDER_SKILL,
            )
        ],
        BIOWARE,
        nuyen_budget=100000,
        skills=SKILLS,
    )
    apply_bioware_improvements(character, selection)

    assert skill_rating(character, allocation, longarms) == 4
    assert dice_pool(character, allocation, longarms) == 4 + character.attribute_value(
        longarms.attribute
    )
    # Essence is still charged, exactly as it was before the bonus was modeled.
    assert essence(character) == Decimal(BASE_ESSENCE) - Decimal("0.1")
    # Every other skill is untouched: one SKILL Improvement, aimed at one name.
    skill_improvements = [
        i for i in character.improvements.improvements if i.improvement_type.name == "SKILL"
    ]
    assert [(i.target, i.value) for i in skill_improvements] == [("Longarms", 1)]


def test_barretts_real_reflex_recorder_still_lands_on_a_fully_bought_skill() -> None:
    """WP82's acceptance criterion, against the same real catalog row as the test above. Buying
    Longarms all the way to the chargen maximum of 6 and *then* installing the recorder used to
    produce a rating of 6 -- 14,000 nuyen and 0.1 Essence for nothing, because `skill_rating`
    clamped at `MAX_SKILL_RATING_CREATE`. SR5's 6 caps what may be bought (p. 131), not what an
    implant adds, so the rating is 7 and the pool follows.
    """
    character = _human_character()
    longarms = next(s for s in SKILLS if s.name == BARRETT_REFLEX_RECORDER_SKILL)
    allocation = create_skill_allocation(
        "C",
        PRIORITIES,
        SKILLS,
        skill_points={longarms.id: MAX_SKILL_RATING_CREATE},
        group_points={},
    )
    character = replace(character, skill_allocation=allocation)

    selection = create_bioware_selection(
        [
            BiowarePurchaseRequest(
                item_id=BIOWARE_BY_NAME["Reflex Recorder"].id,
                chosen_skill=BARRETT_REFLEX_RECORDER_SKILL,
            )
        ],
        BIOWARE,
        nuyen_budget=100000,
        skills=SKILLS,
    )
    apply_bioware_improvements(character, selection)

    assert natural_skill_rating(character, allocation, longarms) == MAX_SKILL_RATING_CREATE
    assert skill_rating(character, allocation, longarms) == MAX_SKILL_RATING_CREATE + 1
    assert dice_pool(character, allocation, longarms) == 7 + character.attribute_value(
        longarms.attribute
    )


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
