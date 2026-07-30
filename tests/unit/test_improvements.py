from decimal import Decimal

import pytest

from chummer5.engine.improvements import (
    Improvement,
    ImprovementCondition,
    ImprovementIndex,
    ImprovementSource,
    ImprovementType,
    ResolutionContext,
)


def _bonus(
    *,
    target: str = "BOD",
    value: int,
    source_id: str,
    improvement_type: ImprovementType = ImprovementType.ATTRIBUTE,
    source_type: ImprovementSource = ImprovementSource.QUALITY,
    unique_name: str | None = None,
) -> Improvement:
    return Improvement(
        improvement_type=improvement_type,
        target=target,
        value=value,
        source_type=source_type,
        source_id=source_id,
        unique_name=unique_name,
    )


def test_resolve_returns_zero_for_untargeted_key() -> None:
    index = ImprovementIndex()
    assert index.resolve(ImprovementType.ATTRIBUTE, "BOD") == 0


def test_resolve_sums_improvements_without_a_unique_name() -> None:
    index = ImprovementIndex()
    index.add(_bonus(value=1, source_id="quality-1"))
    index.add(_bonus(value=2, source_id="quality-2"))
    assert index.resolve(ImprovementType.ATTRIBUTE, "BOD") == 3


def test_resolve_ignores_improvements_for_other_targets_and_types() -> None:
    index = ImprovementIndex()
    index.add(_bonus(target="BOD", value=1, source_id="quality-1"))
    index.add(_bonus(target="AGI", value=5, source_id="quality-2"))
    index.add(
        _bonus(
            target="BOD",
            value=7,
            source_id="skill-1",
            improvement_type=ImprovementType.SKILL,
        )
    )
    assert index.resolve(ImprovementType.ATTRIBUTE, "BOD") == 1


def test_resolve_dedups_same_unique_name_to_highest_value() -> None:
    # SR5's "highest bonus wins" stacking rule: three sources granting the same named bonus to the
    # same target only ever contribute the single highest value, not all three summed.
    index = ImprovementIndex()
    index.add(_bonus(value=2, source_id="quality-1", unique_name="cool_resolve"))
    index.add(_bonus(value=5, source_id="quality-2", unique_name="cool_resolve"))
    index.add(_bonus(value=3, source_id="quality-3", unique_name="cool_resolve"))
    assert index.resolve(ImprovementType.ATTRIBUTE, "BOD") == 5


def test_resolve_combines_stacking_and_deduped_groups() -> None:
    # An unnamed bonus stacks normally alongside a deduped named group targeting the same key.
    index = ImprovementIndex()
    index.add(_bonus(value=1, source_id="metatype-1", source_type=ImprovementSource.METATYPE))
    index.add(_bonus(value=2, source_id="quality-1", unique_name="named_group"))
    index.add(_bonus(value=4, source_id="quality-2", unique_name="named_group"))
    assert index.resolve(ImprovementType.ATTRIBUTE, "BOD") == 5


def test_resolve_keeps_distinct_unique_names_separate() -> None:
    # Different unique_name groups targeting the same key each contribute their own highest value.
    index = ImprovementIndex()
    index.add(_bonus(value=2, source_id="quality-1", unique_name="group_a"))
    index.add(_bonus(value=3, source_id="quality-2", unique_name="group_b"))
    assert index.resolve(ImprovementType.ATTRIBUTE, "BOD") == 5


def test_remove_source_removes_only_its_own_improvements() -> None:
    index = ImprovementIndex()
    index.add(_bonus(value=1, source_id="quality-1"))
    index.add(_bonus(value=2, source_id="quality-2"))
    index.remove_source(ImprovementSource.QUALITY, "quality-1")
    assert index.resolve(ImprovementType.ATTRIBUTE, "BOD") == 2
    assert len(index.improvements) == 1
    assert index.improvements[0].source_id == "quality-2"


def test_remove_source_matches_on_both_type_and_id() -> None:
    # A metatype source with the same id string as a quality source must not be removed by
    # mistake -- source_type and source_id are both part of the identity.
    index = ImprovementIndex()
    index.add(_bonus(value=1, source_id="shared-id", source_type=ImprovementSource.QUALITY))
    index.add(_bonus(value=2, source_id="shared-id", source_type=ImprovementSource.METATYPE))
    index.remove_source(ImprovementSource.QUALITY, "shared-id")
    assert index.resolve(ImprovementType.ATTRIBUTE, "BOD") == 2


def test_remove_source_of_a_deduped_group_falls_back_to_remaining_highest() -> None:
    index = ImprovementIndex()
    index.add(_bonus(value=5, source_id="quality-1", unique_name="named_group"))
    index.add(_bonus(value=3, source_id="quality-2", unique_name="named_group"))
    index.remove_source(ImprovementSource.QUALITY, "quality-1")
    assert index.resolve(ImprovementType.ATTRIBUTE, "BOD") == 3


def test_index_is_rebuilt_after_mutation_not_stale() -> None:
    index = ImprovementIndex()
    bonus = _bonus(value=10, source_id="quality-1")
    index.add(bonus)
    assert index.resolve(ImprovementType.ATTRIBUTE, "BOD") == 10
    index.remove_source(ImprovementSource.QUALITY, "quality-1")
    assert index.resolve(ImprovementType.ATTRIBUTE, "BOD") == 0


def _essence_delta(
    *, value: Decimal, source_id: str, unique_name: str | None = None
) -> Improvement:
    return Improvement(
        improvement_type=ImprovementType.ESSENCE,
        target="",
        value=0,
        essence_value=value,
        source_type=ImprovementSource.CYBERWARE,
        source_id=source_id,
        unique_name=unique_name,
    )


def test_resolve_essence_returns_zero_for_untargeted_key() -> None:
    index = ImprovementIndex()
    assert index.resolve_essence("") == Decimal(0)


def test_resolve_essence_sums_fractional_values() -> None:
    # WP31's real cyberware catalog has essence costs to 3 decimal places (e.g. 1.125) -- Decimal
    # sums these exactly, unlike float.
    index = ImprovementIndex()
    index.add(_essence_delta(value=Decimal("0.3"), source_id="cyberware-1"))
    index.add(_essence_delta(value=Decimal("1.125"), source_id="cyberware-2"))
    assert index.resolve_essence("") == Decimal("1.425")


def test_resolve_essence_ignores_unique_name_dedup() -> None:
    # Unlike resolve()'s "highest bonus wins" stacking rule, Essence costs always stack additively
    # -- there is no "highest cost wins" rule for Essence, so unique_name is not consulted here even
    # when two essence-costing improvements happen to share one.
    index = ImprovementIndex()
    index.add(_essence_delta(value=Decimal("0.5"), source_id="cyberware-1", unique_name="shared"))
    index.add(_essence_delta(value=Decimal("0.25"), source_id="cyberware-2", unique_name="shared"))
    assert index.resolve_essence("") == Decimal("0.75")


def test_resolve_essence_only_sums_essence_typed_improvements() -> None:
    index = ImprovementIndex()
    index.add(_bonus(value=99, source_id="quality-1"))  # ATTRIBUTE-typed, must not leak in
    index.add(_essence_delta(value=Decimal("0.5"), source_id="cyberware-1"))
    assert index.resolve_essence("") == Decimal("0.5")


def test_resolve_rejects_essence_type() -> None:
    # ESSENCE improvements carry their magnitude in essence_value, not value -- resolve() would
    # silently sum zeros if it accepted ESSENCE, so it rejects the type outright instead.
    index = ImprovementIndex()
    index.add(_essence_delta(value=Decimal("0.5"), source_id="cyberware-1"))
    with pytest.raises(ValueError, match="resolve_essence"):
        index.resolve(ImprovementType.ESSENCE, "")


# ------------------------------------------------------------------------------------------------
# WP39: conditional Improvements. See chummer5.engine.improvements' module docstring for the design
# and for the four real SR5 bonuses this primitive exists for.
# ------------------------------------------------------------------------------------------------


def _mental_limit_bonus(
    *,
    value: int,
    source_id: str,
    condition: ImprovementCondition | None = None,
    unique_name: str | None = None,
) -> Improvement:
    return Improvement(
        improvement_type=ImprovementType.MENTAL_LIMIT,
        target="",
        value=value,
        source_type=ImprovementSource.CYBERWARE,
        source_id=source_id,
        unique_name=unique_name,
        condition=condition,
    )


def _mental(index: ImprovementIndex, context: ResolutionContext | None = None) -> int:
    """The character-wide Mental limit total, optionally for one specific kind of test."""
    return index.resolve(ImprovementType.MENTAL_LIMIT, "", context=context)


def test_condition_defaults_to_none_and_is_a_true_no_op() -> None:
    # The zero-drift guarantee WP39's acceptance criteria demand: every Improvement WP5-WP38
    # produces omits `condition`, and must resolve identically with or without a context.
    index = ImprovementIndex()
    index.add(_bonus(value=3, source_id="quality-1"))
    assert index.improvements[0].condition is None
    assert index.resolve(ImprovementType.ATTRIBUTE, "BOD") == 3
    for context in ResolutionContext:
        assert index.resolve(ImprovementType.ATTRIBUTE, "BOD", context=context) == 3


def test_conditional_improvement_counts_only_when_its_context_is_supplied() -> None:
    # Vision Enhancement's shape: a Mental limit bonus that applies only to visual Perception.
    index = ImprovementIndex()
    index.add(
        _mental_limit_bonus(
            value=2,
            source_id="vision-enhancement",
            condition=ImprovementCondition.PERCEPTION_VISUAL_ONLY,
        )
    )
    assert _mental(index) == 0
    assert _mental(index, ResolutionContext.PERCEPTION_VISUAL) == 2
    assert _mental(index, ResolutionContext.PERCEPTION_HEARING) == 0


def test_met_and_unmet_conditions_on_the_same_target_resolve_independently() -> None:
    # The core acceptance case: two conditional improvements on one target, only the met one counts.
    index = ImprovementIndex()
    index.add(
        _mental_limit_bonus(
            value=2,
            source_id="vision-enhancement",
            condition=ImprovementCondition.PERCEPTION_VISUAL_ONLY,
        )
    )
    index.add(
        _mental_limit_bonus(
            value=3,
            source_id="audio-enhancement",
            condition=ImprovementCondition.PERCEPTION_HEARING_ONLY,
        )
    )
    assert _mental(index) == 0
    assert _mental(index, ResolutionContext.PERCEPTION_VISUAL) == 2
    assert _mental(index, ResolutionContext.PERCEPTION_HEARING) == 3


def test_unconditional_improvements_still_count_when_a_context_is_supplied() -> None:
    # A contextual resolution is "the plain value PLUS whatever this context unlocks", not "only
    # the conditional bonuses" -- the trap that would silently drop a character's real Limit.
    index = ImprovementIndex()
    index.add(_mental_limit_bonus(value=1, source_id="indomitable"))
    index.add(
        _mental_limit_bonus(
            value=2,
            source_id="vision-enhancement",
            condition=ImprovementCondition.PERCEPTION_VISUAL_ONLY,
        )
    )
    assert _mental(index) == 1
    assert _mental(index, ResolutionContext.PERCEPTION_VISUAL) == 3


def test_one_condition_may_cover_several_contexts() -> None:
    # Hydraulic Jacks: "Only for Gymnastics (Jumping) and Running (Sprinting)" -- one condition,
    # two unrelated activities. Modeling a condition as a single context would need two
    # Improvements for one bonus.
    index = ImprovementIndex()
    index.add(
        Improvement(
            improvement_type=ImprovementType.PHYSICAL_LIMIT,
            target="",
            value=2,
            source_type=ImprovementSource.CYBERWARE,
            source_id="hydraulic-jacks",
            condition=ImprovementCondition.JUMPING_OR_SPRINTING_ONLY,
        )
    )
    physical = ImprovementType.PHYSICAL_LIMIT
    for context in (ResolutionContext.GYMNASTICS_JUMPING, ResolutionContext.RUNNING_SPRINTING):
        assert index.resolve(physical, "", context=context) == 2
    assert index.resolve(physical, "", context=ResolutionContext.PERCEPTION_VISUAL) == 0


def test_no_subsumption_between_related_conditions() -> None:
    # Deliberate, documented: Spatial Recognizer's "Perception to find the source of a sound" is
    # arguably a special case of "Perception (Hearing)", but matching is plain set membership, with
    # no hierarchy -- see the module docstring for why (no rule establishes it, and the legacy
    # engine never auto-applies a conditional limit modifier at all, so there's no oracle).
    index = ImprovementIndex()
    index.add(
        _mental_limit_bonus(
            value=2,
            source_id="spatial-recognizer",
            condition=ImprovementCondition.PERCEPTION_SOUND_SOURCE_ONLY,
        )
    )
    assert _mental(index, ResolutionContext.PERCEPTION_HEARING) == 0
    assert _mental(index, ResolutionContext.PERCEPTION_SOUND_SOURCE) == 2


def test_condition_filtering_happens_before_unique_name_dedup() -> None:
    # An inapplicable conditional Improvement must not win a dedup group it isn't competing in:
    # with the context absent, the surviving value is the unconditional 1, not the excluded 5.
    index = ImprovementIndex()
    index.add(_mental_limit_bonus(value=1, source_id="quality", unique_name="mental"))
    index.add(
        _mental_limit_bonus(
            value=5,
            source_id="vision-enhancement",
            unique_name="mental",
            condition=ImprovementCondition.PERCEPTION_VISUAL_ONLY,
        )
    )
    assert _mental(index) == 1
    assert _mental(index, ResolutionContext.PERCEPTION_VISUAL) == 5


def test_remove_source_retracts_conditional_improvements_too() -> None:
    index = ImprovementIndex()
    index.add(
        _mental_limit_bonus(
            value=2,
            source_id="vision-enhancement",
            condition=ImprovementCondition.PERCEPTION_VISUAL_ONLY,
        )
    )
    index.remove_source(ImprovementSource.CYBERWARE, "vision-enhancement")
    assert _mental(index, ResolutionContext.PERCEPTION_VISUAL) == 0


def test_is_met_is_false_without_a_context() -> None:
    for condition in ImprovementCondition:
        assert not condition.is_met(None)
        assert condition.contexts
        for context in condition.contexts:
            assert condition.is_met(context)


def test_every_condition_maps_to_at_least_one_context() -> None:
    # Guards against an ImprovementCondition member added without a _CONDITION_CONTEXTS entry,
    # which would silently make its bonus unreachable rather than raising.
    for condition in ImprovementCondition:
        assert isinstance(condition.contexts, frozenset)
    covered = {context for condition in ImprovementCondition for context in condition.contexts}
    assert covered == set(ResolutionContext)


def test_resolve_essence_rejects_a_conditional_essence_improvement() -> None:
    index = ImprovementIndex()
    index.add(
        Improvement(
            improvement_type=ImprovementType.ESSENCE,
            target="",
            value=0,
            source_type=ImprovementSource.CYBERWARE,
            source_id="datajack",
            essence_value=Decimal("-0.1"),
            condition=ImprovementCondition.PERCEPTION_VISUAL_ONLY,
        )
    )
    with pytest.raises(ValueError, match="unconditional by construction"):
        index.resolve_essence("")


def test_improvements_stay_frozen_value_objects_with_a_condition() -> None:
    # The reason a Condition is an Enum and not a closure: Improvement must stay hashable and
    # comparable by value.
    first = _mental_limit_bonus(
        value=2, source_id="x", condition=ImprovementCondition.PERCEPTION_VISUAL_ONLY
    )
    second = _mental_limit_bonus(
        value=2, source_id="x", condition=ImprovementCondition.PERCEPTION_VISUAL_ONLY
    )
    assert first == second
    assert hash(first) == hash(second)
    assert first != _mental_limit_bonus(value=2, source_id="x")
