"""WP113: the Metatype Attribute Table's racial column -- Lifestyle surcharge, Troll Reach and
dermal armor."""

from __future__ import annotations

from chummer5.data.cyberware_subsystems import load_cyberware_entries
from chummer5.data.lifestyle import load_lifestyles
from chummer5.data.metatypes import load_metatypes
from chummer5.data.priorities import load_priorities
from chummer5.data.qualities import load_qualities
from chummer5.data.skills import load_skills
from chummer5.engine.character import Character
from chummer5.engine.cyberware_subsystems import CyberwarePurchaseRequest
from chummer5.engine.derived import armor, armor_breakdown, reach, unmodeled_effect_notes
from chummer5.engine.lifestyle import surcharged_monthly_cost
from chummer5.io.save_format import build_character, create_character_save

METATYPES = {m.name: m for m in load_metatypes()}
PRIORITIES = load_priorities()
CYBERWARE = load_cyberware_entries()


def _build(
    metatype: str,
    heritage: str,
    lifestyle: tuple[str, int] = ("Low", 3),
    gear: tuple[str, ...] = (),
    cyberware: tuple[CyberwarePurchaseRequest, ...] = (),
) -> Character:
    save = create_character_save(
        metatype_name=metatype,
        heritage_letter=heritage,
        attributes_letter="A",
        attribute_points={},
        skills_letter="E",
        skill_points={},
        group_points={},
        quality_picks=(),
        contacts=(),
        resources_letter="C",
        gear_names=gear,
        lifestyle_tier_name=lifestyle[0],
        lifestyle_months=lifestyle[1],
        cyberware_purchases=cyberware,
    )
    return build_character(
        save,
        metatypes=tuple(METATYPES.values()),
        priorities=PRIORITIES,
        skills=load_skills(),
        qualities=load_qualities(),
        lifestyles=load_lifestyles(),
        cyberware=CYBERWARE,
    )


def test_the_racial_bonuses_are_parsed() -> None:
    assert METATYPES["Dwarf"].lifestyle_cost_percent == 20
    troll = METATYPES["Troll"]
    assert (troll.lifestyle_cost_percent, troll.reach, troll.armor, troll.armor_group) == (
        100,
        1,
        1,
        "group0",
    )
    assert METATYPES["Human"].lifestyle_cost_percent == 0


def test_a_trolls_low_lifestyle_for_3_months_costs_12000() -> None:
    """The rulebook's Rob example: Low is 2,000¥ a month, doubled by the troll tax (p. 420)."""
    rob = _build("Troll", "B")
    assert rob.lifestyle_selection is not None
    assert rob.lifestyle_selection.monthly_cost == 4000
    assert rob.lifestyle_selection.total_cost == 12000


def test_a_dwarf_pays_20_percent_more() -> None:
    dwarf = _build("Dwarf", "B", lifestyle=("Low", 1))
    assert dwarf.lifestyle_selection is not None
    assert dwarf.lifestyle_selection.total_cost == 2400


def test_a_humans_lifestyle_is_unchanged() -> None:
    human = _build("Human", "D")
    assert human.lifestyle_selection is not None
    assert human.lifestyle_selection.total_cost == 6000


def test_troll_armor_includes_its_dermal_armor() -> None:
    troll = _build("Troll", "B", gear=("Armor Jacket",))
    assert armor(troll) == 13
    assert armor_breakdown(troll).improvements == 1


def test_dermal_plating_replaces_rather_than_stacks_with_troll_dermal_armor() -> None:
    plating = next(e for e in CYBERWARE if e.name == "Dermal Plating")
    troll = _build(
        "Troll",
        "B",
        cyberware=(CyberwarePurchaseRequest(item_id=plating.id, rating=2),),
    )
    assert armor(troll) == 2  # group0: the higher of 1 and 2, not 3


def test_troll_reach_is_a_sheet_number_with_a_registry_note() -> None:
    troll = _build("Troll", "B")
    assert reach(troll) == 1
    assert "Troll" in dict(unmodeled_effect_notes(troll))
    assert reach(_build("Human", "D")) == 0


def test_the_surcharge_rounds_up_to_the_nuyen() -> None:
    assert surcharged_monthly_cost(500, 20) == 600
    assert surcharged_monthly_cost(333, 10) == 367
