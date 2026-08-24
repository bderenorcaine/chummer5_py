"""Derived stats: initiative, the three Limits, and the two condition monitors.

**WP56** adds one function outside that original scope, `unmodeled_effect_notes` -- not a rules
formula, but the same "pure function of a finalized `Character`, meant for the character sheet"
shape as everything else here, so it lives alongside them rather than in its own module. See that
function's own docstring.

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

**Essence (`essence()`) is `BASE_ESSENCE = 6` plus Σ `ESSENCE` improvements, not
`character.attribute_value("ESS")`.** Two independent findings, both recorded in
`spec/worklogs/WP10.md`, plus a WP30 correction:
- `Character.Essence()` (the real, authoritative Essence used by `LimitSocial`) starts at the
  metatype's Essence maximum and is only ever *reduced* by cyberware/bioware essence cost --
  confirmed all 5 SR5 core metatypes have `essmax = 6` in `metatypes.xml`. Through WP29, MVP models
  no cyberware/bioware (the only Essence-reducing content), so Essence was unconditionally 6 for
  every buildable character; **WP30 turns `BASE_ESSENCE` from a hardcoded final answer into that
  same fixed *starting* point**, reduced by whatever `ImprovementType.ESSENCE` improvements a
  future WP31/WP32 cyberware purchase attaches (see `chummer5.engine.improvements`' own docstring
  for why Essence needs a dedicated `resolve_essence()`/`essence_value` path rather than the
  ordinary `int`-valued `resolve()`). Zero improvements today (no producer exists yet), so
  `essence()` still returns exactly 6 for every character built so far -- this WP is proven-in-
  isolation plumbing, not a behavior change, mirroring WP5's own relationship to WP6+.
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

**`social_limit` rounds Essence up to a whole number before its own division, per an explicit
rulebook instruction (p.100/`spec/rulebooks/learnings.md`'s WP10 entry): "For Social limits, round
up Essence to the nearest whole number prior to calculating the cost."** Confirmed directly in the
legacy C# too, while implementing WP30's fractional Essence support:
`DecimalExtensions.StandardRound` (`Character.cs`'s `LimitSocial` calls `Essence().StandardRound()`)
is `decimal.ToInt32(decToRound >= 0 ? decimal.Ceiling(decToRound) : decimal.Floor(decToRound))` --
despite the name, that's plain ceiling for every non-negative Essence value (which Essence always
is pre-WP32's essence-floor guard), *not* round-to-nearest. `essence()` itself intentionally
returns the exact, unrounded `Decimal` -- only `social_limit` rounds, and only because this one
formula is documented to need it; a future WP35 (Essence-driven Magic-rating loss) needs to see
*any* nonzero fractional loss, which a pre-rounded `essence()` would have silently thrown away.

**`WoundModifier` (a damage-penalty term `Character.InitiativeValue` adds on top of REA+INT) is
always 0 here** -- MVP chargen never tracks damage (no career mode, no condition monitor boxes
filled in), so there is nothing for it to read.
"""

from __future__ import annotations

import math
from decimal import Decimal

from chummer5.engine.character import Character
from chummer5.engine.improvements import ImprovementType, ResolutionContext

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

# Character.Essence()'s fixed starting point (WP30): the SR5 core metatypes' shared Essence maximum
# (6, confirmed for all of Human/Elf/Dwarf/Ork/Troll in metatypes.xml). `essence()` below reduces
# this by Σ ESSENCE improvements -- through WP29 nothing produced any, so this was also the final
# answer; WP31/WP32 (cyberware) are the first real producer. See module docstring for the full
# reasoning and the Yeti ESS-attribute red herring this was checked against.
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


def physical_limit(character: Character, *, context: ResolutionContext | None = None) -> int:
    """`Character.LimitPhysical`: ceil((STR*2 + BOD + REA) / 3) + Σ improvements.

    `context` (WP40) selects which *conditional* improvements count -- `Hydraulic Jacks` raises this
    limit only for jumping and sprinting (p. 457). Omitting it gives the plain, unconditional limit,
    which is what the character sheet's headline figure shows and what every pre-WP40 caller
    already computed. See `chummer5.engine.improvements`' "Conditional Improvements" section.
    """
    total = _ceil_div(
        character.attribute_value("STR") * 2
        + character.attribute_value("BOD")
        + character.attribute_value("REA"),
        3,
    )
    return total + character.improvements.resolve(
        ImprovementType.PHYSICAL_LIMIT, _GLOBAL_TARGET, context=context
    )


def mental_limit(character: Character, *, context: ResolutionContext | None = None) -> int:
    """`Character.LimitMental`: ceil((LOG*2 + INT + WIL) / 3) + Σ improvements.

    `context` (WP40), as in `physical_limit`: `Vision Enhancement`, `Audio Enhancement` and
    `Spatial Recognizer` each raise this limit only during their own kind of Perception test
    (p. 444). A Mental-limited test with no conditional bonus of its own -- a Memory test, say --
    passes no context and sees the plain figure.

    `social_limit` deliberately grows no such parameter: no aspect this engine offers carries a
    conditional Social limit bonus, and WP39's rule is to add a context only where a real bonus
    needs one.
    """
    total = _ceil_div(
        character.attribute_value("LOG") * 2
        + character.attribute_value("INT")
        + character.attribute_value("WIL"),
        3,
    )
    return total + character.improvements.resolve(
        ImprovementType.MENTAL_LIMIT, _GLOBAL_TARGET, context=context
    )


def essence(character: Character) -> Decimal:
    """`Character.Essence()`: `BASE_ESSENCE` (6) reduced by Σ `ESSENCE` improvements (WP30) --
    cyberware/bioware essence cost, once WP31/WP32 give this a real producer. Returns the exact,
    unrounded value -- see module docstring for why only `social_limit` rounds, not this function.
    """
    return Decimal(BASE_ESSENCE) + character.improvements.resolve_essence(_GLOBAL_TARGET)


def social_limit(character: Character) -> int:
    """`Character.LimitSocial`: ceil((CHA*2 + WIL + ceil(Essence)) / 3) + Σ improvements.

    Essence is rounded up to a whole number before this formula's own division -- see module
    docstring's dedicated paragraph for the rulebook citation and the legacy `StandardRound` finding
    this was checked against.
    """
    total = _ceil_div(
        character.attribute_value("CHA") * 2
        + character.attribute_value("WIL")
        + math.ceil(essence(character)),
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


def unmodeled_effect_notes(character: Character) -> tuple[tuple[str, str], ...]:
    """WP56: `(aspect name, note)` pairs for every named, catalog-backed aspect `character`
    currently holds whose catalog entry carries an `unmodeled_effect_note` (Project Overview's
    "Unmodeled real effects" table -- see `chummer5.data.qualities`'s own WP56 docstring paragraph
    for why that markdown table isn't read at runtime; each catalog module instead mirrors its own
    rows into a field on its own dataclass, populated at load/classification time). Deduplicated by
    name (a metatype-granted and player-purchased instance of the same quality -- e.g. an Elf who
    also buys nothing new, or any character with both a metatype grant and a matching purchase --
    contributes one entry, not two) and returned in encounter order, not sorted -- the template
    doesn't need a stable ordering guarantee beyond "consistent within one render".

    **Aspect-kind-agnostic by construction, not by enumerating every kind's own dataclass here**:
    every aspect below is read through a plain `getattr(item, "unmodeled_effect_note", None)`, not
    an `isinstance`/kind check, so a future WP adding this field to `Power`/`Cyberware`/`Bioware`/
    `Focus`/`LifestyleTier`/etc.'s own catalog dataclass (mirroring `Quality`'s WP56 field exactly)
    needs to touch only that catalog module -- this function's own walk already covers every
    selection `Character` holds a name-bearing catalog object in, and doesn't care whether any given
    kind's catalog has started populating the field yet. **WP79 is the first WP to take that up**,
    and it did so without touching this function: adding the field to `chummer5.data.cyberware
    .Cyberware`/`chummer5.data.cyberware_subsystems.CyberwareEntry` (and, empty, to
    `chummer5.data.bioware.Bioware`) was the entire change, and cyberware notes now surface here.
    `Power`/`Focus`/`LifestyleTier`/`StarterGearItem`/`Spell` still populate nothing, so the
    "walks them without crashing, contributes nothing" case below still holds for those kinds.

    **WP95 takes it up for two more kinds, and had to add one loop.** `StarterGearItem` (via
    `chummer5.data.gear._UNMODELED_EFFECT_NOTES`, four rigger-adjacent categories) needed nothing
    here, exactly as the docstring above promised. `Vehicle` did: `vehicle_selection` postdates this
    function and was simply not among the selections walked, so "aspect-kind-agnostic" held for the
    dataclass but not for the selection holding it. The lesson is worth stating plainly, since the
    same trap is waiting for the next selection type: **the `getattr` indirection makes new
    *catalogs* free, not new *selections*.** A WP adding a `Character` field that holds catalog
    objects has to add its loop here. `Power`/`Focus`/`LifestyleTier`/`Spell` still populate
    nothing.
    """
    notes: dict[str, str] = {}

    def add(name: str, note: object) -> None:
        if isinstance(note, str) and name not in notes:
            notes[name] = note

    for quality in character.metatype_qualities:
        add(quality.name, getattr(quality, "unmodeled_effect_note", None))
    if character.quality_selection is not None:
        for quality in character.quality_selection.qualities:
            add(quality.name, getattr(quality, "unmodeled_effect_note", None))
        mentor_spirit = character.quality_selection.mentor_spirit
        if mentor_spirit is not None:
            add(
                mentor_spirit.archetype.name,
                getattr(mentor_spirit.archetype, "unmodeled_effect_note", None),
            )
    if character.power_selection is not None:
        for power_pick in character.power_selection.picks:
            add(power_pick.power.name, getattr(power_pick.power, "unmodeled_effect_note", None))
    if character.cyberware_selection is not None:
        # WP41: every node of every purchase tree, plugins included -- an unmodeled effect on a
        # cybereye's plugin is as real as one on a standalone item.
        for node in character.cyberware_selection.walk():
            add(node.item.name, getattr(node.item, "unmodeled_effect_note", None))
    if character.bioware_selection is not None:
        for bioware_item in character.bioware_selection.items:
            add(bioware_item.name, getattr(bioware_item, "unmodeled_effect_note", None))
    if character.foci_selection is not None:
        for focus_pick in character.foci_selection.picks:
            add(focus_pick.focus.name, getattr(focus_pick.focus, "unmodeled_effect_note", None))
    if character.lifestyle_selection is not None:
        tier = character.lifestyle_selection.tier
        add(tier.name, getattr(tier, "unmodeled_effect_note", None))
    if character.resources_selection is not None:
        for gear_item in character.resources_selection.gear:
            add(gear_item.name, getattr(gear_item, "unmodeled_effect_note", None))
    # WP95: the one selection this walk did not cover at all -- `vehicle_selection` postdates the
    # function (WP92) and was never added. Repeats are legal here (four Fly-Spies), and `add`
    # already dedupes by name, so a fleet contributes one note per distinct model.
    if character.vehicle_selection is not None:
        for vehicle in character.vehicle_selection.vehicles:
            add(vehicle.name, getattr(vehicle, "unmodeled_effect_note", None))
    if character.spell_selection is not None:
        for spell in character.spell_selection.spells:
            add(spell.name, getattr(spell, "unmodeled_effect_note", None))
    if character.bound_spirit_selection is not None:
        for spirit in character.bound_spirit_selection.spirits:
            add(spirit.spirit_type, getattr(spirit.spirit_type, "unmodeled_effect_note", None))

    return tuple(notes.items())
