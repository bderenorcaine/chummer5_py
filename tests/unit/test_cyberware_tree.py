"""Tests for `chummer5.engine.cyberware_subsystems` (WP38's purchase tree + Capacity validation).

Two deliberate layers, mirroring every prior Phase K/J WP's own split:

1. **Synthetic data** -- the validation rules proved in isolation against hand-built
   `CyberwareEntry` rows, so a rule's test can't accidentally pass because some real catalog row
   happens to satisfy it (WP5/WP30/WP32's "prove the mechanism first" precedent).
2. **Real catalog rows** -- the same rules exercised against `load_cyberware_entries()`, with the
   numbers checked against the printed tables transcribed in
   `spec/rulebooks/learnings/phase-k.md`.

The whole-fixture cross-checks (Barrett's limbs, BLUE's cybereyes) live in
`tests/integration/test_cyberware_tree_fixtures.py`.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from chummer5.data.cyberware import BonusSupport, CyberwareConditionalBonus, CyberwareFlatBonus
from chummer5.data.cyberware_formula import CyberwareFormula, parse_cyberware_formula
from chummer5.data.cyberware_subsystems import CyberwareEntry, load_cyberware_entries
from chummer5.data.metatypes import load_metatypes
from chummer5.data.priorities import load_priorities
from chummer5.engine.character import Character, create_character, metatype_choices
from chummer5.engine.cyberware_subsystems import (
    CYBERLIMB_BASE_ATTRIBUTE,
    CyberwarePurchaseRequest,
    CyberwareTreeSelection,
    Installation,
    apply_cyberware_tree_improvements,
    create_cyberware_tree_selection,
    cyberlimb_attribute_maximums,
)
from chummer5.engine.derived import (
    BASE_ESSENCE,
    essence,
    mental_limit,
    physical_condition_monitor,
    physical_limit,
    social_limit,
)
from chummer5.engine.improvements import ImprovementType, ResolutionContext

ENTRIES = load_cyberware_entries()
BY_NAME = {entry.name: entry for entry in ENTRIES}
METATYPES = load_metatypes()
PRIORITIES = load_priorities()


def _formula(text: str) -> CyberwareFormula:
    parsed = parse_cyberware_formula(text)
    assert parsed is not None, text
    return parsed


def _entry(
    name: str,
    *,
    category: str = "Eyeware",
    cost: str = "0",
    ess: str = "0",
    capacity_budget: str | None = None,
    capacity_cost: str | None = None,
    bundled_free: bool = False,
    allowed: tuple[str, ...] = (),
    bundled_names: tuple[str, ...] = (),
    requires_parent: bool = False,
    max_rating: str | None = None,
    min_rating: str | None = None,
    flat_bonuses: tuple[CyberwareFlatBonus, ...] = (),
    conditional_bonuses: tuple[CyberwareConditionalBonus, ...] = (),
) -> CyberwareEntry:
    """A synthetic `CyberwareEntry`, with only the fields WP38's validation actually reads set."""
    parsed_max = int(max_rating) if max_rating is not None and max_rating.isdigit() else None
    parsed_min = int(min_rating) if min_rating is not None and min_rating.isdigit() else None
    return CyberwareEntry(
        id=name.lower().replace(" ", "-"),
        name=name,
        category=category,
        source="SR5",
        page=1,
        cost=_formula(cost),
        essence_cost=_formula(ess),
        raw_max_rating=max_rating,
        raw_min_rating=min_rating,
        max_rating=parsed_max,
        min_rating=parsed_min,
        capacity_budget=_formula(capacity_budget) if capacity_budget is not None else None,
        capacity_cost=_formula(capacity_cost) if capacity_cost is not None else None,
        bundled_free=bundled_free,
        allowed_subsystem_categories=allowed,
        bundled_subsystem_names=bundled_names,
        requires_parent=requires_parent,
        adds_to_parent_essence=False,
        adds_to_parent_capacity=False,
        bonus_support=(
            BonusSupport.CONDITIONAL_BONUS
            if conditional_bonuses
            else BonusSupport.FLAT_BONUS
            if flat_bonuses
            else BonusSupport.NO_EFFECT
        ),
        flat_bonuses=flat_bonuses,
        conditional_bonuses=conditional_bonuses,
        raw_bonus=None,
    )


# A synthetic parent with a Capacity budget of 8 that accepts one plugin category, plus three
# plugins: a flat one, a rating-scaled one, and one that has no Capacity price at all.
LIMB = _entry(
    "Test Limb",
    category="Cyberlimb",
    cost="20000",
    ess="1",
    capacity_budget="8",
    allowed=("Cyberlimb Enhancement", "Headware"),
)
PLUG = _entry(
    "Test Plug", category="Cyberlimb Enhancement", cost="1000", ess="0.2", capacity_cost="3"
)
RATED_PLUG = _entry(
    "Test Rated Plug",
    category="Cyberlimb Enhancement",
    cost="Rating * 1000",
    ess="0.1",
    capacity_cost="Rating",
    max_rating="3",
)
BIG_PLUG = _entry("Test Big Plug", category="Headware", cost="500", ess="0.1", capacity_cost="5")
ESSENCE_ONLY = _entry("Test Essence Only", category="Headware", cost="500", ess="0.3")
WRONG_CATEGORY = _entry(
    "Test Earplug", category="Earware", cost="500", ess="0.1", capacity_cost="1"
)
PLUGIN_ONLY = _entry(
    "Test Plugin Only",
    category="Cyberlimb Enhancement",
    cost="750",
    ess="0",
    capacity_cost="2",
    requires_parent=True,
)
SYNTHETIC = (LIMB, PLUG, RATED_PLUG, BIG_PLUG, ESSENCE_ONLY, WRONG_CATEGORY, PLUGIN_ONLY)


def _request(
    item: CyberwareEntry,
    rating: int = 1,
    plugins: tuple[CyberwarePurchaseRequest, ...] = (),
) -> CyberwarePurchaseRequest:
    return CyberwarePurchaseRequest(item_id=item.id, rating=rating, plugins=plugins)


def _human_character() -> Character:
    heritage = PRIORITIES.heritage["A"]
    human = next(c for c in metatype_choices(heritage, METATYPES) if c.metatype.name == "Human")
    return create_character(
        metatype_choice=human,
        heritage_letter="A",
        attributes_letter="B",
        priorities=PRIORITIES,
        attribute_points={},
    )


# --------------------------------------------------------------------------------------------
# Layer 1: synthetic data -- the validation rules in isolation
# --------------------------------------------------------------------------------------------


def test_standalone_purchase_costs_essence_and_offers_a_capacity_budget() -> None:
    selection = create_cyberware_tree_selection([_request(LIMB)], SYNTHETIC, 100000)
    (limb,) = selection.purchases
    assert limb.installation is Installation.STANDALONE
    assert limb.essence_cost == Decimal("1")
    assert limb.nuyen_cost == 20000
    assert limb.capacity_cost == Decimal(0)
    assert limb.capacity_budget == Decimal("8")
    assert limb.capacity_remaining == Decimal("8")
    assert selection.essence_spent == Decimal("1")
    assert selection.nuyen_spent == 20000


def test_subsystem_costs_capacity_and_contributes_zero_essence() -> None:
    """The dual-costing rule: the same row costs Essence standalone, Capacity as a plugin."""
    standalone = create_cyberware_tree_selection([_request(PLUG)], SYNTHETIC, 100000)
    assert standalone.essence_spent == Decimal("0.2")

    nested = create_cyberware_tree_selection(
        [_request(LIMB, plugins=(_request(PLUG),))], SYNTHETIC, 100000
    )
    (limb,) = nested.purchases
    (plug,) = limb.plugins
    assert plug.installation is Installation.SUBSYSTEM
    assert plug.essence_cost == Decimal(0)  # zero, not 0.2
    assert plug.capacity_cost == Decimal("3")
    assert nested.essence_spent == Decimal("1")  # the limb's own Essence only


def test_subsystem_still_costs_nuyen() -> None:
    nested = create_cyberware_tree_selection(
        [_request(LIMB, plugins=(_request(PLUG),))], SYNTHETIC, 100000
    )
    assert nested.nuyen_spent == 21000
    (limb,) = nested.purchases
    assert limb.nuyen_cost == 20000  # own cost excludes plugins
    assert limb.total_nuyen_cost == 21000


def test_capacity_spend_and_remaining_track_installed_plugins() -> None:
    selection = create_cyberware_tree_selection(
        [_request(LIMB, plugins=(_request(PLUG), _request(RATED_PLUG, rating=2)))],
        SYNTHETIC,
        100000,
    )
    (limb,) = selection.purchases
    assert limb.capacity_spent == Decimal("5")  # 3 + rating 2
    assert limb.capacity_remaining == Decimal("3")


def test_rejects_plugins_exceeding_the_parents_capacity_budget() -> None:
    # 3 (Test Plug) + 3 (Test Rated Plug at rating 3) + 5 (Test Big Plug) = 11, over the limb's 8.
    with pytest.raises(ValueError, match="exceeding its Capacity budget"):
        create_cyberware_tree_selection(
            [
                _request(
                    LIMB,
                    plugins=(
                        _request(PLUG),
                        _request(RATED_PLUG, rating=3),
                        _request(BIG_PLUG),
                    ),
                )
            ],
            SYNTHETIC,
            1_000_000,
        )


def test_rejects_a_plugin_whose_category_the_parent_does_not_allow() -> None:
    with pytest.raises(ValueError, match="cannot hold a Earware subsystem"):
        create_cyberware_tree_selection(
            [_request(LIMB, plugins=(_request(WRONG_CATEGORY),))], SYNTHETIC, 100000
        )


def test_rejects_a_plugin_with_no_capacity_price() -> None:
    # p. 456: a parent "cannot hold ... cyber-implants that take up Essence rather than Capacity."
    with pytest.raises(ValueError, match="has no Capacity cost"):
        create_cyberware_tree_selection(
            [_request(LIMB, plugins=(_request(ESSENCE_ONLY),))], SYNTHETIC, 100000
        )


def test_rejects_a_requireparent_item_bought_standalone() -> None:
    with pytest.raises(ValueError, match="can only be installed as a subsystem"):
        create_cyberware_tree_selection([_request(PLUGIN_ONLY)], SYNTHETIC, 100000)


def test_requireparent_item_is_fine_as_a_plugin() -> None:
    selection = create_cyberware_tree_selection(
        [_request(LIMB, plugins=(_request(PLUGIN_ONLY),))], SYNTHETIC, 100000
    )
    (limb,) = selection.purchases
    assert limb.plugins[0].capacity_cost == Decimal("2")


def test_rejects_plugins_on_an_item_that_allows_no_subsystems() -> None:
    with pytest.raises(ValueError, match="cannot hold subsystems"):
        create_cyberware_tree_selection(
            [_request(ESSENCE_ONLY, plugins=(_request(PLUG),))], SYNTHETIC, 100000
        )


def test_rejects_a_third_nesting_level() -> None:
    # The explicit 2026-07-29 cut -- a plugin may not itself hold plugins.
    with pytest.raises(ValueError, match="out of scope"):
        create_cyberware_tree_selection(
            [_request(LIMB, plugins=(_request(PLUG, plugins=(_request(RATED_PLUG),)),))],
            SYNTHETIC,
            100000,
        )


def test_rejects_two_cyberlimb_enhancements_of_the_same_type_in_one_parent() -> None:
    # p. 456: "Each limb can have only one enhancement of each type."
    with pytest.raises(ValueError, match="only one enhancement of each type"):
        create_cyberware_tree_selection(
            [_request(LIMB, plugins=(_request(PLUG), _request(PLUG)))], SYNTHETIC, 100000
        )


def test_the_same_enhancement_in_two_different_limbs_is_fine() -> None:
    # Barrett really does buy the same enhancement into each of four separate limbs.
    selection = create_cyberware_tree_selection(
        [_request(LIMB, plugins=(_request(PLUG),)), _request(LIMB, plugins=(_request(PLUG),))],
        SYNTHETIC,
        1_000_000,
    )
    assert len(selection.purchases) == 2
    assert selection.essence_spent == Decimal("2")


def test_rejects_a_rating_outside_the_items_bounds() -> None:
    with pytest.raises(ValueError, match="outside its purchasable range 1-3"):
        create_cyberware_tree_selection(
            [_request(LIMB, plugins=(_request(RATED_PLUG, rating=4),))], SYNTHETIC, 1_000_000
        )


def test_rejects_a_rating_above_one_on_an_unrated_item() -> None:
    with pytest.raises(ValueError, match="outside its purchasable range 1-1"):
        create_cyberware_tree_selection([_request(LIMB, rating=2)], SYNTHETIC, 100000)


def test_rejects_unknown_id() -> None:
    with pytest.raises(ValueError, match="not a cyberware catalog id"):
        create_cyberware_tree_selection(
            [CyberwarePurchaseRequest(item_id="nope")], SYNTHETIC, 100000
        )


def test_rejects_nuyen_spend_over_budget() -> None:
    with pytest.raises(ValueError, match="exceeds the nuyen budget"):
        create_cyberware_tree_selection([_request(LIMB)], SYNTHETIC, 19999)


def test_rejects_essence_spend_that_would_leave_no_essence_remaining() -> None:
    with pytest.raises(ValueError, match="would leave no Essence remaining"):
        create_cyberware_tree_selection([_request(LIMB)] * 6, SYNTHETIC, 1_000_000)


def test_other_essence_spent_folds_into_the_floor_check() -> None:
    with pytest.raises(ValueError, match="would leave no Essence remaining"):
        create_cyberware_tree_selection(
            [_request(LIMB)] * 5, SYNTHETIC, 1_000_000, other_essence_spent=Decimal("1")
        )


def test_walk_yields_every_node_parents_first() -> None:
    selection = create_cyberware_tree_selection(
        [_request(LIMB, plugins=(_request(PLUG), _request(RATED_PLUG, rating=1)))],
        SYNTHETIC,
        100000,
    )
    assert [node.item.name for node in selection.walk()] == [
        "Test Limb",
        "Test Plug",
        "Test Rated Plug",
    ]


# --------------------------------------------------------------------------------------------
# Layer 2: real catalog rows, checked against the printed tables
# --------------------------------------------------------------------------------------------


def _real(name: str) -> CyberwarePurchaseRequest:
    return CyberwarePurchaseRequest(item_id=BY_NAME[name].id)


def _real_rated(
    name: str, rating: int, plugins: tuple[CyberwarePurchaseRequest, ...] = ()
) -> CyberwarePurchaseRequest:
    return CyberwarePurchaseRequest(item_id=BY_NAME[name].id, rating=rating, plugins=plugins)


def test_cybereyes_rating_3_with_a_vision_enhancement_matches_the_printed_table() -> None:
    """Core rulebook p. 454: Cybereyes Rating 3 -> 0.4 Essence, Capacity 12, 10,000 nuyen; Vision
    Enhancement Rating 2 -> Capacity cost 2, 8,000 nuyen (and, installed here, zero Essence).
    """
    selection = create_cyberware_tree_selection(
        [_real_rated("Cybereyes Basic System", 3, plugins=(_real_rated("Vision Enhancement", 2),))],
        ENTRIES,
        100000,
    )
    (eyes,) = selection.purchases
    assert eyes.essence_cost == Decimal("0.4")
    assert eyes.nuyen_cost == 10000
    assert eyes.capacity_budget == Decimal("12")

    vision = next(p for p in eyes.plugins if p.item.name == "Vision Enhancement")
    assert vision.capacity_cost == Decimal("2")
    assert vision.nuyen_cost == 8000
    assert vision.essence_cost == Decimal(0)

    # Only the parent's Essence is charged, even though Vision Enhancement's own <ess> is 0.1.
    assert selection.essence_spent == Decimal("0.4")
    assert selection.nuyen_spent == 18000


def test_cybereyes_auto_attach_image_link_free() -> None:
    """Every one of the 8 real `<subsystems>`-bearing purchases across the fixture corpus carries
    its bundled child, so bundled items are auto-attached rather than offered as a choice -- and
    they are free in all three currencies (legacy `Cyberware.Create` forces `Cost = "0"`; p. 454's
    "* Included in the basic cybereyes system").
    """
    selection = create_cyberware_tree_selection(
        [_real_rated("Cybereyes Basic System", 1)], ENTRIES, 100000
    )
    (eyes,) = selection.purchases
    (image_link,) = eyes.plugins
    assert image_link.item.name == "Image Link"
    assert image_link.bundled is True
    assert (image_link.nuyen_cost, image_link.essence_cost, image_link.capacity_cost) == (
        0,
        Decimal(0),
        Decimal(0),
    )
    assert eyes.capacity_spent == Decimal(0)
    assert selection.nuyen_spent == 4000  # the cybereyes alone, p. 454


def test_explicitly_requested_bundled_item_is_not_double_added_and_still_free() -> None:
    # WP41's legacy import will list `Image Link` explicitly in `<children>`; it must resolve to
    # the same free node rather than an extra, charged one.
    selection = create_cyberware_tree_selection(
        [_real_rated("Cybereyes Basic System", 1, plugins=(_real("Image Link"),))],
        ENTRIES,
        100000,
    )
    (eyes,) = selection.purchases
    assert [p.item.name for p in eyes.plugins] == ["Image Link"]
    assert eyes.plugins[0].bundled is True
    assert selection.nuyen_spent == 4000


def test_control_rig_bundles_a_datajack_despite_allowing_no_subsystems() -> None:
    """WP37's correction in practice: `Control Rig` has no `<allowsubsystems>` and `Datajack`'s
    `<capacity>` is a bare `0`, yet the pairing is real fixture content (`Mittens Chargen.chum5`).
    """
    selection = create_cyberware_tree_selection([_real_rated("Control Rig", 1)], ENTRIES, 100000)
    (rig,) = selection.purchases
    (datajack,) = rig.plugins
    assert datajack.item.name == "Datajack"
    assert datajack.bundled is True
    assert selection.nuyen_spent == 43000  # p. 453: Control Rig Rating 1, the Datajack free
    assert selection.essence_spent == Decimal("1")


def test_customized_agility_resolves_its_attribute_placeholder_bounds() -> None:
    """`<minrating>{AGIMinimum}+1</minrating>` is the limb's floor of 3, +1 -> 4 (p. 456, "All
    standard cyberlimbs come with Strength and Agility attributes of 3"); `<rating>{AGIMaximum}
    </rating>` is the character's own natural maximum (p. 456, customizing past it makes the limb
    unusable). Cost at rating 6 is `(6 - 4 + 1) * 5000` = 15,000 nuyen (p. 457).
    """
    character = _human_character()
    maximums = cyberlimb_attribute_maximums(character)
    assert maximums["AGI"] == 6  # Human's natural AGI maximum
    assert CYBERLIMB_BASE_ATTRIBUTE == 3

    selection = create_cyberware_tree_selection(
        [_real_rated("Synthetic Full Arm", 1, plugins=(_real_rated("Customized Agility", 6),))],
        ENTRIES,
        1_000_000,
        attribute_maximums=maximums,
    )
    (arm,) = selection.purchases
    (customized,) = arm.plugins
    assert customized.nuyen_cost == 15000
    assert customized.capacity_cost == Decimal(0)  # printed Capacity column is "—", XML `[0]`
    assert selection.nuyen_spent == 35000


def test_customized_agility_beyond_the_characters_natural_maximum_is_rejected() -> None:
    character = _human_character()
    with pytest.raises(ValueError, match="outside its purchasable range 4-6"):
        create_cyberware_tree_selection(
            [_real_rated("Synthetic Full Arm", 1, plugins=(_real_rated("Customized Agility", 7),))],
            ENTRIES,
            1_000_000,
            attribute_maximums=cyberlimb_attribute_maximums(character),
        )


def test_customized_agility_without_attribute_maximums_raises_rather_than_guessing() -> None:
    # Mirrors WP36's `min_rating=None` decision: a missing character-derived bound is an error,
    # never a silent default.
    with pytest.raises(ValueError, match="needs the character's natural AGI maximum"):
        create_cyberware_tree_selection(
            [_real_rated("Synthetic Full Arm", 1, plugins=(_real_rated("Customized Agility", 6),))],
            ENTRIES,
            1_000_000,
        )


def test_a_troll_may_customize_a_limb_higher_than_a_human() -> None:
    heritage = PRIORITIES.heritage["A"]
    troll_choice = next(
        c for c in metatype_choices(heritage, METATYPES) if c.metatype.name == "Troll"
    )
    troll = create_character(
        metatype_choice=troll_choice,
        heritage_letter="A",
        attributes_letter="B",
        priorities=PRIORITIES,
        attribute_points={},
    )
    maximums = cyberlimb_attribute_maximums(troll)
    assert maximums["STR"] == 10  # Troll's natural STR maximum

    selection = create_cyberware_tree_selection(
        [_real_rated("Synthetic Full Arm", 1, plugins=(_real_rated("Customized Strength", 10),))],
        ENTRIES,
        1_000_000,
        attribute_maximums=maximums,
    )
    (arm,) = selection.purchases
    assert arm.plugins[0].nuyen_cost == (10 - 4 + 1) * 5000


def test_a_cyber_implant_weapon_may_be_installed_in_a_limb_but_holds_no_accessory() -> None:
    """The 11 Cyber Implant Weapons are plugins into a limb; their own `<allowsubsystems>` layer is
    the third level this phase cut (2026-07-29).
    """
    selection = create_cyberware_tree_selection(
        [_real_rated("Synthetic Full Arm", 1, plugins=(_real("Hand Blade"),))], ENTRIES, 1_000_000
    )
    (arm,) = selection.purchases
    assert arm.plugins[0].capacity_cost == Decimal("2")

    with pytest.raises(ValueError, match="out of scope"):
        create_cyberware_tree_selection(
            [
                _real_rated(
                    "Synthetic Full Arm",
                    1,
                    plugins=(
                        CyberwarePurchaseRequest(
                            item_id=BY_NAME["Hand Blade"].id, plugins=(_real("Laser Sight"),)
                        ),
                    ),
                )
            ],
            ENTRIES,
            1_000_000,
        )


def test_smartlink_costs_essence_standalone_and_capacity_in_cybereyes() -> None:
    """p. 454's Smartlink row is 0.2 Essence / `[3]` Capacity / 4,000 nuyen -- the two-prices case
    the equipment-table legend describes ("only one applies, depending on whether you installed it
    in another item or in yourself").
    """
    standalone = create_cyberware_tree_selection([_real("Smartlink")], ENTRIES, 100000)
    assert standalone.essence_spent == Decimal("0.2")
    assert standalone.purchases[0].capacity_cost == Decimal(0)

    installed = create_cyberware_tree_selection(
        [_real_rated("Cybereyes Basic System", 1, plugins=(_real("Smartlink"),))], ENTRIES, 100000
    )
    (eyes,) = installed.purchases
    smartlink = next(p for p in eyes.plugins if p.item.name == "Smartlink")
    assert smartlink.capacity_cost == Decimal("3")
    assert installed.essence_spent == Decimal("0.2")  # the cybereyes', not the smartlink's


# --------------------------------------------------------------------------------------------
# Layer 3 (WP40): applying a purchase tree's Improvements to a character
# --------------------------------------------------------------------------------------------


def test_essence_and_flat_bonuses_reach_the_character_from_a_tree_purchase() -> None:
    """The tree applier mirrors WP32's flat one: every node grants an ESSENCE Improvement (0 for a
    plugin, since dual costing already zeroed it) plus whatever its `<bonus>` classified to.
    """
    character = _human_character()
    base_cm = physical_condition_monitor(character)

    selection = create_cyberware_tree_selection(
        [_real_rated("Synthetic Full Leg", 1, (_real_rated("Hydraulic Jacks", 2),))],
        ENTRIES,
        1_000_000,
    )
    apply_cyberware_tree_improvements(character, selection)

    # p. 457: a Synthetic full leg is 1 Essence and carries the Cyberlimb condition-monitor bonus;
    # its Hydraulic Jacks plugin costs Capacity, not Essence.
    assert essence(character) == Decimal(BASE_ESSENCE) - Decimal("1")
    assert physical_condition_monitor(character) == base_cm + 1


def test_vision_enhancement_raises_the_mental_limit_only_for_visual_perception() -> None:
    """WP40's headline acceptance case. p. 444: Vision enhancement "adds its Rating as a positive
    modifier to your limit on visual Perception Tests."
    """
    character = _human_character()
    base = mental_limit(character)

    selection = create_cyberware_tree_selection(
        [_real_rated("Cybereyes Basic System", 3, (_real_rated("Vision Enhancement", 2),))],
        ENTRIES,
        1_000_000,
    )
    apply_cyberware_tree_improvements(character, selection)

    assert mental_limit(character, context=ResolutionContext.PERCEPTION_VISUAL) == base + 2
    # A Memory test is Mental-limited but has no conditional bonus of its own, so it resolves the
    # plain figure -- the same one the character sheet shows.
    assert mental_limit(character) == base
    assert mental_limit(character, context=ResolutionContext.PERCEPTION_HEARING) == base


def test_audio_enhancement_and_spatial_recognizer_apply_under_their_own_contexts() -> None:
    character = _human_character()
    base = mental_limit(character)

    selection = create_cyberware_tree_selection(
        [
            _real_rated(
                "Cyberears",
                2,
                (_real_rated("Audio Enhancement", 3), _real("Spatial Recognizer")),
            )
        ],
        ENTRIES,
        1_000_000,
    )
    apply_cyberware_tree_improvements(character, selection)

    assert mental_limit(character, context=ResolutionContext.PERCEPTION_HEARING) == base + 3
    assert mental_limit(character, context=ResolutionContext.PERCEPTION_SOUND_SOURCE) == base + 2
    assert mental_limit(character, context=ResolutionContext.PERCEPTION_VISUAL) == base
    assert mental_limit(character) == base


def _legs_with_jacks(*ratings_per_leg: tuple[int, ...]) -> CyberwareTreeSelection:
    """One `Synthetic Full Leg` per argument, each holding jacks at the given ratings."""
    return create_cyberware_tree_selection(
        [
            _real_rated(
                "Synthetic Full Leg",
                1,
                tuple(_real_rated("Hydraulic Jacks", rating) for rating in ratings),
            )
            for ratings in ratings_per_leg
        ],
        ENTRIES,
        1_000_000,
    )


def test_a_matched_pair_of_hydraulic_jacks_grants_its_bonus_once() -> None:
    """p. 457: "This implant requires you to have two cyberlegs with a hydraulic jack of identical
    Ratings in each leg. Each Rating point adds a +1 to your Physical limit for jumping and
    sprinting." A per-node application would grant +2 x Rating here, which is the bug this exists
    to prevent.
    """
    character = _human_character()
    base = physical_limit(character)

    apply_cyberware_tree_improvements(character, _legs_with_jacks((2,), (2,)))

    assert physical_limit(character, context=ResolutionContext.GYMNASTICS_JUMPING) == base + 2
    assert physical_limit(character, context=ResolutionContext.RUNNING_SPRINTING) == base + 2
    assert physical_limit(character) == base
    bonuses = [
        imp
        for imp in character.improvements.improvements
        if imp.improvement_type is ImprovementType.PHYSICAL_LIMIT
    ]
    assert len(bonuses) == 1


def test_a_single_hydraulic_jack_grants_nothing() -> None:
    # "requires you to have two cyberlegs with a hydraulic jack ... in each leg" -- one leg's worth
    # is not the implant.
    character = _human_character()
    base = physical_limit(character)
    apply_cyberware_tree_improvements(character, _legs_with_jacks((3,)))
    assert physical_limit(character, context=ResolutionContext.GYMNASTICS_JUMPING) == base


def test_two_hydraulic_jacks_in_the_same_limb_are_not_a_pair() -> None:
    # Two jacks, one leg. The Capacity budget allows it; the rule does not make it an implant.
    character = _human_character()
    base = physical_limit(character)
    apply_cyberware_tree_improvements(character, _legs_with_jacks((1, 1)))
    assert physical_limit(character, context=ResolutionContext.GYMNASTICS_JUMPING) == base


def test_hydraulic_jacks_of_different_ratings_are_not_a_pair() -> None:
    # "a hydraulic jack of identical Ratings in each leg" -- mismatched ratings grant nothing, and
    # notably not the higher of the two.
    character = _human_character()
    base = physical_limit(character)
    apply_cyberware_tree_improvements(character, _legs_with_jacks((1,), (3,)))
    assert physical_limit(character, context=ResolutionContext.GYMNASTICS_JUMPING) == base


def test_two_pairs_of_jacks_collapse_to_the_highest_rating() -> None:
    # Not reachable with two legs, but this engine counts no limbs -- so the outcome is pinned
    # rather than left to chance. `unique_name` puts these in one "highest bonus wins" group.
    character = _human_character()
    base = physical_limit(character)
    apply_cyberware_tree_improvements(character, _legs_with_jacks((1, 4), (1, 4)))
    assert physical_limit(character, context=ResolutionContext.RUNNING_SPRINTING) == base + 4


def test_conditional_bonuses_leave_every_unconditional_derived_stat_untouched() -> None:
    # WP39's zero-drift guarantee, restated at the content layer: wiring real conditional bonuses
    # must not move any figure a character sheet already showed.
    character = _human_character()
    before = (mental_limit(character), physical_limit(character), social_limit(character))

    selection = create_cyberware_tree_selection(
        [
            _real_rated("Cybereyes Basic System", 3, (_real_rated("Vision Enhancement", 3),)),
            _real_rated("Cyberears", 1, (_real("Spatial Recognizer"),)),
        ],
        ENTRIES,
        1_000_000,
    )
    apply_cyberware_tree_improvements(character, selection)

    assert (mental_limit(character), physical_limit(character)) == before[:2]
    # social_limit moves only because Essence dropped, which is WP30/WP32 behaviour, not WP40's.
    assert social_limit(character) <= before[2]
