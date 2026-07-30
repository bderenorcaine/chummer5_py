"""Cross-checks WP38's purchase tree (`chummer5.engine.cyberware_subsystems`) against the real
nested `<children>` cyberware in the legacy fixture corpus.

Same "read the raw XML by hand" approach as `tests/integration/test_cyberware_fixtures.py`, for the
same reasons: none of these fixtures is `buildmethod == Priority` (so `create_character` can't build
them from their own letters) and `chummer5.io.legacy_chum5` still doesn't parse `<children>` at all
-- that's WP41's job, which this WP deliberately precedes. Each test therefore reads a fixture's
real parent+children names/ratings out of the `.chum5`, replays the **SR5-sourced** subset of that
purchase through this engine, and checks the resulting Capacity/Essence/nuyen math.

Non-SR5 children are filtered out, not treated as failures: this project's MVP content scope is
core-rulebook-only, and most of the corpus's nested purchases are Chrome Flesh/Hard Targets content
(WP33's own finding). Where a fixture's *full* child list happens to fill the parent's Capacity
budget exactly, that's noted -- it's a useful independent check that this engine resolves the same
budget the legacy app did.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from decimal import Decimal

from tests.fixtures.mundane_chum5 import mundane_fixture_path

from chummer5.data.cyberware_subsystems import load_cyberware_entries
from chummer5.data.metatypes import load_metatypes
from chummer5.data.priorities import load_priorities
from chummer5.engine.character import Character, create_character, metatype_choices
from chummer5.engine.cyberware_subsystems import (
    CyberwarePurchaseRequest,
    apply_cyberware_tree_improvements,
    create_cyberware_tree_selection,
    cyberlimb_attribute_maximums,
)
from chummer5.engine.derived import mental_limit, physical_limit
from chummer5.engine.improvements import ResolutionContext

ENTRIES = load_cyberware_entries()
BY_NAME = {entry.name: entry for entry in ENTRIES}
METATYPES = load_metatypes()
PRIORITIES = load_priorities()


def _parent_with_children(
    fixture_name: str, parent_name: str, *, occurrence: int = 0
) -> tuple[int, list[tuple[str, int, str]]]:
    """`(parent rating, [(child name, child rating, child source), ...])` for one real purchase.

    Reads the top-level `<cyberware>` elements only; `occurrence` picks among repeats (Barrett buys
    two `Synthetic Full Arm`).
    """
    root = ET.parse(mundane_fixture_path(fixture_name)).getroot()
    cyberwares = root.find(".//cyberwares")
    assert cyberwares is not None
    matches = [cw for cw in cyberwares.findall("cyberware") if cw.findtext("name") == parent_name]
    assert len(matches) > occurrence, f"{fixture_name}: no {parent_name}[{occurrence}]"
    parent = matches[occurrence]
    children = [
        (
            child.findtext("name", ""),
            int(child.findtext("rating", "0") or 0),
            child.findtext("source", ""),
        )
        for child in parent.findall("children/cyberware")
    ]
    return int(parent.findtext("rating", "0") or 0), children


def _request(
    name: str, rating: int, children: list[tuple[str, int, str]]
) -> CyberwarePurchaseRequest:
    """Replay a fixture's purchase, keeping only its `source == "SR5"` children (MVP scope)."""
    return CyberwarePurchaseRequest(
        item_id=BY_NAME[name].id,
        rating=max(rating, 1),
        plugins=tuple(
            CyberwarePurchaseRequest(item_id=BY_NAME[child].id, rating=max(child_rating, 1))
            for child, child_rating, source in children
            if source == "SR5"
        ),
    )


def _character(metatype_name: str = "Human") -> Character:
    heritage = PRIORITIES.heritage["A"]
    choice = next(
        c for c in metatype_choices(heritage, METATYPES) if c.metatype.name == metatype_name
    )
    return create_character(
        metatype_choice=choice,
        heritage_letter="A",
        attributes_letter="B",
        priorities=PRIORITIES,
        attribute_points={},
    )


def test_barretts_synthetic_full_arm_and_its_sr5_enhancements() -> None:
    """`Barrett.chum5`'s first `Synthetic Full Arm` really carries `Customized Agility` (rating 6),
    `Enhanced Agility` (rating 3), plus 4 non-SR5 children. The SR5 subset spends 0 + 3 of the
    limb's 8 Capacity (p. 457: Synthetic full arm Capacity 8; Customization's Capacity column is
    "—"; an Agility enhancement's is `Rating`).
    """
    rating, children = _parent_with_children("Barrett.chum5", "Synthetic Full Arm")
    names = [name for name, _, _ in children]
    assert names[:2] == ["Customized Agility", "Enhanced Agility"]
    assert [name for name, _, source in children if source == "SR5"] == [
        "Customized Agility",
        "Enhanced Agility",
    ]

    selection = create_cyberware_tree_selection(
        [_request("Synthetic Full Arm", rating, children)],
        ENTRIES,
        1_000_000,
        attribute_maximums=cyberlimb_attribute_maximums(_character()),
    )
    (arm,) = selection.purchases
    assert arm.capacity_budget == Decimal("8")
    assert arm.capacity_spent == Decimal("3")  # Customized 0 + Enhanced Agility rating 3
    assert arm.capacity_remaining == Decimal("5")

    # Only the limb itself charges Essence -- its two enhancements cost Capacity instead (p. 456).
    assert arm.essence_cost == Decimal("1")
    assert selection.essence_spent == Decimal("1")
    # p. 457: limb 20,000 + customization (6-4+1) x 5,000 + Agility enhancement 3 x 6,500.
    assert selection.nuyen_spent == 20000 + 15000 + 19500


def test_barretts_synthetic_full_leg_carries_hydraulic_jacks_within_budget() -> None:
    """The other real SR5 nesting shape in Barrett: a `Synthetic Full Leg` (Capacity 10) holding
    `Hydraulic Jacks` -- WP39's fourth conditional-bonus item, and the one WP40 wires up.
    """
    rating, children = _parent_with_children("Barrett.chum5", "Synthetic Full Leg")
    sr5 = [(name, child_rating) for name, child_rating, source in children if source == "SR5"]
    assert ("Hydraulic Jacks", 1) in sr5

    selection = create_cyberware_tree_selection(
        [_request("Synthetic Full Leg", rating, children)],
        ENTRIES,
        1_000_000,
        attribute_maximums=cyberlimb_attribute_maximums(_character()),
    )
    (leg,) = selection.purchases
    assert leg.capacity_budget == Decimal("10")
    jacks = next(p for p in leg.plugins if p.item.name == "Hydraulic Jacks")
    assert jacks.capacity_cost == Decimal("1")  # p. 457: `[Rating]`, bought at rating 1
    assert jacks.nuyen_cost == 2500  # Rating x 2,500
    assert jacks.essence_cost == Decimal(0)
    assert leg.capacity_spent <= leg.capacity_budget


def test_barretts_matched_pair_of_arms_charges_essence_twice() -> None:
    """Barrett buys two identical arms, each with its own enhancements -- duplicate purchases are
    legal (the same finding WP32 recorded), and the per-limb Capacity budgets are independent.
    """
    first = _parent_with_children("Barrett.chum5", "Synthetic Full Arm", occurrence=0)
    second = _parent_with_children("Barrett.chum5", "Synthetic Full Arm", occurrence=1)

    selection = create_cyberware_tree_selection(
        [
            _request("Synthetic Full Arm", first[0], first[1]),
            _request("Synthetic Full Arm", second[0], second[1]),
        ],
        ENTRIES,
        1_000_000,
        attribute_maximums=cyberlimb_attribute_maximums(_character()),
    )
    assert len(selection.purchases) == 2
    assert selection.essence_spent == Decimal("2")
    for arm in selection.purchases:
        assert arm.capacity_spent <= arm.capacity_budget


def test_blues_rating_3_cybereyes_fills_its_capacity_budget() -> None:
    """`BLUE.chum5` buys Rating 3 Cybereyes (Capacity 12) with 6 children. Its *full* child list
    spends exactly 12 (Image Link `*`=0, Vision Enhancement r3=3, Vision Magnification 2,
    Microscopic Lenses 3 [CF], Smartlink 3, Flare Compensation 1) -- an independent confirmation
    that this engine resolves the same budget the legacy app did. The SR5 subset spends 9.
    """
    rating, children = _parent_with_children("BLUE.chum5", "Cybereyes Basic System")
    assert rating == 3
    assert [name for name, _, _ in children] == [
        "Image Link",
        "Vision Enhancement",
        "Vision Magnification",
        "Microscopic Lenses",
        "Smartlink",
        "Flare Compensation",
    ]

    selection = create_cyberware_tree_selection(
        [_request("Cybereyes Basic System", rating, children)], ENTRIES, 1_000_000
    )
    (eyes,) = selection.purchases
    assert eyes.capacity_budget == Decimal("12")  # p. 454: Rating 3 cybereyes
    assert eyes.capacity_spent == Decimal("9")  # 0 + 3 + 2 + 3 + 1, Microscopic Lenses excluded
    assert eyes.essence_cost == Decimal("0.4")
    assert selection.essence_spent == Decimal("0.4")  # every plugin contributes zero
    # p. 454/453: eyes 10,000 + vision enhancement 3 x 4,000 + magnification 2,000 + smartlink
    # 4,000 + flare compensation 1,000; Image Link bundled free.
    assert selection.nuyen_spent == 10000 + 12000 + 2000 + 4000 + 1000


def test_primes_cyberears_child_list_fills_its_budget_exactly() -> None:
    """`prime.chum5`'s Rating 1 Cyberears (Capacity 4) holds Sound Link (`*`=0), Damper (1) and
    Audio Enhancement rating 3 (3) -- all SR5, summing to exactly the budget. The tightest real
    over-capacity boundary in the corpus, so it's worth pinning.
    """
    rating, children = _parent_with_children("prime.chum5", "Cyberears")
    assert rating == 1
    assert [(name, child_rating) for name, child_rating, _ in children] == [
        ("Sound Link", 0),
        ("Damper", 0),
        ("Audio Enhancement", 3),
    ]
    assert all(source == "SR5" for _, _, source in children)

    selection = create_cyberware_tree_selection(
        [_request("Cyberears", rating, children)], ENTRIES, 1_000_000
    )
    (ears,) = selection.purchases
    assert ears.capacity_budget == Decimal("4")
    assert ears.capacity_spent == Decimal("4")
    assert ears.capacity_remaining == Decimal(0)
    assert ears.essence_cost == Decimal("0.2")  # p. 454: Rating 1 cyberears
    assert selection.nuyen_spent == 3000 + 2250 + 12000


def test_mittens_control_rig_datajack_pairing_imports_as_bundled() -> None:
    """`Mittens Chargen.chum5` is the fixture behind WP37's `<subsystems>` correction: a
    `Control Rig` with a nested `Datajack`, neither carrying `[*]` nor `<allowsubsystems>`.
    """
    rating, children = _parent_with_children("Mittens Chargen.chum5", "Control Rig")
    assert [name for name, _, _ in children] == ["Datajack"]

    selection = create_cyberware_tree_selection(
        [_request("Control Rig", rating, children)], ENTRIES, 1_000_000
    )
    (rig,) = selection.purchases
    (datajack,) = rig.plugins
    assert datajack.bundled is True
    assert (datajack.nuyen_cost, datajack.essence_cost) == (0, Decimal(0))
    assert selection.essence_spent == Decimal("1")  # p. 453: Control Rig Rating 1 -> 1 Essence
    assert selection.nuyen_spent == 43000


def test_barretts_matched_pair_of_legs_grants_one_hydraulic_jacks_bonus() -> None:
    """WP40's real-fixture check. Barrett has two `Synthetic Full Leg`s, each with a rating 1
    `Hydraulic Jacks` -- exactly the matched pair p. 457 requires ("two cyberlegs with a hydraulic
    jack of identical Ratings in each leg"). The pair grants +1 Physical limit for jumping and
    sprinting **once**; a per-node application would give +2.
    """
    first = _parent_with_children("Barrett.chum5", "Synthetic Full Leg", occurrence=0)
    second = _parent_with_children("Barrett.chum5", "Synthetic Full Leg", occurrence=1)
    for _, children in (first, second):
        assert ("Hydraulic Jacks", 1) in [(n, r) for n, r, s in children if s == "SR5"]

    character = _character()
    base = physical_limit(character)
    selection = create_cyberware_tree_selection(
        [
            _request("Synthetic Full Leg", first[0], first[1]),
            _request("Synthetic Full Leg", second[0], second[1]),
        ],
        ENTRIES,
        1_000_000,
        attribute_maximums=cyberlimb_attribute_maximums(character),
    )
    apply_cyberware_tree_improvements(character, selection)

    assert physical_limit(character, context=ResolutionContext.GYMNASTICS_JUMPING) == base + 1
    assert physical_limit(character, context=ResolutionContext.RUNNING_SPRINTING) == base + 1
    assert physical_limit(character) == base


def test_blues_cybereyes_vision_enhancement_reaches_the_character_sheet() -> None:
    """`BLUE.chum5`'s Rating 3 Cybereyes carry a Rating 3 Vision Enhancement -- +3 Mental limit on
    visual Perception tests only (p. 444), and nothing at all on the headline figure.
    """
    rating, children = _parent_with_children("BLUE.chum5", "Cybereyes Basic System")
    assert ("Vision Enhancement", 3) in [(n, r) for n, r, _ in children]

    character = _character()
    base = mental_limit(character)
    selection = create_cyberware_tree_selection(
        [_request("Cybereyes Basic System", rating, children)], ENTRIES, 1_000_000
    )
    apply_cyberware_tree_improvements(character, selection)

    assert mental_limit(character, context=ResolutionContext.PERCEPTION_VISUAL) == base + 3
    assert mental_limit(character, context=ResolutionContext.PERCEPTION_HEARING) == base
    assert mental_limit(character) == base
