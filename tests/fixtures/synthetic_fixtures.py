"""Hand-authored synthetic whole-character fixtures (Phase S / WP72+).

Each fixture is a `SyntheticCharacter` (see `synthetic.py`) whose `expected` values are hand-derived
from the rulebook / `priorities.xml` / legacy C#, with an inline `citations` entry for every one.
WP72 landed the substrate plus the reference fixture below; WP73-76 appended their
interaction-covering fixtures here (cyberware/bioware, magician+cyberware, leftover-Karma,
Sum-to-Ten) as they extended the harness.

The fixtures double as **playable Shadowrun characters** — legal, fully-spent builds with
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
- Magic (WP74, `chummer5.engine.magic`/`.qualities`/`.foci`): Talent-option Magic rating/spell
  budget/free-skill grant from `priorities.xml`; the Essence→Magic loss ("every point or fraction
  thereof of Essence lost reduces Magic by one", core rulebook p.278) via
  `Character.magic_essence_loss`; Drain Resistance = tradition pair (Hermetic = WIL + LOG, p.278);
  the chargen foci total-Force cap (Magic x 2, p.98) and count cap (<= Magic, p.317); Mentor Spirit
  General/Magician `FLAT_BONUS` slots (p.320-324). All already extracted in
  `spec/rulebooks/learnings/phase-i.md` (WP25/WP35) and `phase-m.md` (WP47/WP48) — no new PDF pass.
- Step Seven leftover-Karma spend (WP75, `chummer5.engine.character`/`.skills`/`.magic`): the Karma
  Advancement Tables' own per-step formulas — attribute `new Rating x 5`, Active skill
  `new Rating x 2`, Active skill group `new Rating x 5`, flat 7 Karma per new specialization,
  5 Karma per extra spell — plus the group-breaking rule (raising *or* specializing a
  group-purchased member with Karma breaks that group) and the combined `Magic Rating x 2`
  known-spells cap. All already extracted in `spec/rulebooks/learnings/phase-o.md` (WP51-54) — no
  new PDF pass.
- Sum-to-Ten (WP76, `chummer5.engine.build_method`): the per-letter point values
  (`SUM_TO_TEN_POINT_VALUES`, A=4..E=0) and the exact-equality target (`SUM_TO_TEN_TARGET` = 10),
  both sourced from `SelectMetatypePriority.cs`'s own hardcoded table and `!=` check rather than the
  rulebook — Sum-to-Ten is legacy-Chummer/errata content with **zero** core-rulebook hits (WP44's
  research, `learnings.md`). Everything downstream of the letters is the same `priorities.xml` data
  the Priority fixtures above read.
"""

from __future__ import annotations

from decimal import Decimal

from tests.fixtures.synthetic import SyntheticCharacter

from chummer5.engine.build_method import SUM_TO_TEN_BUILD_METHOD

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


# ==================================================================================================
# WP74 fixture — Sabine "Cinder" Aumann, Hermetic combat mage (Essence->Magic loss, foci/mentor)
# ==================================================================================================
#
# Closes coverage gaps G3 (a magic-enabled character whose cyberware Essence loss reduces the Magic
# rating) and G6 (Foci + Mentor Spirit on a magician build) — see phase-s-test-fixtures.md §2. No
# real `.chum5` fixture is both magic-enabled and cyberware-bearing (Miko/Wesson, the corpus's only
# two magic Priority builds, carry zero cyberware), so the Essence→Magic interaction — the single
# cross-phase link between Phase I's Magic rating and Phase J's Essence tracking — had never had a
# whole-character fixture; nor had any fixture combined a magician with a bonded focus and a mentor.
#
# CONCEPT (flavor; not engine-modeled except where an assertion below says so)
# ------------------------------------------------------------------------------------------------
# Team role: the Combat Mage (see phase-s-test-fixtures.md §5) — the artillery and the astral eyes.
# She throws the spells, watches the astral, and counters the opposition's magic. A Hermetic (Logic-
# based) mage, so LOG is her top attribute (it drives her Drain Resistance and Mental Limit alike),
# distinct from WP75's forthcoming Charisma-based Shaman Face — the two casters don't overlap.
# She keeps her chrome to an absolute minimum (a datajack and a pair of cybereyes), because every
# fraction of an Essence point she spends costs her a full point of Magic — which is exactly the
# interaction this fixture exists to prove.
#
# An ex-corporate arcane researcher who walked out with more than she should have. Reserved and
# precise, under a mentor's discipline (Mountain — patience, endurance, and warding). She carries a
# lawful national SIN from her corp days that she can't shake (SINner (National)). A Power Focus,
# painstakingly bonded, sharpens every spell she casts.
#
#   Handle: Cinder       Metatype: Human (Hermetic Magician)     Pronouns: she/her
#   Loadout (Resources D, 50,000¥ — 40,000 on augmentation + focus below; the ~10,000 remainder is
#     described-not-modeled flavor: a Low lifestyle, a light pistol, a lined coat, a commlink, and a
#     small library of formulae). Contacts: a Talismonger and a former corp-lab colleague.
#
# BUILD (all engine-modeled and asserted)
# ------------------------------------------------------------------------------------------------
# Priorities: Talent A (Magician), Attributes B, Skills C, Resources D, Heritage E.
#   (A magician spends a full priority slot on Talent — Talent A grants Magic 6, a 10-spell budget,
#   and 2 free Magical-Active skills at rating 5. Heritage E only offers Human, which suits a
#   Hermetic mage fine; its lone special-attribute point lifts Edge off its floor to 3.)
#
# Attributes — Attributes B = 20 primary points, ALL spent; EDG from Heritage E/Human's 1 special
#   point. Only one attribute at its natural maximum (LOG 6) — legal per Step Two. Human min 1.
#     BOD +3=4, AGI +1=2, REA +3=4, STR +0=1, CHA +1=2, INT +3=4, LOG +5=6, WIL +4=5   (sum 20)
#     EDG +1=3 (from 1 special point)
#
# Magic — Talent A grants Magic 6 and a 10-spell free budget; the 2 free skills go to Spellcasting
#   and Counterspelling at rating 5 (both Magical Active, so grant-eligible). Tradition: Hermetic
#   (Drain Resistance = LOG + WIL). After the cyberware Essence loss below, her finished Magic is 5.
#
# Cyberware — a datajack + a pair of cybereyes (Image Link + Vision Magnification), Essence 0.3,
#   4,000¥. Essence 6 − 0.3 = 5.7; the 0.3 *fraction* of a point lost reduces Magic by a full point
#   (p.278, "for every point OR FRACTION THEREOF"): Magic 6 → 5. This is the whole point of the
#   fixture — a sub-1.0 Essence loss still costs a full Magic point, and that reduced 5 is what each
#   downstream cap (spells known, foci count/Force) and every MAG-linked dice pool then reads.
#
# Skills — Skills C = 28 skill + 2 group points, ALL spent. (Spellcasting/Counterspelling are the
#   free Talent grant, NOT bought here.)
#     Group: Conjuring 2 -> Summoning/Banishing/Binding at rating 2.
#     Individual (28): Assensing 4, Astral Combat 3, Arcana 3, Perception 4, Survival 2, Pistols 3,
#       Sneaking 2, Con 2, Negotiation 2, First Aid 3.  (4+3+3+4+2+3+2+2+2+3 = 28.)
#   Counterspelling ends at rating 6, not 7: the Talent grant (5) + Mountain's Magician slot (+2)
#     would be 7, capped at the chargen maximum of 6 — the mentor-on-a-granted-skill cap case.
#   Survival ends at rating 4: 2 bought + Mountain's General slot (+2 Survival).
#
# Spells — 7 of the free 10-spell budget (all within the Magic-Rating-x2 = 10 cap, computed on the
#   *reduced* Magic 5): Manabolt, Stunbolt, Powerbolt, Fireball, Increase Reflexes, Improved
#   Invisibility, Heal. 0 leftover Karma spent (all fit the free budget).
#
# Foci — one Power Focus at Force 2 (36,000¥, 12 Karma; Availability 2x4=8 <= 12). Legal against the
#   reduced Magic 5: count 1 <= 5, Force 2 <= Magic x 2 = 10. Its own dice bonus is unmodeled
#   (NOT_YET_SUPPORTED — the augmentation posture), so only its nuyen/Karma cost is asserted.
#
# Qualities — Positive: Mentor Spirit (Mountain) 5 + Indomitable (Mental) 8 = 13; Negative: SINner
#   (National) 5. Quality karma net 13 − 5 = 8. Mountain grants +2 Survival (General) and +2
#   Counterspelling (Magician) as FLAT_BONUS Improvements — the focus/mentor-Improvement half of G6.
#   Karma ledger: 25 − 8 (qualities) − 12 (foci) = 5 left (spells cost 0).
# ==================================================================================================

COMBAT_MAGE_FIXTURE = SyntheticCharacter(
    name='Sabine "Cinder" Aumann — Hermetic combat mage (WP74 Essence->Magic loss, foci/mentor)',
    metatype="Human",
    heritage_letter="E",
    attributes_letter="B",
    skills_letter="C",
    resources_letter="D",
    talent_letter="A",
    magic_type="Magician",
    tradition="Hermetic",
    magic_granted_skills=("Spellcasting", "Counterspelling"),
    attribute_points={
        "BOD": 3,
        "AGI": 1,
        "REA": 3,
        "STR": 0,
        "CHA": 1,
        "INT": 3,
        "LOG": 5,
        "WIL": 4,
        "EDG": 1,
    },
    skill_points={
        "Assensing": 4,
        "Astral Combat": 3,
        "Arcana": 3,
        "Perception": 4,
        "Survival": 2,
        "Pistols": 3,
        "Sneaking": 2,
        "Con": 2,
        "Negotiation": 2,
        "First Aid": 3,
    },
    group_points={"Conjuring": 2},
    qualities=("Mentor Spirit", "Indomitable (Mental)", "SINner (National)"),
    mentor_spirit="Mountain",
    quality_text={"SINner (National)": "UCAS national SIN — registered corporate arcanist"},
    cyberware=("Datajack", "Image Link", "Vision Magnification"),
    spells=(
        "Manabolt",
        "Stunbolt",
        "Powerbolt",
        "Fireball",
        "Increase Reflexes",
        "Improved Invisibility",
        "Heal",
    ),
    foci=(("Power Focus", 2),),
    expected={
        # Attribute totals: Human metatype minimum + points spent (EDG from 1 special point).
        "attr:BOD": 4,
        "attr:AGI": 2,
        "attr:REA": 4,
        "attr:STR": 1,
        "attr:CHA": 2,
        "attr:INT": 4,
        "attr:LOG": 6,
        "attr:WIL": 5,
        "attr:EDG": 3,
        # Magic: the G3 headline — a 0.3 Essence loss costs a full Magic point (6 -> 5).
        "magic:rating": 5,
        "magic:rating_before_essence_loss": 6,
        "magic:essence_loss": 1,
        "essence": Decimal("5.7"),  # 6 - 0.3 cyberware
        "cyberware:essence_spent": Decimal("0.3"),  # Datajack 0.1 + Image Link 0.1 + Vision Mag 0.1
        "cyberware:nuyen_spent": 4000,  # 1000 + 1000 + 2000
        # Skill ratings — the mentor/grant interactions.
        "rating:Spellcasting": 5,  # Talent A grant (5), no mentor bonus
        "rating:Counterspelling": 6,  # grant 5 + Mountain Magician +2 = 7, capped at 6
        "rating:Summoning": 2,  # Conjuring group 2
        "rating:Banishing": 2,  # Conjuring group 2 (proves the group)
        "rating:Survival": 4,  # 2 bought + Mountain General +2
        "rating:Assensing": 4,
        "rating:Arcana": 3,
        # Dice pools: rating + linked attribute — MAG-linked ones read the *reduced* Magic 5.
        "pool:Spellcasting": 10,  # 5 + MAG 5
        "pool:Counterspelling": 11,  # 6 + MAG 5
        "pool:Summoning": 7,  # 2 + MAG 5
        "pool:Assensing": 8,  # 4 + INT 4
        "pool:Astral Combat": 8,  # 3 + WIL 5
        "pool:Arcana": 9,  # 3 + LOG 6
        "pool:Survival": 9,  # 4 + WIL 5
        "pool:Perception": 8,  # 4 + INT 4
        "pool:Pistols": 5,  # 3 + AGI 2
        "pool:Con": 4,  # 2 + CHA 2
        "pool:First Aid": 9,  # 3 + LOG 6
        # Foci + spells — caps computed on the reduced Magic 5.
        "foci:nuyen_cost": 36000,  # Power Focus Force 2 x 18000/Force
        "foci:karma_cost": 12,  # Force 2 x 6 Karma/Force
        "spells:count": 7,  # 7 of the 10 free budget
        "spells:karma_cost": 0,  # all within the free Talent budget
        # Derived stats.
        "drain_resistance": 11,  # Hermetic: LOG 6 + WIL 5
        "power_points": 0,  # Magician, not Adept
        "initiative": 8,  # REA 4 + INT 4
        "initiative_dice": 1,
        "limit:physical": 4,  # ceil((STR*2+BOD+REA)/3) = ceil((2+4+4)/3) = ceil(10/3)
        "limit:mental": 8,  # ceil((LOG*2+INT+WIL)/3)=ceil(21/3)=7, +1 Indomitable (Mental)
        "limit:social": 5,  # ceil((CHA*2+WIL+ceil ESS 5.7->6)/3) = ceil((4+5+6)/3) = ceil(15/3)
        "cm:physical": 10,  # 8 + ceil(BOD/2) = 8 + 2
        "cm:stun": 11,  # 8 + ceil(WIL/2) = 8 + 3
        # Karma: 25 - 8 (qualities: Mentor 5 + Indomitable 8 - SINner 5) - 12 (foci) = 5.
        "karma_spent": 20,
        "karma_remaining": 5,
    },
    citations={
        "attr:BOD": "priorities.xml Attributes B = 20 pts; metatypes.xml Human BOD min 1 (+3)",
        "attr:AGI": "priorities.xml Attributes B; Human AGI min 1 (+1)",
        "attr:REA": "priorities.xml Attributes B; Human REA min 1 (+3)",
        "attr:STR": "priorities.xml Attributes B; Human STR min 1 (+0)",
        "attr:CHA": "priorities.xml Attributes B; Human CHA min 1 (+1)",
        "attr:INT": "priorities.xml Attributes B; Human INT min 1 (+3)",
        "attr:LOG": "priorities.xml Attributes B; Human LOG min 1 (+5) = natural max 6",
        "attr:WIL": "priorities.xml Attributes B; Human WIL min 1 (+4)",
        "attr:EDG": "priorities.xml Heritage E/Human = 1 special pt; Human EDG min 2 (+1)",
        "magic:rating": (
            "attribute_value('MAG') = rating_before_essence_loss 6 - essence_loss 1 = 5 "
            "(character.py; core rulebook p.278, learnings/phase-i.md WP25/WP35)"
        ),
        "magic:rating_before_essence_loss": (
            "priorities.xml Talent A Magician grants Magic 6; capped at Human MAG max 6"
        ),
        "magic:essence_loss": (
            "ceil(0.3 Essence lost) = 1; p.278 'every point OR FRACTION THEREOF' "
            "(Character.magic_essence_loss, learnings/phase-i.md WP35)"
        ),
        "essence": "derived.py essence = BASE_ESSENCE 6 - 0.3 (cyberware ESSENCE improvements)",
        "cyberware:essence_spent": (
            "cyberware.xml <ess>: Datajack 0.1 + Image Link 0.1 + Vision Magnification 0.1 = 0.3"
        ),
        "cyberware:nuyen_spent": (
            "cyberware.xml <cost>: 1000 + 1000 + 2000 = 4000 <= Resources D 50000"
        ),
        "rating:Spellcasting": "priorities.xml Talent A grant (skill_val 5); no mentor bonus",
        "rating:Counterspelling": (
            "grant 5 + Mountain Magician slot +2 (mentors.xml) = 7, capped at MAX_SKILL_RATING_"
            "CREATE 6 (skills.py)"
        ),
        "rating:Summoning": "Skills C group pts; Conjuring group 2",
        "rating:Banishing": "Skills C group pts; Conjuring group 2",
        "rating:Survival": "Skills C 2 bought + Mountain General slot +2 Survival (mentors.xml)",
        "rating:Assensing": "Skills C skill pts; 4 base (no group)",
        "rating:Arcana": "Skills C skill pts; 3 base (no group)",
        "pool:Spellcasting": "learnings/phase-d.md (dice pool): rating 5 + MAG 5 (reduced)",
        "pool:Counterspelling": "learnings/phase-d.md: rating 6 (capped) + MAG 5 (reduced)",
        "pool:Summoning": "learnings/phase-d.md: rating 2 + MAG 5 (reduced)",
        "pool:Assensing": "learnings/phase-d.md: rating 4 + INT 4 (Assensing is INT-linked)",
        "pool:Astral Combat": "learnings/phase-d.md: rating 3 + WIL 5 (Astral Combat: WIL-linked)",
        "pool:Arcana": "learnings/phase-d.md: rating 3 + LOG 6",
        "pool:Survival": "learnings/phase-d.md: rating 4 + WIL 5 (Survival is WIL-linked)",
        "pool:Perception": "learnings/phase-d.md: rating 4 + INT 4",
        "pool:Pistols": "learnings/phase-d.md: rating 3 + AGI 2",
        "pool:Con": "learnings/phase-d.md: rating 2 + CHA 2",
        "pool:First Aid": "learnings/phase-d.md: rating 3 + LOG 6",
        "foci:nuyen_cost": "foci.xml Power Focus cost 18000/Force x Force 2 = 36000 (foci.py)",
        "foci:karma_cost": (
            "foci.xml Power Focus bonding 6 Karma/Force x Force 2 = 12; Force 2 <= Magic 5 x 2 cap "
            "(p.98, learnings/phase-m.md WP47)"
        ),
        "spells:count": "priorities.xml Talent A = 10-spell budget; 7 <= Magic 5 x 2 cap (p.98)",
        "spells:karma_cost": "all 7 within the free 10-spell budget, 0 leftover Karma (magic.py)",
        "drain_resistance": (
            "derived.py drain_resistance: Hermetic tradition pair LOG + WIL = 6 + 5 = 11 "
            "(traditions.xml; p.278, learnings/phase-i.md)"
        ),
        "power_points": "Character.power_points = 0 for a Magician (Adept-only; p.278-279)",
        "initiative": "learnings/phase-d.md (Character.cs InitiativeValue): REA 4 + INT 4",
        "initiative_dice": "learnings/phase-d.md: base 1 (no matrix/astral)",
        "limit:physical": "learnings/phase-d.md LimitPhysical: ceil((2+4+4)/3)=ceil(10/3)=4",
        "limit:mental": (
            "learnings/phase-d.md LimitMental: ceil(21/3)=7, +1 Indomitable (Mental) (qualities)"
        ),
        "limit:social": (
            "learnings/phase-d.md LimitSocial: ceil((CHA*2+WIL+ceil ESS)/3); ESS 5.7 rounds up to 6"
        ),
        "cm:physical": "learnings/phase-d.md (PhysicalCM): 8 + ceil(BOD/2)",
        "cm:stun": "learnings/phase-d.md (StunCM): 8 + ceil(WIL/2)",
        "karma_spent": (
            "p.64 (25 Karma); qualities 8 (Mentor 5 + Indomitable 8 - SINner 5) + foci 12 = 20"
        ),
        "karma_remaining": "STARTING_KARMA 25 - karma_spent 20",
    },
)


# ==================================================================================================
# WP75 fixture — Yseult "Wren" Marchetti, Elf shaman face (Step Seven leftover-Karma spend)
# ==================================================================================================
#
# Closes coverage gaps G4 (Step-Seven leftover-Karma spend on skills/groups, *including* the
# group-breaking case, plus a Karma-funded specialization) and G5 (an extra spell beyond the free
# Talent budget) — see phase-s-test-fixtures.md §2. Both mechanics are flagged "hand-verified, no
# fixture" in their own WPs' research notes: `learnings/phase-o.md`'s WP53 entry ("No fixture in the
# 34-file corpus exercises Karma-funded skill/group/specialization spend at all") and its WP54 entry
# ("No fixture ... exercises Karma-funded extra spells" — Miko's 6 spells fit her free budget of 10,
# Wesson is an Adept with no spell budget). This fixture is the first executable coverage of either.
#
# CONCEPT (flavor; not engine-modeled except where an assertion below says so)
# ------------------------------------------------------------------------------------------------
# Team role: the Face (see phase-s-test-fixtures.md §5) — the one who gets the team invited in
# instead of breaking in, and the team's *second* magic user. Deliberately built against WP74's
# Hermetic combat mage on both axes: Shamanic (CHA-based Drain) rather than Hermetic (LOG), and a
# social specialist with modest magic (Talent C, Magic 3) rather than artillery (Talent A, Magic 6).
# She also fills Cheshire's CHA-2 gap, exactly the complementary spread §5 asks new runners to be
# checked against.
#
# A former corporate PR liaison who found she could hear what people actually meant — and that
# spirits would talk to her about it. She never learned to shoot her way out of anything: she talks,
# and if talk fails, she convinces the room it never saw her. Elf metatype grants Low-Light Vision
# free (metatypes.xml — not karma-charged, not asserted here).
#
#   Handle: Wren      Metatype: Elf (Shamanic Magician)      Pronouns: she/her
#   Loadout (Resources E, 6,000¥ — described, not engine-modeled): a Low lifestyle room she is
#     rarely in, one immaculate suit bought on someone else's credstick, a licensed light pistol she
#     has never fired on a run, a commlink. She is the team's poorest member on paper and its most
#     expensively dressed. Contacts: a fixer who books her as a "consultant" and a talismonger.
#
# BUILD (all engine-modeled and asserted)
# ------------------------------------------------------------------------------------------------
# Priorities: Attributes A, Skills B, Talent C, Heritage D, Resources E.
#   (Talent C's Magician option — Magic 3, a 5-spell free budget, and *no* free-skill grant at all
#   (`skill_qty` is unset at letter C, unlike WP74's Talent A) — is the price of Attributes A +
#   Skills B, and it's what makes her a secondary caster rather than a second artillery mage. Elf is
#   offered at Heritage D, whose special-attribute-point budget is **0**, so Edge starts at the Elf
#   floor of 1 and only Step Seven Karma can lift it.)
#
# Attributes — Attributes A = 24 primary points, ALL spent; 0 special points to spend (Heritage D).
#   Elf minimums: AGI 2, CHA 3, all others 1 (EDG 1). CHA 8 is her one attribute at its natural
#   maximum — legal per Step Two, and the Karma spend below only touches EDG, which that rule
#   explicitly exempts (p.99).
#     BOD +2=3, AGI +2=4, REA +3=4, STR +2=3, CHA +5=8, INT +4=5, LOG +2=3, WIL +4=5   (sum 24)
#     EDG +0=1 from priority points → 2 after the Step Seven Karma buy below.
#
# Magic — Talent C grants Magic 3 and a 5-spell free budget, no free skills. Tradition: Shamanic
#   (Drain Resistance = WIL + CHA = 5 + 8 = 13, her best pool of any kind). No cyberware, so no
#   Essence→Magic loss: finished Magic 3, known-spells cap = 3 x 2 = 6.
#
# Skills — Skills B = 36 skill + 5 group points, ALL spent.
#   Groups (5): Influence 4 → Etiquette/Leadership/Negotiation all at 4; Conjuring 1 →
#     Summoning/Banishing/Binding all at 1 (raised to 2 by Karma below).
#   Individual (35 + 1 specialization = 36): Spellcasting 5, Counterspelling 2, Assensing 3, Con 5
#     (+"Fast Talk" specialization, 1 skill point — the Step Five, skill-point-funded kind),
#     Impersonation 3, Performance 2, Intimidation 3, Perception 3, Sneaking 2, Pistols 2,
#     First Aid 2, Arcana 2, Disguise 1.  (5+2+3+5+3+2+3+3+2+2+2+2+1 = 35, +1 spec = 36.)
#
# Step Seven — leftover Karma, 25 of 25 spent (karma_remaining 0). The Karma pool is 42, not 25:
#   Positive Qualities cost 8 (Indomitable (Social)) and Negative Qualities credit 25 — Codeblock 10
#   + SINner (Corporate Limited) 15, exactly the 25-Karma Negative cap — so the quality ledger is a
#   net *credit* of 17 (25 - (8 - 25) = 42). Spent, in the engine's own fixed Step Seven order
#   (attributes → skills → spells, per chummer5.io.save_format.build_character):
#     - EDG 1 → 2:               10 Karma  (new rating 2 x 5)
#     - Negotiation 4 → 5:       10 Karma  (new rating 5 x 2) — and this BREAKS the Influence group:
#         Negotiation becomes individually tracked at 5 while Etiquette/Leadership stay at 4.
#     - Negotiation specialization ("Bargaining"): 7 Karma (flat) — the second, independent
#         group-breaking trigger, landing on the same skill as the raise.
#     - Conjuring group 1 → 2:   10 Karma  (new rating 2 x 5) — a group raised *as a group* with
#         Karma, legal precisely because nothing broke this group (a group can't be both raised and
#         broken in one submission).
#     - A 6th spell:              5 Karma  (5 Karma/spell) — one beyond the free budget of 5, and
#         exactly at the Magic 3 x 2 = 6 known-spells cap.
#   Total 42. Which specific spell is the Karma-funded one is never tracked (only the count matters
#   — see SpellSelection's own docstring); in-concept it's Mind Probe, bought last.
#
# Spells (6): Influence, Analyze Truth, Physical Mask, Heal, Stunbolt, Mind Probe — a Face's kit:
#   persuade, detect the lie, wear another face, patch the team up, and one bolt for emergencies.
# ==================================================================================================

SHAMAN_FACE_FIXTURE = SyntheticCharacter(
    name='Yseult "Wren" Marchetti — Elf shaman face (WP75 Step Seven leftover-Karma spend)',
    metatype="Elf",
    heritage_letter="D",
    attributes_letter="A",
    skills_letter="B",
    resources_letter="E",
    talent_letter="C",
    magic_type="Magician",
    tradition="Shamanic",
    attribute_points={
        "BOD": 2,
        "AGI": 2,
        "REA": 3,
        "STR": 2,
        "CHA": 5,
        "INT": 4,
        "LOG": 2,
        "WIL": 4,
    },
    skill_points={
        "Spellcasting": 5,
        "Counterspelling": 2,
        "Assensing": 3,
        "Con": 5,
        "Impersonation": 3,
        "Performance": 2,
        "Intimidation": 3,
        "Perception": 3,
        "Sneaking": 2,
        "Pistols": 2,
        "First Aid": 2,
        "Arcana": 2,
        "Disguise": 1,
    },
    group_points={"Influence": 4, "Conjuring": 1},
    specializations={"Con": "Fast Talk"},
    qualities=("Indomitable (Social)", "Codeblock", "SINner (Corporate Limited)"),
    quality_text={
        "Codeblock": "Matrix Search — she has never trusted a search she didn't run by hand",
        "SINner (Corporate Limited)": "Horizon limited corporate SIN — ex-PR liaison, on file",
    },
    spells=(
        "Influence",
        "Analyze Truth",
        "Physical Mask",
        "Heal",
        "Stunbolt",
        "Mind Probe",
    ),
    karma_attribute_points={"EDG": 1},
    karma_skill_points={"Negotiation": 1},
    karma_group_points={"Conjuring": 1},
    karma_specializations={"Negotiation": "Bargaining"},
    expected={
        # Attribute totals: Elf metatype minimum + priority points; EDG also + its Karma point.
        "attr:BOD": 3,
        "attr:AGI": 4,
        "attr:REA": 4,
        "attr:STR": 3,
        "attr:CHA": 8,
        "attr:INT": 5,
        "attr:LOG": 3,
        "attr:WIL": 5,
        "attr:EDG": 2,  # Elf floor 1 + 0 priority (Heritage D = 0 special pts) + 1 Karma
        "magic:rating": 3,
        "magic:essence_loss": 0,  # no cyberware, so no Essence→Magic reduction
        # G4 — the group-breaking split: Negotiation left the Influence group, its siblings didn't.
        "karma_skill:broken_groups": frozenset({"Influence"}),
        "rating:Negotiation": 5,  # group 4 + 1 Karma point, now individually tracked
        "rating:Etiquette": 4,  # unchanged group rating
        "rating:Leadership": 4,  # unchanged group rating
        # G4 — a group raised *as a group* with Karma (priority 1 + Karma 1), no breakage.
        "rating:Summoning": 2,
        "rating:Banishing": 2,
        "rating:Binding": 2,
        "rating:Con": 5,
        "rating:Spellcasting": 5,
        # Dice pools — the two specializations (one skill-point-funded, one Karma-funded) both +2.
        "pool:Negotiation": 15,  # 5 + CHA 8 + 2 (Karma specialization "Bargaining")
        "pool:Con": 15,  # 5 + CHA 8 + 2 (skill-point specialization "Fast Talk")
        "pool:Etiquette": 12,  # 4 + CHA 8
        "pool:Leadership": 12,  # 4 + CHA 8
        "pool:Impersonation": 11,  # 3 + CHA 8
        "pool:Intimidation": 11,  # 3 + CHA 8
        "pool:Performance": 10,  # 2 + CHA 8
        "pool:Spellcasting": 8,  # 5 + MAG 3
        "pool:Counterspelling": 5,  # 2 + MAG 3
        "pool:Summoning": 5,  # 2 (incl. the Karma group point) + MAG 3
        "pool:Assensing": 8,  # 3 + INT 5
        "pool:Perception": 8,  # 3 + INT 5
        "pool:Disguise": 6,  # 1 + INT 5
        "pool:Sneaking": 6,  # 2 + AGI 4
        "pool:Pistols": 6,  # 2 + AGI 4
        "pool:First Aid": 5,  # 2 + LOG 3
        # G5 — the 6th spell is Karma-funded, at exactly the Magic x 2 known-spells cap.
        "spells:count": 6,
        "spells:karma_cost": 5,
        # Per-selection Step Seven costs, so the ledger is asserted per source, not only in total.
        "karma_attribute:karma_cost": 10,  # EDG 1 -> 2
        "karma_skill:karma_cost": 27,  # Negotiation 10 + specialization 7 + Conjuring group 10
        # Derived stats.
        "essence": 6,  # no augmentation
        "drain_resistance": 13,  # Shamanic: WIL 5 + CHA 8
        "power_points": 0,  # Magician, not Adept
        "initiative": 9,  # REA 4 + INT 5
        "initiative_dice": 1,
        "limit:physical": 5,  # ceil((STR*2+BOD+REA)/3) = ceil((6+3+4)/3) = ceil(13/3)
        "limit:mental": 6,  # ceil((LOG*2+INT+WIL)/3) = ceil((6+5+5)/3) = ceil(16/3)
        "limit:social": 10,  # ceil((16+5+6)/3)=9, +1 Indomitable (Social)
        "cm:physical": 10,  # 8 + ceil(BOD/2) = 8 + 2
        "cm:stun": 11,  # 8 + ceil(WIL/2) = 8 + 3
        # Karma: qualities -17 (8 positive - 25 negative) + 10 + 27 + 5 = 25, i.e. every point of
        # the 25-Karma starting pool spent, nothing left.
        "karma_spent": 25,
        "karma_remaining": 0,
    },
    citations={
        "attr:BOD": "priorities.xml Attributes A = 24 pts; metatypes.xml Elf BOD min 1 (+2)",
        "attr:AGI": "priorities.xml Attributes A; Elf AGI min 2 (+2)",
        "attr:REA": "priorities.xml Attributes A; Elf REA min 1 (+3)",
        "attr:STR": "priorities.xml Attributes A; Elf STR min 1 (+2)",
        "attr:CHA": "priorities.xml Attributes A; Elf CHA min 3 (+5) = natural max 8",
        "attr:INT": "priorities.xml Attributes A; Elf INT min 1 (+4)",
        "attr:LOG": "priorities.xml Attributes A; Elf LOG min 1 (+2)",
        "attr:WIL": "priorities.xml Attributes A; Elf WIL min 1 (+4)",
        "attr:EDG": (
            "priorities.xml Heritage D/Elf = 0 special pts, so Elf EDG min 1; +1 Karma point "
            "(character.py karma_attribute_selection; p.99 exempts Edge from the natural-max rule)"
        ),
        "magic:rating": "priorities.xml Talent C Magician grants Magic 3; no Essence loss",
        "magic:essence_loss": "ceil(0 Essence lost) = 0 (no cyberware/bioware); p.278",
        "karma_skill:broken_groups": (
            "p.87-88 via learnings/phase-o.md WP53: raising OR specializing a group member with "
            "Karma in Step Seven breaks that group (skills.py create_karma_skill_selection)"
        ),
        "rating:Negotiation": (
            "Influence group 4 (Skills B group pts) + 1 Karma point; individually tracked once the "
            "group is broken (skills.py skill_rating's broken-group branch)"
        ),
        "rating:Etiquette": "Influence group 4; unaffected by the broken sibling (skills.py)",
        "rating:Leadership": "Influence group 4; unaffected by the broken sibling (skills.py)",
        "rating:Summoning": "Conjuring group 1 (Skills B group pts) + 1 Karma group point = 2",
        "rating:Banishing": "Conjuring group 1 + 1 Karma group point = 2 (proves the group)",
        "rating:Binding": "Conjuring group 1 + 1 Karma group point = 2 (proves the group)",
        "rating:Con": "Skills B skill pts; 5 base (Acting group unbought)",
        "rating:Spellcasting": "Skills B skill pts; 5 base (Sorcery unbought, no Talent grant)",
        "pool:Negotiation": (
            "learnings/phase-d.md (dice pool): rating 5 + CHA 8 + 2 Karma specialization "
            "(KARMA_SPECIALIZATION_COST path, skills.py dice_pool)"
        ),
        "pool:Con": "learnings/phase-d.md: rating 5 + CHA 8 + 2 skill-point specialization (WP50)",
        "pool:Etiquette": "learnings/phase-d.md: rating 4 + CHA 8",
        "pool:Leadership": "learnings/phase-d.md: rating 4 + CHA 8",
        "pool:Impersonation": "learnings/phase-d.md: rating 3 + CHA 8",
        "pool:Intimidation": "learnings/phase-d.md: rating 3 + CHA 8",
        "pool:Performance": "learnings/phase-d.md: rating 2 + CHA 8",
        "pool:Spellcasting": "learnings/phase-d.md: rating 5 + MAG 3",
        "pool:Counterspelling": "learnings/phase-d.md: rating 2 + MAG 3",
        "pool:Summoning": "learnings/phase-d.md: rating 2 (incl. Karma group point) + MAG 3",
        "pool:Assensing": "learnings/phase-d.md: rating 3 + INT 5 (Assensing is INT-linked)",
        "pool:Perception": "learnings/phase-d.md: rating 3 + INT 5",
        "pool:Disguise": "learnings/phase-d.md: rating 1 + INT 5 (Disguise is INT-linked)",
        "pool:Sneaking": "learnings/phase-d.md: rating 2 + AGI 4",
        "pool:Pistols": "learnings/phase-d.md: rating 2 + AGI 4",
        "pool:First Aid": "learnings/phase-d.md: rating 2 + LOG 3",
        "spells:count": (
            "priorities.xml Talent C Magician = 5-spell free budget; 6 known = exactly the "
            "Magic 3 x 2 cap (p.98, learnings/phase-o.md WP54)"
        ),
        "spells:karma_cost": (
            "1 spell beyond the free budget x KARMA_PER_SPELL 5 (p.98 Additional Purchases table, "
            "learnings/phase-o.md WP54)"
        ),
        "karma_attribute:karma_cost": (
            "karma_advancement_cost(1, 1, ATTRIBUTE_KARMA_PER_RATING 5) = new rating 2 x 5 = 10 "
            "(p.106-107 Karma Advancement Table for Attributes, learnings/phase-o.md WP51/WP52)"
        ),
        "karma_skill:karma_cost": (
            "Negotiation 4->5 = new rating 5 x KARMA_SKILL_PER_RATING 2 = 10; specialization "
            "KARMA_SPECIALIZATION_COST 7 (flat); Conjuring group 1->2 = new rating 2 x "
            "KARMA_SKILL_GROUP_PER_RATING 5 = 10; total 27 (p.106-107, learnings/phase-o.md WP51)"
        ),
        "essence": "derived.py BASE_ESSENCE = 6 (metatypes.xml Elf essmax 6); no augmentation",
        "drain_resistance": (
            "derived.py drain_resistance: Shamanic tradition pair WIL + CHA = 5 + 8 = 13 "
            "(traditions.xml; p.278, learnings/phase-i.md)"
        ),
        "power_points": "Character.power_points = 0 for a Magician (Adept-only; p.278-279)",
        "initiative": "learnings/phase-d.md (Character.cs InitiativeValue): REA 4 + INT 5",
        "initiative_dice": "learnings/phase-d.md: base 1 (no matrix/astral)",
        "limit:physical": "learnings/phase-d.md LimitPhysical: ceil((6+3+4)/3)=ceil(13/3)=5",
        "limit:mental": "learnings/phase-d.md LimitMental: ceil((6+5+5)/3)=ceil(16/3)=6",
        "limit:social": (
            "learnings/phase-d.md LimitSocial: ceil((CHA*2+WIL+ceil ESS)/3)=ceil(27/3)=9, "
            "+1 Indomitable (Social) (qualities.xml FLAT_BONUS social_limit)"
        ),
        "cm:physical": "learnings/phase-d.md (PhysicalCM): 8 + ceil(BOD/2)",
        "cm:stun": "learnings/phase-d.md (StunCM): 8 + ceil(WIL/2)",
        "karma_spent": (
            "p.64 (25 Karma); qualities 8 - 25 = -17 (Negative cap 25 hit exactly) + attributes 10 "
            "+ skills 27 + spells 5 = 25"
        ),
        "karma_remaining": "STARTING_KARMA 25 - karma_spent 25 = 0 (fully spent)",
    },
)


# ==================================================================================================
# WP76 fixture — Bakari "Nullsec" Osei, Dwarf decker (Sum-to-Ten build method + a cyberware layer)
# ==================================================================================================
#
# Closes coverage gap G7 (the Sum-to-Ten build method — WP44's sibling letter-assignment rule —
# combined with a cyberware layer) — see phase-s-test-fixtures.md §2. `.chum5`-corpus-wise this gap
# looks *covered* and isn't: 33 of the 34 legacy fixtures are `SumtoTen`-built, but WP4 only ever
# reads their finished values, so not one of them ever runs a set of letters through this project's
# own Sum-to-Ten validation, and none is built through this engine at all. Every synthetic fixture
# before this one is a Priority build, so `chummer5.engine.build_method`'s validation had only unit
# tests (`tests/unit/test_build_method.py`) and the web route behind it — no whole character.
#
# The Sum-to-Ten letters below are what make that concrete: **Heritage B / Skills B / Attributes C /
# Resources C / Talent E**, i.e. 3 + 3 + 2 + 2 + 0 = exactly 10 (SUM_TO_TEN_POINT_VALUES,
# SUM_TO_TEN_TARGET). Two letters appear twice, so this assignment is *illegal* under the Priority
# bijection every other fixture uses — `tests/integration/test_synthetic_fixtures.py` asserts that
# rejection directly, which is the actual content of "this is a different build method" (nothing
# downstream of the letters differs: both methods read the same `priorities.xml` rows).
#
# CONCEPT (flavor; not engine-modeled except where an assertion below says so)
# ------------------------------------------------------------------------------------------------
# Team role: the Decker (see phase-s-test-fixtures.md §5) — the Matrix. They open the *other* kind
# of door: cameras looped, alarms muted, paydata copied while Cheshire is still on the roof. This is
# the one role Cheshire structurally cannot cover (Simsense Vertigo), and the reason her LOG 3 and
# Rebar's LOG 2 aren't holes in the team. Deliberately no climber, no talker, no gunfighter: AGI 2,
# CHA 2, and a pistol they carry rather than use.
#
# A Dwarf ex-Renraku systems auditor who found the audit trail led upstairs, copied it, and left.
# Slow on their feet and immovable everywhere else: they run hot-sim with a naturally hardened
# nervous system (Natural Hardening), think in structured layers (Indomitable (Mental)), and don't
# get shaken out of a host once they're inside. They still hold a *full* corporate SIN in Renraku's
# files — the heaviest Negative quality in the SR5 catalog, and the reason they will never fly under
# a real name again. Dwarf grants Thermographic Vision and Resistance to Pathogens/Toxins free
# (metatypes.xml — not karma-charged, not asserted here; see the "Unmodeled real effects" registry).
#
#   Handle: Nullsec     Metatype: Dwarf (mundane)     Pronouns: they/them
#   Loadout (Resources C, 140,000¥ — 8,000 on the implanted rig below; the ~132,000 remainder is
#     described-not-modeled flavor: a proper hand-held cyberdeck with a real Attribute array and a
#     program library, a Middle lifestyle with its own hardline, an armor jacket, a light pistol).
#     The implanted deck is the *backup* — the one they can't be separated from. Contacts: a
#     hardware fixer who sells them grey-market chips and a decker friend still inside Renraku.
#
# BUILD (all engine-modeled and asserted)
# ------------------------------------------------------------------------------------------------
# Sum-to-Ten (Talent E, mundane): Heritage B (3) + Skills B (3) + Attributes C (2) + Resources C (2)
#   + Talent E (0) = 10.  Under Priority this spread is simply unavailable: B and C each used twice
#   buys Skills B *and* Heritage B (Dwarf with 4 special-attribute points) *and* Resources C
#   (140,000¥) at the price of a merely-adequate Attributes C — a trade Priority's one-letter-each
#   rule can't express at all. Sum-to-Ten's whole point, and why a decker (who needs skills, nuyen,
#   and only a couple of high attributes) is a natural fit for it.
#
# Attributes — Attributes C = 16 primary points, ALL spent; EDG from Heritage B/Dwarf's 4 special
#   points, ALL spent. Dwarf minimums: BOD 3, STR 3, WIL 2, all others 1 (EDG 1). LOG 6 is their one
#   attribute at its natural maximum — legal per Step Two.
#     BOD +0=3, AGI +1=2, REA +3=4, STR +0=3, CHA +1=2, INT +4=5, LOG +5=6, WIL +2=4   (sum 16)
#     EDG +4=5 (from 4 special points)
#   REA stops at 4 on purpose: Dwarf is the only SR5-core metatype whose REA maximum is **5**, not
#   6 (metatypes.xml), so REA 5 would be a *second* attribute at its natural maximum, making the
#   build illegal — and it would block the WIL Karma raise below, which re-checks that same rule.
#
# Skills — Skills B = 36 skill + 5 group points, ALL spent.
#   Group (5): Electronics 5 → Computer/Hardware/Software all at 5 (the whole group budget in one
#     group — the Matrix generalist half of a decker).
#   Individual (36): Hacking 6 (the Cracking group is deliberately *not* group-bought, so its
#     members can be bought individually at uneven ratings — strict skill groups forbid mixing),
#     Cybercombat 5, Electronic Warfare 4, Perception 4, Sneaking 3, Pistols 3, Etiquette 3, Con 3,
#     First Aid 2, Gymnastics 2, Palming 1.  (6+5+4+4+3+3+3+3+2+2+1 = 36.)
#
# Cyberware — an internal AR/VR rig, Essence 0.7, 8,000¥: Cyberdeck (0.4 ess — the implanted deck
#   itself; its Matrix Attributes are NOT modeled, no Matrix subsystem exists), Datajack (0.1),
#   Image Link (0.1), Sound Link (0.1). Essence 6 − 0.7 = 5.3 (mundane, so no Essence→Magic
#   interaction — that's WP74's job; here Essence only feeds the Social Limit's ceil(ESS) term).
#   *(Phase S's own WP76 blurb suggested "datajack + cerebral booster"; Cerebral Booster is
#   rating-scaled bioware and therefore outside WP45's flat-cost catalog, the same illustrative-only
#   mismatch WP73's "wired reflexes + muscle toner" blurb hit. Flat equivalents used instead.)*
#
# Qualities — Positive 18 of the 25 cap (Natural Hardening 10 + Indomitable (Mental) 8); Negative 25
#   of the 25 cap in a **single** quality (SINner (Corporate) 25 — the largest Negative in the SR5
#   core catalog, and the first fixture to hit the Negative cap with one entry rather than a pair).
#   Net quality Karma 18 − 25 = **−7**, i.e. a credit: the Step Seven pool is 25 + 7 = 32.
#
# Step Seven — leftover Karma, all 32 spent (karma_spent 25, karma_remaining 0):
#     - WIL 4 → 5:                    25 Karma (new rating 5 x 5). Re-checks the natural-maximum
#         rule (LOG 6 is the only one there; Dwarf WIL maxes at 7, so 5 is well clear).
#     - Hacking specialization "Devices": 7 Karma (flat). Hacking is a Cracking member, but Cracking
#         was never group-bought, so this specialization breaks **nothing** — `broken_groups` is
#         empty, the complement of WP75's group-breaking case and the reason both are asserted.
# ==================================================================================================

DECKER_FIXTURE = SyntheticCharacter(
    name='Bakari "Nullsec" Osei — Dwarf decker (WP76 Sum-to-Ten + cyberware)',
    metatype="Dwarf",
    build_method=SUM_TO_TEN_BUILD_METHOD,
    heritage_letter="B",
    attributes_letter="C",
    skills_letter="B",
    resources_letter="C",
    attribute_points={
        "BOD": 0,
        "AGI": 1,
        "REA": 3,
        "STR": 0,
        "CHA": 1,
        "INT": 4,
        "LOG": 5,
        "WIL": 2,
        "EDG": 4,
    },
    skill_points={
        "Hacking": 6,
        "Cybercombat": 5,
        "Electronic Warfare": 4,
        "Perception": 4,
        "Sneaking": 3,
        "Pistols": 3,
        "Etiquette": 3,
        "Con": 3,
        "First Aid": 2,
        "Gymnastics": 2,
        "Palming": 1,
    },
    group_points={"Electronics": 5},
    qualities=("Natural Hardening", "Indomitable (Mental)", "SINner (Corporate)"),
    quality_text={"SINner (Corporate)": "Renraku full corporate SIN — ex-systems auditor, on file"},
    cyberware=("Cyberdeck", "Datajack", "Image Link", "Sound Link"),
    karma_attribute_points={"WIL": 1},
    karma_specializations={"Hacking": "Devices"},
    expected={
        # Attribute totals: Dwarf metatype minimum + points spent (WIL also + its Karma point).
        "attr:BOD": 3,
        "attr:AGI": 2,
        "attr:REA": 4,
        "attr:STR": 3,
        "attr:CHA": 2,
        "attr:INT": 5,
        "attr:LOG": 6,
        "attr:WIL": 5,  # 2 min + 2 priority + 1 Karma
        "attr:EDG": 5,
        # Skill ratings — the group-bought Electronics trio vs. the individually-bought Cracking
        # members at uneven ratings (the two halves strict skill groups keep apart).
        "rating:Computer": 5,
        "rating:Hardware": 5,
        "rating:Software": 5,
        "rating:Hacking": 6,
        "rating:Cybercombat": 5,
        "rating:Electronic Warfare": 4,
        # Dice pools: rating + linked attribute (+2 for the Karma-funded specialization).
        "pool:Hacking": 14,  # 6 + LOG 6 + 2 ("Devices", Karma-funded)
        "pool:Cybercombat": 11,  # 5 + LOG 6
        "pool:Electronic Warfare": 10,  # 4 + LOG 6
        "pool:Computer": 11,  # 5 + LOG 6
        "pool:Hardware": 11,  # 5 + LOG 6
        "pool:Software": 11,  # 5 + LOG 6
        "pool:Perception": 9,  # 4 + INT 5
        "pool:Sneaking": 5,  # 3 + AGI 2
        "pool:Pistols": 5,  # 3 + AGI 2
        "pool:Etiquette": 5,  # 3 + CHA 2
        "pool:Con": 5,  # 3 + CHA 2
        "pool:First Aid": 8,  # 2 + LOG 6
        "pool:Gymnastics": 4,  # 2 + AGI 2
        "pool:Palming": 3,  # 1 + AGI 2
        # Cyberware: the implanted rig's own Essence/nuyen (no bioware on this build).
        "cyberware:essence_spent": Decimal("0.7"),
        "cyberware:nuyen_spent": 8000,
        "essence": Decimal("5.3"),  # 6 - 0.7
        # Step Seven: the WIL raise and the specialization, and the group that *didn't* break.
        "karma_attribute:karma_cost": 25,  # WIL 4 -> 5
        "karma_skill:karma_cost": 7,  # flat specialization cost
        "karma_skill:broken_groups": frozenset(),
        # Derived stats.
        "initiative": 9,  # REA 4 + INT 5
        "initiative_dice": 1,
        "limit:physical": 5,  # ceil((STR*2+BOD+REA)/3) = ceil((6+3+4)/3) = ceil(13/3)
        "limit:mental": 9,  # ceil((LOG*2+INT+WIL)/3)=ceil(22/3)=8, +1 Indomitable (Mental)
        "limit:social": 5,  # ceil((CHA*2+WIL+ceil ESS 5.3->6)/3) = ceil((4+5+6)/3) = ceil(15/3)
        "cm:physical": 10,  # 8 + ceil(BOD/2) = 8 + 2
        "cm:stun": 11,  # 8 + ceil(WIL/2) = 8 + 3 (the Karma-raised WIL 5)
        # Karma: qualities -7 (18 positive - 25 negative, the cap hit by one quality) + 25 + 7 = 25,
        # i.e. the whole 32-Karma pool spent, nothing left.
        "karma_spent": 25,
        "karma_remaining": 0,
    },
    citations={
        "attr:BOD": "priorities.xml Attributes C = 16 pts; metatypes.xml Dwarf BOD min 3 (+0)",
        "attr:AGI": "priorities.xml Attributes C; Dwarf AGI min 1 (+1)",
        "attr:REA": (
            "priorities.xml Attributes C; Dwarf REA min 1 (+3); Dwarf REA maximum is 5, not 6 "
            "(metatypes.xml), so 4 keeps LOG the only attribute at its natural maximum"
        ),
        "attr:STR": "priorities.xml Attributes C; Dwarf STR min 3 (+0)",
        "attr:CHA": "priorities.xml Attributes C; Dwarf CHA min 1 (+1)",
        "attr:INT": "priorities.xml Attributes C; Dwarf INT min 1 (+4)",
        "attr:LOG": "priorities.xml Attributes C; Dwarf LOG min 1 (+5) = natural max 6",
        "attr:WIL": (
            "priorities.xml Attributes C; Dwarf WIL min 2 (+2) = 4, +1 Karma point "
            "(character.py karma_attribute_selection); Dwarf WIL maximum 7"
        ),
        "attr:EDG": "priorities.xml Heritage B/Dwarf = 4 special pts; Dwarf EDG min 1 (+4)",
        "rating:Computer": "Skills B group pts; Electronics group 5",
        "rating:Hardware": "Skills B group pts; Electronics group 5 (proves the group)",
        "rating:Software": "Skills B group pts; Electronics group 5 (proves the group)",
        "rating:Hacking": (
            "Skills B skill pts; 6 base = the chargen cap (Cracking group deliberately unbought, "
            "so its members may take individual points — skills.py strict-skill-groups check)"
        ),
        "rating:Cybercombat": "Skills B skill pts; 5 base (Cracking group unbought)",
        "rating:Electronic Warfare": "Skills B skill pts; 4 base (Cracking group unbought)",
        "pool:Hacking": (
            "learnings/phase-d.md (dice pool): rating 6 + LOG 6 + 2 Karma specialization "
            "(KARMA_SPECIALIZATION_COST path, skills.py dice_pool)"
        ),
        "pool:Cybercombat": "learnings/phase-d.md: rating 5 + LOG 6",
        "pool:Electronic Warfare": "learnings/phase-d.md: rating 4 + LOG 6",
        "pool:Computer": "learnings/phase-d.md: rating 5 + LOG 6",
        "pool:Hardware": "learnings/phase-d.md: rating 5 + LOG 6",
        "pool:Software": "learnings/phase-d.md: rating 5 + LOG 6",
        "pool:Perception": "learnings/phase-d.md: rating 4 + INT 5",
        "pool:Sneaking": "learnings/phase-d.md: rating 3 + AGI 2",
        "pool:Pistols": "learnings/phase-d.md: rating 3 + AGI 2",
        "pool:Etiquette": "learnings/phase-d.md: rating 3 + CHA 2",
        "pool:Con": "learnings/phase-d.md: rating 3 + CHA 2",
        "pool:First Aid": "learnings/phase-d.md: rating 2 + LOG 6 (First Aid is LOG-linked)",
        "pool:Gymnastics": "learnings/phase-d.md: rating 2 + AGI 2",
        "pool:Palming": "learnings/phase-d.md: rating 1 + AGI 2",
        "cyberware:essence_spent": (
            "cyberware.xml <ess>: Cyberdeck 0.4 + Datajack 0.1 + Image Link 0.1 + Sound Link 0.1 "
            "= 0.7 (engine/cyberware.py essence_spent)"
        ),
        "cyberware:nuyen_spent": (
            "cyberware.xml <cost>: 5000 + 1000 + 1000 + 1000 = 8000 <= Resources C 140000"
        ),
        "essence": (
            "derived.py essence = BASE_ESSENCE 6 - Sigma ESSENCE improvements (0.7 cyberware) = 5.3"
        ),
        "karma_attribute:karma_cost": (
            "karma_advancement_cost(4, 1, ATTRIBUTE_KARMA_PER_RATING 5) = new rating 5 x 5 = 25 "
            "(p.106-107 Karma Advancement Table for Attributes, learnings/phase-o.md WP51/WP52)"
        ),
        "karma_skill:karma_cost": (
            "KARMA_SPECIALIZATION_COST 7, flat (p.106-107 Character Improvement Table, "
            "learnings/phase-o.md WP53)"
        ),
        "karma_skill:broken_groups": (
            "empty: a Karma specialization breaks a group only if that group is group-purchased "
            "(skills.py create_karma_skill_selection); Cracking has 0 group points here"
        ),
        "initiative": "learnings/phase-d.md (Character.cs InitiativeValue): REA 4 + INT 5",
        "initiative_dice": "learnings/phase-d.md: base 1 (no matrix/astral)",
        "limit:physical": "learnings/phase-d.md LimitPhysical: ceil((6+3+4)/3)=ceil(13/3)=5",
        "limit:mental": (
            "learnings/phase-d.md LimitMental: ceil((12+5+5)/3)=ceil(22/3)=8, "
            "+1 Indomitable (Mental) (qualities.xml FLAT_BONUS mental_limit)"
        ),
        "limit:social": (
            "learnings/phase-d.md LimitSocial: ceil((CHA*2+WIL+ceil ESS)/3); ESS 5.3 rounds up to 6"
        ),
        "cm:physical": "learnings/phase-d.md (PhysicalCM): 8 + ceil(BOD/2)",
        "cm:stun": "learnings/phase-d.md (StunCM): 8 + ceil(WIL/2), WIL 5 incl. the Karma point",
        "karma_spent": (
            "p.64 (25 Karma); qualities 18 - 25 = -7 (Negative cap 25 hit by SINner (Corporate) "
            "alone) + attributes 25 + skills 7 = 25"
        ),
        "karma_remaining": "STARTING_KARMA 25 - karma_spent 25 = 0 (fully spent)",
    },
)


# Every synthetic fixture, for the parametrized regression test.
SYNTHETIC_FIXTURES = (
    REFERENCE_MUNDANE_FIXTURE,
    STREET_SAMURAI_FIXTURE,
    COMBAT_MAGE_FIXTURE,
    SHAMAN_FACE_FIXTURE,
    DECKER_FIXTURE,
)
