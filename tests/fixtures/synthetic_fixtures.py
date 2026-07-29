"""Hand-authored synthetic whole-character fixtures (Phase S / WP72+).

Each fixture is a `SyntheticCharacter` (see `synthetic.py`) whose `expected` values are hand-derived
from the rulebook / `priorities.xml` / legacy C#, with an inline `citations` entry for every one.
WP72 lands the substrate plus the single reference fixture below; WP73-76 append their
interaction-covering fixtures here (cyberware/bioware, magician+cyberware, leftover-Karma,
Sum-to-Ten) as they extend the harness.

The fixtures double as **playable Shadowrun characters** — legal, fully-spent priority builds with a
name and concept, not degenerate test artifacts — so a reader can pick one up as a real runner.
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
- Karma ledger: core rulebook p.64 "start with 25 Karma" (`STARTING_KARMA`); qualities net signed.
"""

from __future__ import annotations

from tests.fixtures.synthetic import SyntheticCharacter

# ==================================================================================================
# WP72 reference fixture — Renata "Cheshire" Vance, human infiltrator / cat burglar.
# ==================================================================================================
#
# CONCEPT (flavor; not engine-modeled except where an assertion below says so)
# ------------------------------------------------------------------------------------------------
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


# Every synthetic fixture, for the parametrized regression test. WP73-76 append their fixtures here.
SYNTHETIC_FIXTURES = (REFERENCE_MUNDANE_FIXTURE,)
