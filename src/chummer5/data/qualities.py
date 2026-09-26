"""Loader for `legacy/Chummer/data/qualities.xml`, restricted to SR5 core-rulebook content.

MVP's "core rulebook only" scope (see `Project Overview.md`) narrows the file's 803 `<quality>`
entries to the 96 with `source == "SR5"`. `<bonus>` nodes are a mini-language mirroring the general
Improvement bonus grammar the legacy engine parses (metatype bonuses, notoriety shifts,
category-wide skill bonuses, select-a-target choices, ...); MVP does not implement that general
parser. Instead, each in-scope quality's `<bonus>` is classified as one of three `BonusSupport`
values:

- `FLAT_BONUS` — an unconditional, flat point bonus to one or more specifically-named skills,
  attributes, (since WP22) Inherent Limits, or (since WP49) the native-language limit — the shapes
  simple enough to feed directly into WP5's Improvement engine without a condition/selection
  sub-parser.
- `NO_EFFECT` (WP22) — a verified-inert quality: an empty `<bonus/>` node *and* individually
  confirmed, via the rulebook text and a `grep` of the legacy C# for by-name special-casing,
  to produce no computed value anywhere this engine's scope reaches (combat/Matrix/vehicle/
  perception mechanics MVP doesn't model). Deliberately name-gated (`_VERIFIED_NO_EFFECT_NAMES`),
  not "any empty `<bonus/>` qualifies" — several other empty-`<bonus/>` SR5 qualities
  (Human-Looking, the Insomnia pair, ...) are excluded from *this* list because they need a
  different kind of engine support (a metatype-gate check, a mutual-exclusion check) that WP22
  didn't build, not because their bonus is unverified. See `spec/worklogs/WP22.md` and
  `spec/rulebooks/learnings.md`'s WP22 entry for the full per-quality research.
- `SELECT_TEXT` (WP55) — a quality whose only unrecognized `<bonus>` content is a `<selecttext>`
  node (a free-text detail the player fills in, e.g. which SIN, which protected group, which
  disease) plus, for one quality (SINner (Criminal)), an accompanying `<notoriety>` (applied since
  WP110 through `Quality.notoriety`, which is parsed independently of this classification).
  Name-gated (`_VERIFIED_SELECT_TEXT_NAMES`), the identical pattern `NO_EFFECT` already
  established — see `spec/worklogs/WP55.md` and `spec/rulebooks/learnings.md`'s WP55 entry for the
  full per-quality research into why each of these 9 has no *other* unmodeled computed effect.
- `NOT_YET_SUPPORTED` — everything else.

WP8 offers only `FLAT_BONUS` qualities to the player; WP22 widens that to `FLAT_BONUS` and
`NO_EFFECT`; WP55 widens it again to include `SELECT_TEXT` (see
`chummer5.engine.qualities.mvp_quality_catalog`). `NOT_YET_SUPPORTED` qualities are excluded from
the offered list rather than silently applied with their bonus dropped. See `spec/worklogs/WP3.md`.

**`Quality.forbidden_names` (WP55)** is a general parse of `<forbidden><oneof><quality>...` —
every SR5 quality's mutual-exclusion list, not just the 9 this WP offers (e.g. SINner's 4-way
mutual exclusion, Natural Immunity vs. the not-yet-offered Weak Immune System). Parsed uniformly
since it costs nothing extra (the shape is a plain list of sibling `<quality>` name tags in every
one of the 31 SR5 qualities that carry a `<forbidden>` block at all — confirmed no other shape
exists), so a future WP offering e.g. Insomnia (Basic)/(Full) or Distinctive Style/Blandness (WP22's
own "deliberately deferred" pair) gets mutual-exclusion enforcement for free rather than needing to
extend this parser too.

**`Quality.unmodeled_effect_note` (WP56)** mirrors Project Overview's "Unmodeled real effects"
table by name — the specific, real SR5 effect a `NO_EFFECT`/`SELECT_TEXT` quality (or, for
Resistance to Pathogens/Toxins, a `NOT_YET_SUPPORTED` one WP23 still grants for free to Dwarf) has
that this engine's scope doesn't compute anything for. This is a hand-kept mirror of that markdown
table, not something read from it at runtime (see `chummer5.engine.derived.unmodeled_effect_notes`'s
own docstring for why runtime code can't read a `.md` file as data) — name-gated
(`_UNMODELED_EFFECT_NOTES`) the same way `_VERIFIED_NO_EFFECT_NAMES`/`_VERIFIED_SELECT_TEXT_NAMES`
already are, and independent of `bonus_support`: a quality's offerability/grant status and whether
it carries a disclosure note are two separate questions.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

# legacy/Chummer/data/qualities.xml, resolved relative to this file (not cwd).
DEFAULT_QUALITIES_PATH = (
    Path(__file__).resolve().parents[3] / "legacy" / "Chummer" / "data" / "qualities.xml"
)

# MVP content scope: only entries carrying this <source> tag are loaded. See "MVP content scope" in
# Implementation Plan.md.
CORE_RULEBOOK_SOURCE = "SR5"

# The two <bonus> child shapes MVP treats as "flat": a bare name + unconditional numeric value, with
# no other fields (no <condition>, no <max>/<min> range changes, no category/select machinery).
_FLAT_SKILL_FIELDS = frozenset({"name", "bonus"})
_FLAT_ATTRIBUTE_FIELDS = frozenset({"name", "val"})

# WP22 Tranche 1: the Indomitable trio's <bonus> is a single bare-numeric leaf tag (e.g.
# <mentallimit>1</mentallimit>, no children, no <condition>) -- flat in the same sense as
# <specificskill>/<specificattribute> above, just untargeted (there's only one Mental/Physical/
# Social Limit per character). Maps to the FlatBonus.target_kind values
# `chummer5.engine.qualities._TARGET_KIND_TO_IMPROVEMENT_TYPE` resolves against the derived-stats
# global sentinel target (see `chummer5.engine.derived._GLOBAL_TARGET`).
#
# WP49 adds `nativelanguagelimit` (Bilingual's own `<bonus>`, verified to be the identical
# bare-numeric-leaf shape -- see spec/rulebooks/learnings.md's WP49 entry): a Plan-stated "already
# offered" claim turned out to be wrong (Bilingual was actually `NOT_YET_SUPPORTED` before this WP),
# so classifying it here is what makes it FLAT_BONUS -- and therefore offerable at all -- for the
# first time.
_GLOBAL_BONUS_TAGS = {
    "mentallimit": "mental_limit",
    "physicallimit": "physical_limit",
    "sociallimit": "social_limit",
    "nativelanguagelimit": "native_language_limit",
    # WP114: Toughness's Damage Resistance die and Photographic Memory's Memory dice.
    "damageresistance": "damage_resistance",
    "memory": "memory",
    # WP115: Dependents' +10/20/30% Lifestyle cost.
    "lifestylecost": "lifestyle_cost",
}

# WP114: `<conditionmonitor>` holding exactly one of these leaves -- High Pain Tolerance's ignored
# wound box and Will to Live's Overflow box, both per rating.
# WP115 adds Low Pain Tolerance's `threshold` (-1: a wound modifier per 2 boxes, not 3).
_CONDITION_MONITOR_TAGS = {
    "thresholdoffset": "cm_threshold_offset",
    "overflow": "cm_overflow",
    "threshold": "cm_threshold",
}

# WP22 Tranche 2: SR5 qualities individually verified (rulebook text + a `grep` of the legacy C#
# for by-name special-casing, both turning up nothing) to have zero mechanical effect this engine's
# scope ever computes -- Gearhead/Juryrigger (vehicle/repair mechanics, no vehicles in MVP), Guts
# (fear-test resistance, no such test), Natural Hardening (Matrix-attack resistance, no Matrix in
# MVP), Low-Light Vision/Thermographic Vision (lighting-condition perception, not modeled),
# Simsense Vertigo (AR/VR/simsense dice-pool penalty, no such test), Unsteady Hands (called-shot
# penalty, no combat system). See spec/rulebooks/learnings.md's WP22 entry for the citations. Every
# one of these has an
# empty `<bonus/>` node in the real data, but this set is name-gated rather than "any empty <bonus/>
# qualifies" -- see the module docstring for why (other empty-`<bonus/>` qualities need different,
# not-yet-built engine support, not a NO_EFFECT verdict).
_VERIFIED_NO_EFFECT_NAMES = frozenset(
    {
        "Gearhead",
        "Guts",
        "Juryrigger",
        "Natural Hardening",
        "Low-Light Vision",
        "Thermographic Vision",
        "Simsense Vertigo",
        "Unsteady Hands",
        # WP114: the positive qualities whose whole effect is in play -- each has a note below.
        "Ambidextrous",
        "Analytical Mind",
        "Astral Chameleon",
        "Blandness",
        "First Impression",
        "Focused Concentration",
        "Human-Looking",
        "Magic Resistance",
        "Quick Healer",
        "Resistance to Pathogens",
        "Resistance to Toxins",
        "Resistance to Pathogens and Toxins",
        # WP115: the negative qualities whose whole effect is in play (Gremlins is rated 1-4 and
        # carries no `<bonus>` at all; its Notoriety comes from `_NOTORIETY_OVERRIDES`).
        "Astral Beacon",
        "Bad Luck",
        "Bad Rep",
        "Combat Paralysis",
        "Distinctive Style",
        "Elf Poser",
        "Gremlins",
        "Insomnia (Basic)",
        "Insomnia (Full)",
        "Ork Poser",
        "Weak Immune System",
    }
)

# WP114: qualities whose pick names one thing from a fixed list (`Quality.choice_kind`) and whose
# effect is otherwise in play -- offered as NO_EFFECT, with the choice carried and validated.
_CHOICE_KIND_NAMES: Mapping[str, str] = {
    "Codeslinger": "matrix_action",
    "Home Ground": "home_ground",
    "Spirit Affinity": "spirit_type",
    # WP115: Scorched names one effect from p. 83's Scorched Physical Side Effects Table; Spirit
    # Bane names a spirit type, like Spirit Affinity (the data's `<selecttext>` lists spirits).
    "Scorched": "scorched_effect",
    "Spirit Bane": "spirit_type",
}

# WP55: 9 SR5 qualities individually verified (rulebook text via `pdftotext -layout`, cross-checked
# against qualities.xml) to have no computed effect this engine's scope reaches beyond the free-text
# detail itself -- see spec/rulebooks/learnings.md's WP55 entry for the full per-quality citation.
# SINner (Criminal)'s own <bonus> also carries a <notoriety>1</notoriety> sibling to <selecttext>.
# Since WP110 that is read separately, into `Quality.notoriety`, so this classifier still doesn't
# need to recognize it structurally.
_VERIFIED_SELECT_TEXT_NAMES = frozenset(
    {
        "SINner (National)",
        "SINner (Corporate Limited)",
        "SINner (Criminal)",
        "SINner (Corporate)",
        "Code of Honor",
        "Codeblock",
        "Social Stress",
        "Natural Immunity (Natural)",
        "Natural Immunity (Synthetic)",
        # WP115: the substance, the allergen, the target group. Addiction (Burnout)'s
        # `<skillcategory>` is parsed alongside the text (see `_classify_bonus`).
        "Addiction (Mild)",
        "Addiction (Moderate)",
        "Addiction (Severe)",
        "Addiction (Burnout)",
        "Allergy (Uncommon, Mild)",
        "Allergy (Uncommon, Moderate)",
        "Allergy (Uncommon, Severe)",
        "Allergy (Uncommon, Extreme)",
        "Allergy (Common, Mild)",
        "Allergy (Common, Moderate)",
        "Allergy (Common, Severe)",
        "Allergy (Common, Extreme)",
        "Prejudiced (Common, Biased)",
        "Prejudiced (Common, Outspoken)",
        "Prejudiced (Common, Radical)",
        "Prejudiced (Specific, Biased)",
        "Prejudiced (Specific, Outspoken)",
        "Prejudiced (Specific, Radical)",
    }
)

# WP115: the three negative families whose rows differ only by severity. Each tuple is the
# severity's in-play effect as p. 78 (Addiction, Allergy Table) and p. 82 (Prejudiced) print it.
_ADDICTION_EFFECTS = {
    "Mild": ("Monthly cravings", "-2", "Its +1 Notoriety is"),
    "Moderate": ("Cravings every two weeks", "-4", "Its +1 Notoriety is"),
    "Severe": (
        "Weekly cravings",
        "-4",
        "Its constant -2 dice on Social Tests and +1 Notoriety are",
    ),
    "Burnout": (
        "Daily cravings",
        "-6",
        "Its constant -3 dice on Social Tests and +1 Notoriety are",
    ),
}
_ALLERGY_EFFECTS = {
    "Mild": ("-2 dice to Physical Tests while symptomatic", 1),
    "Moderate": ("-4 dice to all Physical Tests while symptomatic", 2),
    "Severe": (
        "-4 dice to all tests while symptomatic, and 1 box of unresisted Physical damage per "
        "minute of exposure",
        3,
    ),
    "Extreme": (
        "anaphylactic shock: -6 dice to everything, and 1 box of unresisted Physical damage per "
        "30 seconds of exposure",
        4,
    ),
}
_PREJUDICE_LEVELS = {"Biased": 1, "Outspoken": 2, "Radical": 3}

_SEVERITY_NOTES: Mapping[str, str] = {
    **{
        f"Addiction ({severity})": (
            f"{cravings}; a failed Withdrawal Test gives {penalty} dice to Mental- or "
            f"Physical-based tests until the craving is satisfied (pp. 77-78, 414) -- no craving "
            f"or Withdrawal Test tracking exists. ({applied} applied.)"
        )
        for severity, (cravings, penalty, applied) in _ADDICTION_EFFECTS.items()
    },
    **{
        f"Allergy ({prevalence}, {severity})": (
            f"On contact with the allergen, {effect}; and {dice} fewer "
            f"{'die' if dice == 1 else 'dice'} on Resistance Tests against attacks using it "
            f"(p. 78) -- no exposure, symptom or damage resolution exists. The allergen is "
            f"recorded."
        )
        for prevalence in ("Uncommon", "Common")
        for severity, (effect, dice) in _ALLERGY_EFFECTS.items()
    },
    **{
        f"Prejudiced ({prevalence}, {degree})": (
            f"-{2 * level} dice on all Social Tests when dealing with the target group, and "
            f"+{2 * level} dice for them in negotiations with the character (p. 82) -- no Social "
            f"test resolution exists. The target group is recorded."
        )
        for prevalence in ("Common", "Specific")
        for degree, level in _PREJUDICE_LEVELS.items()
    },
}

# WP56: Project Overview's "Unmodeled real effects" table, transcribed here as the runtime source
# `_parse_quality` reads (the markdown table itself is a hand-kept mirror, not read at runtime --
# see module docstring). Every quality named here already has a WP22/WP23/WP55-verified citation for
# exactly this unmodeled effect; this dict does not itself decide what's inert vs. not, it only
# carries the player-facing text for qualities `_classify_bonus`/`resolve_metatype_qualities`
# already treat as inert-except-for-this-one-real-effect.
_UNMODELED_EFFECT_NOTES: Mapping[str, str] = {
    "Gearhead": (
        "Vehicle/drone Speed/Handling/dice-pool bonus during vehicle or chase combat (p. 74) -- "
        "no vehicle/combat subsystem exists."
    ),
    "Guts": (
        "+2 dice pool resisting fear/intimidation tests, including magically induced (p. 74) -- "
        "no test-resolution system exists."
    ),
    "Juryrigger": (
        "+2 dice pool for Mechanical Tests when juryrigging temporary repairs (p. 75) -- no "
        "repair/test subsystem exists."
    ),
    "Natural Hardening": (
        "1 point of natural biofeedback filtering vs. Matrix biofeedback damage (p. 76) -- no "
        "Matrix rules exist."
    ),
    "Low-Light Vision": (
        "Negates low-light vision penalties on visual Perception (p. 444/446) -- no "
        "lighting-condition Perception system exists."
    ),
    "Thermographic Vision": (
        "Negates darkness/heat-pattern vision penalties (p. 446) -- no lighting-condition "
        "Perception system exists."
    ),
    "Simsense Vertigo": (
        "-2 dice pool to all AR/VR/simsense tests (p. 83) -- no Matrix/AR test system exists."
    ),
    "Unsteady Hands": (
        "-2 dice pool for Agility-based tests, re-triggerable via an Agility+Body(4) test after a "
        "stressful encounter (p. 87) -- no in-play test-resolution system exists."
    ),
    "Resistance to Pathogens/Toxins": (
        "The Dwarf racial trait: +2 dice on Resistance Tests against pathogens and toxins "
        "(Metatype Attribute Table, p. 66; the quality itself, p. 79) -- no toxin/pathogen "
        "resistance subsystem exists."
    ),
    "SINner (National)": (
        "Background-check/arrest consequences described across a full page (p. 84) -- no "
        "background-check/arrest-risk subsystem exists."
    ),
    "SINner (Corporate Limited)": (
        "Background-check/arrest consequences described across a full page (p. 84) -- no "
        "background-check/arrest-risk subsystem exists."
    ),
    "SINner (Criminal)": (
        "Background-check/arrest consequences (p. 84-85) -- no background-check/arrest-risk "
        "subsystem exists. (Its Notoriety point is applied, since WP110.)"
    ),
    "SINner (Corporate)": (
        "Background-check/arrest consequences (p. 85), the single largest-magnitude Negative "
        "quality in the SR5 core catalog -- no background-check/arrest-risk subsystem exists."
    ),
    "Code of Honor": (
        "In-play Karma-loss/Public-Awareness consequences for violating the code (p. 79) -- no "
        "in-play consequence-tracking subsystem exists."
    ),
    "Codeblock": (
        "-2 dice pool modifier on the chosen Matrix action (p. 80) -- no Matrix rules exist."
    ),
    "Social Stress": (
        "Reduces the number of 1s required to glitch a Leadership/Etiquette test by 1 (p. 85) -- "
        "no test-resolution/glitch system exists."
    ),
    "Natural Immunity (Natural)": (
        "Full immunity to one chosen disease or toxin (p. 76) -- no toxin/pathogen resistance "
        "subsystem exists."
    ),
    "Natural Immunity (Synthetic)": (
        "Full immunity to one chosen disease or toxin, at the higher (synthetic) tier (p. 76) -- "
        "no toxin/pathogen resistance subsystem exists."
    ),
    # WP114: the positive qualities offered with their in-play effect registered.
    "Ambidextrous": (
        "No -2 off-hand penalty on actions done solely with the off hand, such as firing a gun "
        "(p. 71) -- no attack or off-hand action resolution exists."
    ),
    "Analytical Mind": (
        "+2 dice to Logic Tests involving pattern recognition, evidence analysis, clue hunting "
        "or puzzles, and half the time to solve a problem (p. 72) -- no test resolution exists."
    ),
    "Astral Chameleon": (
        "Astral signatures last half as long and Assensing Tests against them take -2 dice (p. "
        "72) -- no astral-signature or Assensing resolution exists."
    ),
    "Blandness": (
        "+1 to the threshold to recall details about the character, and -2 dice to shadow or "
        "locate them by appearance in a crowd (p. 72); lost while they carry distinguishing "
        "features -- no Memory-test or search resolution exists. (Its -1 Notoriety is applied.)"
    ),
    "First Impression": (
        "+2 dice to relevant Social Tests at a first meeting only (p. 74) -- no Social test "
        "resolution exists. (Its -1 Notoriety is applied.)"
    ),
    "Focused Concentration": (
        "Sustains one spell of Force up to the rating without the -2 per sustained spell "
        "penalty (p. 74) -- no spell-sustaining or casting resolution exists."
    ),
    "Human-Looking": (
        "Passes for human in most Social-test circumstances (p. 75) -- no Social test "
        "resolution exists."
    ),
    "Magic Resistance": (
        "+1 die per rating to Spell Resistance Tests, always on, and voluntary-subject spells "
        "always fail on the character (p. 76) -- no spell resolution exists."
    ),
    "Quick Healer": (
        "+2 dice to all Healing Tests made on, for or by the character, including magical "
        "healing (p. 77) -- no healing resolution exists."
    ),
    "Resistance to Pathogens": (
        "+1 die to Resistance Tests against pathogens (p. 77) -- no toxin/pathogen resistance "
        "subsystem exists."
    ),
    "Resistance to Toxins": (
        "+1 die to Resistance Tests against toxins (p. 77) -- no toxin/pathogen resistance "
        "subsystem exists."
    ),
    "Resistance to Pathogens and Toxins": (
        "+1 die to Resistance Tests against both pathogens and toxins (p. 77) -- no "
        "toxin/pathogen resistance subsystem exists."
    ),
    "Codeslinger": (
        "+2 dice on the chosen Matrix action (p. 72) -- no Matrix test resolution exists. The "
        "chosen action is recorded."
    ),
    "Home Ground": (
        "The chosen home-turf bonus (p. 74) -- ignoring background count, local Street Cred, "
        "Matrix, Evasion or gang-Knowledge dice there -- none of those tests or locations exist "
        "here. The chosen bonus is recorded."
    ),
    "Spirit Affinity": (
        "One extra service from each spirit of the chosen type, and +1 die to bind it (p. 77) "
        "-- bound spirits' services are the player's own entry here and no Binding Test exists. "
        "The chosen type is recorded."
    ),
    # WP115: the negative qualities offered with their in-play effect registered.
    **_SEVERITY_NOTES,
    "Astral Beacon": (
        "Its astral signature is highly visible and lasts twice as long, and Assensing Tests "
        "against it get -1 to the threshold (p. 78) -- no astral-signature or Assensing "
        "resolution exists."
    ),
    "Bad Luck": (
        "Whenever Edge is spent, a 1 on 1D6 spends the point for the opposite effect, at most once "
        "per session (p. 79) -- no Edge-spend resolution exists. (Its +1 Notoriety is applied.)"
    ),
    "Bad Rep": (
        "How NPCs react to the bad reputation, removable only by resolving its source and buying "
        "the quality off (p. 79) -- no NPC-reaction or buy-off tracking exists. (Its Notoriety of "
        "3 is applied.)"
    ),
    "Combat Paralysis": (
        "The first Initiative Score of a combat is halved (rounded up), -3 dice on Surprise "
        "Tests, and +1 threshold on Composure Tests under fire (p. 80) -- no combat, Surprise or "
        "Composure resolution exists. (Its +1 Notoriety is applied.)"
    ),
    "Dependent (Nuisance)": (
        "Learning or improving a skill takes 50% longer, and so does any long-term project (p. "
        "80) -- no training-time tracking exists. (Its +10% Lifestyle cost is applied.)"
    ),
    "Dependent (Inconvenience)": (
        "Learning or improving a skill takes 50% longer, and so does any long-term project (p. "
        "80) -- no training-time tracking exists. (Its +20% Lifestyle cost is applied.)"
    ),
    "Dependent (Demanding)": (
        "Learning or improving a skill takes 50% longer, and so does any long-term project (p. "
        "80) -- no training-time tracking exists. (Its +30% Lifestyle cost is applied.)"
    ),
    "Distinctive Style": (
        "+2 dice for anyone trying to identify, trace or locate the character, and -1 to the "
        "threshold of NPC Memory Tests about them (p. 80) -- no search or NPC Memory resolution "
        "exists."
    ),
    "Elf Poser": (
        "Passes as an elf; elves who discover the secret react with contempt or hostility (p. "
        "81) -- no Social-modifier resolution exists. (Its +1 Notoriety is applied.)"
    ),
    "Gremlins": (
        "One fewer 1 is needed for a glitch per level when using a moderately sophisticated "
        "device (p. 81) -- no test or glitch resolution exists. (Its +1 Notoriety is applied.)"
    ),
    "Insomnia (Basic)": (
        "An Intuition + Willpower (4) Test before each Stun recovery roll; failure doubles the "
        "recovery time and delays Edge refresh by up to 24 hours (pp. 81-82) -- no healing or "
        "Edge-refresh resolution exists."
    ),
    "Insomnia (Full)": (
        "An Intuition + Willpower (4) Test before each Stun recovery roll; failure negates that "
        "recovery attempt and delays Edge refresh by 24 hours (p. 82) -- no healing or "
        "Edge-refresh resolution exists."
    ),
    "Loss of Confidence": (
        "Edge can't be used on tests with the chosen skill (p. 82) -- no Edge-spend resolution "
        "exists. (Its -2 dice and the lost specialization are applied.)"
    ),
    "Ork Poser": (
        "Passes as an ork; orks who discover the secret may turn hostile, and prejudiced humans "
        "or elves see a race traitor (p. 82) -- no Social-modifier resolution exists. (Its +1 "
        "Notoriety is applied.)"
    ),
    "Scorched": (
        "The chosen side effect, for 6 hours (24 on a glitch) after a failed Body + Willpower (4) "
        "Test on entering VR or slotting a BTL, plus a Willpower (3) Test to face Black or "
        "Psychotropic IC and -2 dice resisting its damage (p. 83) -- no VR, BTL or IC resolution "
        "exists. The chosen effect is recorded. (Its +1 Notoriety is applied.)"
    ),
    "Spirit Bane": (
        "Spirits of the chosen type resent the character: -2 dice to summon or bind them, +2 "
        "dice for them to resist the character's banishing, and they single the character out in "
        "combat (p. 85) -- no summoning, binding or spirit-combat resolution exists. The chosen "
        "type is recorded. (Its +1 Notoriety is applied.)"
    ),
    "Weak Immune System": (
        "+2 to the Power of any disease the character resists (p. 87) -- no toxin/pathogen "
        "resistance subsystem exists. (Its +1 Notoriety is applied.)"
    ),
}


# WP108: where the rulebook's own gate is broader than the data's, the rulebook wins. Each entry
# adds conditions to the named quality's first `<required><oneof>` group. See
# spec/rulebooks/learnings/phase-x.md's WP108 entry for the citation behind each.
_RULEBOOK_REQUIRED_ADDITIONS: Mapping[str, tuple[tuple[str, str], ...]] = {
    # p. 77: "Available only to magic users" -- the data lists only spellcasting talents and so
    # leaves out Adept, who is as much a magic user as anyone on the data's list.
    "Spirit Affinity": (("quality", "Adept"),),
}

# WP114: forbidden-list additions, same rulebook-wins posture. The three purchasable Resistance rows
# may not be bought on top of the Dwarf's racial "+2 dice vs. pathogen/toxin" (the metatype-granted
# `Resistance to Pathogens/Toxins` row) -- the same "don't re-buy a racial trait" rule WP23 applies
# to Low-Light Vision, extended to the variants the grant already covers.
_RULEBOOK_FORBIDDEN_ADDITIONS: Mapping[str, tuple[tuple[str, str], ...]] = {
    "Resistance to Pathogens": (("quality", "Resistance to Pathogens/Toxins"),),
    "Resistance to Toxins": (("quality", "Resistance to Pathogens/Toxins"),),
    "Resistance to Pathogens and Toxins": (("quality", "Resistance to Pathogens/Toxins"),),
    # WP115: p. 87, Weak Immune System "cannot be combined with [...] Resistance to
    # Pathogens/Toxins" -- the printed name is exactly the Dwarf's racial row, which the data's
    # own forbidden list leaves out.
    "Weak Immune System": (("quality", "Resistance to Pathogens/Toxins"),),
}


# WP110: Gremlins is on p. 368's list of Notoriety-raising negative qualities, but its data row has
# no `<bonus>` at all -- the one gap in the data's otherwise complete `<notoriety>` coverage (see
# spec/plan/phase-x-rulebook-completeness.md's Finding 3). Name-gated, rulebook wins.
_NOTORIETY_OVERRIDES: Mapping[str, int] = {"Gremlins": 1}


def _parse_notoriety(name: str, bonus_elem: ET.Element | None) -> int:
    """A quality's Notoriety shift (WP110): its `<bonus><notoriety>` value, or an override."""
    if name in _NOTORIETY_OVERRIDES:
        return _NOTORIETY_OVERRIDES[name]
    if bonus_elem is None:
        return 0
    return sum(int(n.text) for n in bonus_elem.findall("notoriety") if n.text)


class BonusSupport(Enum):
    """Whether/how a quality's `<bonus>` node was parsed. See module docstring for the 4 values."""

    FLAT_BONUS = "flat_bonus"
    NO_EFFECT = "no_effect"
    SELECT_TEXT = "select_text"
    NOT_YET_SUPPORTED = "not_yet_supported"


@dataclass(frozen=True)
class FlatBonus:
    """One unconditional, flat point bonus to a skill, attribute, or (WP22) Inherent Limit.

    `target_name` is the specifically-named skill/attribute for those two kinds; for the 3
    limit kinds (`"mental_limit"`/`"physical_limit"`/`"social_limit"`) it's `""` — there's only one
    of each per character, so there's nothing to name (mirrors `chummer5.engine.derived`'s own
    `_GLOBAL_TARGET` sentinel for the same reason).
    """

    # "skill", "attribute", "mental_limit", "physical_limit", "social_limit", or (WP112)
    # "attribute_maximum" -- whose empty `target_name` means "the attribute the pick chose"
    target_kind: str
    target_name: str
    value: int


# WP115: bonuses the rulebook prints but the data lacks, rulebook wins. p. 78: a Severe addict
# "suffers a -2 dice pool modifier to all Social Tests, whether he is in withdrawal or not" -- the
# data gives Burnout its -3 as a Social Active `<skillcategory>` and Severe nothing.
_RULEBOOK_BONUS_ADDITIONS: Mapping[str, tuple[FlatBonus, ...]] = {
    "Addiction (Severe)": (
        FlatBonus(target_kind="skill_category_pool", target_name="Social Active", value=-2),
    ),
}


@dataclass(frozen=True)
class Requirement:
    """One child group of a `<required>` or `<forbidden>` block (WP108).

    `mode` is `"oneof"` or `"allof"`. Each condition is a `(kind, value)` pair taken verbatim from
    the XML (`("metatype", "Elf")`, `("quality", "Magician")`, `("magenabled", "")`, ...). This
    module only records them; `chummer5.engine.qualities.requirement_failure` decides what each kind
    means for a character, and which kinds this project can never satisfy.
    """

    mode: str
    conditions: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class Quality:
    id: str
    name: str
    category: str  # "Positive" or "Negative"
    karma: int  # negative for Negative-category qualities, per the source data's sign convention
    # raw string: a count, "True"/"False", or a formula like "{arm} - 1" -- read it through
    # `max_rating`/`repeatable` (WP107), not directly
    limit: str | None
    source: str
    page: int
    bonus_support: BonusSupport
    flat_bonuses: tuple[FlatBonus, ...]  # populated only when bonus_support is FLAT_BONUS
    raw_bonus: str | None  # serialized <bonus> element, kept for future parser work; None if absent
    # WP55: other quality *names* this one may never be taken alongside (parsed from
    # <forbidden><oneof><quality>...) -- () if the quality carries no <forbidden> block at all. See
    # module docstring for why this is parsed generally, not just for this WP's own 9 qualities.
    forbidden_names: tuple[str, ...] = ()
    # WP56: this quality's real, unmodeled SR5 effect (Project Overview's "Unmodeled real effects"
    # table, mirrored via _UNMODELED_EFFECT_NOTES), or None for a quality with no such gap (every
    # FLAT_BONUS quality, and every NOT_YET_SUPPORTED one not individually verified inert-but-for-
    # one-real-effect the way Resistance to Pathogens/Toxins is).
    unmodeled_effect_note: str | None = None
    # WP107: sibling quality names whose levels count against this one's `max_rating` (parsed from
    # `<includeinlimit>`). In the SR5 slice only the Indomitable trio carries one: p. 74 caps it at
    # 3 levels *in total*, and the data splits it into three rows that each name the other two.
    include_in_limit: tuple[str, ...] = ()
    # WP108: the parsed `<required>` / `<forbidden>` blocks. A quality is available only when every
    # `required` group is met, and unavailable when any `forbidden` group is. `forbidden_names`
    # above stays as the quality-name-only view WP55 introduced.
    required: tuple[Requirement, ...] = ()
    forbidden: tuple[Requirement, ...] = ()
    # WP110: this quality's Notoriety shift at creation (p. 368) -- +1 per listed negative, -1 per
    # listed positive, 3 for Bad Rep. Parsed independently of `bonus_support`: the `<notoriety>`
    # child still counts as unsupported when classifying, so a quality whose only other content is
    # unmodeled stays unoffered until its own WP registers the rest.
    notoriety: int = 0
    # WP112: the kind of player choice a pick must carry (`QualityPick.choice`), or None. Only
    # "attribute" so far (Exceptional Attribute); later Phase X WPs add skills, Matrix actions, ...
    choice_kind: str | None = None
    # WP112: attributes a `choice_kind == "attribute"` pick may not name (`<excludeattribute>`).
    choice_excludes: tuple[str, ...] = ()
    # WP115: the rating a `choice_kind == "skill"` pick's skill must already have
    # (`<selectskill minimumrating>`) -- Loss of Confidence's 4. 0 means no minimum.
    choice_minimum_rating: int = 0

    @property
    def max_rating(self) -> int:
        """The highest level this quality can be bought at (WP107): `<limit>`'s integer for a rated
        quality (Focused Concentration 6, Gremlins 4, ...), 1 for everything else.

        `{arm} - 1` (Ambidextrous, the one formula-valued `<limit>` in the SR5 slice) reads as 1:
        no core metatype has more than two arms, so the formula always evaluates to 1 there.
        """
        if self.limit is not None and self.limit.isdigit():
            return int(self.limit)
        return 1

    @property
    def repeatable(self) -> bool:
        """`<limit>False</limit>` (WP107): any number of instances, each with its own detail --
        Addiction to several substances, Code of Honor towards several groups."""
        return self.limit == "False"


def _is_flat_skill_bonus(elem: ET.Element) -> bool:
    return {child.tag for child in elem} == _FLAT_SKILL_FIELDS


def _is_flat_attribute_bonus(elem: ET.Element) -> bool:
    return {child.tag for child in elem} == _FLAT_ATTRIBUTE_FIELDS


def _classify_bonus(
    name: str,
    bonus_elem: ET.Element | None,
) -> tuple[BonusSupport, tuple[FlatBonus, ...]]:
    """Classify a `<bonus>` node, extracting flat bonuses when every child is a flat shape.

    A single unsupported child (or an empty/absent `<bonus>`) marks the whole quality
    `NOT_YET_SUPPORTED` — MVP never partially applies a quality's effects — unless `name` is
    one of WP22's individually-verified `_VERIFIED_NO_EFFECT_NAMES`, in which case it's
    `NO_EFFECT` instead.
    """
    if name in _VERIFIED_NO_EFFECT_NAMES or name in _CHOICE_KIND_NAMES:
        return BonusSupport.NO_EFFECT, ()
    # WP115: a SELECT_TEXT quality's other children are parsed like anyone's -- Addiction
    # (Burnout)'s Social Active penalty sits beside its `<selecttext>`.
    select_text = name in _VERIFIED_SELECT_TEXT_NAMES
    if not select_text and (bonus_elem is None or len(bonus_elem) == 0):
        return BonusSupport.NOT_YET_SUPPORTED, ()

    flat_bonuses = []
    for child in bonus_elem if bonus_elem is not None else ():
        if select_text and child.tag == "selecttext":
            continue
        if child.tag == "notoriety":
            # WP110/WP112: read separately into `Quality.notoriety`. Recognised here only
            # *alongside* another supported child (the check after this loop), so a quality whose
            # whole `<bonus>` is a Notoriety shift (Bad Luck, Blandness, ...) stays unoffered until
            # its own WP registers the rest of its effect.
            continue
        if child.tag == "specificattribute" and {c.tag for c in child} == {"name", "max"}:
            # WP112: Lucky's "+1 to Edge's maximum" -- `<max>` raises the attribute's natural and
            # augmented maximum, not its value.
            flat_bonuses.append(
                FlatBonus(
                    target_kind="attribute_maximum",
                    target_name=child.findtext("name", ""),
                    value=int(child.findtext("max", "0")),
                )
            )
            continue
        if child.tag == "selectattributes" and _is_select_attribute_maximum(child):
            # WP112: Exceptional Attribute's "+1 to one attribute's maximum, player's choice". An
            # empty `target_name` means "the pick's `choice`"; see `Quality.choice_kind`.
            flat_bonuses.append(
                FlatBonus(
                    target_kind="attribute_maximum",
                    target_name="",
                    value=int(child.findtext("selectattribute/max", "0")),
                )
            )
            continue
        if child.tag == "specificskill" and _is_flat_skill_bonus(child):
            flat_bonuses.append(
                FlatBonus(
                    target_kind="skill",
                    target_name=child.findtext("name", ""),
                    value=int(child.findtext("bonus", "0")),
                )
            )
        elif child.tag == "specificattribute" and _is_flat_attribute_bonus(child):
            flat_bonuses.append(
                FlatBonus(
                    target_kind="attribute",
                    target_name=child.findtext("name", ""),
                    value=int(child.findtext("val", "0")),
                )
            )
        elif (
            child.tag == "conditionmonitor"
            and len(child) == 1
            and child[0].tag in _CONDITION_MONITOR_TAGS
            and len(child[0]) == 0
        ):
            flat_bonuses.append(
                FlatBonus(
                    target_kind=_CONDITION_MONITOR_TAGS[child[0].tag],
                    target_name="",
                    value=int(child[0].text or "0"),
                )
            )
        elif child.tag in _GLOBAL_BONUS_TAGS and len(child) == 0 and child.text is not None:
            flat_bonuses.append(
                FlatBonus(
                    target_kind=_GLOBAL_BONUS_TAGS[child.tag],
                    target_name="",
                    value=int(child.text),
                )
            )
        elif child.tag == "skillcategory" and _is_flat_skill_bonus(child):
            # WP115: a dice-pool modifier to every skill of one category, not a rating bonus.
            flat_bonuses.append(
                FlatBonus(
                    target_kind="skill_category_pool",
                    target_name=child.findtext("name", ""),
                    value=int(child.findtext("bonus", "0")),
                )
            )
        elif child.tag == "selectskill" and _is_select_skill_pool(child):
            # WP115: Loss of Confidence -- a dice-pool modifier on the chosen skill, and that
            # skill's specialization switched off. Empty target: "the pick's `choice`".
            flat_bonuses.append(
                FlatBonus(
                    target_kind="skill_pool",
                    target_name="",
                    value=int(child.findtext("val", "0")),
                )
            )
            if child.find("disablespecializationeffects") is not None:
                flat_bonuses.append(
                    FlatBonus(target_kind="specialization_disabled", target_name="", value=1)
                )
        else:
            return BonusSupport.NOT_YET_SUPPORTED, ()
    flat_bonuses.extend(_RULEBOOK_BONUS_ADDITIONS.get(name, ()))
    if select_text:
        return BonusSupport.SELECT_TEXT, tuple(flat_bonuses)
    if not flat_bonuses:
        return BonusSupport.NOT_YET_SUPPORTED, ()
    return BonusSupport.FLAT_BONUS, tuple(flat_bonuses)


def _is_select_skill_pool(elem: ET.Element) -> bool:
    """`<selectskill>` holding one `<val>` and optionally `<disablespecializationeffects/>` --
    a pool modifier on a chosen skill. Aptitude's `<max>` shape is not this."""
    tags = [c.tag for c in elem]
    return tags.count("val") == 1 and set(tags) <= {"val", "disablespecializationeffects"}


def _is_select_attribute_maximum(elem: ET.Element) -> bool:
    """`<selectattributes><selectattribute>` holding only `<excludeattribute>`s and one `<max>`."""
    choices = elem.findall("selectattribute")
    if len(choices) != 1 or len(elem) != 1:
        return False
    tags = [c.tag for c in choices[0]]
    return tags.count("max") == 1 and set(tags) <= {"max", "excludeattribute"}


def _choice_kind(name: str, flat_bonuses: tuple[FlatBonus, ...]) -> str | None:
    """WP112: which kind of thing a pick of this quality must name in `QualityPick.choice`."""
    if name in _CHOICE_KIND_NAMES:
        return _CHOICE_KIND_NAMES[name]
    if any(b.target_kind == "attribute_maximum" and not b.target_name for b in flat_bonuses):
        return "attribute"
    if any(b.target_kind == "skill_pool" and not b.target_name for b in flat_bonuses):
        return "skill"
    return None


def _parse_forbidden_names(elem: ET.Element) -> tuple[str, ...]:
    """Parse `<forbidden><oneof><quality>...` -- the only shape found among all SR5 qualities'
    `<forbidden>` blocks (verified: every one is a single `<oneof>` wrapping only `<quality>`
    children). Returns `()` if the quality carries no `<forbidden>` block at all.
    """
    forbidden_elem = elem.find("forbidden")
    if forbidden_elem is None:
        return ()
    oneof_elem = forbidden_elem.find("oneof")
    if oneof_elem is None:
        return ()
    return tuple(q.text for q in oneof_elem.findall("quality") if q.text)


def _parse_requirements(elem: ET.Element | None) -> tuple[Requirement, ...]:
    """Parse every `<oneof>` / `<allof>` child of a `<required>` or `<forbidden>` block."""
    if elem is None:
        return ()
    return tuple(
        Requirement(
            mode=group.tag,
            conditions=tuple((c.tag, (c.text or "").strip()) for c in group),
        )
        for group in elem
        if group.tag in ("oneof", "allof")
    )


def _with_rulebook_additions(
    name: str, required: tuple[Requirement, ...]
) -> tuple[Requirement, ...]:
    additions = _RULEBOOK_REQUIRED_ADDITIONS.get(name)
    if not additions:
        return required
    first, *rest = required
    widened = Requirement(mode=first.mode, conditions=(*first.conditions, *additions))
    return (widened, *rest)


def _with_forbidden_additions(
    name: str, forbidden: tuple[Requirement, ...]
) -> tuple[Requirement, ...]:
    additions = _RULEBOOK_FORBIDDEN_ADDITIONS.get(name)
    if not additions:
        return forbidden
    return (*forbidden, Requirement(mode="oneof", conditions=additions))


def _select_skill_minimum_rating(elem: ET.Element) -> int:
    """WP115: `<selectskill minimumrating="N">`'s N, or 0."""
    select_skill = elem.find("bonus/selectskill")
    if select_skill is None:
        return 0
    return int(select_skill.get("minimumrating", "0"))


def _parse_quality(elem: ET.Element) -> Quality:
    bonus_elem = elem.find("bonus")
    support, flat_bonuses = _classify_bonus(elem.findtext("name", ""), bonus_elem)
    raw_bonus = (
        ET.tostring(bonus_elem, encoding="unicode").strip() if bonus_elem is not None else None
    )
    return Quality(
        id=elem.findtext("id", ""),
        name=elem.findtext("name", ""),
        category=elem.findtext("category", ""),
        karma=int(elem.findtext("karma", "0")),
        limit=elem.findtext("limit"),
        source=elem.findtext("source", ""),
        page=int(elem.findtext("page", "0")),
        bonus_support=support,
        flat_bonuses=flat_bonuses,
        raw_bonus=raw_bonus,
        forbidden_names=_parse_forbidden_names(elem),
        required=_with_rulebook_additions(
            elem.findtext("name", ""), _parse_requirements(elem.find("required"))
        ),
        forbidden=_with_forbidden_additions(
            elem.findtext("name", ""), _parse_requirements(elem.find("forbidden"))
        ),
        notoriety=_parse_notoriety(elem.findtext("name", ""), bonus_elem),
        choice_kind=_choice_kind(elem.findtext("name", ""), flat_bonuses),
        choice_excludes=tuple(
            e.text
            for e in elem.findall("bonus/selectattributes/selectattribute/excludeattribute")
            if e.text
        ),
        choice_minimum_rating=_select_skill_minimum_rating(elem),
        include_in_limit=tuple(
            n.text for n in elem.findall("includeinlimit/name") if n.text is not None
        ),
        unmodeled_effect_note=_UNMODELED_EFFECT_NOTES.get(elem.findtext("name", "")),
    )


def load_qualities(xml_path: Path = DEFAULT_QUALITIES_PATH) -> tuple[Quality, ...]:
    """Parse `qualities.xml`, restricted to `source == "SR5"` entries (96 of 803)."""
    root = ET.parse(xml_path).getroot()
    qualities_elem = root.find("qualities")
    if qualities_elem is None:
        return ()
    return tuple(
        _parse_quality(q)
        for q in qualities_elem.findall("quality")
        if q.findtext("source") == CORE_RULEBOOK_SOURCE
    )


def count_by_support(qualities: Iterable[Quality]) -> Mapping[BonusSupport, int]:
    """Count qualities per `BonusSupport` value, so the supported/unsupported split is visible."""
    counts = Counter(q.bonus_support for q in qualities)
    return {support: counts[support] for support in BonusSupport}
