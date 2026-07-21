from decimal import Decimal

import pytest

from chummer5.engine.improvements import (
    Improvement,
    ImprovementIndex,
    ImprovementSource,
    ImprovementType,
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
