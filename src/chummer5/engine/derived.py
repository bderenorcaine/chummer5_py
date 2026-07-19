"""Derived stats: initiative, the three Limits, and the two condition monitors.

The headless-MVP milestone (per the Implementation Plan): pure functions of a finalized
`Character` (WP6's attribute allocation, composed with WP5's Improvement engine) that need nothing
beyond `Character.attribute_value()`. Checked directly against `legacy/Chummer/Backend/Characters/
Character.cs`'s `LimitPhysical`/`LimitMental`/`LimitSocial`, `PhysicalCM`/`StunCM`, and
`InitiativeValue`/`InitiativeDice` getters. See `spec/worklogs/WP10.md` for the full research this
was checked against, including why none of these formulas have a stored `.chum5` field to diff
against directly (unlike attributes' `<totalvalue>`) -- the same "no ground truth in the save
format, prove the formula via hand-computed values" gap WP7 already found for the skill dice pool.

**Every legacy formula referenced here rounds "away from zero"**
(`IntegerExtensions.DivAwayFromZero`) -- confirmed by reading the extension method directly. For
every non-negative dividend/divisor this project's MVP scope ever produces (BOD/STR/REA/etc. are
never negative), that's equivalent to plain ceiling division, which is what `_ceil_div` implements
-- there is no live case in MVP scope where the "away from zero" distinction from ordinary ceiling
division (which only differs for negative operands) actually matters.

**Essence is a fixed constant (`BASE_ESSENCE = 6`), not `character.attribute_value("ESS")`.**
Two independent findings led here, both recorded in `spec/worklogs/WP10.md`:
- `Character.Essence()` (the real, authoritative Essence used by `LimitSocial`) starts at the
  metatype's Essence maximum and is only ever *reduced* by cyberware/bioware essence cost --
  confirmed all 5 SR5 core metatypes have `essmax = 6` in `metatypes.xml`, and MVP models no
  cyberware/bioware (the only Essence-reducing content), so Essence is unconditionally 6 for every
  MVP-buildable character.
- The `<attribute name="ESS">` element some `.chum5` saves carry is **not** that value and must
  not be read as if it were: `Yeti-#ffffff2.chum5`'s own `ESS` attribute has
  `<totalvalue>1</totalvalue>` despite Yeti having zero cyberware (confirmed) and therefore a real
  Essence of 6.000. Essence
  isn't tracked through the generic `min + points + improvements` `CharacterAttrib` shape every
  other attribute uses (`Attribute.Core.cs`'s `Essence()` is a wholly separate decimal computation
  from `CharacterAttrib.TotalValue`) -- this save-format field is a vestigial/unrelated artifact,
  not a bug in this project's parsing. Using `character.attribute_value("ESS")` here would silently
  compute metatype-minimum(0) + 0 points + 0 improvements = 0, which is wrong in a way that would
  have been easy to miss without checking a real fixture's numbers by hand.

**`WoundModifier` (a damage-penalty term `Character.InitiativeValue` adds on top of REA+INT) is
always 0 here** -- MVP chargen never tracks damage (no career mode, no condition monitor boxes
filled in), so there is nothing for it to read.
"""

from __future__ import annotations

from chummer5.engine.character import Character
from chummer5.engine.improvements import ImprovementType

# Resolution target for the 7 character-wide ImprovementTypes this module reads -- see
# ImprovementType's docstring for why a fixed sentinel, rather than a per-instance target, is
# correct here (there is only ever one Physical Limit, one Initiative, etc. per character).
_GLOBAL_TARGET = ""

# CharacterSettings.MinInitiativeDice/MaxInitiativeDice (legacy field defaults: 1 and 5). MVP never
# builds a matrix/astral-capable character, so the base-Initiative dice pool is the only one
# modeled.
BASE_INITIATIVE_DICE = 1
MAX_INITIATIVE_DICE = 5

# Character.PhysicalCM/StunCM's literal `8 +` base offsets.
BASE_PHYSICAL_CM = 8
BASE_STUN_CM = 8

# Character.Essence(), fixed at the SR5 core metatypes' shared Essence maximum (6, confirmed for
# all of Human/Elf/Dwarf/Ork/Troll in metatypes.xml) since MVP has no cyberware/bioware -- the only
# things that ever reduce it. See module docstring for the full reasoning and the Yeti ESS-attribute
# red herring this was checked against.
BASE_ESSENCE = 6


def _ceil_div(numerator: int, denominator: int) -> int:
    """Ceiling division for the non-negative operands every formula below uses -- equivalent to
    legacy's `DivAwayFromZero` in that regime (see module docstring).
    """
    return -(-numerator // denominator)


def initiative_value(character: Character) -> int:
    """`Character.InitiativeValue`: REA + INT + Σ improvements, floored at 0."""
    total = (
        character.attribute_value("REA")
        + character.attribute_value("INT")
        + character.improvements.resolve(ImprovementType.INITIATIVE, _GLOBAL_TARGET)
    )
    return max(total, 0)


def initiative_dice(character: Character) -> int:
    """`Character.InitiativeDice`: base 1 + Σ improvements, capped at 5."""
    total = BASE_INITIATIVE_DICE + character.improvements.resolve(
        ImprovementType.INITIATIVE_DICE, _GLOBAL_TARGET
    )
    return min(total, MAX_INITIATIVE_DICE)


def physical_limit(character: Character) -> int:
    """`Character.LimitPhysical`: ceil((STR*2 + BOD + REA) / 3) + Σ improvements."""
    total = _ceil_div(
        character.attribute_value("STR") * 2
        + character.attribute_value("BOD")
        + character.attribute_value("REA"),
        3,
    )
    return total + character.improvements.resolve(ImprovementType.PHYSICAL_LIMIT, _GLOBAL_TARGET)


def mental_limit(character: Character) -> int:
    """`Character.LimitMental`: ceil((LOG*2 + INT + WIL) / 3) + Σ improvements."""
    total = _ceil_div(
        character.attribute_value("LOG") * 2
        + character.attribute_value("INT")
        + character.attribute_value("WIL"),
        3,
    )
    return total + character.improvements.resolve(ImprovementType.MENTAL_LIMIT, _GLOBAL_TARGET)


def social_limit(character: Character) -> int:
    """`Character.LimitSocial`: ceil((CHA*2 + WIL + Essence) / 3) + Σ improvements."""
    total = _ceil_div(
        character.attribute_value("CHA") * 2 + character.attribute_value("WIL") + BASE_ESSENCE,
        3,
    )
    return total + character.improvements.resolve(ImprovementType.SOCIAL_LIMIT, _GLOBAL_TARGET)


def physical_condition_monitor(character: Character) -> int:
    """`Character.PhysicalCM`: 8 + ceil(BOD / 2) + Σ improvements."""
    total = BASE_PHYSICAL_CM + _ceil_div(character.attribute_value("BOD"), 2)
    return total + character.improvements.resolve(ImprovementType.PHYSICAL_CM, _GLOBAL_TARGET)


def stun_condition_monitor(character: Character) -> int:
    """`Character.StunCM`: 8 + ceil(WIL / 2) + Σ improvements."""
    total = BASE_STUN_CM + _ceil_div(character.attribute_value("WIL"), 2)
    return total + character.improvements.resolve(ImprovementType.STUN_CM, _GLOBAL_TARGET)


def drain_resistance(character: Character) -> int | None:
    """Drain Resistance: the dice pool used to resist Drain, resolved via a fixed attribute pair
    plus Σ improvements. `None` for a Mundane character (`magic_type is None`) -- there is nothing
    to resist Drain with, the same "not meaningful" carve-out `BASE_ESSENCE`'s own docstring uses
    for a similarly not-applicable case.

    Two different formulas, per WP27's own correction to this phase's earlier framing (Drain
    Resistance is not Magician-only):
    - **Magician**: `character.tradition`'s own `drain_attributes` pair (core rulebook p.278,
      "TRADITIONS": "Each tradition's description also includes the Attributes used in the Drain
      Resistance Test for spellcasters of this tradition" -- confirmed directly in prose for both
      offered traditions, p.278-279: Hermetic is "Logic + Willpower", Shamanic is "Charisma +
      Willpower", matching `chummer5.data.traditions.load_traditions()`'s own parsed
      `drain_attributes`).
    - **Adept**: fixed `BOD + WIL` (core rulebook p.308, "USING POWERS": "Adept Drain: Some powers
      cause Drain. The Drain from adept powers is Stun unless specified in the description, and is
      resisted with Body + Willpower" -- unlike a Magician's tradition-dependent pair, this is the
      same formula for every Adept regardless of which powers were actually bought, the same
      "shown regardless of build specifics" shape Physical/Mental/Social Limit already have).
    """
    if character.magic_type == "Magician":
        assert character.tradition is not None
        attr_a, attr_b = character.tradition.drain_attributes
    elif character.magic_type == "Adept":
        attr_a, attr_b = "BOD", "WIL"
    else:
        return None
    total = character.attribute_value(attr_a) + character.attribute_value(attr_b)
    return total + character.improvements.resolve(ImprovementType.DRAIN_RESISTANCE, _GLOBAL_TARGET)
