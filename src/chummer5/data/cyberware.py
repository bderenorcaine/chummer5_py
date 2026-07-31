"""Loader for `legacy/Chummer/data/cyberware.xml`, restricted to SR5 core-rulebook content, flat
cost, flat Essence, Standard grade only (WP31 -- Phase J's first content WP, following WP30's
Essence-tracking prerequisite).

Of `cyberware.xml`'s 362 entries, 87 carry `source == "SR5"`. Grade is not offered at all this
phase (Phase J intro) -- `<cost>`/`<ess>` are consumed directly as Standard-grade values, with no
`<grades>` multiplier applied. Beyond that, this loader further restricts to items whose `<cost>`
is a bare integer literal and whose `<ess>` is a bare (optionally fractional) decimal literal --
mirroring `chummer5.data.gear`'s identical "flat, not a formula" filter for WP21's gear catalog.
Confirmed directly against the XML (not assumed from the Implementation Plan's own pre-stated
count): 60 of the 87 SR5 entries pass both filters. The other 27 carry a `Rating * N`/
`FixedValues(...)`/compound-arithmetic formula in `<cost>` and/or `<ess>` (e.g. Wired Reflexes'
`FixedValues(2,3,5)`
Essence cost) -- the legacy engine resolves those at read time against a purchased rating; this
loader does not evaluate rules-language expressions, mirroring WP21's own gear-formula exclusion.
None of the 60 flat items carry a `<rating>` tag at all (checked directly), confirming they are
genuinely single-purchase items with no rating dimension to resolve in the first place -- simpler
than WP27's powers, which needed a rating multiplier despite being flat-PP-cost.

`<bonus>` nodes are classified with a 3-way `BonusSupport` scheme mirroring
`chummer5.data.qualities.BonusSupport` (not `chummer5.data.powers.BonusSupport`, which deliberately
has no `NO_EFFECT` member) -- a genuinely new `BonusSupport` Enum per module, not an import shared
across `qualities`/`powers`/`cyberware`, since each module's own docstring already documents why its
membership differs (WP27's docstring explains why powers has no `NO_EFFECT`; this one explains why
cyberware's `NO_EFFECT` needs no name-gate, unlike qualities'). Verified directly against every one
of the 60 flat items' raw `<bonus>` node:

- `NO_EFFECT` -- an empty/absent `<bonus>` (42 of 60: pure Essence/nuyen cost, no other effect at
  all). Unlike `chummer5.data.qualities.BonusSupport.NO_EFFECT`, no name-gate is needed here: an
  empty `<bonus>` on a piece of cyberware already means literally nothing beyond its Essence/nuyen
  cost -- there's no equivalent of a quality's "empty `<bonus>` but a real in-play narrative effect"
  ambiguity WP22 had to individually verify away, because cyberware's own narrative/mechanical
  effects (if any) always show up as a real `<bonus>` child.
- `FLAT_BONUS` -- 8 of 60, all Cyberlimb-category items (Obvious/Synthetic Full Arm, Torso, Skull;
  Obvious/Synthetic Full Leg) whose `<bonus>` reduces, after stripping `<disablequality>` (see next
  bullet), to exactly one `<conditionmonitor><physical>1</physical></conditionmonitor>` child --
  maps directly onto the existing `ImprovementType.PHYSICAL_CM`, the same type WP10 already wired
  into `chummer5.engine.derived.physical_condition_monitor`. Every one of these 8 carries the
  identical value (`1`), confirmed directly rather than assumed. **WP78 adds three more flat
  shapes** -- `<specificattribute>`, `<initiativepass>` and `<specificskill>` -- see its own
  section at the bottom of this docstring; none of them appears on a row `load_cyberware()` keeps,
  so the flat catalog's own 8/42/1/5 split is untouched by that WP.
- **A verified-inert bonus child, `<disablequality>`, is stripped before classification rather than
  disqualifying the item to `NOT_YET_SUPPORTED`.** 6 of the 60 flat items (the same 8 Cyberlimb
  FLAT_BONUS items above, minus the 2 that carry *only* `<conditionmonitor>`, plus 4 more --
  Obvious/Synthetic Foot and Lower Leg -- whose `<bonus>` is *only* `<disablequality>Celerity
  </disablequality>`, no `<conditionmonitor>` at all) name-disable the Celerity quality (SR5's
  running-speed-boost metagenic quality) while that limb is installed. Verified moot for this
  engine's actual offered scope, not assumed: `Celerity` is `source == "RF"` (not `SR5` -- excluded
  from `mvp_quality_catalog` on source grounds alone) and additionally gated behind a `<required>`
  of Changeling-SURGE qualities in the raw data, so it is categorically unreachable by any character
  this engine can build regardless of this loader's own scope. Concretely: after stripping
  `<disablequality>` children, the 2 Full-Leg items reduce to a bare `<conditionmonitor>` (still
  `FLAT_BONUS`) and the 4 Foot/Lower-Leg items reduce to nothing at all (`NO_EFFECT`, the same
  bucket as a genuinely empty `<bonus>`) -- 8 `FLAT_BONUS` + 4 of these = the 12 Cyberlimb items
  that carry *any* `<bonus>` at all, out of 16 total flat Cyberlimb entries.
  **WP78 re-checked this exclusion against the wider (87-row) catalog and it still holds, but for a
  second reason the WP31 text above doesn't cover:** two of the rating-scaled rows
  (`Wired Reflexes`, and `Cybereyes Basic System`'s 7-strong list) name their disabled quality by
  **raw guid** rather than by name. The one that matters is
  `3564b678-7721-4a8d-ac79-1600cf92dc14`, resolved against `qualities.xml` -- it is
  **Lightning Reflexes**, `source == "RF"`, so it is excluded from the SR5 quality catalog on
  source grounds exactly as `Celerity` is, and is likewise unreachable by any character this
  engine can build. Stripping it therefore drops nothing real.
- `CONDITIONAL_BONUS` (WP40 -- Phase K) -- a `<limitmodifier>` whose `<condition>` is one of the
  four named conditions `chummer5.engine.improvements.ImprovementCondition` compiles (see below).
  Exactly 1 of the 60 flat items: **Spatial Recognizer**, which WP31 classified `NOT_YET_SUPPORTED`
  purely because nothing could express "only during this kind of test" yet. WP39 built that
  primitive, so this is now real, modeled content rather than a documented gap. The other three
  conditional items (Vision Enhancement, Audio Enhancement, Hydraulic Jacks) are rating-scaled and
  therefore outside this loader's flat-only scope entirely -- they reach the engine through
  `chummer5.data.cyberware_subsystems`, which shares `classify_bonus` verbatim, so this one
  classifier covers all four.
- `NOT_YET_SUPPORTED` -- the remaining 5: Smartlink (`<smartlink>2</smartlink>` -- no smartlink/
  called-shot mechanic modeled), Damper (`<sonicresist>2</sonicresist>` -- no sonic-attack
  resistance modeled), and the 3 Bone Lacing variants (`<armor>`/`<damageresistance>`/
  `<unarmeddv>`/`<unarmeddvphysical>` -- an armor/unarmed-combat bundle, no combat system in this
  engine's scope). Each individually confirmed to have a real, non-Essence/non-nuyen mechanical
  effect, not shape-matched by accident.

**The four supported conditions are a whitelist of confirmed real `<condition>` strings, not a
condition language** -- mirroring this module's own "classify known, named shapes" posture for
`<bonus>` generally, and WP39's identical decision one layer up (`ImprovementCondition` is an Enum
with one member per confirmed shape). `_SUPPORTED_BONUS_CONDITIONS` below is the complete set of
`<condition>` values appearing anywhere in the SR5 cyberware rows -- verified by enumeration, so
"whitelist" costs no coverage today; an unrecognized one falls through to `NOT_YET_SUPPORTED`
exactly as an unrecognized `<bonus>` child already does. The condition key is carried through as
its **verbatim legacy string**, not as an engine enum: this module is the data layer and does not
import from `chummer5.engine`, the same split `CyberwareFlatBonus.target_kind`'s string already
uses (`chummer5.engine.cyberware` owns both string -> enum maps).

## WP78 (Phase K) -- the three flat shapes that make four rating-scaled rows stop being inert

WP77's audit split the `NOT_YET_SUPPORTED` rows into "genuinely outside this engine's scope"
(registered in the Project Overview's "Unmodeled real effects" table) and "computable today, and
therefore a live policy violation while it stays unmodeled." WP78 is the second bucket's fix for the
four cyberware rows in it. Three new `<bonus>` child shapes, whitelisted the same "classify known,
named shapes" way everything above already is -- **not** a general `<bonus>` interpreter:

- `<specificattribute><name>REA</name><val>Rating</val></specificattribute>` -- `target_kind
  "attribute"`, `target_name` the attribute code. Reaction Enhancers (REA), Wired Reflexes (REA),
  Muscle Replacement (AGI **and** STR, one child each). Exactly `{name, val}` and nothing else is
  accepted: legacy's own handler also reads `<min>`/`<max>`/`<aug>`/`<affectbase>` children, which
  modify an attribute's *bounds* rather than its value and are a different mechanic this engine has
  no representation of -- a row carrying one falls through to `NOT_YET_SUPPORTED` rather than being
  half-applied. No SR5 cyberware row carries one (verified by enumeration).
- `<initiativepass>Rating</initiativepass>` -- `target_kind "initiative_dice"`, no target name.
  Wired Reflexes only. Named "initiative *pass*" for historical reasons; legacy's own
  `AddImprovementCollection.initiativepass` is a one-line delegation to `initiativedice`, so this
  maps onto `ImprovementType.INITIATIVE_DICE`, not `INITIATIVE`.
- `<specificskill><name>Impersonation</name><bonus>Rating</bonus></specificskill>` -- `target_kind
  "skill"`, `target_name` the skill's **name** (which is what `ImprovementType.SKILL` resolves
  against throughout this engine -- see `chummer5.engine.skills.skill_rating`). Voice Modulator
  only. The identical shape `chummer5.data.qualities`/`chummer5.data.bioware`/`chummer5.data.powers`
  already classify; the one new thing here is that cyberware's value may be the literal string
  `Rating` rather than an integer.

**A value of `Rating` is carried as `value=None`, not as the number 1** -- mirroring
`CyberwareConditionalBonus.value` exactly, and for the same reason: the magnitude isn't known until
a rating is purchased. Read it through `resolve_value(rating)`.

**Stacking: `precedence`/`unique` become `Improvement.unique_name`.** Three of the four rows carry a
legacy dedup marker, and dropping it would produce numbers the rulebook explicitly forbids:

- `precedence="0"` on a `<bonus>` child (Reaction Enhancers' and Wired Reflexes' REA bonuses, Wired
  Reflexes' Initiative Dice bonus) -> `unique_name "precedence0"`. This is what stops a character
  who owns both from getting +2 REA: p. 455 says reaction enhancers "are incompatible with all other
  enhancements to Reaction, including wired reflexes," and wired reflexes are likewise "incompatible
  with augmentations that affect Reaction or Initiative." `SCSi.chum5` is the fixture proof -- it
  owns both at Rating 1 and its legacy-computed REA `<totalvalue>` is 3, not 4.
- `unique="muscle"` on the `<bonus>` *element* (Muscle Replacement) -> the same `unique_name` for
  every child that doesn't override it with its own `precedence`. p. 455: muscle replacement "cannot
  be combined with other augmentations to the muscles, including muscle augmentation or muscle toner
  bioware" -- both of which carry the same `unique="muscle"` marker in `bioware.xml`.

The legacy semantics of `precedence0` are marginally stronger than `Improvement.unique_name`'s
plain "highest wins": legacy takes `max(sum of unmarked improvements, highest precedence0)` rather
than adding the two. The difference is only reachable when an *unmarked* bonus to the same attribute
coexists (in this engine's scope: an adept's Improved Physical Attribute alongside cyberware), and
closing it means changing `ImprovementIndex.resolve` itself. Recorded rather than silently
differing -- see `spec/decisions-log.md`, 2026-07-31.

## WP79 (Phase K) -- `unmodeled_effect_note`, and why one dict serves both cyberware catalogs

WP77 wrote the Project Overview's "Unmodeled real effects" rows for augmentation content; nothing
*showed* them to a player. `UNMODELED_EFFECT_NOTES` below is the hand-kept mirror of that markdown
table (the same posture `chummer5.data.qualities._UNMODELED_EFFECT_NOTES` established in WP56 --
runtime code never reads a `.md` file as data), keyed by catalog name and surfaced through
`chummer5.engine.derived.unmodeled_effect_notes` on the character sheet.

**One constant, not one per catalog.** `Cyberware` (this module's flat 60) and
`chummer5.data.cyberware_subsystems.CyberwareEntry` (all 87) are two views of the *same rows of the
same file*, so two dicts would be two mirrors of one registry table, free to drift apart while both
looked maintained. `cyberware_subsystems` imports this one, exactly as it already imports
`classify_bonus`/`BonusSupport`/`CyberwareFlatBonus` from here. (`chummer5.data.bioware` keeps its
own, because it loads a different file -- it happens to be empty today; see its docstring.)

**A note is independent of `bonus_support`, and covers two different situations.** Ten of the
sixteen named rows are `NOT_YET_SUPPORTED` (WP77's registry rows: the effect is absent entirely).
The other six are `NO_EFFECT`/`CONDITIONAL_BONUS` rows whose effect this engine models *in part* --
WP38's cyberlimb Customization/Enhancement and WP40's four conditional limit bonuses -- so their
note is the unmodeled **remainder**, and is worded to say what *is* applied too, since "Enhanced
Agility: adds its Rating to the limb's Agility" read as a bare gap would be actively misleading.

WP32 is what actually turns `FLAT_BONUS` items into real `Improvement` records (mirroring
`chummer5.engine.qualities.apply_quality_improvements`'s shape) -- this module only classifies.
`NOT_YET_SUPPORTED` items are still loaded (unlike qualities'/powers' catalogs, which exclude them
from what a player can pick): a piece of cyberware's fundamental content *is* its Essence/nuyen
cost, with `<bonus>` a secondary, sometimes-absent effect on top -- so WP32/WP34 remain free to
offer Bone Lacing (Titanium) for purchase (real fixture data confirms multiple curated mundane
characters own it) while simply not applying its unmodeled armor/damage-resistance bonus, the same
"purchase is real, secondary effect is dropped and documented" posture `chummer5.data.gear` already
established for gear generally (no engine-side bonus modeling for any gear item at all). This is a
deliberate
difference from `chummer5.data.qualities`'s "never partially apply, so exclude entirely" rule --
recorded here because it is a real, considered choice, not an oversight: a quality's entire content
*is* its bonus (nothing to buy otherwise), while cyberware's Essence/nuyen cost stands on its own as
real, correctly-modeled content even when its bonus doesn't.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from pathlib import Path

# legacy/Chummer/data/cyberware.xml, resolved relative to this file (not cwd).
DEFAULT_CYBERWARE_PATH = (
    Path(__file__).resolve().parents[3] / "legacy" / "Chummer" / "data" / "cyberware.xml"
)

# MVP content scope: only entries carrying this <source> tag are loaded. See "MVP content scope" in
# Implementation Plan.md.
CORE_RULEBOOK_SOURCE = "SR5"

# A bare (optionally negative) integer literal, e.g. "1000" -- not "Rating * 1000" or
# "FixedValues(...)". Mirrors chummer5.data.gear's identical flat-cost filter.
_FLAT_INT_RE = re.compile(r"-?\d+")
# A bare (optionally negative, optionally fractional) decimal literal, e.g. "0.2" or "1.5" -- not
# "Rating * 0.3" or "FixedValues(2,3,5)". Essence costs, unlike cost, are routinely fractional.
_FLAT_DECIMAL_RE = re.compile(r"-?\d+(\.\d+)?")

# The one <bonus> child tag verified moot for this engine's actual offered scope -- see module
# docstring's "verified-inert bonus child" paragraph. Stripped before classification rather than
# treated as a real, unmodeled effect.
_VERIFIED_INERT_BONUS_TAGS = frozenset({"disablequality"})

# <limitmodifier><limit>X</limit> -> CyberwareConditionalBonus.target_kind. Only Mental and
# Physical occur in the SR5 cyberware rows (verified by enumeration); a `Social` one would fall
# through to NOT_YET_SUPPORTED rather than being mapped on the assumption it works the same way.
_LIMIT_TARGET_KINDS = {"Mental": "mental_limit", "Physical": "physical_limit"}

# <limitmodifier><value>Rating</value>, <specificattribute><val>Rating</val>, ...: the bonus is the
# purchased Rating, not a literal. The only non-literal value shape in the SR5 rows.
_RATING_VALUE = "Rating"

# WP78's three flat-bonus shapes, each accepted only with exactly this child-tag set -- see the
# module docstring for why an extra child (legacy's <min>/<max>/<aug>, <applytorating>, ...) sends
# the whole item to NOT_YET_SUPPORTED instead of being ignored.
_SPECIFIC_ATTRIBUTE_FIELDS = frozenset({"name", "val"})
_SPECIFIC_SKILL_FIELDS = frozenset({"name", "bonus"})

# Every <condition> string appearing in the SR5 cyberware rows, verified by enumeration (WP39's
# learnings entry has the item/limit/condition/English-text table). A whitelist, not a parser --
# see module docstring.
_SUPPORTED_BONUS_CONDITIONS = frozenset(
    {
        "LimitCondition_SkillsActivePerceptionVisual",  # Vision Enhancement
        "LimitCondition_SkillsActivePerceptionHearing",  # Audio Enhancement
        "LimitCondition_SkillsActivePerceptionSpatialRecognizer",  # Spatial Recognizer
        "LimitCondition_CyberwareHydraulicJacks",  # Hydraulic Jacks
    }
)

# WP79: the Project Overview's "Unmodeled real effects" rows for `cyberware.xml` content, mirrored
# by hand and keyed by catalog name -- see the module docstring for why this is one constant shared
# with `chummer5.data.cyberware_subsystems` rather than one per catalog, and why six of the sixteen
# rows describe a *remainder* rather than a total absence. Page numbers are the printed core
# rulebook's; the extracted quotes behind each are in `spec/rulebooks/learnings/phase-k.md`
# (WP38/WP39/WP40's entries for the six partial rows, WP77's for the ten absent ones).
UNMODELED_EFFECT_NOTES: Mapping[str, str] = {
    # --- WP77's registry rows: nothing of the printed effect is modeled ---------------------------
    "Bone Lacing (Plastic)": (
        "+1 Body dice for resisting physical damage, +1 Armor, and an unarmed Damage Value of "
        "(STR + 1)P (p. 454) -- no character-level Armor total exists for the bonus to add to, and "
        "there is no damage-resistance test or unarmed-combat representation at all."
    ),
    "Bone Lacing (Aluminum)": (
        "+2 Body dice for resisting physical damage, +2 Armor, and an unarmed Damage Value of "
        "(STR + 2)P (p. 454) -- no character-level Armor total exists for the bonus to add to, and "
        "there is no damage-resistance test or unarmed-combat representation at all."
    ),
    "Bone Lacing (Titanium)": (
        "+3 Body dice for resisting physical damage, +3 Armor, and an unarmed Damage Value of "
        "(STR + 3)P (p. 454) -- no character-level Armor total exists for the bonus to add to, and "
        "there is no damage-resistance test or unarmed-combat representation at all."
    ),
    "Smartlink": (
        "+2 to a smartgun's Accuracy while you fire it (p. 433, via the p. 444 accessory this "
        "implant is the eyeware version of) -- no weapon, Accuracy or attack-test representation "
        "exists. The legacy engine reads the same data as a wireless-gated ranged dice-pool "
        "modifier instead; both readings are equally unmodeled here."
    ),
    "Damper": (
        "+2 dice resisting sonic attacks, including flashbangs (p. 454) -- no test-resolution or "
        "sonic/damage-resistance subsystem exists."
    ),
    "Dermal Plating": (
        "+Rating Armor, cumulative with other armor and without adding Encumbrance (p. 454) -- no "
        "character-level Armor total exists for the bonus to add to."
    ),
    "Armor": (  # the Cyberlimb Enhancement, not a gear/armor item
        "+Rating Armor on the limb, cumulative and without adding Encumbrance (p. 456) -- no "
        'character-level Armor total exists for the bonus to add to. Its "one enhancement of each '
        'type per limb" cap belongs to the same unmodeled per-limb attribute system Customized/'
        "Enhanced Agility and Strength are registered for."
    ),
    "Internal Air Tank": (
        "Holding your breath for up to Rating hours, and complete protection from "
        "inhalation-vector toxin attacks while you do (p. 455) -- no breath/environmental or "
        "toxin/pathogen resistance subsystem exists."
    ),
    "Skillwires": (
        "Use of activesofts up to the skillwire's Rating, and only while they run on an implanted "
        "skilljack (p. 455) -- no skillsoft subsystem exists, and no skillsoft is purchasable to "
        "run in the first place."
    ),
    "Skilljack": (
        "Interpreting knowsofts and linguasofts and running activesofts, capped at Rating x 2 "
        "skills in total and Rating per skill (p. 452) -- no skillsoft subsystem exists, and no "
        "skillsoft is purchasable to run in the first place."
    ),
    # --- WP38/WP40's partly-modeled rows: the note is the unmodeled remainder ---------------------
    "Customized Agility": (
        "Raises the *limb's own* Agility above its cyberlimb base of 3 (p. 456) -- cyberlimbs have "
        "a per-limb attribute system this engine does not represent, so nothing downstream reads "
        "that value. The purchase's nuyen cost and its cap at your natural Agility maximum are "
        "modeled."
    ),
    "Customized Strength": (
        "Raises the *limb's own* Strength above its cyberlimb base of 3 (p. 456) -- cyberlimbs "
        "have a per-limb attribute system this engine does not represent, so nothing downstream "
        "reads that value. The purchase's nuyen cost and its cap at your natural Strength maximum "
        "are modeled."
    ),
    "Enhanced Agility": (
        "Adds its Rating to the limb's own Agility (p. 456) -- the same unmodeled per-limb "
        "attribute system as Customized Agility. The purchase's nuyen and Capacity costs are "
        "modeled."
    ),
    "Enhanced Strength": (
        "Adds its Rating to the limb's own Strength (p. 456) -- the same unmodeled per-limb "
        "attribute system as Customized Strength. The purchase's nuyen and Capacity costs are "
        "modeled."
    ),
    "Vision Enhancement": (
        "Its Wireless clause's separate +Rating dice pool modifier on visual Perception tests "
        "(p. 444) -- no wireless state and no test-resolution system exists. The +Rating Mental "
        "limit on those same tests is modeled."
    ),
    "Audio Enhancement": (
        "Its Wireless clause's separate +Rating dice pool modifier on audio Perception tests "
        "(p. 444) -- no wireless state and no test-resolution system exists. The +Rating Mental "
        "limit on those same tests is modeled."
    ),
    "Spatial Recognizer": (
        "Its Wireless clause's separate dice pool modifier on Perception tests to find the source "
        "of a sound (p. 444) -- no wireless state and no test-resolution system exists. The +2 "
        "Mental limit on that test is modeled."
    ),
    "Hydraulic Jacks": (
        "Twenty percent added to your maximum jump distance, and two metres taken off your falling "
        "distance for falling-damage purposes (p. 457) -- no movement or falling-damage system "
        "exists. The +Rating Physical limit for jumping and sprinting, granted once per matched "
        "pair, is modeled."
    ),
}


class BonusSupport(Enum):
    """Whether/how a cyberware item's `<bonus>` node was parsed. See module docstring for the 4
    values -- WP31's 3-way scheme mirroring `chummer5.data.qualities.BonusSupport` (not
    `chummer5.data.powers.BonusSupport`'s 2-way one), plus WP40's `CONDITIONAL_BONUS`, which no
    other catalog module has because no other catalog has a bonus that applies only during a
    specific kind of test.
    """

    FLAT_BONUS = "flat_bonus"
    CONDITIONAL_BONUS = "conditional_bonus"
    NO_EFFECT = "no_effect"
    NOT_YET_SUPPORTED = "not_yet_supported"


@dataclass(frozen=True)
class CyberwareFlatBonus:
    """One unconditional, flat point bonus produced by a cyberware item.

    `target_kind` is `"physical_cm"` (WP31's Cyberlimb condition-monitor bonus) or, since WP78,
    one of `"attribute"`, `"skill"`, `"initiative_dice"`. `chummer5.engine.cyberware` maps it to an
    `ImprovementType`, the same string -> enum split `CyberwareConditionalBonus.target_kind`
    already uses.

    `target_name` names *which* attribute (`"REA"`) or skill (`"Impersonation"`) is affected, and
    is `""` for the character-wide kinds (`physical_cm`, `initiative_dice`) -- which is also the
    `_GLOBAL_TARGET` sentinel `chummer5.engine` resolves those against, so a caller can pass it
    through unconditionally. Mirrors `chummer5.data.bioware.BiowareFlatBonus`/`chummer5.data
    .qualities.FlatBonus`, which made the same "empty name for a global target" choice.

    `value` is `None` when the bonus is the item's own purchased Rating (`<val>Rating</val>`)
    rather than a literal -- identical to `CyberwareConditionalBonus.value`, and read the same way,
    through `resolve_value(rating)`. A `None` here is "ask the purchase," not "no bonus."

    `unique_name` is the legacy dedup group (`"precedence0"` from a child's `precedence` attribute,
    or a `<bonus unique="...">` value), passed straight through to `Improvement.unique_name` so
    SR5's "these don't stack" rules land on the existing highest-bonus-wins pass. `None` means the
    bonus stacks additively -- the correct answer for the Cyberlimb condition-monitor bonus, where
    a second cyberlimb really does add a second box.
    """

    target_kind: str
    value: int | None
    target_name: str = ""
    unique_name: str | None = None

    def resolve_value(self, rating: int) -> int:
        """This bonus's magnitude for a purchase at `rating`."""
        return rating if self.value is None else self.value


@dataclass(frozen=True)
class CyberwareConditionalBonus:
    """One point bonus that applies only during a specific kind of test (WP40).

    `target_kind` is `"mental_limit"` or `"physical_limit"` -- the `<limitmodifier><limit>` value,
    mapped to an `ImprovementType` by `chummer5.engine.cyberware`, the same way
    `CyberwareFlatBonus.target_kind` already is.

    `value` is `None` when the bonus is the item's own purchased Rating
    (`<value>Rating</value>` -- Vision/Audio Enhancement, Hydraulic Jacks) rather than a literal
    (`<value>2</value>` -- Spatial Recognizer). Use `resolve_value(rating)` rather than reading the
    field directly; a `None` here is "ask the purchase," not "no bonus."

    `condition` is the verbatim legacy `<condition>` key (e.g.
    `"LimitCondition_SkillsActivePerceptionVisual"`), which `chummer5.engine.cyberware` maps to an
    `ImprovementCondition` -- see the module docstring for why the data layer keeps the string.
    """

    target_kind: str
    value: int | None
    condition: str

    def resolve_value(self, rating: int) -> int:
        """This bonus's magnitude for a purchase at `rating`."""
        return rating if self.value is None else self.value


@dataclass(frozen=True)
class Cyberware:
    id: str
    name: str
    category: str
    cost: int
    essence_cost: Decimal
    source: str
    page: int
    bonus_support: BonusSupport
    flat_bonuses: tuple[CyberwareFlatBonus, ...]  # populated only when bonus_support is FLAT_BONUS
    # populated only when bonus_support is CONDITIONAL_BONUS (WP40)
    conditional_bonuses: tuple[CyberwareConditionalBonus, ...]
    raw_bonus: str | None  # serialized <bonus> element, kept for future parser work; None if absent
    # WP79: this item's real, unmodeled (or partly-modeled) SR5 effect, from UNMODELED_EFFECT_NOTES;
    # None for an item with no such gap. Independent of `bonus_support` -- see module docstring.
    unmodeled_effect_note: str | None = None


def _is_flat_cost(text: str | None) -> bool:
    return text is not None and _FLAT_INT_RE.fullmatch(text) is not None


def _is_flat_essence(text: str | None) -> bool:
    return text is not None and _FLAT_DECIMAL_RE.fullmatch(text) is not None


def _is_flat_physical_cm_bonus(elem: ET.Element) -> bool:
    physical = elem.find("physical")
    if physical is None or len(physical) != 0:
        return False
    return {child.tag for child in elem} == {"physical"} and physical.text is not None


def _parse_rating_or_literal(text: str | None) -> tuple[bool, int | None]:
    """`(recognized, value)` for a `Rating`-or-bare-integer bonus value, where `value is None`
    means "the purchased Rating" -- see `CyberwareFlatBonus.value`.
    """
    if text is None:
        return False, None
    stripped = text.strip()
    if stripped == _RATING_VALUE:
        return True, None
    if _FLAT_INT_RE.fullmatch(stripped) is not None:
        return True, int(stripped)
    return False, None


def _unique_name(bonus_elem: ET.Element, child: ET.Element) -> str | None:
    """The legacy dedup group for one `<bonus>` child, or `None` if it stacks additively.

    A child's own `precedence` attribute wins over the `<bonus>` element's `unique` attribute --
    which is exactly what legacy's own handlers do (each starts from the collection-wide
    `_strUnique`, read from `<bonus unique="...">`, then overwrites it with `"precedence" + value`
    when the child carries one). See the module docstring's WP78 stacking section.
    """
    precedence = child.get("precedence")
    if precedence is not None:
        return f"precedence{precedence.strip()}"
    unique = bonus_elem.get("unique")
    return unique.strip() if unique else None


def _parse_specific_attribute_bonus(
    elem: ET.Element, *, unique_name: str | None
) -> CyberwareFlatBonus | None:
    """Parse a `<specificattribute>` child (WP78), or `None` if it isn't the supported shape."""
    if {child.tag for child in elem} != _SPECIFIC_ATTRIBUTE_FIELDS:
        return None
    name = elem.findtext("name", "").strip()
    recognized, value = _parse_rating_or_literal(elem.findtext("val"))
    if not name or not recognized:
        return None
    return CyberwareFlatBonus(
        target_kind="attribute", value=value, target_name=name, unique_name=unique_name
    )


def _parse_specific_skill_bonus(
    elem: ET.Element, *, unique_name: str | None
) -> CyberwareFlatBonus | None:
    """Parse a `<specificskill>` child (WP78), or `None` if it isn't the supported shape."""
    if {child.tag for child in elem} != _SPECIFIC_SKILL_FIELDS:
        return None
    name = elem.findtext("name", "").strip()
    recognized, value = _parse_rating_or_literal(elem.findtext("bonus"))
    if not name or not recognized:
        return None
    return CyberwareFlatBonus(
        target_kind="skill", value=value, target_name=name, unique_name=unique_name
    )


def _parse_initiative_dice_bonus(
    elem: ET.Element, *, unique_name: str | None
) -> CyberwareFlatBonus | None:
    """Parse an `<initiativepass>` leaf (WP78), or `None` if it isn't the supported shape.

    Maps to Initiative *Dice*, not Initiative -- legacy's `initiativepass` handler is a straight
    delegation to `initiativedice`. See the module docstring.
    """
    if len(elem) != 0:
        return None
    recognized, value = _parse_rating_or_literal(elem.text)
    if not recognized:
        return None
    return CyberwareFlatBonus(target_kind="initiative_dice", value=value, unique_name=unique_name)


def _parse_conditional_limit_bonus(elem: ET.Element) -> CyberwareConditionalBonus | None:
    """Parse a `<limitmodifier>` child, or return `None` if it isn't a shape WP40 supports.

    The supported shape is exactly `<limit>` + `<value>` + `<condition>`, with a mapped limit, a
    whitelisted condition, and a value that is either the literal string `Rating` or a bare
    integer. Anything else -- an extra child, an unmapped limit, an unknown condition, an
    arithmetic value -- returns `None`, which sends the whole item to `NOT_YET_SUPPORTED`.
    """
    if {child.tag for child in elem} != {"limit", "value", "condition"}:
        return None

    target_kind = _LIMIT_TARGET_KINDS.get(elem.findtext("limit", "").strip())
    condition = elem.findtext("condition", "").strip()
    if target_kind is None or condition not in _SUPPORTED_BONUS_CONDITIONS:
        return None

    recognized, value = _parse_rating_or_literal(elem.findtext("value"))
    if not recognized:
        return None
    return CyberwareConditionalBonus(target_kind=target_kind, value=value, condition=condition)


def classify_bonus(
    bonus_elem: ET.Element | None,
) -> tuple[BonusSupport, tuple[CyberwareFlatBonus, ...], tuple[CyberwareConditionalBonus, ...]]:
    """Classify a `<bonus>` node, extracting flat and conditional bonuses when every remaining
    child is a supported shape. `<disablequality>` children are stripped first (see module
    docstring) -- an item whose `<bonus>` is empty, absent, or reduces to nothing after that
    stripping is `NO_EFFECT`; a single unsupported remaining child marks the whole item
    `NOT_YET_SUPPORTED` (mirrors `chummer5.data.qualities._classify_bonus`'s "never partially
    classify" rule for the bonus itself, independent of WP31's own "still load NOT_YET_SUPPORTED
    items" catalog-inclusion choice -- see module docstring).

    An item carrying **any** supported conditional bonus is `CONDITIONAL_BONUS`, even if it also
    carries a flat one; both tuples are populated either way, so a caller applies what it finds
    rather than branching on the support value. No SR5 row actually mixes the two (each of the four
    conditional items' `<bonus>` is a single `<limitmodifier>`), so this is a rule chosen for the
    mixed case rather than one any current row exercises -- said out loud because "which support
    value wins" would otherwise be invisible guesswork for whoever hits the first mixed row.

    Supported flat children: `<conditionmonitor><physical>` (WP31) and, since WP78,
    `<specificattribute>`, `<specificskill>` and `<initiativepass>` -- see the module docstring for
    each shape, its rulebook citation, and how `precedence`/`unique` become a dedup group. An item
    may carry several (Muscle Replacement carries two `<specificattribute>` children, Wired
    Reflexes one of those plus an `<initiativepass>`), and every recognized one is collected.

    Public (unlike `chummer5.data.qualities`/`powers`/`mentors`' identically-named private
    classifiers) because WP37's `chummer5.data.cyberware_subsystems` reads the *same* rows out of
    the *same* file and so shares this grammar verbatim -- see that module's docstring for why it
    reuses this rather than re-implementing it the way `chummer5.data.bioware` had to.
    """
    if bonus_elem is None or len(bonus_elem) == 0:
        return BonusSupport.NO_EFFECT, (), ()

    children = [child for child in bonus_elem if child.tag not in _VERIFIED_INERT_BONUS_TAGS]
    if not children:
        return BonusSupport.NO_EFFECT, (), ()

    flat_bonuses = []
    conditional_bonuses = []
    for child in children:
        unique_name = _unique_name(bonus_elem, child)
        if child.tag == "conditionmonitor" and _is_flat_physical_cm_bonus(child):
            flat_bonuses.append(
                CyberwareFlatBonus(
                    target_kind="physical_cm",
                    value=int(child.findtext("physical", "0")),
                    unique_name=unique_name,
                )
            )
            continue
        if child.tag == "specificattribute":
            attribute_bonus = _parse_specific_attribute_bonus(child, unique_name=unique_name)
            if attribute_bonus is not None:
                flat_bonuses.append(attribute_bonus)
                continue
        if child.tag == "specificskill":
            skill_bonus = _parse_specific_skill_bonus(child, unique_name=unique_name)
            if skill_bonus is not None:
                flat_bonuses.append(skill_bonus)
                continue
        if child.tag == "initiativepass":
            dice_bonus = _parse_initiative_dice_bonus(child, unique_name=unique_name)
            if dice_bonus is not None:
                flat_bonuses.append(dice_bonus)
                continue
        if child.tag == "limitmodifier":
            conditional = _parse_conditional_limit_bonus(child)
            if conditional is not None:
                conditional_bonuses.append(conditional)
                continue
        return BonusSupport.NOT_YET_SUPPORTED, (), ()

    support = BonusSupport.CONDITIONAL_BONUS if conditional_bonuses else BonusSupport.FLAT_BONUS
    return support, tuple(flat_bonuses), tuple(conditional_bonuses)


def _parse_cyberware(elem: ET.Element) -> Cyberware:
    bonus_elem = elem.find("bonus")
    support, flat_bonuses, conditional_bonuses = classify_bonus(bonus_elem)
    raw_bonus = (
        ET.tostring(bonus_elem, encoding="unicode").strip() if bonus_elem is not None else None
    )
    name = elem.findtext("name", "")
    return Cyberware(
        id=elem.findtext("id", ""),
        name=name,
        category=elem.findtext("category", ""),
        cost=int(elem.findtext("cost", "0")),
        essence_cost=Decimal(elem.findtext("ess", "0")),
        source=elem.findtext("source", ""),
        page=int(elem.findtext("page", "0")),
        bonus_support=support,
        flat_bonuses=flat_bonuses,
        conditional_bonuses=conditional_bonuses,
        raw_bonus=raw_bonus,
        unmodeled_effect_note=UNMODELED_EFFECT_NOTES.get(name),
    )


def load_cyberware(xml_path: Path = DEFAULT_CYBERWARE_PATH) -> tuple[Cyberware, ...]:
    """Parse `cyberware.xml`, restricted to `source == "SR5"` AND flat cost AND flat Essence (60
    of 87 SR5 entries) -- Standard grade only, per the Implementation Plan's Phase J intro.
    """
    root = ET.parse(xml_path).getroot()
    cyberwares_elem = root.find("cyberwares")
    if cyberwares_elem is None:
        return ()
    return tuple(
        _parse_cyberware(c)
        for c in cyberwares_elem.findall("cyberware")
        if c.findtext("source") == CORE_RULEBOOK_SOURCE
        and _is_flat_cost(c.findtext("cost"))
        and _is_flat_essence(c.findtext("ess"))
    )


def count_by_support(cyberware: Iterable[Cyberware]) -> Mapping[BonusSupport, int]:
    """Count cyberware items per `BonusSupport` value, so the supported/unsupported split is
    visible.
    """
    counts = Counter(c.bonus_support for c in cyberware)
    return {support: counts[support] for support in BonusSupport}
