from dataclasses import replace
from types import MappingProxyType

import pytest

from chummer5.data.metatypes import load_metatypes
from chummer5.data.priorities import load_priorities
from chummer5.data.skills import load_skills
from chummer5.data.spells import load_spells
from chummer5.data.traditions import load_traditions
from chummer5.engine.character import Character, create_character, metatype_choices
from chummer5.engine.improvements import ImprovementType
from chummer5.engine.magic import (
    MagicSelection,
    SpellSelection,
    apply_magic_skill_grant_improvements,
    create_magic_selection,
    create_spell_selection,
    magic_skill_grant_eligible_skills,
    offered_talent_options,
)
from chummer5.engine.skills import SkillAllocation, dice_pool

PRIORITIES = load_priorities()
TRADITIONS = load_traditions()
SKILLS = load_skills()
SPELLS = load_spells()
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
        "A", "Magician", HERMETIC_ID, [COUNTERSPELLING_ID, SPELLCASTING_ID],
        PRIORITIES, TRADITIONS, SKILLS,
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
            "A", "Magician", HERMETIC_ID, [COUNTERSPELLING_ID, PISTOLS_ID],
            PRIORITIES, TRADITIONS, SKILLS,
        )


def test_magician_free_skill_grant_rejects_wrong_count() -> None:
    with pytest.raises(ValueError, match="grants exactly 2"):
        create_magic_selection(
            "A", "Magician", HERMETIC_ID, [COUNTERSPELLING_ID], PRIORITIES, TRADITIONS, SKILLS
        )


def test_magician_free_skill_grant_rejects_duplicates() -> None:
    with pytest.raises(ValueError, match="selected more than once"):
        create_magic_selection(
            "A", "Magician", HERMETIC_ID, [COUNTERSPELLING_ID, COUNTERSPELLING_ID],
            PRIORITIES, TRADITIONS, SKILLS,
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
    selection = create_spell_selection([MANABOLT_ID, STUNBOLT_ID], SPELLS, budget=10)
    assert selection == SpellSelection(
        spells=tuple(s for s in SPELLS if s.id in {MANABOLT_ID, STUNBOLT_ID}),
        budget=10,
    )


def test_spell_selection_allows_partial_spend() -> None:
    # Mirrors every other create_* function's "doesn't require the full budget to be spent" rule.
    selection = create_spell_selection([MANABOLT_ID], SPELLS, budget=10)
    assert len(selection.spells) == 1


def test_spell_selection_rejects_unknown_id() -> None:
    with pytest.raises(ValueError, match="not an SR5-scoped spell id"):
        create_spell_selection(["not-a-real-id"], SPELLS, budget=10)


def test_spell_selection_rejects_duplicates() -> None:
    with pytest.raises(ValueError, match="selected more than once"):
        create_spell_selection([MANABOLT_ID, MANABOLT_ID], SPELLS, budget=10)


def test_spell_selection_rejects_exceeding_budget() -> None:
    with pytest.raises(ValueError, match="exceeding the budget of 2"):
        create_spell_selection([MANABOLT_ID, STUNBOLT_ID, HEAL_ID], SPELLS, budget=2)


def test_spell_selection_zero_budget_rejects_any_pick() -> None:
    # Adept/Mundane characters have no spell grant at all -- a caller passing budget=0 for either
    # already gets the right rejection with no magic_type check needed inside this function.
    with pytest.raises(ValueError, match="exceeding the budget of 0"):
        create_spell_selection([MANABOLT_ID], SPELLS, budget=0)


def test_spell_selection_empty_pick_with_zero_budget_is_fine() -> None:
    selection = create_spell_selection([], SPELLS, budget=0)
    assert selection == SpellSelection(spells=(), budget=0)
