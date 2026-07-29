"""Hand-authored synthetic whole-character fixtures (Phase S / WP72+).

Each fixture is a `SyntheticCharacter` (see `synthetic.py`) whose `expected` values are hand-derived
from the rulebook / `priorities.xml` / legacy C#, with an inline `citations` entry for every one.
WP72 lands the substrate plus the single reference fixture below; WP73-76 append their
interaction-covering fixtures here (cyberware/bioware, magician+cyberware, leftover-Karma,
Sum-to-Ten) as they extend the harness.

The fixtures double as **playable Shadowrun characters** — legal, fully-spent priority builds with
a name and concept, not degenerate test artifacts — so a reader can pick one up as a real runner.
More than that, the set is authored as **one coherent runner team** (see `phase-s-test-fixtures.md`
§5 for the full roster): WP72's Cheshire is the Infiltrator; WP73-76 fill the Street Samurai, Combat
Mage, Shaman Face, and Decker roles — each archetype chosen to fit the mechanic its WP already has
to test, and to cover a gap the others leave (the Decker covers the Matrix, which Cheshire's
Simsense Vertigo keeps her out of; the Face covers social, which her CHA 2 doesn't).
That deliberately costs nothing in test rigour: a *fully*-spent budget exercises the engine's
validators harder than a half-empty one, and a coherent character naturally touches more interaction
paths (a skill boosted by a quality, a group rating capped by another quality's bonus, a Limit
raised by a third). Only the mechanically-derived numbers are asserted; the loadout, contacts, and
lifestyle in a fixture's prose are character concept (this engine models gear only shallowly — see
the Project Overview), flagged as flavor, not engine-checked.

All figures below are cross-checked as follows:
- Priority budgets: `legacy/Chummer/data/priorities.xml` (Attributes A = 24 points; Skills B = 36
  skill + 5 group points; Heritage C / Human = 5 special-attribute points; Resources D = 50000¥).
- Human attribute ranges: `metatypes.xml` — every primary attribute 1-6, EDG 2-7.
- Derived-stat formulas: `spec/rulebooks/learnings/phase-d.md` (WP10), mirroring
  `chummer5.engine.derived`'s own docstring citations to `Character.cs`'s
  `LimitPhysical`/`LimitMental`/`LimitSocial`/`PhysicalCM`/`StunCM`/`InitiativeValue`.
- Quality bonuses (all `FLAT_BONUS`, `qualities.xml`): Catlike +2 Sneaking (7¥k); Natural Athlete +2
  Gymnastics/+2 Running (7); Indomitable (Physical) +1 Physical Limit (8). Negatives are karma-only:
  SINner (Criminal) -10 (needs a free-text SIN detail, WP55) and Simsense Vertigo -5.
- Cyberware/bioware costs & Essence (WP73, `cyberware.xml`/`bioware.xml` `<cost>`/`<ess>`, Standard
  grade): resolved through the real `chummer5.engine.cyberware`/`chummer5.engine.bioware` selection
  functions, which share one nuyen budget and one Essence pool (cyberware resolved first, bioware
  second — see `chummer5.engine.bioware`'s docstring). The one modeled cyberware bonus is the
  Cyberlimb +1 Physical CM; the one modeled bioware bonus is Enhanced Articulation's +1 Physical
  Limit / +1 Escape Artist. Every other implant's `<bonus>` is `NO_EFFECT`/`NOT_YET_SUPPORTED`, so
  only its Essence/nuyen cost is engine content (Project Overview's "Unmodeled real effects" posture
  for augmentation).
- Karma ledger: core rulebook p.64 "start with 25 Karma" (`STARTING_KARMA`); qualities net signed.
"""

from __future__ import annotations

from decimal import Decimal

from tests.fixtures.synthetic import SyntheticCharacter

# ==================================================================================================
# WP72 reference fixture — Renata "Cheshire" Vance, human infiltrator / cat burglar.
# ==================================================================================================
#
# CONCEPT (flavor; not engine-modeled except where an assertion below says so)
# ------------------------------------------------------------------------------------------------
# Team role: the Infiltrator (see phase-s-test-fixtures.md §5) — she opens the door the rest of the
# team walks through. Deliberately weak where teammates are strong: CHA 2 (the Shaman Face handles
# talking) and no real Matrix game (the Decker handles that; she has Simsense Vertigo besides).
#
# A mundane human second-story artist: rooftops, ductwork, and locked vaults, in and out before
# anyone knows she was there. Preternaturally graceful (Catlike), a natural climber and sprinter
# (Natural Athlete), and just plain hard to put down when a job goes sideways — she trusts her luck
# more than her gun (Edge maxed at 7, "nine lives"). She keeps a criminal SIN she can't shake (a
# Lone Star B&E jacket) and can't stand hot-sim, so she stays a meat-world operator who never jacks
# in if she can help it.
#
#   Handle: Cheshire      Metatype: Human (mundane)      Gender: she/her
#   Loadout (Resources D, 50,000¥ — described, not engine-modeled): a Low lifestyle safehouse; a
#     silenced holdout pistol; a lined coat (light armor); an autopicker + sequencer for locks; a
#     grapple gun and catsuit for the climb. Contacts: a Fixer (Connection 3 / Loyalty 2) and a
#     Talismonger-turned-fence (Connection 2 / Loyalty 3).
#
# BUILD (all engine-modeled and asserted)
# ------------------------------------------------------------------------------------------------
# Priorities (Talent forced to E, mundane): Attributes A, Skills B, Heritage C, Resources D.
#
# Attributes — Attributes A = 24 primary points, ALL spent; EDG from Heritage C/Human's 5 special
#   points, ALL spent. At most one Mental/Physical attribute at its natural max (AGI 6) — legal per
#   Step Two's "only one attribute at natural maximum" rule (Edge is exempt).
#     BOD +3=4, AGI +5=6, REA +4=5, STR +2=3, CHA +1=2, INT +4=5, LOG +2=3, WIL +3=4   (sum 24)
#     EDG +5=7 (from 5 special points)
#
# Skills — Skills B = 36 skill + 5 group points, ALL spent.
#   Athletics group = 5 -> Gymnastics/Running/Swimming base 5 (Natural Athlete adds +2 to Gymnastics
#     & Running -> both capped at the chargen max of 6; Swimming stays 5).
#   Individual skills (ratings): Sneaking 3 (+2 Catlike = 5), Palming 3, Perception 4 (+"Visual"
#     specialization +1 pt), Pistols 6, Locksmith 5, Escape Artist 3, Hacking 3, Con 4, Etiquette 4.
#     skill points: 3+3+4+6+5+3+3+4+4 = 35, +1 specialization = 36 (fully spent); group points: 5.
#
# Qualities — Positive 22¥k of the 25 cap (Catlike 7 + Natural Athlete 7 + Indomitable Physical 8);
#   Negative 15 of the 25 cap (SINner Criminal 10 + Simsense Vertigo 5). Net karma spent 22-15 = 7.
# ==================================================================================================

REFERENCE_MUNDANE_FIXTURE = SyntheticCharacter(
    name='Renata "Cheshire" Vance — mundane Human infiltrator (WP72 reference)',
    metatype="Human",
    heritage_letter="C",
    attributes_letter="A",
    skills_letter="B",
    resources_letter="D",
    attribute_points={
        "BOD": 3,
        "AGI": 5,
        "REA": 4,
        "STR": 2,
        "CHA": 1,
        "INT": 4,
        "LOG": 2,
        "WIL": 3,
        "EDG": 5,
    },
    skill_points={
        "Sneaking": 3,
        "Palming": 3,
        "Perception": 4,
        "Pistols": 6,
        "Locksmith": 5,
        "Escape Artist": 3,
        "Hacking": 3,
        "Con": 4,
        "Etiquette": 4,
    },
    group_points={"Athletics": 5},
    specializations={"Perception": "Visual"},
    qualities=(
        "Catlike",
        "Natural Athlete",
        "Indomitable (Physical)",
        "SINner (Criminal)",
        "Simsense Vertigo",
    ),
    quality_text={"SINner (Criminal)": "Lone Star criminal SIN — breaking-and-entering priors"},
    expected={
        # Attribute totals: metatype minimum + points spent (EDG maxed at 7).
        "attr:BOD": 4,
        "attr:AGI": 6,
        "attr:REA": 5,
        "attr:STR": 3,
        "attr:CHA": 2,
        "attr:INT": 5,
        "attr:LOG": 3,
        "attr:WIL": 4,
        "attr:EDG": 7,
        # Skill ratings — group members (+ Natural Athlete, capped), Catlike-boosted, plain.
        "rating:Gymnastics": 6,  # group 5 + Natural Athlete 2, capped at 6
        "rating:Running": 6,  # group 5 + Natural Athlete 2, capped at 6
        "rating:Swimming": 5,  # group 5, no bonus
        "rating:Sneaking": 5,  # 3 base + 2 Catlike
        "rating:Pistols": 6,
        "rating:Locksmith": 5,
        "rating:Perception": 4,
        # Dice pools: rating + linked attribute (+2 if specialized).
        "pool:Gymnastics": 12,  # 6 + AGI 6
        "pool:Running": 9,  # 6 + STR 3
        "pool:Swimming": 8,  # 5 + STR 3
        "pool:Sneaking": 11,  # 5 + AGI 6
        "pool:Palming": 9,  # 3 + AGI 6
        "pool:Pistols": 12,  # 6 + AGI 6
        "pool:Locksmith": 11,  # 5 + AGI 6
        "pool:Escape Artist": 9,  # 3 + AGI 6
        "pool:Hacking": 6,  # 3 + LOG 3
        "pool:Con": 6,  # 4 + CHA 2
        "pool:Etiquette": 6,  # 4 + CHA 2
        "pool:Perception": 11,  # 4 + INT 5 + 2 (Visual specialization)
        # Derived stats.
        "initiative": 10,  # REA 5 + INT 5
        "initiative_dice": 1,
        "limit:physical": 6,  # ceil((STR*2+BOD+REA)/3)=ceil(15/3)=5, +1 Indomitable (Physical)
        "limit:mental": 5,  # ceil((LOG*2+INT+WIL)/3) = ceil((6+5+4)/3) = ceil(15/3)
        "limit:social": 5,  # ceil((CHA*2+WIL+ceil ESS)/3) = ceil((4+4+6)/3) = ceil(14/3)
        "cm:physical": 10,  # 8 + ceil(BOD/2) = 8 + 2
        "cm:stun": 10,  # 8 + ceil(WIL/2) = 8 + 2
        "essence": 6,  # no cyberware/bioware
        # Karma: positives 22 (7+7+8) - negatives 15 (10+5) = 7 spent of the 25 starting.
        "karma_spent": 7,
        "karma_remaining": 18,
    },
    citations={
        "attr:BOD": "priorities.xml Attributes A = 24 pts; metatypes.xml Human BOD min 1 (+3)",
        "attr:AGI": "priorities.xml Attributes A; Human AGI min 1 (+5) = natural max 6",
        "attr:REA": "priorities.xml Attributes A; Human REA min 1 (+4)",
        "attr:STR": "priorities.xml Attributes A; Human STR min 1 (+2)",
        "attr:CHA": "priorities.xml Attributes A; Human CHA min 1 (+1)",
        "attr:INT": "priorities.xml Attributes A; Human INT min 1 (+4)",
        "attr:LOG": "priorities.xml Attributes A; Human LOG min 1 (+2)",
        "attr:WIL": "priorities.xml Attributes A; Human WIL min 1 (+3)",
        "attr:EDG": "priorities.xml Heritage C/Human = 5 special pts; Human EDG min 2 (+5) = max 7",
        "rating:Gymnastics": "Athletics group 5 + Natural Athlete 2 (qualities.xml), capped at 6",
        "rating:Running": "Athletics group 5 + Natural Athlete 2 (qualities.xml), capped at 6",
        "rating:Swimming": "Athletics group 5, no quality bonus",
        "rating:Sneaking": "Skills B skill pts; 3 base + 2 Catlike improvement (qualities.xml)",
        "rating:Pistols": "Skills B skill pts; 6 base, Firearms group unbought",
        "rating:Locksmith": "Skills B skill pts; 5 base (no group)",
        "rating:Perception": "Skills B skill pts; 4 base (no group)",
        "pool:Gymnastics": "learnings/phase-d.md (WP7 dice pool): rating 6 + AGI 6",
        "pool:Running": "learnings/phase-d.md: rating 6 + STR 3 (Running is STR-linked)",
        "pool:Swimming": "learnings/phase-d.md: rating 5 + STR 3",
        "pool:Sneaking": "learnings/phase-d.md: rating 5 + AGI 6",
        "pool:Palming": "learnings/phase-d.md: rating 3 + AGI 6",
        "pool:Pistols": "learnings/phase-d.md: rating 6 + AGI 6",
        "pool:Locksmith": "learnings/phase-d.md: rating 5 + AGI 6",
        "pool:Escape Artist": "learnings/phase-d.md: rating 3 + AGI 6",
        "pool:Hacking": "learnings/phase-d.md: rating 3 + LOG 3",
        "pool:Con": "learnings/phase-d.md: rating 4 + CHA 2",
        "pool:Etiquette": "learnings/phase-d.md: rating 4 + CHA 2",
        "pool:Perception": "learnings/phase-d.md: rating 4 + INT 5 + 2 spec (Visual)",
        "initiative": "learnings/phase-d.md (Character.cs InitiativeValue): REA 5 + INT 5",
        "initiative_dice": "learnings/phase-d.md: base 1 (no matrix/astral)",
        "limit:physical": "learnings/phase-d.md LimitPhysical: ceil(15/3)=5 +1 Indomitable(Phys)",
        "limit:mental": "learnings/phase-d.md LimitMental: ceil((LOG*2+INT+WIL)/3)=ceil(15/3)",
        "limit:social": "learnings/phase-d.md LimitSocial: ceil((CHA*2+WIL+ceilESS)/3)=ceil(14/3)",
        "cm:physical": "learnings/phase-d.md (PhysicalCM): 8 + ceil(BOD/2)",
        "cm:stun": "learnings/phase-d.md (StunCM): 8 + ceil(WIL/2)",
        "essence": "derived.py BASE_ESSENCE = 6 (metatypes.xml Human essmax 6); no augmentation",
        "karma_spent": "p.64 (25 Karma); positives 22 - negatives 15 (SINner 10 + Simsense 5) = 7",
        "karma_remaining": "STARTING_KARMA 25 - karma_spent 7",
    },
)


# ==================================================================================================
# WP73 fixture — Dražen "Rebar" Kovač, Ork street samurai (cyberware + bioware Essence stacking).
# ==================================================================================================
#
# Closes coverage gaps G1 (a Priority-built character bearing cyberware, Essence computed from real
# implants) and G2 (cyberware + bioware Essence costs stacking against the one shared pool) — see
# phase-s-test-fixtures.md §2. No real `.chum5` fixture is simultaneously Priority-built and
# cyberware-bearing, and none combines cyberware with bioware at all (the 8 cyberware-bearing
# curated fixtures are all SumtoTen and carry zero bioware — Phase J/L intros), so this interaction
# has never had a whole-character fixture.
#
# CONCEPT (flavor; not engine-modeled except where an assertion below says so)
# ------------------------------------------------------------------------------------------------
# Team role: the Street Samurai (see phase-s-test-fixtures.md §5) — the muscle. He walks in the door
# Cheshire opened and holds the room. Deliberately the team's soak/frontline: peak BODY and STR,
# chromed to the teeth, but only CHA 2 (the Shaman Face talks) and LOG 2 (the Decker hacks) — the
# same complementary-gap discipline the roster was authored against.
#
# An Ork ex-corp-security enforcer turned shadow muscle: a chromed arm, titanium-laced bones under
# the skin, retractable spurs, and reflex-tuned bioware. He soaks fire so the runners behind him
# don't have to, lives by a runner's code (never sell out the team), and is plainly hard to rattle.
# Ork metatype grants Low-Light Vision free (metatypes.xml — not karma-charged, not asserted here).
#
#   Handle: Rebar        Metatype: Ork (mundane)        Pronouns: he/him
#   Loadout (Resources C, 140,000¥ — 96,000 on augmentation below; the ~44,000 remainder buys, as
#     described-not-modeled flavor: a Middle lifestyle, a milspec-surplus assault rifle + heavy
#     pistol, an armor jacket, and a combat knife). Contacts: an ex-squadmate Fixer and a
#     back-alley Street Doc who installed the chrome.
#
# BUILD (all engine-modeled and asserted)
# ------------------------------------------------------------------------------------------------
# Priorities (Talent forced to E, mundane): Attributes A, Heritage B, Resources C, Skills D.
#   (Ork is only offered at Heritage A/B/C — never D, which is Human/Elf only — so with Attributes A
#   and one of Skills/Resources forced to D, Heritage B is the highest an Ork samurai can take here;
#   B funds 4 special-attribute points, exactly enough to lift Edge off its floor to a livable 5.)
#
# Attributes — Attributes A = 24 primary points, ALL spent; EDG from Heritage B/Ork's 4 special
#   points, ALL spent. At most one Mental/Physical attribute at its natural maximum (AGI 6) — legal
#   per Step Two. Ork minimums: BOD 4, STR 3, all others 1 (EDG 1).
#     BOD +2=6, AGI +5=6, REA +4=5, STR +3=6, CHA +1=2, INT +4=5, LOG +1=2, WIL +4=5   (sum 24)
#     EDG +4=5 (from 4 special points)
#
# Skills — Skills D = 22 skill points, 0 group points (Priority D grants no groups), ALL spent.
#     Automatics 6, Blades 4, Pistols 3, Perception 3, Intimidation 2, Sneaking 2, Escape Artist 1,
#     Gymnastics 1.  (6+4+3+3+2+2+1+1 = 22.)  Escape Artist ends at rating 2 — 1 bought + 1 from the
#     Enhanced Articulation bioware bonus below, exactly the bioware→skill path this fixture
#     exists to exercise.
#
# Augmentation — Cyberware (resolved first, Essence 3.1) then Bioware (second, Essence 0.5),
#   total Essence 3.6 → remaining Essence 6 − 3.6 = 2.4 (strictly positive, a legal build):
#     Cyberware (55,000¥): Obvious Full Arm (1.0 ess, +1 Physical CM — the one modeled cyberware
#       bonus, ImprovementType.PHYSICAL_CM), Bone Lacing (Titanium) (1.5 ess — armor/damage bundle
#       NOT modeled, Essence charged), Spurs (0.3 ess), Datajack (0.1 ess), Smartlink (0.2 ess —
#       targeting bonus NOT modeled, Essence charged).
#     Bioware (41,000¥): Enhanced Articulation (0.3 ess, +1 Physical Limit AND +1 Escape Artist),
#       Platelet Factories (0.2 ess — damage-resistance narrative NOT modeled, Essence charged).
#   Nuyen: 55,000 + 41,000 = 96,000 of the 140,000 Resources-C pool (the rest is loadout flavor).
#
# Qualities — Positive 18 of the 25 cap (Indomitable (Physical) 8 + Guts 10); Negative 15 of the 25
#   cap (Code of Honor 15, a select-text warrior's code — WP55 path). Net karma spent 18 − 15 = 3.
#   Physical Limit therefore takes +1 from Indomitable AND +1 from Enhanced Articulation (two
#   independent sources stacking on the same ImprovementType.PHYSICAL_LIMIT): base 8 → 10.
# ==================================================================================================

STREET_SAMURAI_FIXTURE = SyntheticCharacter(
    name='Dražen "Rebar" Kovač — Ork street samurai (WP73 cyberware+bioware Essence stacking)',
    metatype="Ork",
    heritage_letter="B",
    attributes_letter="A",
    skills_letter="D",
    resources_letter="C",
    attribute_points={
        "BOD": 2,
        "AGI": 5,
        "REA": 4,
        "STR": 3,
        "CHA": 1,
        "INT": 4,
        "LOG": 1,
        "WIL": 4,
        "EDG": 4,
    },
    skill_points={
        "Automatics": 6,
        "Blades": 4,
        "Pistols": 3,
        "Perception": 3,
        "Intimidation": 2,
        "Sneaking": 2,
        "Escape Artist": 1,
        "Gymnastics": 1,
    },
    qualities=("Indomitable (Physical)", "Guts", "Code of Honor"),
    quality_text={"Code of Honor": "The Runner's Code — never sell out a teammate"},
    cyberware=(
        "Obvious Full Arm",
        "Bone Lacing (Titanium)",
        "Spurs",
        "Datajack",
        "Smartlink",
    ),
    bioware=("Enhanced Articulation", "Platelet Factories"),
    expected={
        # Attribute totals: Ork metatype minimum + points spent (EDG from 4 special points).
        "attr:BOD": 6,
        "attr:AGI": 6,
        "attr:REA": 5,
        "attr:STR": 6,
        "attr:CHA": 2,
        "attr:INT": 5,
        "attr:LOG": 2,
        "attr:WIL": 5,
        "attr:EDG": 5,
        # Skill ratings — Escape Artist proves the bioware→skill bonus (1 bought + 1 bioware).
        "rating:Automatics": 6,
        "rating:Blades": 4,
        "rating:Pistols": 3,
        "rating:Escape Artist": 2,  # 1 bought + 1 Enhanced Articulation (bioware)
        "rating:Gymnastics": 1,
        # Dice pools: rating + linked attribute.
        "pool:Automatics": 12,  # 6 + AGI 6
        "pool:Blades": 10,  # 4 + AGI 6
        "pool:Pistols": 9,  # 3 + AGI 6
        "pool:Perception": 8,  # 3 + INT 5
        "pool:Intimidation": 4,  # 2 + CHA 2
        "pool:Sneaking": 8,  # 2 + AGI 6
        "pool:Escape Artist": 8,  # 2 + AGI 6 (rating already includes +1 bioware)
        "pool:Gymnastics": 7,  # 1 + AGI 6
        # Per-source Essence/nuyen — makes the shared-pool stacking explicit (G2): 3.1 + 0.5 = 3.6.
        "cyberware:essence_spent": Decimal("3.1"),
        "cyberware:nuyen_spent": 55000,
        "bioware:essence_spent": Decimal("0.5"),
        "bioware:nuyen_spent": 41000,
        # Derived stats.
        "essence": Decimal("2.4"),  # 6 - 3.1 cyberware - 0.5 bioware
        "initiative": 10,  # REA 5 + INT 5
        "initiative_dice": 1,
        "limit:physical": 10,  # ceil((STR*2+BOD+REA)/3)=ceil(23/3)=8, +1 Indomitable +1 Enh.Art
        "limit:mental": 5,  # ceil((LOG*2+INT+WIL)/3) = ceil((4+5+5)/3) = ceil(14/3)
        "limit:social": 4,  # ceil((CHA*2+WIL+ceil ESS 2.4->3)/3) = ceil((4+5+3)/3) = ceil(12/3)
        "cm:physical": 12,  # 8 + ceil(BOD/2)=11, +1 Obvious Full Arm (cyberlimb)
        "cm:stun": 11,  # 8 + ceil(WIL/2) = 8 + 3
        # Karma: positives 18 (8+10) - negatives 15 (Code of Honor) = 3 spent of the 25 starting.
        "karma_spent": 3,
        "karma_remaining": 22,
    },
    citations={
        "attr:BOD": "priorities.xml Attributes A = 24 pts; metatypes.xml Ork BOD min 4 (+2)",
        "attr:AGI": "priorities.xml Attributes A; Ork AGI min 1 (+5) = natural max 6",
        "attr:REA": "priorities.xml Attributes A; Ork REA min 1 (+4)",
        "attr:STR": "priorities.xml Attributes A; Ork STR min 3 (+3)",
        "attr:CHA": "priorities.xml Attributes A; Ork CHA min 1 (+1)",
        "attr:INT": "priorities.xml Attributes A; Ork INT min 1 (+4)",
        "attr:LOG": "priorities.xml Attributes A; Ork LOG min 1 (+1)",
        "attr:WIL": "priorities.xml Attributes A; Ork WIL min 1 (+4)",
        "attr:EDG": "priorities.xml Heritage B/Ork = 4 special pts; Ork EDG min 1 (+4)",
        "rating:Automatics": "Skills D skill pts; 6 base (Firearms group unbought), chargen cap 6",
        "rating:Blades": "Skills D skill pts; 4 base (Close Combat group unbought)",
        "rating:Pistols": "Skills D skill pts; 3 base",
        "rating:Escape Artist": "Skills D 1 base + 1 Enhanced Articulation (bioware.xml)",
        "rating:Gymnastics": "Skills D skill pts; 1 base (no group under Priority D)",
        "pool:Automatics": "learnings/phase-d.md (WP7 dice pool): rating 6 + AGI 6",
        "pool:Blades": "learnings/phase-d.md: rating 4 + AGI 6",
        "pool:Pistols": "learnings/phase-d.md: rating 3 + AGI 6",
        "pool:Perception": "learnings/phase-d.md: rating 3 + INT 5",
        "pool:Intimidation": "learnings/phase-d.md: rating 2 + CHA 2",
        "pool:Sneaking": "learnings/phase-d.md: rating 2 + AGI 6",
        "pool:Escape Artist": "learnings/phase-d.md: rating 2 (incl. +1 bioware) + AGI 6",
        "pool:Gymnastics": "learnings/phase-d.md: rating 1 + AGI 6",
        "cyberware:essence_spent": (
            "cyberware.xml <ess>: Obvious Full Arm 1.0 + Bone Lacing (Titanium) 1.5 + Spurs 0.3 "
            "+ Datajack 0.1 + Smartlink 0.2 = 3.1 (engine/cyberware.py essence_spent)"
        ),
        "cyberware:nuyen_spent": (
            "cyberware.xml <cost>: 15000 + 30000 + 5000 + 1000 + 4000 = 55000 <= Resources C 140000"
        ),
        "bioware:essence_spent": (
            "bioware.xml <ess>: Enhanced Articulation 0.3 + Platelet Factories 0.2 = 0.5 "
            "(engine/bioware.py essence_spent, resolved after cyberware per shared-pool order)"
        ),
        "bioware:nuyen_spent": "bioware.xml <cost>: 24000 + 17000 = 41000 (<= 140000 - 55000 left)",
        "essence": (
            "derived.py essence = BASE_ESSENCE 6 - Sigma ESSENCE improvements (3.1 cyberware + 0.5 "
            "bioware) = 2.4; one shared pool (engine/bioware.py resolve_essence docstring)"
        ),
        "initiative": "learnings/phase-d.md (Character.cs InitiativeValue): REA 5 + INT 5",
        "initiative_dice": "learnings/phase-d.md: base 1 (no matrix/astral)",
        "limit:physical": (
            "learnings/phase-d.md LimitPhysical: ceil(23/3)=8, +1 Indomitable(Phys) "
            "+1 Enhanced Articulation physicallimit (two ImprovementType.PHYSICAL_LIMIT sources)"
        ),
        "limit:mental": "learnings/phase-d.md LimitMental: ceil((LOG*2+INT+WIL)/3)=ceil(14/3)",
        "limit:social": (
            "learnings/phase-d.md LimitSocial: ceil((CHA*2+WIL+ceil ESS)/3); ESS 2.4 rounds up to 3"
        ),
        "cm:physical": "learnings/phase-d.md (PhysicalCM): 8 + ceil(BOD/2)=11, +1 Obvious Full Arm",
        "cm:stun": "learnings/phase-d.md (StunCM): 8 + ceil(WIL/2)",
        "karma_spent": "p.64 (25 Karma); positives 18 (Indomitable 8 + Guts 10) - COH 15 = 3",
        "karma_remaining": "STARTING_KARMA 25 - karma_spent 3",
    },
)


# Every synthetic fixture, for the parametrized regression test. WP74-76 append their fixtures here.
SYNTHETIC_FIXTURES = (REFERENCE_MUNDANE_FIXTURE, STREET_SAMURAI_FIXTURE)
