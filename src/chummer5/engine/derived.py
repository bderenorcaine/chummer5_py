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

**WP109 (Phase X) adds the four character-level numbers the phase's Finding 6 lists** -- Overflow,
the wound-modifier rule, Armor, and the Damage Resistance pool -- each with its own Improvement type
so later WPs (Will to Live, High/Low Pain Tolerance, Troll dermal armor, Orthoskin, ...) have
something to target:

- **Overflow** (`overflow`) is `BOD + Σ CM_OVERFLOW` -- p. 101's "Body + Augmentation bonuses", read
  against legacy `CMOverflow`, which uses `BOD.TotalValue` (the *augmented* Body). Legacy adds one
  more box "to mark the character as dead"; that is a record-sheet convention, not a rule, and the
  rulebook's own examples (James: Overflow 3 at Body 3) leave it out, so this does too.
- **Wound modifiers** (`wound_modifier_rule`): -1 per `3 + Σ CM_THRESHOLD` boxes (p. 169), with
  `Σ CM_THRESHOLD_OFFSET + Σ CM_SHARED_THRESHOLD_OFFSET` boxes ignored before the first one, on each
  track. Legacy splits the shared offset between tracks by how much *damage* each has taken; with
  no damage at creation both tracks get all of it, which is what this reports.
- **Armor** (`armor_breakdown`): the highest-rated worn body armor, plus worn `+N` accessories
  capped at Strength, plus `Σ ARMOR` (p. 169; legacy `GetArmorRatingWithImprovement`). Accessories
  over Strength also cost -1 Agility and Reaction per 2 full points; that penalty applies only
  *while* the pile is worn, so it is reported for the sheet rather than subtracted from the
  attributes.
- **Damage Resistance** (`damage_resistance`): `BOD + Armor + Σ DAMAGE_RESISTANCE` (legacy
  `DamageResistancePool`).

**WP111 adds the remaining Step Eight initiative rows** (Living Persona is out of scope):

- **Astral Initiative** (`astral_initiative`): `INT x 2` + 3D6, and only for a character who can
  astrally *project* -- a Magician. p. 313: "Only characters who are full Magicians can astrally
  project"; an Adept or an Aspected Magician can at most *perceive*, and a perceiving character
  stays in its body on the physical Initiative (p. 159 swaps to Astral Initiative on the action
  that *projects*). The dice follow p. 314's Astral Attributes table ("+2D6 (3D6 total)") and
  legacy's default of 3, by the user's ruling of 2026-09-26; the Step Eight table and p. 159's
  chart print 2D6 -- a printed conflict, recorded in `spec/rulebooks/learnings/phase-x.md`.
- **Matrix AR Initiative** is the physical Initiative, augmentations and all (p. 229: "When in AR,
  you use your normal Initiative and Initiative Dice"; the User Modes Table says the same). It is
  shown for everyone, as its own row, with the physical numbers.
- **Matrix VR Initiative** (`matrix_vr_initiative`): Data Processing + INT, with 3D6 (cold-sim) or
  4D6 (hot-sim) (pp. 229-230). VR needs a sim module *and* a direct neural interface (pp. 227, 438)
  and a device to run the persona on; hot-sim needs a hot-sim module, which every cyberdeck has
  built in (p. 439). See that function for which purchases provide which.

**`WoundModifier` (a damage-penalty term `Character.InitiativeValue` adds on top of REA+INT) is
always 0 here** -- MVP chargen never tracks damage (no career mode, no condition monitor boxes
filled in), so there is nothing for it to read.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING

from chummer5.engine.character import Character
from chummer5.engine.improvements import ImprovementType, ResolutionContext

if TYPE_CHECKING:
    from chummer5.engine.resources import StarterGearItem

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


# p. 169: "a –1 modifier for every 3 boxes of damage", before any CM_THRESHOLD change.
BASE_WOUND_BOXES_PER_MODIFIER = 3

# The gear category whose items are body armor or `+N` accessories (armor.xml's own category name).
ARMOR_CATEGORY = "Armor"

# WP111: Astral Initiative's dice -- 3, per p. 314 and the user's 2026-09-26 ruling (see module
# docstring for the 2D6 printings it overrides) -- and the two VR modes' (pp. 229-230).
ASTRAL_INITIATIVE_DICE = 3
COLD_SIM_INITIATIVE_DICE = 3
HOT_SIM_INITIATIVE_DICE = 4

# WP111: what provides the pieces VR needs, by catalog name. A direct neural interface: trodes, or
# an implanted datajack, commlink, cyberdeck or control rig ("like getting a free datajack",
# p. 452) -- pp. 227, 438, 451-452. A sim module: the commlink upgrade (p. 438), an implanted
# commlink ("comes with a sim module at no additional cost", p. 451), a control rig ("It has a
# built-in sim module", p. 452). Hot-sim: the upgrade's hot-sim version, or any cyberdeck ("All
# cyberdecks include illegal hot-sim modules right out of the box", p. 439).
_DNI_GEAR = frozenset({"Trodes"})
_DNI_CYBERWARE = frozenset({"Datajack", "Commlink", "Cyberdeck", "Control Rig"})
_COLD_SIM_GEAR = frozenset({"Sim Module"})
_HOT_SIM_GEAR = frozenset({"Sim Module, Hot"})
_SIM_CYBERWARE = frozenset({"Commlink", "Control Rig"})
_COMMLINK_CATEGORY = "Commlinks"
_CYBERDECK_CATEGORY = "Cyberdecks"


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
    if character.magic_type in ("Magician", "Aspected Magician"):  # WP121: tradition Drain too
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

    # WP113: the metatype's own racial effect (Troll Reach) -- keyed by metatype name.
    add(character.metatype.name, getattr(character.metatype, "unmodeled_effect_note", None))
    for quality in character.metatype_qualities:
        add(quality.name, getattr(quality, "unmodeled_effect_note", None))
    if character.quality_selection is not None:
        for pick in character.quality_selection.qualities:
            add(pick.quality.name, getattr(pick.quality, "unmodeled_effect_note", None))
        mentor_spirit = character.quality_selection.mentor_spirit
        if mentor_spirit is not None:
            add(
                mentor_spirit.archetype.name,
                getattr(mentor_spirit.archetype, "unmodeled_effect_note", None),
            )
            # WP122: what the mentor grants -- free powers, and Eagle's Allergy.
            for free in mentor_spirit.free_powers:
                add(free.power.name, getattr(free.power, "unmodeled_effect_note", None))
            for granted in mentor_spirit.granted_qualities:
                add(granted.quality.name, getattr(granted.quality, "unmodeled_effect_note", None))
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
        # WP132: the Lifestyle Options' in-play effects.
        for option_pick in character.lifestyle_selection.options:
            add(option_pick.option.name, option_pick.option.unmodeled_effect_note)
    if character.resources_selection is not None:
        for gear_item in character.resources_selection.gear:
            add(gear_item.name, getattr(gear_item, "unmodeled_effect_note", None))
        # WP130: accessories on purchased weapons.
        for installed in character.resources_selection.weapon_accessories:
            add(installed.name, installed.unmodeled_effect_note)
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


def overflow(character: Character) -> int:
    """Overflow boxes (WP109): augmented `BOD + Σ CM_OVERFLOW` -- see module docstring."""
    return character.attribute_value("BOD") + character.improvements.resolve(
        ImprovementType.CM_OVERFLOW, _GLOBAL_TARGET
    )


@dataclass(frozen=True)
class WoundModifierRule:
    """How damage turns into wound modifiers (WP109): -1 per `boxes_per_modifier` boxes of damage,
    after the first `*_boxes_ignored` boxes on that track. See module docstring."""

    boxes_per_modifier: int
    physical_boxes_ignored: int
    stun_boxes_ignored: int


def wound_modifier_rule(character: Character) -> WoundModifierRule:
    index = character.improvements
    boxes = BASE_WOUND_BOXES_PER_MODIFIER + index.resolve(
        ImprovementType.CM_THRESHOLD, _GLOBAL_TARGET
    )
    ignored = index.resolve(ImprovementType.CM_THRESHOLD_OFFSET, _GLOBAL_TARGET) + index.resolve(
        ImprovementType.CM_SHARED_THRESHOLD_OFFSET, _GLOBAL_TARGET
    )
    return WoundModifierRule(
        boxes_per_modifier=max(boxes, 1),
        physical_boxes_ignored=ignored,
        stun_boxes_ignored=ignored,
    )


@dataclass(frozen=True)
class ArmorBreakdown:
    """The parts of a character's Armor (WP109), so the sheet can say where the number comes from.

    `body_armor` is the worn body armor that counts (the highest-rated one, p. 169), or `None`.
    `accessory_total` is every worn `+N` accessory summed; `accessory_bonus` is that capped at
    Strength. `encumbrance_penalty` is the -N to Agility and Reaction the excess costs *while*
    worn -- 0 when within Strength. `improvements` is `Σ ARMOR` (cyberware, racial, powers).
    """

    body_armor: StarterGearItem | None
    accessory_total: int
    accessory_bonus: int
    improvements: int
    encumbrance_penalty: int

    @property
    def total(self) -> int:
        body = 0
        if self.body_armor is not None and self.body_armor.armor_rating is not None:
            body = self.body_armor.armor_rating
        return body + self.accessory_bonus + self.improvements


def worn_armor(character: Character) -> tuple[StarterGearItem, ...]:
    """Every purchased Armor-category item not marked unworn (WP109)."""
    if character.resources_selection is None:
        return ()
    return tuple(
        item
        for item in character.resources_selection.gear
        if item.category == ARMOR_CATEGORY
        and item.armor_rating is not None
        and item.name not in character.unworn_armor
    )


def armor_breakdown(character: Character) -> ArmorBreakdown:
    worn = worn_armor(character)
    body = [item for item in worn if not item.armor_stacks]
    body_armor = max(body, key=lambda item: item.armor_rating or 0, default=None)
    accessory_total = sum(item.armor_rating or 0 for item in worn if item.armor_stacks)
    strength = character.attribute_value("STR")
    excess = max(accessory_total - strength, 0)
    return ArmorBreakdown(
        body_armor=body_armor,
        accessory_total=accessory_total,
        accessory_bonus=min(accessory_total, strength),
        improvements=character.improvements.resolve(ImprovementType.ARMOR, _GLOBAL_TARGET),
        encumbrance_penalty=excess // 2,
    )


def armor(character: Character) -> int:
    """The character's Armor (WP109) -- see `armor_breakdown`."""
    return armor_breakdown(character).total


def damage_resistance(character: Character) -> int:
    """The Damage Resistance pool (WP109): augmented `BOD + Armor + Σ DAMAGE_RESISTANCE`."""
    return (
        character.attribute_value("BOD")
        + armor(character)
        + character.improvements.resolve(ImprovementType.DAMAGE_RESISTANCE, _GLOBAL_TARGET)
    )


def street_cred(character: Character) -> int:
    """Street Cred at creation (WP110): always 0.

    p. 368: "Street Cred equals the character's total Karma [earned], divided by 10". Karma is
    *earned* in play; the 25 Karma a character is built with, and any Karma a negative quality
    refunds, are spent at creation, not earned. The legacy engine agrees (`CalculatedStreetCred`
    reads career Karma only). GM awards come later still.
    """
    del character
    return 0


def notoriety(character: Character) -> int:
    """Notoriety (WP110): Σ `NOTORIETY` -- p. 368's "starts off with a Notoriety of 0", shifted by
    the listed qualities (+1 per negative, -1 per positive, 3 for Bad Rep). May be negative."""
    return character.improvements.resolve(ImprovementType.NOTORIETY, _GLOBAL_TARGET)


def public_awareness(character: Character) -> int:
    """Public Awareness at creation (WP110): always 0. p. 368: "the gamemaster determines when the
    actions of a runner should be awarded a point of Public Awareness" -- nothing at creation.
    Legacy has an optional house rule deriving it as (Street Cred + Notoriety) / 3; it is off by
    default and not in the rulebook, so it isn't followed."""
    del character
    return 0


def astral_initiative(character: Character) -> int | None:
    """Astral Initiative's attribute part (WP111): `INT x 2`, or `None` for a character who can't
    astrally project (anyone but a Magician) -- see module docstring. Add
    `ASTRAL_INITIATIVE_DICE` D6."""
    if character.magic_type != "Magician":
        return None
    return character.attribute_value("INT") * 2


@dataclass(frozen=True)
class MatrixVRInitiative:
    """Matrix VR Initiative (WP111): `data_processing + INT`, with cold-sim always available when
    VR is, and hot-sim only when a hot-sim module is (`hot_sim`).

    `device` is the purchase whose Data Processing is used: the character's best persona device, a
    cyberdeck over a commlink when both are owned since the deck is what a decker runs. A cyberdeck
    has no fixed Data Processing -- its Attribute Array is assigned by the decker (p. 439) -- so
    `from_array` says the figure assumes its highest array value there.
    """

    data_processing: int
    device: StarterGearItem
    from_array: bool
    hot_sim: bool
    intuition: int

    @property
    def value(self) -> int:
        return self.data_processing + self.intuition


def matrix_vr_initiative(character: Character) -> MatrixVRInitiative | None:
    """The VR Initiative rows (WP111), or `None` when the character can't enter VR at all.

    VR needs three things (pp. 227, 229, 438): a direct neural interface, a sim module, and a device
    to run the persona on. `None` if any is missing -- so a character with only a commlink gets the
    AR row and nothing else, which is what the book says a plain commlink user has.
    """
    gear = character.resources_selection.gear if character.resources_selection is not None else ()
    gear_names = {item.name for item in gear}
    cyberware_names = (
        {node.item.name for node in character.cyberware_selection.walk()}
        if character.cyberware_selection is not None
        else set()
    )
    decks = [item for item in gear if item.category == _CYBERDECK_CATEGORY and item.attribute_array]
    commlinks = [
        item for item in gear if item.category == _COMMLINK_CATEGORY and item.data_processing
    ]
    has_dni = bool(gear_names & _DNI_GEAR or cyberware_names & _DNI_CYBERWARE)
    hot_sim = bool(decks or gear_names & _HOT_SIM_GEAR)
    has_sim = hot_sim or bool(gear_names & _COLD_SIM_GEAR or cyberware_names & _SIM_CYBERWARE)
    if not has_dni or not has_sim or not (decks or commlinks):
        return None
    if decks:
        deck = max(decks, key=lambda item: max(item.attribute_array or (0,)))
        return MatrixVRInitiative(
            data_processing=max(deck.attribute_array or (0,)),
            device=deck,
            from_array=True,
            hot_sim=True,
            intuition=character.attribute_value("INT"),
        )
    commlink = max(commlinks, key=lambda item: item.data_processing or 0)
    return MatrixVRInitiative(
        data_processing=commlink.data_processing or 0,
        device=commlink,
        from_array=False,
        hot_sim=hot_sim,
        intuition=character.attribute_value("INT"),
    )


def reach(character: Character) -> int:
    """Extra melee Reach (WP113): Σ `REACH` -- the Troll's racial +1 (p. 185). A sheet number only;
    no melee resolution exists here to read it (Project Overview registry)."""
    return character.improvements.resolve(ImprovementType.REACH, _GLOBAL_TARGET)


# WP129, p. 94: "if a character takes cyberware or bioware, it may remove a particular racial
# bonus. For example, if a player who has an elf character buys cybereyes, their natural low-light
# vision is removed and replaced with the cybereyes [...] she'll have to select the low-light
# modification for the cybereyes. Similarly, orthoskin replaces the natural dermal deposits of a
# troll so he would no longer receive the +1 dermal armor from his natural skin hardness."
CYBEREYES = "Cybereyes Basic System"
# A racial vision quality -> the cybereye plugin that keeps it (the same names in both files).
RACIAL_VISION_PLUGINS = {
    "Low-Light Vision": "Low-Light Vision",
    "Thermographic Vision": "Thermographic Vision",
}
# The skin augmentations that replace a troll's dermal armor: Orthoskin (p. 94), and Dermal
# Plating, which legacy puts in the same `armor group="0"` dedup group (so its Armor already
# replaces, never stacks with, the racial +1 -- `Improvement.unique_name`).
SKIN_ARMOR_AUGMENTATIONS = ("Orthoskin", "Dermal Plating")
# `SuppressedRacialTrait.trait` for the Troll's racial Armor, which is not a quality.
DERMAL_ARMOR_TRAIT = "dermal armor"


@dataclass(frozen=True)
class SuppressedRacialTrait:
    """A racial trait an implant has taken the place of (WP129): `trait` is the metatype
    quality's name, or `DERMAL_ARMOR_TRAIT`; `replaced_by` names the implant."""

    trait: str
    replaced_by: str


def suppressed_racial_traits(character: Character) -> tuple[SuppressedRacialTrait, ...]:
    """The racial traits the character's implants replace (WP129, p. 94) -- for the sheet. Nothing
    here changes a number: the vision qualities carry no computed effect, and the dermal armor's
    replacement is already the Armor dedup group's highest-wins.

    Cybereyes remove a racial Low-Light or Thermographic Vision unless some pair of cybereyes
    carries that plugin. A troll's dermal armor is replaced by Orthoskin or Dermal Plating.
    Cyberears replace nothing: no core metatype has a racial hearing trait (checked against the
    Metatype Attribute Table, p. 66).
    """
    cyberware = character.cyberware_selection
    nodes = cyberware.walk() if cyberware is not None else ()
    eyes = [node for node in nodes if node.item.name == CYBEREYES]
    eye_plugins = {plugin.item.name for node in eyes for plugin in node.plugins}
    suppressed: list[SuppressedRacialTrait] = []
    if eyes:
        for quality in character.metatype_qualities:
            plugin = RACIAL_VISION_PLUGINS.get(quality.name)
            if plugin is not None and plugin not in eye_plugins:
                suppressed.append(SuppressedRacialTrait(quality.name, CYBEREYES))
    if character.metatype.armor:
        bioware = character.bioware_selection
        implants = [node.item.name for node in nodes] + (
            [item.name for item in bioware.items] if bioware is not None else []
        )
        replacement = next((name for name in implants if name in SKIN_ARMOR_AUGMENTATIONS), None)
        if replacement is not None:
            suppressed.append(SuppressedRacialTrait(DERMAL_ARMOR_TRAIT, replacement))
    return tuple(suppressed)


def memory(character: Character) -> int:
    """Memory (WP114): `LOG + WIL + Σ MEMORY` -- what Memory Tests roll (p. 152), raised by
    Photographic Memory's +2 (p. 76) and, from WP128, the Mnemonic Enhancer."""
    return (
        character.attribute_value("LOG")
        + character.attribute_value("WIL")
        + character.improvements.resolve(ImprovementType.MEMORY, _GLOBAL_TARGET)
    )
