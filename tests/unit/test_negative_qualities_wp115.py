"""WP115: the remaining core negative qualities."""

from __future__ import annotations

from dataclasses import replace

import pytest

from chummer5.data.mentors import load_mentors
from chummer5.data.metatypes import load_metatypes
from chummer5.data.priorities import load_priorities
from chummer5.data.qualities import BonusSupport, load_qualities
from chummer5.data.skills import load_skills
from chummer5.engine.character import Character, create_character, metatype_choices
from chummer5.engine.derived import notoriety, wound_modifier_rule
from chummer5.engine.lifestyle import lifestyle_cost_percent
from chummer5.engine.qualities import (
    SCORCHED_EFFECT_CHOICES,
    SKILL_CHOICES,
    SPIRIT_TYPE_CHOICES,
    LaterStepFacts,
    QualityPickRequest,
    apply_metatype_bonus_improvements,
    apply_quality_improvements,
    create_quality_selection,
    mvp_quality_catalog,
    offerable_quality_catalog,
    resolve_metatype_qualities,
)
from chummer5.engine.skills import create_skill_allocation, dice_pool
from chummer5.io.legacy_import import _legacy_quality_choice

QUALITIES = load_qualities()
BY_NAME = {q.name: q for q in QUALITIES}
METATYPES = load_metatypes()
PRIORITIES = load_priorities()
SKILLS = load_skills()
SKILL = {s.name: s for s in SKILLS}

# The 36 negative rows this WP offers.
WP115_NAMES = frozenset(
    {
        *(f"Addiction ({s})" for s in ("Mild", "Moderate", "Severe", "Burnout")),
        *(
            f"Allergy ({p}, {s})"
            for p in ("Uncommon", "Common")
            for s in ("Mild", "Moderate", "Severe", "Extreme")
        ),
        *(
            f"Prejudiced ({p}, {d})"
            for p in ("Common", "Specific")
            for d in ("Biased", "Outspoken", "Radical")
        ),
        *(f"Dependent ({d})" for d in ("Nuisance", "Inconvenience", "Demanding")),
        "Astral Beacon",
        "Bad Luck",
        "Bad Rep",
        "Combat Paralysis",
        "Distinctive Style",
        "Elf Poser",
        "Gremlins",
        "Insomnia (Basic)",
        "Insomnia (Full)",
        "Loss of Confidence",
        "Low Pain Tolerance",
        "Ork Poser",
        "Scorched",
        "Spirit Bane",
        "Weak Immune System",
    }
)


def _character(metatype: str = "Human") -> Character:
    choice = next(
        c
        for c in metatype_choices(PRIORITIES.heritage["A"], METATYPES)
        if c.metatype.name == metatype
    )
    points = {"BOD": 2, "AGI": 3, "CHA": 3, "LOG": 2, "WIL": 1}
    character = create_character(choice, "A", "A", PRIORITIES, points)
    character = replace(
        character, metatype_qualities=resolve_metatype_qualities(choice.metatype, QUALITIES)
    )
    apply_metatype_bonus_improvements(character)
    return character


def _select(*picks: str | QualityPickRequest, **kwargs: object):  # type: ignore[no-untyped-def]
    return create_quality_selection(list(picks), QUALITIES, **kwargs)  # type: ignore[arg-type]


def _apply(character: Character, *picks: str | QualityPickRequest) -> Character:
    selection = _select(*picks, metatype_name=character.metatype.name)
    apply_quality_improvements(character, selection.qualities)
    return replace(character, quality_selection=selection)


def _with_skills(character: Character, points: dict[str, int], specs: dict[str, str]) -> Character:
    allocation = create_skill_allocation(
        "A",
        PRIORITIES,
        SKILLS,
        {SKILL[name].id: rating for name, rating in points.items()},
        {},
        {SKILL[name].id: spec for name, spec in specs.items()},
    )
    return replace(character, skill_allocation=allocation)


def _pick(name: str, **kwargs: object) -> QualityPickRequest:
    return QualityPickRequest(BY_NAME[name].id, **kwargs)  # type: ignore[arg-type]


# --- the offered catalog ---------------------------------------------------------------------


def test_every_wp115_row_is_offered_and_every_one_but_low_pain_tolerance_has_a_note() -> None:
    offered = {q.name for q in mvp_quality_catalog(QUALITIES)}
    assert offered >= WP115_NAMES
    for name in WP115_NAMES - {"Low Pain Tolerance"}:
        assert BY_NAME[name].unmodeled_effect_note, name
    # Low Pain Tolerance's whole effect is the wound interval, which is computed.
    assert BY_NAME["Low Pain Tolerance"].unmodeled_effect_note is None


# --- computed effects ------------------------------------------------------------------------


def test_dependents_raise_the_lifestyle_surcharge() -> None:
    human = _apply(_character(), BY_NAME["Dependent (Inconvenience)"].id)
    assert lifestyle_cost_percent(human) == 20
    troll = _apply(_character("Troll"), BY_NAME["Dependent (Demanding)"].id)
    assert lifestyle_cost_percent(troll) == 100 + 30


def test_dependents_are_mutually_exclusive() -> None:
    with pytest.raises(ValueError, match="cannot be taken together"):
        _select(BY_NAME["Dependent (Nuisance)"].id, BY_NAME["Dependent (Demanding)"].id)


def test_low_pain_tolerance_takes_a_modifier_every_two_boxes() -> None:
    character = _character()
    assert wound_modifier_rule(character).boxes_per_modifier == 3
    _apply(character, BY_NAME["Low Pain Tolerance"].id)
    assert wound_modifier_rule(character).boxes_per_modifier == 2


@pytest.mark.parametrize(
    ("severity", "penalty"), [("Mild", 0), ("Moderate", 0), ("Severe", 2), ("Burnout", 3)]
)
def test_severe_and_burnout_addictions_cost_social_dice(severity: str, penalty: int) -> None:
    """p. 78: Severe "-2 dice pool modifier to all Social Tests", Burnout "-3". The data only has
    Burnout's; Severe's is the rulebook-wins addition."""
    character = _with_skills(_character(), {"Etiquette": 3, "Pistols": 3}, {})
    allocation = character.skill_allocation
    assert allocation is not None
    etiquette_before = dice_pool(character, allocation, SKILL["Etiquette"])
    con_before = dice_pool(character, allocation, SKILL["Con"])  # defaulting, still Social
    pistols_before = dice_pool(character, allocation, SKILL["Pistols"])
    _apply(character, _pick(f"Addiction ({severity})", text="Novacoke"))
    assert dice_pool(character, allocation, SKILL["Etiquette"]) == etiquette_before - penalty
    assert dice_pool(character, allocation, SKILL["Con"]) == con_before - penalty
    assert dice_pool(character, allocation, SKILL["Pistols"]) == pistols_before


def test_loss_of_confidence_costs_two_dice_and_the_specialization() -> None:
    character = _with_skills(_character(), {"Pistols": 5, "Blades": 4}, {"Pistols": "Revolvers"})
    allocation = character.skill_allocation
    assert allocation is not None
    assert dice_pool(character, allocation, SKILL["Pistols"]) == 5 + 4 + 2  # AGI 4, spec +2
    _apply(character, _pick("Loss of Confidence", choice="Pistols"))
    assert dice_pool(character, allocation, SKILL["Pistols"]) == 5 + 4 - 2
    assert dice_pool(character, allocation, SKILL["Pistols"], specialized=True) == 5 + 4 - 2
    assert dice_pool(character, allocation, SKILL["Blades"]) == 4 + 4


def test_loss_of_confidence_needs_a_rating_four_skill_when_the_facts_are_known() -> None:
    assert "Pistols" in SKILL_CHOICES
    pick = _pick("Loss of Confidence", choice="Pistols")
    facts = LaterStepFacts(skill_ratings={"Pistols": 3}, owns_cyberdeck=False)
    with pytest.raises(ValueError, match="rating 4 or higher; Pistols is at 3"):
        _select(pick, later_steps=facts)
    _select(pick, later_steps=replace(facts, skill_ratings={"Pistols": 4}))
    # A save or import resolves qualities before skills and passes no facts: not checked there.
    _select(pick)


def test_loss_of_confidence_repeats_only_for_different_skills() -> None:
    first = _pick("Loss of Confidence", choice="Pistols")
    _select(first, _pick("Loss of Confidence", choice="Blades"))
    with pytest.raises(ValueError, match="the same quality instance was selected twice"):
        _select(first, first)
    with pytest.raises(ValueError, match="needs one of"):
        _select(_pick("Loss of Confidence"))


# --- choices and prerequisites ---------------------------------------------------------------


def test_scorched_takes_one_effect_from_the_table() -> None:
    assert len(SCORCHED_EFFECT_CHOICES) == 5
    _select(_pick("Scorched", choice="Migraines"))
    with pytest.raises(ValueError, match="needs one of"):
        _select(_pick("Scorched", choice="Headaches"))


def test_scorched_needs_a_btl_addiction_or_a_cyberdeck() -> None:
    scorched = _pick("Scorched", choice="Blackout")
    no_deck = LaterStepFacts(skill_ratings={}, owns_cyberdeck=False)
    with pytest.raises(ValueError, match="Scorched requires an Addiction to BTLs"):
        _select(scorched, later_steps=no_deck)
    with pytest.raises(ValueError, match="Scorched requires an Addiction to BTLs"):
        _select(scorched, _pick("Addiction (Mild)", text="Novacoke"), later_steps=no_deck)
    _select(scorched, _pick("Addiction (Mild)", text="Dreamchips (btl)"), later_steps=no_deck)
    _select(scorched, later_steps=replace(no_deck, owns_cyberdeck=True))
    _select(scorched)  # no facts: the decker half can't be judged, so nothing is checked


def test_spirit_bane_is_for_magic_users_and_names_a_spirit_type() -> None:
    bane = BY_NAME["Spirit Bane"]
    assert bane not in offerable_quality_catalog(_character(), QUALITIES)
    first = _pick("Spirit Bane", choice=SPIRIT_TYPE_CHOICES[0])
    second = _pick("Spirit Bane", choice=SPIRIT_TYPE_CHOICES[1])
    selection = _select(first, second, magic_type="Adept")
    assert selection.negative_karma == 14


def test_repeatable_negatives_need_distinct_details() -> None:
    _select(
        _pick("Allergy (Common, Mild)", text="Soy"), _pick("Allergy (Common, Mild)", text="Pollen")
    )
    with pytest.raises(ValueError, match="the same quality instance was selected twice"):
        _select(
            _pick("Prejudiced (Common, Biased)", text="Elves"),
            _pick("Prejudiced (Common, Biased)", text="Elves"),
        )
    with pytest.raises(ValueError, match="requires a free-text detail"):
        _select(_pick("Addiction (Mild)"))


def test_weak_immune_system_is_not_for_a_dwarf_and_excludes_the_resistances() -> None:
    weak = BY_NAME["Weak Immune System"]
    assert weak in offerable_quality_catalog(_character("Human"), QUALITIES)
    assert weak not in offerable_quality_catalog(_character("Dwarf"), QUALITIES)
    with pytest.raises(ValueError, match="cannot be taken together"):
        _select(weak.id, BY_NAME["Resistance to Toxins"].id)


def test_gremlins_is_rated_and_counts_notoriety_once() -> None:
    character = _apply(_character(), _pick("Gremlins", rating=4))
    assert character.quality_selection is not None
    assert character.quality_selection.negative_karma == 16
    assert notoriety(character) == 1
    with pytest.raises(ValueError, match="outside 1-4"):
        _select(_pick("Gremlins", rating=5))


def test_elf_poser_is_for_humans_only_and_ork_poser_for_humans_and_elves() -> None:
    elf = offerable_quality_catalog(_character("Elf"), QUALITIES)
    assert BY_NAME["Elf Poser"] not in elf
    assert BY_NAME["Ork Poser"] in elf
    assert BY_NAME["Ork Poser"] not in offerable_quality_catalog(_character("Ork"), QUALITIES)


# --- the rulebook's Step Four worked examples ------------------------------------------------


def test_james_step_four() -> None:
    """19 Karma of positives, 20 of negatives: 25 Karma becomes 26."""
    selection = _select(
        BY_NAME["Natural Hardening"].id,
        BY_NAME["Analytical Mind"].id,
        BY_NAME["Resistance to Toxins"].id,
        _pick("Addiction (Moderate)", text="BTLs"),
        BY_NAME["Dependent (Inconvenience)"].id,
        _pick("Prejudiced (Common, Biased)", text="Corporate Wageslaves"),
    )
    assert (selection.positive_karma, selection.negative_karma) == (19, 20)
    assert 25 - selection.karma_cost == 26


def test_rob_step_four() -> None:
    """20 Karma each way: 25 stays 25."""
    selection = _select(
        _pick("Exceptional Attribute", choice="STR"),
        BY_NAME["Quick Healer"].id,
        _pick("Will to Live", rating=1),
        _pick("SINner (National)", text="UCAS"),
        BY_NAME["Bad Rep"].id,
        _pick("Gremlins", rating=2),
        metatype_name="Troll",
    )
    assert (selection.positive_karma, selection.negative_karma) == (20, 20)
    assert 25 - selection.karma_cost == 25


def test_kyra_step_four() -> None:
    """Kyra is a Mystic Adept (out of scope), so her 10 Karma of Power Points is taken off by
    hand; her qualities are built as a Magician's. 13 + 10 spent, 24 gained: 25 becomes 26."""
    sea = next(m for m in load_mentors() if m.name == "Sea")
    selection = _select(
        _pick("Focused Concentration", rating=2),
        BY_NAME["Mentor Spirit"].id,
        _pick("Code of Honor", text="Never kills elves"),
        BY_NAME["Distinctive Style"].id,
        _pick("Addiction (Mild)", text="Bliss"),
        magic_type="Magician",
        mentor_catalog=load_mentors(),
        mentor_spirit_archetype_id=sea.id,
    )
    assert (selection.positive_karma, selection.negative_karma) == (13, 24)
    assert 25 - selection.karma_cost - 10 == 26


# --- legacy import -----------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("name", "extra", "choice"),
    [
        ("Spirit Bane", "Man", "Spirit of Man"),
        ("Exceptional Attribute", "INT", "INT"),
        ("Scorched", "Memory Loss (short term)", "MemoryLossShortTerm"),
        ("Home Ground", "You Know a Guy", "YouKnowAGuy"),
        ("Loss of Confidence", "Pistols", "Pistols"),
        ("Exceptional Attribute", "RES", None),  # Resonance is out of scope: dropped
        ("Spirit Bane", "", None),
    ],
)
def test_a_legacy_extra_becomes_the_pick_choice(name: str, extra: str, choice: str | None) -> None:
    assert _legacy_quality_choice(BY_NAME[name], extra, magic_enabled=True) == choice


def test_offered_negative_support_kinds() -> None:
    assert BY_NAME["Addiction (Burnout)"].bonus_support is BonusSupport.SELECT_TEXT
    assert BY_NAME["Loss of Confidence"].bonus_support is BonusSupport.FLAT_BONUS
    assert BY_NAME["Loss of Confidence"].choice_kind == "skill"
    assert BY_NAME["Loss of Confidence"].choice_minimum_rating == 4
