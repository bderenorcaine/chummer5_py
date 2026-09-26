from dataclasses import replace
from decimal import Decimal
from types import MappingProxyType

import pytest

from chummer5.data.metatypes import load_metatypes
from chummer5.data.powers import load_powers
from chummer5.data.priorities import load_priorities
from chummer5.data.skills import load_skills
from chummer5.data.spells import load_spells
from chummer5.data.traditions import load_traditions
from chummer5.engine.character import Character, create_character, metatype_choices
from chummer5.engine.improvements import ImprovementSource, ImprovementType
from chummer5.engine.magic import (
    MagicSelection,
    PowerSelection,
    SpellSelection,
    apply_magic_skill_grant_improvements,
    apply_power_improvements,
    create_magic_attribute_points,
    create_magic_selection,
    create_power_selection,
    create_spell_selection,
    magic_skill_grant_eligible_skills,
    offered_talent_options,
)
from chummer5.engine.skills import SkillAllocation, dice_pool

PRIORITIES = load_priorities()
TRADITIONS = load_traditions()
SKILLS = load_skills()
SPELLS = load_spells()
POWERS = load_powers()
METATYPES = load_metatypes()

HERMETIC_ID = next(t.id for t in TRADITIONS if t.name == "Hermetic")
PISTOLS_ID = next(s.id for s in SKILLS if s.name == "Pistols")
COUNTERSPELLING_ID = next(s.id for s in SKILLS if s.name == "Counterspelling")
SPELLCASTING_ID = next(s.id for s in SKILLS if s.name == "Spellcasting")
COMPILING_ID = next(s.id for s in SKILLS if s.name == "Compiling")


# -- Mundane --------------------------------------------------------------------------------


def test_mundane_resolves_to_no_magic() -> None:
    selection = create_magic_selection("E", "Mundane", None, [], PRIORITIES, TRADITIONS, SKILLS)
    assert selection == MagicSelection(
        magic_type=None,
        magic_rating=0,
        tradition=None,
        granted_skill_ids=(),
        granted_skill_rating=0,
    )


def test_mundane_rejects_a_tradition() -> None:
    with pytest.raises(ValueError, match="cannot choose a tradition"):
        create_magic_selection("E", "Mundane", HERMETIC_ID, [], PRIORITIES, TRADITIONS, SKILLS)


def test_mundane_rejects_a_free_skill_grant() -> None:
    with pytest.raises(ValueError, match="no Talent free-skill grant"):
        create_magic_selection("E", "Mundane", None, [PISTOLS_ID], PRIORITIES, TRADITIONS, SKILLS)


# -- Magician ---------------------------------------------------------------------------------


def test_magician_letter_a_resolves_magic_rating_tradition_and_free_skills() -> None:
    # Hand-checked against priorities.xml (also matches Miko.chum5): letter A's Magician grants 6
    # Magic and 2 free skills at rating 5, drawn from the "magic" skilltype filter.
    selection = create_magic_selection(
        "A",
        "Magician",
        HERMETIC_ID,
        [COUNTERSPELLING_ID, SPELLCASTING_ID],
        PRIORITIES,
        TRADITIONS,
        SKILLS,
    )
    assert selection.magic_type == "Magician"
    assert selection.magic_rating == 6
    assert selection.tradition is not None
    assert selection.tradition.name == "Hermetic"
    assert set(selection.granted_skill_ids) == {COUNTERSPELLING_ID, SPELLCASTING_ID}
    assert selection.granted_skill_rating == 5


def test_magician_requires_a_tradition() -> None:
    with pytest.raises(ValueError, match="requires a tradition"):
        create_magic_selection("A", "Magician", None, [], PRIORITIES, TRADITIONS, SKILLS)


def test_magician_rejects_unknown_tradition_id() -> None:
    with pytest.raises(ValueError, match="not an offered tradition"):
        create_magic_selection("A", "Magician", "not-a-real-id", [], PRIORITIES, TRADITIONS, SKILLS)


def test_magician_letter_c_grants_no_free_skill() -> None:
    # Hand-checked: letter C's Magician option has no <skillqty> at all (unlike A/B).
    selection = create_magic_selection(
        "C", "Magician", HERMETIC_ID, [], PRIORITIES, TRADITIONS, SKILLS
    )
    assert selection.magic_rating == 3
    assert selection.granted_skill_ids == ()
    with pytest.raises(ValueError, match="grants no free skill"):
        create_magic_selection(
            "C", "Magician", HERMETIC_ID, [COUNTERSPELLING_ID], PRIORITIES, TRADITIONS, SKILLS
        )


def test_magician_free_skill_grant_rejects_ineligible_skill() -> None:
    # Pistols is Combat Active, not Magical/Pseudo-Magical Active -- not eligible for the "magic"
    # skilltype grant.
    with pytest.raises(ValueError, match="not eligible"):
        create_magic_selection(
            "A",
            "Magician",
            HERMETIC_ID,
            [COUNTERSPELLING_ID, PISTOLS_ID],
            PRIORITIES,
            TRADITIONS,
            SKILLS,
        )


def test_magician_free_skill_grant_rejects_wrong_count() -> None:
    with pytest.raises(ValueError, match="grants exactly 2"):
        create_magic_selection(
            "A", "Magician", HERMETIC_ID, [COUNTERSPELLING_ID], PRIORITIES, TRADITIONS, SKILLS
        )


def test_magician_free_skill_grant_rejects_duplicates() -> None:
    with pytest.raises(ValueError, match="selected more than once"):
        create_magic_selection(
            "A",
            "Magician",
            HERMETIC_ID,
            [COUNTERSPELLING_ID, COUNTERSPELLING_ID],
            PRIORITIES,
            TRADITIONS,
            SKILLS,
        )


# -- Adept --------------------------------------------------------------------------------------


def test_adept_letter_c_resolves_magic_rating_and_xpath_free_skill() -> None:
    # Correction to the Implementation Plan's own claim ("Adept letter B grants 1 at rating 4,
    # letters C/D grant none") -- letter C *does* grant one, at rating 2, confirmed against both
    # priorities.xml directly and Wesson.chum5's own <priorityskills> (Pistols). See
    # spec/worklogs/WP25.md.
    selection = create_magic_selection(
        "C", "Adept", None, [PISTOLS_ID], PRIORITIES, TRADITIONS, SKILLS
    )
    assert selection.magic_type == "Adept"
    assert selection.magic_rating == 4
    assert selection.tradition is None
    assert selection.granted_skill_ids == (PISTOLS_ID,)
    assert selection.granted_skill_rating == 2


def test_adept_cannot_choose_a_tradition() -> None:
    with pytest.raises(ValueError, match="cannot choose a tradition"):
        create_magic_selection("C", "Adept", HERMETIC_ID, [], PRIORITIES, TRADITIONS, SKILLS)


def test_adept_free_skill_grant_rejects_magical_active_skill_with_a_group() -> None:
    # Counterspelling is Magical Active *and* belongs to the Sorcery skill group -- excluded by the
    # xpath predicate's second clause.
    with pytest.raises(ValueError, match="not eligible"):
        create_magic_selection(
            "C", "Adept", None, [COUNTERSPELLING_ID], PRIORITIES, TRADITIONS, SKILLS
        )


def test_adept_free_skill_grant_rejects_resonance_linked_skill() -> None:
    with pytest.raises(ValueError, match="not eligible"):
        create_magic_selection("C", "Adept", None, [COMPILING_ID], PRIORITIES, TRADITIONS, SKILLS)


def test_adept_letter_d_grants_no_free_skill() -> None:
    selection = create_magic_selection("D", "Adept", None, [], PRIORITIES, TRADITIONS, SKILLS)
    assert selection.magic_rating == 2
    assert selection.granted_skill_ids == ()


def test_adept_not_offered_at_letter_a() -> None:
    with pytest.raises(ValueError, match="not an offered Talent option"):
        create_magic_selection("A", "Adept", None, [], PRIORITIES, TRADITIONS, SKILLS)


# -- Scope cuts: Mystic Adept/Technomancer/A.I. are never offered ------------------------------


def test_mystic_adept_is_never_offered() -> None:
    assert "Mystic Adept" not in {opt.codename for opt in offered_talent_options("A", PRIORITIES)}
    with pytest.raises(ValueError, match="not an offered Talent option"):
        create_magic_selection("A", "Mystic Adept", None, [], PRIORITIES, TRADITIONS, SKILLS)


def test_technomancer_is_never_offered() -> None:
    assert "Technomancer" not in {opt.codename for opt in offered_talent_options("A", PRIORITIES)}


# -- magic_skill_grant_eligible_skills ------------------------------------------------------------


def test_magic_skilltype_filters_to_magical_categories() -> None:
    option = PRIORITIES.talent["A"].options[0]
    assert option.codename == "Magician"
    eligible = {s.name for s in magic_skill_grant_eligible_skills(option, SKILLS)}
    assert "Counterspelling" in eligible
    assert "Arcana" in eligible  # Pseudo-Magical Active
    assert "Pistols" not in eligible


def test_xpath_skilltype_excludes_res_dep_and_grouped_magical_skills() -> None:
    option = next(o for o in PRIORITIES.talent["C"].options if o.codename == "Adept")
    eligible = {s.name for s in magic_skill_grant_eligible_skills(option, SKILLS)}
    assert "Pistols" in eligible
    assert "Compiling" not in eligible
    assert "Counterspelling" not in eligible  # Magical Active with a non-empty skill group


def test_unrecognized_skill_type_raises() -> None:
    option = next(o for o in PRIORITIES.talent["C"].options if o.codename == "Adept")
    with pytest.raises(ValueError, match="unrecognized"):
        magic_skill_grant_eligible_skills(replace(option, skill_type="something-else"), SKILLS)


# -- apply_magic_skill_grant_improvements: reuses the SKILL Improvement mechanism, doesn't touch
# SkillAllocation's budget -----------------------------------------------------------------------


def _mundane_human() -> Character:
    heritage = PRIORITIES.heritage["D"]
    human = next(c for c in metatype_choices(heritage, METATYPES) if c.metatype.name == "Human")
    return create_character(
        metatype_choice=human,
        heritage_letter="D",
        attributes_letter="A",
        priorities=PRIORITIES,
        attribute_points={},
    )


def test_free_skill_grant_shows_up_in_dice_pool_without_skill_allocation_budget() -> None:
    character = _mundane_human()
    selection = create_magic_selection(
        "C", "Adept", None, [PISTOLS_ID], PRIORITIES, TRADITIONS, SKILLS
    )
    apply_magic_skill_grant_improvements(character, selection, SKILLS)

    assert character.improvements.resolve(ImprovementType.SKILL, "Pistols") == 2

    pistols = next(s for s in SKILLS if s.id == PISTOLS_ID)
    empty_allocation = SkillAllocation(
        skill_points=MappingProxyType({}), group_points=MappingProxyType({})
    )
    # rating 2 (the grant) + AGI 1 (Human's bare metatype minimum, unspent) = 3; no points were
    # spent from any Skills-priority budget to get there.
    assert dice_pool(character, empty_allocation, pistols) == 2 + character.attribute_value("AGI")


# -- create_spell_selection (WP26) ---------------------------------------------------------------

MANABOLT_ID = next(s.id for s in SPELLS if s.name == "Manabolt")
STUNBOLT_ID = next(s.id for s in SPELLS if s.name == "Stunbolt")
HEAL_ID = next(s.id for s in SPELLS if s.name == "Heal")


def test_spell_selection_within_budget() -> None:
    selection = create_spell_selection(
        [MANABOLT_ID, STUNBOLT_ID], SPELLS, budget=10, magic_rating=6, karma_budget=0
    )
    assert selection == SpellSelection(
        spells=tuple(s for s in SPELLS if s.id in {MANABOLT_ID, STUNBOLT_ID}),
        budget=10,
        karma_spell_count=0,
        karma_cost=0,
    )


def test_spell_selection_allows_partial_spend() -> None:
    # Mirrors every other create_* function's "doesn't require the full budget to be spent" rule.
    selection = create_spell_selection(
        [MANABOLT_ID], SPELLS, budget=10, magic_rating=6, karma_budget=0
    )
    assert len(selection.spells) == 1


def test_spell_selection_rejects_unknown_id() -> None:
    with pytest.raises(ValueError, match="not an SR5-scoped spell id"):
        create_spell_selection(["not-a-real-id"], SPELLS, budget=10, magic_rating=6, karma_budget=0)


def test_spell_selection_rejects_duplicates() -> None:
    with pytest.raises(ValueError, match="selected more than once"):
        create_spell_selection(
            [MANABOLT_ID, MANABOLT_ID], SPELLS, budget=10, magic_rating=6, karma_budget=0
        )


# -- WP54: Karma-funded extra spells, beyond the free budget, up to the Magic Rating x2 cap ------


def test_spell_selection_beyond_free_budget_is_karma_funded() -> None:
    # 3 spells picked against a free budget of 2: 1 spell is Karma-funded at 5 Karma (KARMA_PER_
    # SPELL), well within both the Magic 6 x2 = 12 known cap and a 5-Karma budget.
    selection = create_spell_selection(
        [MANABOLT_ID, STUNBOLT_ID, HEAL_ID], SPELLS, budget=2, magic_rating=6, karma_budget=5
    )
    assert selection.karma_spell_count == 1
    assert selection.karma_cost == 5
    assert len(selection.spells) == 3


def test_spell_selection_rejects_exceeding_the_magic_rating_x2_known_cap() -> None:
    # Magic 2 -> known cap 4; 5 spells picked, even with an enormous Karma budget, still rejected.
    five_ids = [s.id for s in SPELLS[:5]]
    with pytest.raises(ValueError, match="Magic Rating x2 cap of 4"):
        create_spell_selection(five_ids, SPELLS, budget=2, magic_rating=2, karma_budget=10**6)


def test_spell_selection_rejects_exceeding_the_karma_budget() -> None:
    # 1 spell beyond the free budget of 2 costs 5 Karma, exceeding a 4-Karma budget.
    with pytest.raises(ValueError, match="exceeding the Karma budget of 4"):
        create_spell_selection(
            [MANABOLT_ID, STUNBOLT_ID, HEAL_ID], SPELLS, budget=2, magic_rating=6, karma_budget=4
        )


def test_spell_selection_zero_budget_and_zero_magic_rating_rejects_any_pick() -> None:
    # Adept/Mundane characters have no spell grant and no Magic Rating x2 cap headroom at all -- a
    # caller passing budget=0, magic_rating=0 for either already gets the right rejection (via the
    # known-spells cap, now 0) with no magic_type check needed inside this function.
    with pytest.raises(ValueError, match="Magic Rating x2 cap of 0"):
        create_spell_selection([MANABOLT_ID], SPELLS, budget=0, magic_rating=0, karma_budget=10**6)


def test_spell_selection_empty_pick_with_zero_budget_is_fine() -> None:
    selection = create_spell_selection([], SPELLS, budget=0, magic_rating=0, karma_budget=0)
    assert selection == SpellSelection(spells=(), budget=0, karma_spell_count=0, karma_cost=0)


# -- create_power_selection (WP27) -----------------------------------------------------------

ENHANCED_PERCEPTION_ID = next(p.id for p in POWERS if p.name == "Enhanced Perception")
IMPROVED_PHYSICAL_ATTRIBUTE_ID = next(
    p.id for p in POWERS if p.name == "Improved Physical Attribute"
)
IMPROVED_POTENTIAL_PHYSICAL_ID = next(
    p.id for p in POWERS if p.name == "Improved Potential (Physical)"
)
VOICE_CONTROL_ID = next(p.id for p in POWERS if p.name == "Voice Control")
ATTRIBUTE_BOOST_ID = next(p.id for p in POWERS if p.name == "Attribute Boost")  # NOT_YET_SUPPORTED


def test_power_selection_within_budget() -> None:
    selection = create_power_selection(
        [(ENHANCED_PERCEPTION_ID, 1, None)], POWERS, power_point_budget=4
    )
    assert selection.power_points_spent == Decimal("0.5")
    assert selection.power_point_budget == 4
    assert len(selection.picks) == 1
    assert selection.picks[0].power.name == "Enhanced Perception"
    assert selection.picks[0].rating == 1
    assert selection.picks[0].target is None


def test_power_selection_allows_partial_spend() -> None:
    selection = create_power_selection([], POWERS, power_point_budget=4)
    assert selection == PowerSelection(
        picks=(), power_points_spent=Decimal(0), power_point_budget=4
    )


def test_power_selection_rejects_unknown_id() -> None:
    with pytest.raises(ValueError, match="not an MVP-offered power id"):
        create_power_selection([("not-a-real-id", 1, None)], POWERS, power_point_budget=4)


def test_power_selection_rejects_not_yet_supported_power() -> None:
    # Attribute Boost is a real SR5 power but NOT_YET_SUPPORTED (see test_powers.py) -- it's
    # excluded from mvp_power_catalog, so it's rejected the same way an unknown id is.
    with pytest.raises(ValueError, match="not an MVP-offered power id"):
        create_power_selection([(ATTRIBUTE_BOOST_ID, 1, None)], POWERS, power_point_budget=4)


def test_power_selection_rejects_duplicate_pick() -> None:
    with pytest.raises(ValueError, match="selected more than once"):
        create_power_selection(
            [(ENHANCED_PERCEPTION_ID, 1, None), (ENHANCED_PERCEPTION_ID, 1, None)],
            POWERS,
            power_point_budget=4,
        )


def test_power_selection_rejects_exceeding_budget() -> None:
    # Improved Physical Attribute costs 1 PP/level; rating 3 = 3 PP, over a budget of 2.
    with pytest.raises(ValueError, match="out of range 1..2"):
        create_power_selection(
            [(IMPROVED_PHYSICAL_ATTRIBUTE_ID, 3, "BOD")], POWERS, power_point_budget=2
        )


def test_power_selection_rejects_total_spend_exceeding_budget() -> None:
    # Two picks each individually within their own rating cap, but their summed cost exceeds budget.
    with pytest.raises(ValueError, match="exceeding the budget of 1"):
        create_power_selection(
            [
                (IMPROVED_PHYSICAL_ATTRIBUTE_ID, 1, "BOD"),
                (IMPROVED_POTENTIAL_PHYSICAL_ID, 1, None),
            ],
            POWERS,
            power_point_budget=1,
        )


def test_power_selection_rejects_rating_below_one() -> None:
    with pytest.raises(ValueError, match="out of range 1.."):
        create_power_selection([(ENHANCED_PERCEPTION_ID, 0, None)], POWERS, power_point_budget=4)


def test_power_selection_rejects_rating_above_power_point_budget_cap() -> None:
    # Rulebook p.308: max levels of any one power is the lesser of the power's own limit and the
    # Magic rating. Voice Control's own limit is 20, but a budget of 2 caps it at 2.
    with pytest.raises(ValueError, match="out of range 1..2"):
        create_power_selection([(VOICE_CONTROL_ID, 3, None)], POWERS, power_point_budget=2)


def test_power_selection_rejects_nonlevels_power_with_rating_other_than_one() -> None:
    with pytest.raises(ValueError, match="has no levels; rating must be 1"):
        create_power_selection(
            [(IMPROVED_POTENTIAL_PHYSICAL_ID, 2, None)], POWERS, power_point_budget=4
        )


def test_power_selection_select_attribute_requires_selected_attribute() -> None:
    with pytest.raises(ValueError, match="needs one of"):
        create_power_selection(
            [(IMPROVED_PHYSICAL_ATTRIBUTE_ID, 1, None)], POWERS, power_point_budget=4
        )


def test_power_selection_select_attribute_rejects_ineligible_attribute() -> None:
    with pytest.raises(ValueError, match="needs one of"):
        create_power_selection(
            [(IMPROVED_PHYSICAL_ATTRIBUTE_ID, 1, "LOG")], POWERS, power_point_budget=4
        )


def test_power_selection_rejects_selected_attribute_when_not_needed() -> None:
    with pytest.raises(ValueError, match="does not take a target"):
        create_power_selection([(ENHANCED_PERCEPTION_ID, 1, "BOD")], POWERS, power_point_budget=4)


def test_power_selection_select_attribute_success() -> None:
    selection = create_power_selection(
        [(IMPROVED_PHYSICAL_ATTRIBUTE_ID, 2, "AGI")], POWERS, power_point_budget=4
    )
    assert selection.power_points_spent == Decimal("2")
    assert selection.picks[0].target == "AGI"
    assert selection.picks[0].rating == 2


# -- apply_power_improvements ------------------------------------------------------------------


def test_apply_power_improvements_select_attribute_raises_the_chosen_attribute() -> None:
    character = _mundane_human()
    selection = create_power_selection(
        [(IMPROVED_PHYSICAL_ATTRIBUTE_ID, 2, "AGI")], POWERS, power_point_budget=4
    )
    apply_power_improvements(character, selection)
    assert character.improvements.resolve(ImprovementType.ATTRIBUTE, "AGI") == 2
    assert character.improvements.resolve(ImprovementType.ATTRIBUTE, "BOD") == 0


def test_apply_power_improvements_limit_bonus() -> None:
    character = _mundane_human()
    selection = create_power_selection(
        [(IMPROVED_POTENTIAL_PHYSICAL_ID, 1, None)], POWERS, power_point_budget=4
    )
    apply_power_improvements(character, selection)
    assert character.improvements.resolve(ImprovementType.PHYSICAL_LIMIT, "") == 1


def test_apply_power_improvements_enhanced_perception_raises_two_named_skills() -> None:
    # Enhanced Perception's own <limit> is 1 (confirmed in the raw XML) despite levels=True, so
    # rating is capped at 1 regardless of Power Point budget.
    character = _mundane_human()
    selection = create_power_selection(
        [(ENHANCED_PERCEPTION_ID, 1, None)], POWERS, power_point_budget=4
    )
    apply_power_improvements(character, selection)
    assert character.improvements.resolve(ImprovementType.SKILL, "Perception") == 1
    assert character.improvements.resolve(ImprovementType.SKILL, "Assensing") == 1


def test_apply_power_improvements_voice_control_raises_limit_and_skill_together() -> None:
    character = _mundane_human()
    selection = create_power_selection([(VOICE_CONTROL_ID, 3, None)], POWERS, power_point_budget=4)
    apply_power_improvements(character, selection)
    assert character.improvements.resolve(ImprovementType.SOCIAL_LIMIT, "") == 3
    assert character.improvements.resolve(ImprovementType.SKILL, "Impersonation") == 3


def test_apply_power_improvements_source_id_is_the_powers_own_id() -> None:
    character = _mundane_human()
    selection = create_power_selection(
        [(IMPROVED_POTENTIAL_PHYSICAL_ID, 1, None)], POWERS, power_point_budget=4
    )
    apply_power_improvements(character, selection)
    (improvement,) = character.improvements.improvements
    assert improvement.source_type == ImprovementSource.ADEPT_POWER
    assert improvement.source_id == IMPROVED_POTENTIAL_PHYSICAL_ID


# -- create_magic_attribute_points (post-WP29 correction) --------------------------------------
# Core rulebook p.65: Special Attribute Points "may be split... between... Edge and Magic or
# Resonance." See spec/rulebooks/learnings.md's "Post-WP29 correction" entry for the full research.


def test_magic_attribute_points_mundane_rejects_any_nonzero_spend() -> None:
    with pytest.raises(ValueError, match="not allocatable"):
        create_magic_attribute_points(None, 1, 0, 6, 3, 0)


def test_magic_attribute_points_mundane_allows_zero() -> None:
    assert create_magic_attribute_points(None, 0, 0, 6, 3, 0) == 0


def test_magic_attribute_points_rejects_negative() -> None:
    with pytest.raises(ValueError, match="must not be negative"):
        create_magic_attribute_points("Adept", -1, 4, 6, 3, 0)


def test_magic_attribute_points_rejects_exceeding_the_metatype_magic_maximum() -> None:
    with pytest.raises(ValueError, match="exceed the metatype's Magic maximum"):
        create_magic_attribute_points("Adept", 3, 4, 6, 5, 0)


def test_magic_attribute_points_rejects_exceeding_the_shared_special_attribute_budget() -> None:
    # magic_rating=2, magic_maximum=6 leaves plenty of headroom on MAG alone, but 2 points on top
    # of 2 already spent on EDG exceeds a budget of 3.
    with pytest.raises(ValueError, match="Edge \\+ Magic combined"):
        create_magic_attribute_points("Adept", 2, 2, 6, 3, 2)


def test_magic_attribute_points_valid_spend_returns_the_points_unchanged() -> None:
    assert create_magic_attribute_points("Magician", 2, 4, 6, 3, 1) == 2


def test_magic_attribute_points_zero_spend_is_always_fine_for_a_magic_active_character() -> None:
    assert create_magic_attribute_points("Adept", 0, 6, 6, 0, 0) == 0
