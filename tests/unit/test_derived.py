"""Synthetic tests for `chummer5.engine.derived`'s formulas, proven in isolation the same way WP5
proved the Improvement engine's dedup and WP7 proved the dice-pool formula: no `.chum5` fixture
stores a computed Initiative/Limit/condition-monitor value to diff against directly (see the
module's own docstring and `spec/worklogs/WP10.md`), so these formulas are checked against
hand-computed expected values built on real `create_character` output.
"""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal

from chummer5.data.metatypes import load_metatypes
from chummer5.data.priorities import load_priorities
from chummer5.data.traditions import load_traditions
from chummer5.engine.character import Character, create_character, metatype_choices
from chummer5.engine.derived import (
    BASE_ESSENCE,
    drain_resistance,
    essence,
    initiative_dice,
    initiative_value,
    mental_limit,
    physical_condition_monitor,
    physical_limit,
    social_limit,
    stun_condition_monitor,
)
from chummer5.engine.improvements import Improvement, ImprovementSource, ImprovementType

METATYPES = load_metatypes()
PRIORITIES = load_priorities()
TRADITIONS = load_traditions()
HERMETIC = next(t for t in TRADITIONS if t.name == "Hermetic")
SHAMANIC = next(t for t in TRADITIONS if t.name == "Shamanic")


def _human_choice(heritage_letter: str = "D") -> object:
    heritage = PRIORITIES.heritage[heritage_letter]
    return next(c for c in metatype_choices(heritage, METATYPES) if c.metatype.name == "Human")


def _character(**attribute_points: int) -> Character:
    return create_character(
        metatype_choice=_human_choice("D"),
        heritage_letter="D",
        attributes_letter="A",
        priorities=PRIORITIES,
        attribute_points=attribute_points,
    )


def _add(character: Character, improvement_type: ImprovementType, value: int) -> None:
    character.improvements.add(
        Improvement(
            improvement_type=improvement_type,
            target="",
            value=value,
            source_type=ImprovementSource.QUALITY,
            source_id="synthetic",
        )
    )


def _add_essence_loss(character: Character, loss: Decimal) -> None:
    """`loss` is a positive Essence-cost amount; stored as a negative `essence_value` (an
    `ESSENCE` improvement's own sign convention -- see `chummer5.engine.improvements`)."""
    character.improvements.add(
        Improvement(
            improvement_type=ImprovementType.ESSENCE,
            target="",
            value=0,
            essence_value=-loss,
            source_type=ImprovementSource.CYBERWARE,
            source_id="synthetic-cyberware",
        )
    )


def test_initiative_value_is_rea_plus_int() -> None:
    # Human metatype minimum for both REA and INT is 1; no points spent -> 1 + 1 = 2.
    character = _character()
    assert initiative_value(character) == 2


def test_initiative_value_sums_improvements() -> None:
    character = _character(REA=2, INT=3)  # 1+2=3, 1+3=4 -> 7
    _add(character, ImprovementType.INITIATIVE, 2)
    assert initiative_value(character) == 9


def test_initiative_value_floors_at_zero() -> None:
    character = _character()  # REA=1, INT=1 -> 2 unmodified
    _add(character, ImprovementType.INITIATIVE, -10)
    assert initiative_value(character) == 0


def test_initiative_dice_defaults_to_one() -> None:
    character = _character()
    assert initiative_dice(character) == 1


def test_initiative_dice_caps_at_five() -> None:
    character = _character()
    _add(character, ImprovementType.INITIATIVE_DICE, 10)
    assert initiative_dice(character) == 5


def test_physical_limit_hand_computed() -> None:
    # STR=1(min)+1=2, BOD=1(min)+3=4, REA=1(min)+1=2 -> ceil((2*2+4+2)/3) = ceil(10/3) = 4.
    character = _character(STR=1, BOD=3, REA=1)
    assert physical_limit(character) == 4


def test_physical_limit_exact_division_needs_no_rounding() -> None:
    # STR=1(min)+2=3, BOD=1(min)+2=3, REA=1(min)+2=3 -> (3*2+3+3)/3 = 12/3 = 4 exactly.
    character = _character(STR=2, BOD=2, REA=2)
    assert physical_limit(character) == 4


def test_physical_limit_sums_improvements() -> None:
    character = _character(STR=1, BOD=3, REA=1)  # base 4, per the hand-computed test above
    _add(character, ImprovementType.PHYSICAL_LIMIT, 2)
    assert physical_limit(character) == 6


def test_mental_limit_hand_computed() -> None:
    # LOG=1(min)+5=6, INT=1(min)+4=5, WIL=1(min)+4=5 -> ceil((6*2+5+5)/3) = ceil(22/3) = 8.
    character = _character(LOG=5, INT=4, WIL=4)
    assert mental_limit(character) == 8


def test_social_limit_hand_computed() -> None:
    # CHA=1(min)+4=5, WIL=1(min)+4=5, Essence=6 (fixed) -> ceil((5*2+5+6)/3) = ceil(21/3) = 7.
    character = _character(CHA=4, WIL=4)
    assert social_limit(character) == 7


def test_social_limit_uses_fixed_essence_not_ess_attribute_value() -> None:
    # MAG/RES/ESS aren't in ALLOCATABLE_ATTRIBUTES at all, so attribute_value("ESS") would return
    # metatype minimum (0) + 0 points + 0 improvements = 0 if this formula read it directly --
    # social_limit must use the fixed BASE_ESSENCE constant instead. Same character as the
    # hand-computed test above; if this used attribute_value("ESS") the result would be
    # ceil((5*2+5+0)/3) = 5, not 7.
    character = _character(CHA=4, WIL=4)
    assert social_limit(character) == 7


def test_essence_defaults_to_base_essence_with_no_improvements() -> None:
    # WP30: proven with synthetic data, no real producer exists yet (WP31/WP32 will add one).
    character = _character()
    assert essence(character) == Decimal(BASE_ESSENCE)


def test_essence_reduced_by_essence_improvements() -> None:
    character = _character()
    _add_essence_loss(character, Decimal("0.3"))
    _add_essence_loss(character, Decimal("1.125"))
    assert essence(character) == Decimal(BASE_ESSENCE) - Decimal("1.425")


def test_social_limit_rounds_fractional_essence_up_before_dividing() -> None:
    # CHA=1(min)+4=5, WIL=1(min)+4=5, per the hand-computed test above (base Essence 6 -> limit 7).
    # Losing 0.5 Essence -> 5.5, rounds *up* to 6 (rulebook p.100's explicit instruction) -> the
    # limit is unchanged at 7, not silently different because of the fractional loss.
    character = _character(CHA=4, WIL=4)
    _add_essence_loss(character, Decimal("0.5"))
    assert essence(character) == Decimal("5.5")
    assert social_limit(character) == 7


def test_social_limit_reflects_a_real_essence_loss() -> None:
    # Losing 3.0 Essence -> Essence 3 (already whole, nothing to round) -> ceil((5*2+5+3)/3) =
    # ceil(18/3) = 6, a real drop from the base-Essence test's 7.
    character = _character(CHA=4, WIL=4)
    _add_essence_loss(character, Decimal("3.0"))
    assert essence(character) == Decimal("3.0")
    assert social_limit(character) == 6


def test_physical_condition_monitor_hand_computed() -> None:
    # BOD=1(min)+3=4 -> 8 + ceil(4/2) = 8 + 2 = 10.
    character = _character(BOD=3)
    assert physical_condition_monitor(character) == 10


def test_physical_condition_monitor_rounds_odd_bod_up() -> None:
    # BOD=1(min)+2=3 -> 8 + ceil(3/2) = 8 + 2 = 10.
    character = _character(BOD=2)
    assert physical_condition_monitor(character) == 10


def test_stun_condition_monitor_hand_computed() -> None:
    # WIL=1(min)+4=5 -> 8 + ceil(5/2) = 8 + 3 = 11.
    character = _character(WIL=4)
    assert stun_condition_monitor(character) == 11


def test_condition_monitors_sum_improvements() -> None:
    character = _character(BOD=3, WIL=4)  # 10, 11 per the hand-computed tests above
    _add(character, ImprovementType.PHYSICAL_CM, 1)
    _add(character, ImprovementType.STUN_CM, 2)
    assert physical_condition_monitor(character) == 11
    assert stun_condition_monitor(character) == 13


def test_drain_resistance_is_none_for_mundane() -> None:
    character = _character()
    assert drain_resistance(character) is None


def test_drain_resistance_hermetic_uses_logic_plus_willpower() -> None:
    # Hermetic: Logic + Willpower (core rulebook p.278). LOG=1(min)+5=6, WIL=1(min)+4=5 -> 11.
    character = replace(_character(LOG=5, WIL=4), magic_type="Magician", tradition=HERMETIC)
    assert drain_resistance(character) == 11


def test_drain_resistance_shamanic_uses_charisma_plus_willpower() -> None:
    # Shamanic: Charisma + Willpower (core rulebook p.279). CHA=1(min)+3=4, WIL=1(min)+2=3 -> 7.
    character = replace(_character(CHA=3, WIL=2), magic_type="Magician", tradition=SHAMANIC)
    assert drain_resistance(character) == 7


def test_drain_resistance_adept_uses_fixed_body_plus_willpower() -> None:
    # Adept Drain (core rulebook p.308): fixed Body + Willpower, no tradition involved.
    # BOD=1(min)+3=4, WIL=1(min)+2=3 -> 7.
    character = replace(_character(BOD=3, WIL=2), magic_type="Adept")
    assert character.tradition is None
    assert drain_resistance(character) == 7


def test_drain_resistance_sums_improvements() -> None:
    character = replace(_character(BOD=3, WIL=2), magic_type="Adept")  # base 7, per above
    _add(character, ImprovementType.DRAIN_RESISTANCE, 2)
    assert drain_resistance(character) == 9
