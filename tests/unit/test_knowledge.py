"""Tests for `chummer5.engine.knowledge` (WP49): Knowledge/Language skill selection."""

from __future__ import annotations

from dataclasses import replace

import pytest

from chummer5.data.metatypes import load_metatypes
from chummer5.data.priorities import load_priorities
from chummer5.data.qualities import load_qualities
from chummer5.engine.character import Character, create_character, metatype_choices
from chummer5.engine.improvements import ImprovementType
from chummer5.engine.knowledge import (
    BASE_NATIVE_LANGUAGE_LIMIT,
    KARMA_KNOWLEDGE_PER_RATING,
    KnowledgeSkillPick,
    LanguageSkillPick,
    create_karma_knowledge_selection,
    create_knowledge_selection,
    free_knowledge_points,
    native_language_limit,
)
from chummer5.engine.qualities import apply_quality_improvements
from chummer5.engine.skills import MAX_SKILL_RATING_CREATE

METATYPES = load_metatypes()
PRIORITIES = load_priorities()
QUALITIES = load_qualities()


def _human_with_int_log(int_points: int, log_points: int) -> Character:
    heritage = PRIORITIES.heritage["D"]
    human = next(c for c in metatype_choices(heritage, METATYPES) if c.metatype.name == "Human")
    return create_character(
        metatype_choice=human,
        heritage_letter="D",
        attributes_letter="A",
        priorities=PRIORITIES,
        attribute_points={"INT": int_points, "LOG": log_points},
    )


def test_free_knowledge_points_is_int_plus_log_times_two() -> None:
    # Human metatype minimum for both INT/LOG is 1 -- 0 points spent on either still gives a
    # nonzero (1+1)*2 = 4 point floor, confirmed directly rather than assumed.
    character = _human_with_int_log(0, 0)
    assert character.attribute_value("INT") == 1
    assert character.attribute_value("LOG") == 1
    assert free_knowledge_points(character) == 4

    character = _human_with_int_log(3, 2)
    assert character.attribute_value("INT") == 4
    assert character.attribute_value("LOG") == 3
    assert free_knowledge_points(character) == 14


def test_native_language_limit_is_one_without_bilingual() -> None:
    character = _human_with_int_log(0, 0)
    assert native_language_limit(character) == BASE_NATIVE_LANGUAGE_LIMIT == 1


def test_native_language_limit_raised_by_bilingual() -> None:
    character = _human_with_int_log(0, 0)
    bilingual = next(q for q in QUALITIES if q.name == "Bilingual")
    apply_quality_improvements(character, (bilingual,))
    assert character.improvements.resolve(ImprovementType.NATIVE_LANGUAGE_LIMIT, "") == 1
    assert native_language_limit(character) == 2


def test_accepts_knowledge_and_language_picks_within_budget() -> None:
    character = _human_with_int_log(3, 2)  # 14-point budget
    knowledge = (
        KnowledgeSkillPick(name="Corporations", category="Street", rating=3),
        KnowledgeSkillPick(name="Magic Theory", category="Academic", rating=2),
    )
    languages = (
        LanguageSkillPick(name="English", rating=0, native=True),
        LanguageSkillPick(name="Japanese", rating=1),
    )

    selection = create_knowledge_selection(character, knowledge, languages)

    assert selection.free_points == 14
    assert selection.points_spent == 6  # native language costs 0
    assert selection.knowledge_skills == knowledge
    assert selection.languages == languages
    assert selection.native_language_limit == 1


def test_does_not_require_full_budget_spend() -> None:
    # Mirrors chummer5.engine.skills.create_skill_allocation's own established precedent.
    character = _human_with_int_log(3, 2)
    selection = create_knowledge_selection(character, (), ())
    assert selection.points_spent == 0
    assert selection.free_points == 14


def test_rejects_spend_over_budget() -> None:
    character = _human_with_int_log(0, 0)  # 4-point budget
    knowledge = (KnowledgeSkillPick(name="Corporations", category="Street", rating=5),)
    with pytest.raises(ValueError, match="exceeds the free budget"):
        create_knowledge_selection(character, knowledge, ())


def test_rejects_blank_name() -> None:
    character = _human_with_int_log(3, 2)
    with pytest.raises(ValueError, match="must not be blank"):
        create_knowledge_selection(
            character, (KnowledgeSkillPick(name="  ", category="Street", rating=1),), ()
        )


def test_rejects_duplicate_knowledge_name() -> None:
    character = _human_with_int_log(3, 2)
    picks = (
        KnowledgeSkillPick(name="Corporations", category="Street", rating=1),
        KnowledgeSkillPick(name="Corporations", category="Academic", rating=1),
    )
    with pytest.raises(ValueError, match="duplicate knowledge skill name"):
        create_knowledge_selection(character, picks, ())


def test_rejects_duplicate_language_name() -> None:
    character = _human_with_int_log(3, 2)
    picks = (
        LanguageSkillPick(name="Spanish", rating=1),
        LanguageSkillPick(name="Spanish", rating=2),
    )
    with pytest.raises(ValueError, match="duplicate language skill name"):
        create_knowledge_selection(character, (), picks)


def test_rejects_unknown_category() -> None:
    character = _human_with_int_log(3, 2)
    with pytest.raises(ValueError, match="not a knowledge-skill category"):
        create_knowledge_selection(
            character, (KnowledgeSkillPick(name="X", category="Language", rating=1),), ()
        )


@pytest.mark.parametrize("rating", [0, -1, MAX_SKILL_RATING_CREATE + 1])
def test_rejects_out_of_range_knowledge_rating(rating: int) -> None:
    character = _human_with_int_log(3, 2)
    with pytest.raises(ValueError, match="rating must be between"):
        create_knowledge_selection(
            character, (KnowledgeSkillPick(name="X", category="Street", rating=rating),), ()
        )


@pytest.mark.parametrize("rating", [0, -1, MAX_SKILL_RATING_CREATE + 1])
def test_rejects_out_of_range_language_rating(rating: int) -> None:
    character = _human_with_int_log(3, 2)
    with pytest.raises(ValueError, match="rating must be between"):
        create_knowledge_selection(character, (), (LanguageSkillPick(name="X", rating=rating),))


def test_native_language_must_have_zero_rating() -> None:
    character = _human_with_int_log(3, 2)
    with pytest.raises(ValueError, match="native language's rating must be 0"):
        create_knowledge_selection(
            character, (), (LanguageSkillPick(name="English", rating=3, native=True),)
        )


def test_rejects_too_many_native_languages_without_bilingual() -> None:
    character = _human_with_int_log(3, 2)
    picks = (
        LanguageSkillPick(name="English", rating=0, native=True),
        LanguageSkillPick(name="Sperethiel", rating=0, native=True),
    )
    with pytest.raises(ValueError, match="at most 1 language"):
        create_knowledge_selection(character, (), picks)


def test_bilingual_allows_a_second_native_language() -> None:
    character = _human_with_int_log(3, 2)
    bilingual = next(q for q in QUALITIES if q.name == "Bilingual")
    apply_quality_improvements(character, (bilingual,))
    picks = (
        LanguageSkillPick(name="English", rating=0, native=True),
        LanguageSkillPick(name="Sperethiel", rating=0, native=True),
    )
    selection = create_knowledge_selection(character, (), picks)
    assert selection.native_language_limit == 2
    assert selection.points_spent == 0


def test_max_rating_of_six_is_accepted() -> None:
    character = _human_with_int_log(3, 2)
    selection = create_knowledge_selection(
        character, (KnowledgeSkillPick(name="X", category="Street", rating=6),), ()
    )
    assert selection.points_spent == 6


# WP53: Karma-funded Knowledge/Language rating increases.


def _character_with_knowledge_selection(
    knowledge: tuple[KnowledgeSkillPick, ...] = (), languages: tuple[LanguageSkillPick, ...] = ()
) -> Character:
    character = _human_with_int_log(3, 2)  # 14-point budget, generous enough for these tests
    selection = create_knowledge_selection(character, knowledge, languages)
    return replace(character, knowledge_selection=selection)


def test_karma_knowledge_points_raises_a_knowledge_skill_rating() -> None:
    character = _character_with_knowledge_selection(
        knowledge=(KnowledgeSkillPick(name="Corporations", category="Street", rating=2),)
    )
    selection = create_karma_knowledge_selection(
        character, {"Corporations": 1}, karma_budget=100
    )
    # KARMA ADVANCEMENT TABLE FOR SKILLS, Knowledge Skills row: 2->3 costs new_rating x 1 = 3.
    assert KARMA_KNOWLEDGE_PER_RATING == 1
    assert selection.karma_cost == 3
    assert selection.points["Corporations"] == 1


def test_karma_knowledge_points_raises_a_language_skill_rating() -> None:
    character = _character_with_knowledge_selection(
        languages=(LanguageSkillPick(name="Japanese", rating=1),)
    )
    selection = create_karma_knowledge_selection(character, {"Japanese": 2}, karma_budget=100)
    # 1->2 (2) + 2->3 (3) = 5.
    assert selection.karma_cost == 5


def test_karma_knowledge_points_rejects_unknown_name() -> None:
    character = _character_with_knowledge_selection()
    with pytest.raises(ValueError, match="not a committed"):
        create_karma_knowledge_selection(character, {"Nope": 1}, karma_budget=100)


def test_karma_knowledge_points_rejects_native_language() -> None:
    character = _character_with_knowledge_selection(
        languages=(LanguageSkillPick(name="English", rating=0, native=True),)
    )
    with pytest.raises(ValueError, match="not a committed, non-native"):
        create_karma_knowledge_selection(character, {"English": 1}, karma_budget=100)


def test_karma_knowledge_points_rejects_negative_spend() -> None:
    character = _character_with_knowledge_selection(
        knowledge=(KnowledgeSkillPick(name="Corporations", category="Street", rating=2),)
    )
    with pytest.raises(ValueError, match="must not be negative"):
        create_karma_knowledge_selection(character, {"Corporations": -1}, karma_budget=100)


def test_karma_knowledge_points_rejects_rating_above_chargen_max() -> None:
    character = _character_with_knowledge_selection(
        knowledge=(
            KnowledgeSkillPick(
                name="Corporations", category="Street", rating=MAX_SKILL_RATING_CREATE
            ),
        )
    )
    with pytest.raises(ValueError, match="exceeds the chargen skill rating maximum"):
        create_karma_knowledge_selection(character, {"Corporations": 1}, karma_budget=100)


def test_karma_knowledge_selection_rejects_over_budget_spend() -> None:
    character = _character_with_knowledge_selection(
        knowledge=(KnowledgeSkillPick(name="Corporations", category="Street", rating=2),)
    )
    with pytest.raises(ValueError, match="exceeds the Karma budget"):
        create_karma_knowledge_selection(character, {"Corporations": 1}, karma_budget=0)


def test_karma_knowledge_points_rejects_ambiguous_name_shared_with_a_language() -> None:
    # create_knowledge_selection checks each list's own names for uniqueness separately, so a
    # Knowledge pick and a Language pick can legally share a name -- Karma spend against that name
    # must not silently guess which one was meant.
    character = _character_with_knowledge_selection(
        knowledge=(KnowledgeSkillPick(name="Sioux", category="Street", rating=2),),
        languages=(LanguageSkillPick(name="Sioux", rating=1),),
    )
    with pytest.raises(ValueError, match="ambiguously matches"):
        create_karma_knowledge_selection(character, {"Sioux": 1}, karma_budget=100)
